# N=10 Upgrade Quick Reference Card

## 🚀 START

```bash
nohup bash Scripts/run_n10_upgrade_overnight.sh > n10_upgrade.log 2>&1 &
echo $! > n10_upgrade.pid
```

## ⏸️ PAUSE

### Graceful Pause (Recommended)
Current benchmark will finish, then stop:
```bash
kill -SIGTERM $(cat n10_upgrade.pid)
```

### Immediate Pause
Force stop immediately:
```bash
kill -SIGKILL $(cat n10_upgrade.pid)
```

### Alternative (if PID file missing)
```bash
# Find process
ps aux | grep run_n10_upgrade_overnight

# Kill by PID
kill <PID>
```

## ▶️ RESUME

Simply restart (automatically skips completed runs):
```bash
nohup bash Scripts/run_n10_upgrade_overnight.sh > n10_upgrade.log 2>&1 &
echo $! > n10_upgrade.pid
```

## 📊 CHECK PROGRESS

### Quick Status
```bash
bash Scripts/check_n10_progress.sh
```

### Auto-Refresh (every 60 seconds)
```bash
watch -n 60 bash Scripts/check_n10_progress.sh
```

### View Live Log
```bash
tail -f n10_upgrade.log
```

### Check Progress JSON
```bash
cat results/n10_upgrade_progress.json | python -m json.tool
```

## 🔍 VERIFY STATUS

### Check if Running
```bash
ps aux | grep run_n10_upgrade_overnight
# Or check PID file
ps -p $(cat n10_upgrade.pid 2>/dev/null) 2>/dev/null && echo "Running" || echo "Not running"
```

### Check Disk Space
```bash
df -h .
```

### Check Latest Activity
```bash
# Most recent benchmark activity
ls -lt results/*_scaling_n10/*/run_*/results.json | head -5
```

## 🎯 COMPLETION CHECK

### Count Completed Runs
```bash
find results/*_scaling_n10 -name "results.json" | wc -l
# Target: 320 files (32 corpus × 10 runs)
```

### Check N=10 Directories Created
```bash
ls -ld results/*_scaling_n10
# Should see 7 databases
```

### Verify Aggregated Results
```bash
find results/*_scaling_n10 -name "aggregated_results.json" | wc -l
# Target: 32 files (one per corpus size)
```

## ⚠️ TROUBLESHOOTING

### Stuck Benchmark
```bash
# Check running processes
ps aux | grep run_.*_benchmark.py

# Kill stuck benchmark
kill <PID>

# Resume will restart that corpus
```

### Docker Container Issues
```bash
# Check containers
docker-compose ps

# Restart specific database
docker-compose restart qdrant

# View container logs
docker-compose logs --tail=50 qdrant
```

### Disk Full
```bash
# Check space
df -h .

# Clean old backups
find results -name "*.bak" -delete

# Clean logs if needed
rm -f logs/*.log.old
```

## 📈 PROGRESS TRACKING

### Expected Progress Per Night (10 hours)
- Night 1: ~27 runs (12%)
- Night 2: ~54 runs (24%)
- Night 3: ~81 runs (36%)
- Night 4: ~108 runs (48%)
- Night 5: ~135 runs (60%)
- Night 6: ~162 runs (72%)
- Night 7: ~189 runs (84%)
- Night 8: ~216 runs (96%)
- Night 9: Complete! (100%)

### Database Completion Order
Smaller databases finish first:
1. OpenSearch (3 corpus × 7 runs = 21)
2. Chroma, Qdrant, Weaviate, Milvus, PGVector (4 corpus × 7 runs = 28 each)
3. FAISS (9 corpus × 7 runs = 63) - takes longest!

## 🎨 AFTER COMPLETION

### Regenerate Plots
```bash
python Scripts/plot_multi_database_scaling.py
python Scripts/plot_resource_utilization.py
```

### View Summary
```bash
cat results/n10_upgrade_summary.json | python -m json.tool
```

### Compare N=3 vs N=10 Error Bars
```bash
# Example: Check improvement for Chroma 50k
python3 << 'EOF'
import json
n3 = json.load(open('results/chroma_scaling_n3/corpus_50k/aggregated_results.json'))
n10 = json.load(open('results/chroma_scaling_n10/corpus_50k/aggregated_results.json'))
n3_std = n3['statistics']['p50_latency_ms']['std']
n10_std = n10['statistics']['p50_latency_ms']['std']
improvement = (n3_std - n10_std) / n3_std * 100
print(f"Error bar improvement: {improvement:.1f}%")
EOF
```

## 📞 EMERGENCY CONTACTS

### System Issues
- Check logs: `n10_upgrade.log`
- Check progress: `results/n10_upgrade_progress.json`
- Check guide: `N10_UPGRADE_GUIDE.md`

### Key Files
- Main script: `Scripts/run_scaling_n7_additional.py`
- Wrapper: `Scripts/run_n10_upgrade_overnight.sh`
- Progress checker: `Scripts/check_n10_progress.sh`
- This reference: `N10_QUICK_REFERENCE.md`
