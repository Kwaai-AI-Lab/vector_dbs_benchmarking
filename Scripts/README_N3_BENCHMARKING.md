# N=3 Statistical Benchmarking System

## Overview

This system enables running benchmarks with **N=3 repetitions** for statistical rigor, automatically aggregating results with mean and standard deviation, and visualizing error bars on comparison plots.

## Key Features

- **Multiple Runs**: Automatically runs each benchmark N times (default: 3)
- **Statistical Aggregation**: Computes mean, std, min, max for all metrics
- **Error Bar Visualization**: Plots include ±1 standard deviation error bars
- **Backward Compatible**: Plotting script works with both single-run and N-run data
- **Individual Run Preservation**: All individual runs saved for detailed analysis

---

## Quick Start

### Run N=3 Benchmark for a Single Database

```bash
# Run Chroma with N=3 runs per corpus size
python Scripts/run_scaling_experiment_n3.py --database chroma

# Run Qdrant with N=5 runs (custom)
python Scripts/run_scaling_experiment_n3.py --database qdrant --runs 5

# Run only specific corpus size
python Scripts/run_scaling_experiment_n3.py --database faiss --corpus 10k
```

### Generate Plots with Error Bars

```bash
# Automatically detects N-run data and adds error bars
python Scripts/plot_multi_database_scaling.py
```

The plotting script will:
1. First check for N-run results (`{database}_scaling_n3`, `_n5`, etc.)
2. Fall back to single-run results if N-run data not found
3. Automatically add error bars when N-run data is detected

---

## Output Structure

### N=3 Results Directory Layout

```
results/
├── chroma_scaling_n3/                    # N=3 results root
│   ├── corpus_baseline/
│   │   ├── run_1/
│   │   │   ├── results.json              # Individual run 1
│   │   │   └── benchmark.log
│   │   ├── run_2/
│   │   │   ├── results.json              # Individual run 2
│   │   │   └── benchmark.log
│   │   ├── run_3/
│   │   │   ├── results.json              # Individual run 3
│   │   │   └── benchmark.log
│   │   └── aggregated_results.json       # ⭐ Mean/std across 3 runs
│   ├── corpus_1k/
│   │   ├── run_1/ ...
│   │   └── aggregated_results.json
│   ├── experiment_progress.json          # Real-time progress tracking
│   └── experiment_summary.json           # Final summary
```

### Aggregated Results Format

```json
{
  "n_runs": 3,
  "statistics": {
    "p50_latency_ms": {
      "mean": 8.45,
      "std": 0.32,
      "min": 8.1,
      "max": 8.8,
      "values": [8.1, 8.5, 8.8],
      "n": 3
    },
    "queries_per_second": {
      "mean": 144.2,
      "std": 5.1,
      "min": 139.0,
      "max": 149.5,
      "values": [139.0, 144.3, 149.5],
      "n": 3
    },
    "ingestion_time": {
      "mean": 62.3,
      "std": 1.8,
      "min": 60.5,
      "max": 64.1,
      "values": [60.5, 62.3, 64.1],
      "n": 3
    }
  },
  "mean_result": {
    "ingestion": {
      "num_chunks": 5562,
      "total_time_sec": 62.3
    },
    "query_results": [...]
  },
  "individual_runs": [...]
}
```

---

## Command Reference

### run_scaling_experiment_n3.py

**Usage:**
```bash
python Scripts/run_scaling_experiment_n3.py [OPTIONS]
```

**Required Arguments:**
- `--database {faiss,chroma,qdrant,weaviate,milvus,opensearch}` - Database to benchmark

**Optional Arguments:**
- `--runs N` - Number of runs per corpus size (default: 3)
- `--corpus {baseline,1k,10k,50k,full}` - Run only specific corpus (default: all)

**Examples:**
```bash
# Standard N=3 run
python Scripts/run_scaling_experiment_n3.py --database chroma

# Custom N=5 for higher confidence
python Scripts/run_scaling_experiment_n3.py --database faiss --runs 5

# Quick test: single corpus, N=2
python Scripts/run_scaling_experiment_n3.py --database qdrant --corpus baseline --runs 2
```

