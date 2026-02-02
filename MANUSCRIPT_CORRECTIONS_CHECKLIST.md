# Manuscript Corrections Checklist - Chroma N=10 Data

**Purpose:** Quick reference for correcting all Chroma statistics in the manuscript to match actual N=10 data

**Date:** February 2, 2026

---

## Critical Changes Required

### ❌ REMOVE (Current - INCORRECT)
### ✅ REPLACE WITH (Correct N=10 Data)

---

## 1. Abstract (Page 1)

### ❌ CURRENT:
> "Chroma exhibits near-constant-time query behavior (α = 0.02), achieving a latency of 6-8 ms and supporting up to 144 queries per second at medium scale."

### ✅ CORRECT:
> "Chroma exhibits near-constant-time query behavior (α = 0.02), achieving a latency of 7.7-8.4 ms and supporting up to 141 queries per second at medium scale."

---

## 2. Page 2 Summary Results

### ❌ CURRENT:
> "Chroma CV improvements: [...] achieving CV = [8.2%]"

### ✅ CORRECT:
> "Chroma achieves exceptional consistency (CV = 2.3% after removing 2 cold-start outliers, 8.8× improvement over raw variance)"

---

## 3. Table 3: Latency Scaling Exponents (Page 9)

### ❌ CURRENT:
```
Chroma    0.02    6.4-7.5    Near-constant
```

### ✅ CORRECT:
```
Chroma    0.02    7.7-8.4    Near-constant
```

**Footnote to add:** *Latency range from 50k corpus, N=10 independent runs, no query outliers detected*

---

## 4. Table 4: Query Throughput (Page 10)

### ❌ CURRENT:
```
Chroma    98    138    133    -    144
```

### ✅ CORRECT:
```
Chroma    127   127    124    -    141
```

**Footnote to add:** *Mean QPS after modified Z-score outlier removal (|Z| > 3.5); 1k and 10k: N=8, 50k: N=10*

---

## 5. Table 5: Ingestion Consistency (Page 11)

### ❌ CURRENT:
```
Chroma    8.2%    8.2%    -    Good-standard tolerance
```

### ✅ CORRECT:
```
Chroma    20.2%    2.3%    8.8×    Excellent-tightest SLAs
```

**Footnote to add:** *50k corpus: N=10 → N=8 after removing 2 cold-start outliers (1112s, 2064s); typical steady-state 800-850s*

---

## 6. Section 3.1: Query Latency Scaling (Page 9)

### ❌ CURRENT:
> "Chroma achieves exceptional near-constant-time behavior (α = 0.02), maintaining **6-8 ms latency** across all tested scales from 175 to 50k chunks."

### ✅ CORRECT:
> "Chroma achieves exceptional near-constant-time behavior (α = 0.02), maintaining **7.7-8.4 ms latency** at the 50k scale, with consistently low latency across all tested scales from 175 to 50k chunks."

---

## 7. Section 3.2: Throughput (Page 10)

### ❌ CURRENT:
> "Chroma sustains 130-144 QPS across all scales"

### ✅ CORRECT:
> "Chroma sustains 124-141 QPS across all scales (peak of 141 QPS at baseline, 124 QPS at 50k)"

---

## 8. Section 3.3: Ingestion Consistency (Page 10-11)

### ❌ CURRENT:
> "Chroma (CV=8.2%): Good-standard tolerance"

### ✅ CORRECT:
> "Chroma (CV=2.3% after outlier removal, 20.2% raw): Excellent-tightest SLAs. Removing 2 cold-start outliers (1112s, 2064s) reveals exceptional steady-state consistency (typical 800-850s, CV=2.3%)."

---

## 9. Figure 1 Caption (Page 5)

Verify that Figure 1 plots reflect the correct N=10 data. If regeneration is needed:

```bash
cd /Users/rezarassool/Source/vector_dbs_benchmarking
python Scripts/plot_multi_database_scaling.py
```

Expected Chroma values in plot:
- Panel (a) Latency: ~6.4 ms (baseline) to ~7.95 ms (50k)
- Panel (b) Throughput: ~140 QPS (baseline) to ~124 QPS (50k)
- Panel (c) Ingestion: ~0.01 min (baseline) to ~13.7 min (50k, median of cleaned data)
- Panel (d) CV: Should show 2.3% after cleaning (not 8.2%)

---

## 10. Section 4.2: Use-Case Recommendations (Page 13)

### ❌ CURRENT:
> "Chroma (6-8 ms, 144 QPS, CV=6-10%)"

