#!/bin/bash
#
# OVERNIGHT N=10 STATISTICAL UPGRADE
# ===================================
# This script upgrades all existing N=3 benchmarks to N=10 by running
# 7 additional iterations for each database and corpus size.
#
# Estimated total time: 56-112 hours (2-4 days continuous)
# - ~224 additional runs total
# - 15-30 minutes per run
#
# USAGE:
#   # Run all databases overnight (recommended)
#   nohup bash Scripts/run_n10_upgrade_overnight.sh > n10_upgrade.log 2>&1 &
#
#   # Run specific database
#   nohup bash Scripts/run_n10_upgrade_overnight.sh chroma > n10_chroma.log 2>&1 &
#
# MONITOR PROGRESS:
#   tail -f n10_upgrade.log
#   cat results/n10_upgrade_progress.json
#

set -e  # Exit on error

START_TIME=$(date +%s)
DATABASE="${1:-all}"

echo "=================================================================="
echo "   N=10 STATISTICAL UPGRADE - OVERNIGHT RUN"
echo "=================================================================="
echo "Start time: $(date)"
echo "Database: $DATABASE"
echo ""
echo "Strategy:"
echo "  - Leverage existing N=3 results"
echo "  - Run 7 additional iterations (runs 4-10)"
echo "  - Aggregate all 10 runs for refined error bars"
echo ""
echo "Expected improvements:"
echo "  - Error bars reduced by ~42% (sqrt(10/3))"
echo "  - More robust statistical conclusions"
echo "  - Coefficient of variation more precise"
echo "=================================================================="
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Create logs directory
mkdir -p logs

# Run the upgrade script
echo "Starting N=10 upgrade..."
echo ""

if [ "$DATABASE" = "all" ]; then
    # Run all databases sequentially
    python Scripts/run_scaling_n7_additional.py 2>&1 | tee logs/n10_upgrade_$(date +%Y%m%d_%H%M%S).log
else
    # Run specific database
    python Scripts/run_scaling_n7_additional.py --database "$DATABASE" 2>&1 | tee logs/n10_${DATABASE}_$(date +%Y%m%d_%H%M%S).log
fi

END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))
TOTAL_HOURS=$((TOTAL_DURATION / 3600))
TOTAL_MINUTES=$(((TOTAL_DURATION % 3600) / 60))

echo ""
echo "=================================================================="
echo "              N=10 UPGRADE COMPLETE"
echo "=================================================================="
echo "End time: $(date)"
echo "Total duration: ${TOTAL_HOURS}h ${TOTAL_MINUTES}m"
echo ""
echo "Results:"
echo "  - N=10 results saved to: results/*_scaling_n10/"
echo "  - Summary: results/n10_upgrade_summary.json"
echo "  - Progress log: results/n10_upgrade_progress.json"
echo ""
echo "Next steps:"
echo "  1. Regenerate plots with refined error bars:"
echo "     python Scripts/plot_multi_database_scaling.py"
echo ""
echo "  2. Update analysis scripts to use N=10 data"
echo ""
echo "  3. Verify statistical improvements:"
echo "     - Error bars should be ~42% narrower"
echo "     - CV measurements more precise"
echo "=================================================================="

exit 0