### Supported Databases

| Database | Script Required | Notes |
|----------|----------------|-------|
| FAISS | `run_faiss_benchmark.py` | ✅ Available |
| Chroma | `run_chroma_benchmark.py` | ✅ Available |
| Qdrant | `run_qdrant_benchmark.py` | ✅ Available |
| Weaviate | `run_weaviate_benchmark.py` | ✅ Available |
| Milvus | `run_milvus_benchmark.py` | ✅ Available |
| OpenSearch | `run_opensearch_benchmark.py` | ✅ Available |

---

## Statistical Rigor

### Why N=3?

- **Minimum for Variance**: N=3 is the minimum for meaningful standard deviation
- **Practical Balance**: Triples experiment time but provides statistical confidence
- **Publication Standard**: Most papers require N≥3 for quantitative claims

### Coefficient of Variation (CV)

CV is calculated as: `CV = (std / mean) × 100%`

**Interpretation:**
- **CV < 5%**: Excellent consistency (e.g., FAISS: 2.5%)
- **CV 5-10%**: Good consistency (acceptable for production)
- **CV 10-20%**: Moderate variability (investigate causes)
- **CV > 20%**: High variability (results may not be reliable)

### Error Propagation

For derived metrics like ingestion throughput (`rate = chunks / time`):

```
σ_rate = rate × (σ_time / time)
```

This is automatically handled by the plotting script.

---

## Plotting with Error Bars

### 4-Panel Figure with Error Bars

The enhanced `plot_multi_database_scaling.py` automatically:

1. **Detects N-run data**: Checks for `*_scaling_n3` directories first
2. **Extracts statistics**: Reads mean and std from aggregated results
3. **Plots error bars**: Uses `matplotlib.errorbar()` with ±1σ
4. **Falls back gracefully**: Works with single-run data (no error bars)

**Panel-Specific Error Bars:**
- **(a) Query Latency**: P50 latency ± std (log-log scale)
- **(b) Query Throughput**: QPS ± std
- **(c) Ingestion Time**: Time ± std (log-log scale)
- **(d) Ingestion Throughput**: Rate ± propagated std

**Visual Style:**
- Error bar caps: 4pt
- Error bar thickness: 1.5pt
- Alpha: 0.8 for semi-transparency

---

## Time Estimates

### Per-Database Timing (N=3)

Assuming 5 corpus sizes × 3 runs = 15 total runs:

| Database | Time/Corpus | Total (N=3) | Notes |
|----------|-------------|-------------|-------|
| **FAISS** | 10-15 min | **5-7.5 hours** | Fastest, handles 2.2M |
| **Chroma** | 8-12 min | **4-6 hours** | Fast, stops at 345K |
| **Qdrant** | 12-18 min | **6-9 hours** | Good, stops at 345K |
| **Weaviate** | 12-18 min | **6-9 hours** | Similar to Qdrant |
| **Milvus** | 15-20 min | **7.5-10 hours** | Slower startup |
| **OpenSearch** | Fails at 345K | **2-3 hours** | Only 3 corpus sizes |

**Recommendation**: Run overnight or use screen/tmux sessions.

---

## Example Workflow

### Complete N=3 Benchmark for Chroma

```bash
# 1. Run N=3 benchmarks (4-6 hours)
python Scripts/run_scaling_experiment_n3.py --database chroma

# 2. Monitor progress
tail -f results/chroma_scaling_n3/experiment_progress.json

# 3. Check results
cat results/chroma_scaling_n3/corpus_10k/aggregated_results.json | jq '.statistics'

# 4. Generate plots with error bars
python Scripts/plot_multi_database_scaling.py

# 5. View 4-panel figure
open results/multi_database_scaling_plots/figure_4panel_scaling_comparison.png
```

### Batch Run All Databases