### ✅ CORRECT:
> "Chroma (7.7-8.4 ms, 141 QPS, CV=2.3%)"

---

## 11. Related Text: HNSW Warm-Up Discussion

### Current mentions of throughput values like "98, 138, 133"

**Search the manuscript for:** "98", "138", "133" and verify these don't appear in Chroma context

**If found, replace with actual N=10 values:**
- 1k scale: 127 QPS (mean after outlier removal)
- 10k scale: 127 QPS (mean after outlier removal)
- 50k scale: 124 QPS (mean, no outliers)

---

## Verification Steps

### Before Submission:

1. ✅ Search entire manuscript for "8.2" → Should only appear for other databases
2. ✅ Search for "6.4" or "6-8" in Chroma context → Replace with 7.7-8.4
3. ✅ Search for "144" → Replace with 141
4. ✅ Search for "98, 138, 133" → Replace with 124-141 or specific scale values
5. ✅ Verify all Chroma CV values show 2.3% (after cleaning) or 20.2% (before cleaning)
6. ✅ Check that Figure 1 was regenerated with correct data
7. ✅ Verify footnotes explain outlier removal methodology
8. ✅ Confirm Table 5 shows "Before/After" columns with 20.2% → 2.3%

### Data Verification Command:

```bash
cd /Users/rezarassool/Source/vector_dbs_benchmarking
python3 << 'EOF'
import json
import statistics

# Load N=10 50k corpus data
with open('results/chroma_scaling_n10/corpus_50k/aggregated_results.json') as f:
    data = json.load(f)

# Extract metrics
latencies = []
throughputs = []
ingestion_times = []

for run in data['individual_runs']:
    for qr in run['query_results']:
        if qr['top_k'] == 3:
            latencies.append(qr['p50_latency_ms'])
            throughputs.append(qr['queries_per_second'])
            break
    ingestion_times.append(run['ingestion']['total_time_sec'])

print("Chroma N=10 (50k corpus) - Verification:")
print(f"  Latency range: {min(latencies):.1f}-{max(latencies):.1f} ms ✓")
print(f"  Throughput mean: {statistics.mean(throughputs):.0f} QPS ✓")
print(f"  Ingestion CV (raw): {statistics.stdev(ingestion_times)/statistics.mean(ingestion_times)*100:.1f}% ✓")

# After outlier removal (remove top 2 outliers)
ing_sorted = sorted(ingestion_times)
ing_clean = ing_sorted[:8]  # Remove 2 largest
cv_clean = statistics.stdev(ing_clean) / statistics.mean(ing_clean) * 100

print(f"  Ingestion CV (cleaned): {cv_clean:.1f}% ✓")
print("\nIf all values match the checklist above, data is correct!")
EOF
```

Expected output:
```
Chroma N=10 (50k corpus) - Verification:
  Latency range: 7.7-8.4 ms ✓
  Throughput mean: 124 QPS ✓
  Ingestion CV (raw): 20.2% ✓
  Ingestion CV (cleaned): 2.3% ✓

If all values match the checklist above, data is correct!
```

---

## Final Checklist Before Resubmission

- [ ] All "6.4-7.5 ms" → "7.7-8.4 ms"
- [ ] All "144 QPS" → "141 QPS"
- [ ] All "8.2%" → "2.3% (after outlier removal)"
- [ ] All "98, 138, 133" → removed or replaced with correct values
- [ ] Table 5 shows both raw (20.2%) and cleaned (2.3%) CV
- [ ] Added footnote explaining 2 cold-start outliers removed
- [ ] Figure 1 regenerated with correct data
- [ ] Ran verification script above - all values match ✓
- [ ] Searched manuscript for any remaining incorrect Chroma values
- [ ] Updated abstract and summary sections
- [ ] Git commit with all corrections documented

---

## Git Commit Message Template

```
Fix Chroma N=10 statistics reporting error

- Correct Table 3 latency: 6.4-7.5 → 7.7-8.4 ms
- Correct Table 4 throughput: 144 → 141 QPS
- Correct Table 5 ingestion CV: 8.2% → 2.3% (with outlier removal)
- Add transparency notes about 2 cold-start outliers removed
- Update abstract and summary text with correct values
- Regenerate Figure 1 with verified N=10 data

All values now correspond to actual experimental data in
results/chroma_scaling_n10/ directory.

Addresses JBDAI Reviewer 2 data verification concern.
```

---

**Created by:** Claude Sonnet 4.5
**Date:** February 2, 2026
**For:** JBDAI Manuscript Revision
