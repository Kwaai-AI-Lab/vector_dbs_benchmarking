#!/bin/bash
#
# Check progress of N=10 upgrade runs
#
# USAGE:
#   bash Scripts/check_n10_progress.sh
#   watch -n 60 bash Scripts/check_n10_progress.sh  # Auto-refresh every minute
#

PROGRESS_FILE="results/n10_upgrade_progress.json"

echo "=================================================================="
echo "   N=10 UPGRADE PROGRESS CHECK"
echo "=================================================================="
echo "Timestamp: $(date)"
echo ""

# Check if progress file exists
if [ ! -f "$PROGRESS_FILE" ]; then
    echo "❌ No progress file found yet."
    echo "Expected location: $PROGRESS_FILE"
    echo ""
    echo "The upgrade may not have started, or is still initializing."
    exit 1
fi

# Parse progress file
echo "📊 OVERALL PROGRESS:"
echo ""

# Extract basic info
START_TIME=$(python3 -c "import json; f=open('$PROGRESS_FILE'); d=json.load(f); print(d.get('start_time', 'Unknown'))" 2>/dev/null || echo "Unknown")
echo "  Start time: $START_TIME"

# Count databases processed
TOTAL_DBS=$(python3 -c "import json; f=open('$PROGRESS_FILE'); d=json.load(f); print(len(d.get('databases', [])))" 2>/dev/null || echo "0")
echo "  Databases processed: $TOTAL_DBS"

# Detailed breakdown by database
echo ""
echo "📈 DATABASE BREAKDOWN:"
echo ""

python3 << 'EOF'
import json
from pathlib import Path

try:
    with open('results/n10_upgrade_progress.json', 'r') as f:
        data = json.load(f)

    for db_data in data.get('databases', []):
        db_name = db_data.get('database', 'Unknown')
        corpuses = db_data.get('corpuses_processed', [])

        successful = sum(1 for c in corpuses if c.get('status') == 'success')
        failed = sum(1 for c in corpuses if c.get('status') == 'failed')

        print(f"  {db_name.upper()}:")
        print(f"    Corpuses: {successful} successful, {failed} failed, {len(corpuses)} total")

        if corpuses:
            print(f"    Details:")
            for corpus in corpuses:
                status_icon = "✅" if corpus['status'] == 'success' else "❌"
                n_runs = corpus.get('n_runs', 0)
                duration = corpus.get('duration_minutes', 0)
                print(f"      {status_icon} {corpus['name']}: N={n_runs}, {duration:.1f} min")

        print()

except FileNotFoundError:
    print("  No progress data available yet")
except json.JSONDecodeError:
    print("  Progress file is corrupted or incomplete")
except Exception as e:
    print(f"  Error reading progress: {e}")
EOF

# Check for log files
echo ""
echo "📝 RECENT LOG ACTIVITY:"
echo ""

# Find most recent log
LATEST_LOG=$(ls -t n10_*.log logs/n10_*.log 2>/dev/null | head -1)

if [ -n "$LATEST_LOG" ]; then
    echo "  Latest log: $LATEST_LOG"
    echo "  Last 10 lines:"
    tail -10 "$LATEST_LOG" | sed 's/^/    /'
else
    echo "  No log files found"
fi

# Check for any currently running benchmarks
echo ""
echo "🔄 SYSTEM STATUS:"
echo ""

# Check if python benchmark processes are running
RUNNING_PROCS=$(ps aux | grep -E "run_(faiss|chroma|qdrant|weaviate|milvus|opensearch|pgvector)_benchmark.py" | grep -v grep | wc -l)
if [ "$RUNNING_PROCS" -gt 0 ]; then
    echo "  ✅ Benchmark process currently running"
    ps aux | grep -E "run_(faiss|chroma|qdrant|weaviate|milvus|opensearch|pgvector)_benchmark.py" | grep -v grep | awk '{print "    PID " $2 ": " $11}' | head -5
else
    echo "  ⏸️  No active benchmark processes detected"
fi

# Estimate completion time
echo ""
echo "⏱️  ESTIMATED COMPLETION:"
echo ""

python3 << 'EOF'
import json
from datetime import datetime, timedelta

try:
    with open('results/n10_upgrade_progress.json', 'r') as f:
        data = json.load(f)

    # Calculate average time per corpus
    total_duration = 0
    completed_corpuses = 0

    for db_data in data.get('databases', []):
        for corpus in db_data.get('corpuses_processed', []):
            if corpus.get('status') == 'success' and 'duration_minutes' in corpus:
                total_duration += corpus['duration_minutes']
                completed_corpuses += 1

    if completed_corpuses > 0:
        avg_duration = total_duration / completed_corpuses
        print(f"  Average time per corpus: {avg_duration:.1f} minutes")

        # Estimate remaining
        # Count total expected corpuses (approximate based on README)
        # Chroma: 4, FAISS: 9, Qdrant: 4, Weaviate: 4, Milvus: 4, OpenSearch: 3, PGVector: 4 = 32 total
        total_expected = 32
        remaining = max(0, total_expected - completed_corpuses)

        if remaining > 0:
            est_remaining_hours = (remaining * avg_duration) / 60
            print(f"  Estimated remaining: {est_remaining_hours:.1f} hours ({remaining} corpuses)")

            # Estimate completion time
            now = datetime.now()
            completion = now + timedelta(hours=est_remaining_hours)
            print(f"  Estimated completion: {completion.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print(f"  All corpuses completed!")
    else:
        print("  Not enough data to estimate completion time")

except Exception as e:
    print(f"  Cannot estimate: {e}")
EOF

echo ""
echo "=================================================================="
echo ""
echo "💡 TIP: Run with 'watch' for auto-refresh:"
echo "   watch -n 60 bash Scripts/check_n10_progress.sh"
echo ""