```bash
#!/bin/bash
# Run N=3 for all databases in sequence

for db in chroma qdrant weaviate milvus faiss; do
    echo "Starting $db..."
    python Scripts/run_scaling_experiment_n3.py --database $db --runs 3

    echo "Completed $db at $(date)"
    echo "----------------------------------------"
done

# Generate unified plots
python Scripts/plot_multi_database_scaling.py
```

**Total time**: ~30-40 hours for all 6 databases with N=3

---

## Interpreting Error Bars

### Small Error Bars (σ < 5% of mean)
- **Good**: System is stable and reproducible
- **Example**: FAISS ingestion (CV=2.5%)
- **Implication**: Results are reliable for comparison

### Medium Error Bars (σ = 5-15% of mean)
- **Acceptable**: Normal system variability
- **Example**: Query latency under load
- **Implication**: Consider N=5 for higher confidence

### Large Error Bars (σ > 15% of mean)
- **Warning**: High variability detected
- **Possible causes**:
  - Background processes interfering
  - Garbage collection events
  - Resource contention
  - Non-deterministic algorithms
- **Action**: Investigate or increase N

---

## Comparison: Single-Run vs N=3

| Aspect | Single-Run | N=3 |
|--------|-----------|-----|
| **Time** | Baseline | 3× baseline |
| **Statistical Rigor** | None | ✅ Mean + std |
| **Publication Ready** | ❌ No | ✅ Yes |
| **Detects Variance** | ❌ No | ✅ Yes |
| **Error Bars** | ❌ No | ✅ Yes |
| **Confidence** | Low | Medium-High |
| **Suitable For** | Initial exploration | Research papers |

---

## Known Limitations

### Database-Specific Timeouts

Some databases may timeout at large corpus sizes even with multiple attempts:

| Database | Known Limit | Timeout Behavior |
|----------|-------------|------------------|
| Chroma | 2.2M chunks | All 3 runs timeout (memory) |
| Qdrant | 2.2M chunks | All 3 runs timeout (memory) |
| Weaviate | 2.2M chunks | All 3 runs timeout (memory) |
| Milvus | 2.2M chunks | All 3 runs timeout (memory) |
| OpenSearch | 345K chunks | All 3 runs fail |
| FAISS | No limit | ✅ Completes 2.2M |

**Solution**: The script marks corpus as "failed" if all N runs timeout. Results up to that point are preserved.

### Variance Sources

- **Docker overhead**: Container startup/shutdown
- **Memory pressure**: GC pauses increase with corpus size
- **Network latency**: For client-server databases
- **Background processes**: OS-level interference

**Mitigation**: Close unnecessary applications, use dedicated hardware, run overnight.

---

## Troubleshooting

### Error: "No results found"
```bash
# Check if results directory exists
ls results/{database}_scaling_n3/

# Check if aggregated files exist
find results/{database}_scaling_n3/ -name "aggregated_results.json"
```

### Error: "Benchmark timed out"
- **Increase timeout**: Edit line 81 in `run_scaling_experiment_n3.py` (default: 7200s = 2 hours)
- **Skip large corpuses**: Use `--corpus` flag to test smaller sizes first

### Warning: "High standard deviation"
- **Check logs**: Review individual `benchmark.log` files in `run_1`, `run_2`, `run_3`
- **Verify consistency**: Ensure no background processes are running
- **Consider N=5**: More runs reduce uncertainty

---

## References

- **Original Script**: `Scripts/run_scaling_experiment_generic.py` (single-run)
- **Plotting Script**: `Scripts/plot_multi_database_scaling.py` (supports both formats)
- **Paper Section**: `paper_sections/section_5_3_scaling_analysis.md`
- **Key Findings**: `paper_sections/KEY_FINDINGS_SUMMARY.md`

---

## Future Enhancements

- [ ] Parallel N-run execution (reduce time by running N runs concurrently)
- [ ] Automatic outlier detection and removal
- [ ] Confidence interval calculation (t-distribution for small N)
- [ ] Automated report generation with statistical tests
- [ ] Integration with CI/CD for regression detection

---

**For questions or issues, see [CONTRIBUTOR_GUIDE.md](../CONTRIBUTOR_GUIDE.md)**
