# Overnight N=2 Additional Runs - Status

**Started:** December 22, 2025 (late evening)
**Expected Completion:** December 23, 2025 (morning)

## 🚀 Running Experiments

All 5 databases are currently running N=2 additional iterations to achieve N=3 statistical rigor:

| Database | Task ID | Corpus Sizes | Est. Time | Status |
|----------|---------|--------------|-----------|--------|
| **Chroma** | b1da20e | 4 (baseline, 1k, 10k, 50k) | 2.5-4 hours | ⏳ Running |
| **Qdrant** | baba093 | 4 (baseline, 1k, 10k, 50k) | 3-4.5 hours | ⏳ Running |
| **Weaviate** | b6225e9 | 4 (baseline, 1k, 10k, 50k) | 3-4.5 hours | ⏳ Running |
| **Milvus** | b92d3d4 | 4 (baseline, 1k, 10k, 50k) | 3.5-5 hours | ⏳ Running |
| **OpenSearch** | b476683 | 3 (baseline, 1k, 10k) | 2-3 hours | ⏳ Running |

**Total Runtime:** 12-20 hours (running in parallel)

## 📊 What's Being Generated

For each database, the script will:

1. **Copy existing result** as `run_1/results.json`
2. **Run iteration 2** → `run_2/results.json`
3. **Run iteration 3** → `run_3/results.json`
4. **Aggregate statistics** → `aggregated_results.json` with mean ± std

## 📁 Output Locations

Results will be saved in:
```
results/
├── chroma_scaling_n3/
│   ├── corpus_baseline/aggregated_results.json
│   ├── corpus_1k/aggregated_results.json
│   ├── corpus_10k/aggregated_results.json
│   └── corpus_50k/aggregated_results.json
├── qdrant_scaling_n3/
│   └── ... (same structure)
├── weaviate_scaling_n3/
├── milvus_scaling_n3/
└── opensearch_scaling_n3/
```

## 🔍 How to Check Progress

### Check if experiments are still running:
```bash
ps aux | grep run_scaling_n2_additional.py
```

### Check progress for specific database:
```bash
# Check experiment progress file
cat results/chroma_scaling_n3/experiment_progress.json

# Check which corpus is currently being processed
ls -ltr results/chroma_scaling_n3/corpus_*/run_*/results.json
```

### Check detailed logs:
```bash
# Check background task output
cat /tmp/claude/-Users-rezarassool-Source-vector-dbs-benchmarking/tasks/b1da20e.output
```

### Monitor real-time (if still running):
```bash
# Watch for new results files being created
watch -n 30 'find results/*_scaling_n3 -name "aggregated_results.json" | wc -l'
```

## ✅ Expected Results

By tomorrow morning, you should have:

- **19 aggregated result files** (4+4+4+4+3 corpus sizes)
- **N=3 statistics** for each: mean, std, min, max, CV%
- **Error bar data** ready for visualization

## 🎨 Next Step: Generate Plots

Once all experiments complete, run:
```bash
python Scripts/plot_multi_database_scaling.py
```

This will generate the 4-panel figure with error bars showing:
- **(a)** Query latency ± std (log-log with α exponents)
- **(b)** Throughput ± std (with 100 QPS threshold)
- **(c)** Ingestion time ± std (log-log)
- **(d)** Ingestion throughput ± std (with CV% annotations)

## 📈 Current Status: FAISS

FAISS already has N=3 for 2.2M chunks:
- **Latency:** 61.5 ± 1.9 ms (CV = 3.0%)
- **Throughput:** 16.3 ± 0.5 QPS
- **Ingestion:** 5508 ± 119 sec (CV = 2.2%)

The plotting script will show error bars for FAISS's 2.2M data point even now.

## ⚠️ Known Issues

- **Timeouts:** Some databases may timeout at 50k corpus (OpenSearch already failed here)
- **Memory:** Large corpus sizes may cause OOM errors
- **Duration:** If any individual run times out (2 hour limit), that corpus will be marked as failed

## 🔄 If Something Goes Wrong

If a database fails or times out:

1. **Check the logs** in the task output files
2. **Verify progress** in `experiment_progress.json`
3. **Re-run specific corpus** if needed:
   ```bash
   python Scripts/run_scaling_n2_additional.py --database chroma --corpus 10k
   ```

## 📝 Summary Files

When complete, each database will have:
- `experiment_progress.json` - Real-time progress tracking
- `experiment_summary.json` - Final summary with timestamps
- Individual `aggregated_results.json` per corpus with full statistics

---

**Check this file tomorrow morning to see completion status!**

**To see if experiments are done:**
```bash
# Should show ~19 aggregated result files when complete
find results/*_scaling_n3 -name "aggregated_results.json" -exec ls -lh {} \;
```
