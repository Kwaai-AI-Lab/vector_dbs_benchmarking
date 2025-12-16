#!/usr/bin/env python3
"""
Analyze scaling experiment results with statistical analysis for replicate runs.

This script handles multiple runs of the same corpus size and calculates:
- Mean, standard deviation, min, max
- 95% confidence intervals
- Coefficient of variation
"""

import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from scipy import stats
from collections import defaultdict

def load_all_results(results_dir):
    """Load results from all corpus sizes."""
    results_dir = Path(results_dir)
    all_results = []

    for corpus_dir in sorted(results_dir.glob('corpus_*')):
        results_file = corpus_dir / 'results.json'
        if results_file.exists():
            with open(results_file, 'r') as f:
                data = json.load(f)
                all_results.append({
                    'name': corpus_dir.name,
                    'data': data
                })
                print(f"✓ Loaded: {corpus_dir.name} ({data['ingestion']['num_chunks']:,} chunks)")

    return all_results

def group_by_chunk_count(all_results):
    """Group results by chunk count (for handling replicates)."""
    grouped = defaultdict(list)

    for result in all_results:
        chunks = result['data']['ingestion']['num_chunks']
        grouped[chunks].append(result)

    return grouped

def calculate_stats(values):
    """Calculate statistical measures for a list of values."""
    arr = np.array(values)
    n = len(arr)

    if n == 0:
        return {
            'mean': 0, 'std': 0, 'min': 0, 'max': 0,
            'ci_lower': 0, 'ci_upper': 0, 'cv': 0, 'n': 0
        }

    mean = np.mean(arr)
    std = np.std(arr, ddof=1) if n > 1 else 0

    # 95% confidence interval (t-distribution for small samples)
    if n > 1:
        sem = stats.sem(arr)
        ci = stats.t.interval(0.95, n-1, loc=mean, scale=sem)
        ci_lower, ci_upper = ci
    else:
        ci_lower = ci_upper = mean

    # Coefficient of variation (relative std dev)
    cv = (std / mean * 100) if mean > 0 else 0

    return {
        'mean': float(mean),
        'std': float(std),
        'min': float(np.min(arr)),
        'max': float(np.max(arr)),
        'ci_lower': float(ci_lower),
        'ci_upper': float(ci_upper),
        'cv': float(cv),
        'n': int(n)
    }

def extract_metrics_with_stats(all_results):
    """Extract metrics and calculate statistics for replicate runs."""

    # Group by chunk count
    grouped = group_by_chunk_count(all_results)

    # Storage for aggregated metrics
    chunk_sizes = sorted(grouped.keys())
    metrics = {
        'chunk_sizes': chunk_sizes,
        'corpus_names': [],
        'ingestion_time': [],
        'ingestion_throughput': [],
        'query_metrics_by_topk': defaultdict(lambda: {
            'avg_latency': [],
            'p50_latency': [],
            'p95_latency': [],
            'p99_latency': [],
            'qps': [],
            'avg_similarity': []
        })
    }

    # For each unique chunk size, calculate statistics
    for chunks in chunk_sizes:
        runs = grouped[chunks]
        run_names = [r['name'] for r in runs]

        # Collect metrics across all runs at this chunk size
        ingestion_times = []
        ingestion_throughputs = []

        for run in runs:
            data = run['data']
            ingest_time = data['ingestion']['total_time_sec']
            ingestion_times.append(ingest_time)
            ingestion_throughputs.append(chunks / ingest_time if ingest_time > 0 else 0)

        # Calculate stats for ingestion
        metrics['corpus_names'].append(f"{run_names[0]} (n={len(runs)})")
        metrics['ingestion_time'].append(calculate_stats(ingestion_times))
        metrics['ingestion_throughput'].append(calculate_stats(ingestion_throughputs))

        # Calculate stats for each top-k value
        for run in runs:
            for query_result in run['data']['query_results']:
                top_k = query_result['top_k']
                metrics['query_metrics_by_topk'][top_k]['avg_latency'].append(query_result['avg_latency_ms'])
                metrics['query_metrics_by_topk'][top_k]['p50_latency'].append(query_result['p50_latency_ms'])
                metrics['query_metrics_by_topk'][top_k]['p95_latency'].append(query_result['p95_latency_ms'])
                metrics['query_metrics_by_topk'][top_k]['p99_latency'].append(query_result['p99_latency_ms'])
                metrics['query_metrics_by_topk'][top_k]['qps'].append(query_result['queries_per_second'])
                metrics['query_metrics_by_topk'][top_k]['avg_similarity'].append(query_result['avg_similarity'])

    # Convert lists to stats for each top-k
    for top_k in metrics['query_metrics_by_topk']:
        metrics_k = metrics['query_metrics_by_topk'][top_k]

        # Group by chunk size
        for metric_name in ['avg_latency', 'p50_latency', 'p95_latency', 'p99_latency', 'qps', 'avg_similarity']:
            values_by_chunks = []
            idx = 0
            for chunks in chunk_sizes:
                n_runs = len(grouped[chunks])
                chunk_values = metrics_k[metric_name][idx:idx+n_runs]
                values_by_chunks.append(calculate_stats(chunk_values))
                idx += n_runs
            metrics_k[metric_name] = values_by_chunks

    return metrics

def fit_scaling_curve(x, y):
    """Fit power law curve: y = a * x^b."""
    log_x = np.log(x)
    log_y = np.log(y)
    slope, intercept, r_value, p_value, std_err = stats.linregress(log_x, log_y)
    a = np.exp(intercept)
    b = slope
    r_squared = r_value ** 2
    return a, b, r_squared

def create_scaling_plots_with_stats(metrics, output_dir):
    """Create scaling plots with error bars for statistical rigor."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    chunks = np.array(metrics['chunk_sizes'])

    # Extract mean values for curve fitting
    ingestion_times_mean = np.array([m['mean'] for m in metrics['ingestion_time']])
    ingestion_throughput_mean = np.array([m['mean'] for m in metrics['ingestion_throughput']])

    # Create comprehensive figure
    fig = plt.figure(figsize=(20, 16))
    gs = fig.add_gridspec(3, 3, hspace=0.35, wspace=0.3)

    # 1. Ingestion Time Scaling with Error Bars
    ax1 = fig.add_subplot(gs[0, 0])
    ingestion_times_std = np.array([m['std'] for m in metrics['ingestion_time']])
    ax1.errorbar(chunks, ingestion_times_mean, yerr=ingestion_times_std,
                 fmt='o-', markersize=8, linewidth=2, capsize=5, capthick=2,
                 color='#2ecc71', ecolor='#27ae60', label='Mean ± SD')

    ax1.set_xscale('log')
    ax1.set_yscale('log')
    a, b, r2 = fit_scaling_curve(chunks, ingestion_times_mean)
    x_fit = np.logspace(np.log10(chunks.min()), np.log10(chunks.max()), 100)
    y_fit = a * (x_fit ** b)
    ax1.plot(x_fit, y_fit, '--', linewidth=2, color='#e74c3c',
             label=f'Power Law: O(N^{b:.3f}), R²={r2:.3f}')

    ax1.set_xlabel('Number of Chunks', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Ingestion Time (sec)', fontsize=12, fontweight='bold')
    ax1.set_title('Ingestion Time Scaling', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3, which='both')
    ax1.legend(fontsize=10)

    # 2. Ingestion Throughput with Error Bars
    ax2 = fig.add_subplot(gs[0, 1])
    throughput_std = np.array([m['std'] for m in metrics['ingestion_throughput']])
    ax2.errorbar(chunks, ingestion_throughput_mean, yerr=throughput_std,
                 fmt='o-', markersize=8, linewidth=2, capsize=5, capthick=2,
                 color='#3498db', ecolor='#2980b9', label='Mean ± SD')

    ax2.set_xscale('log')
    ax2.set_xlabel('Number of Chunks', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Throughput (chunks/sec)', fontsize=12, fontweight='bold')
    ax2.set_title('Ingestion Throughput Scaling', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    avg_throughput = np.mean(ingestion_throughput_mean)
    ax2.axhline(y=avg_throughput, color='red', linestyle='--', linewidth=2,
                label=f'Average: {avg_throughput:.0f} ch/s')
    ax2.legend(fontsize=10)

    # 3. Query Latency Scaling for All Top-K with Error Bars
    ax3 = fig.add_subplot(gs[0, 2])
    colors = ['#e74c3c', '#f39c12', '#2ecc71', '#3498db', '#9b59b6']

    for i, top_k in enumerate(sorted(metrics['query_metrics_by_topk'].keys())):
        metrics_k = metrics['query_metrics_by_topk'][top_k]
        latency_mean = np.array([m['mean'] for m in metrics_k['avg_latency']])
        latency_std = np.array([m['std'] for m in metrics_k['avg_latency']])

        ax3.errorbar(chunks, latency_mean, yerr=latency_std,
                     fmt='o-', markersize=6, linewidth=2, capsize=4, capthick=1.5,
                     color=colors[i % len(colors)], alpha=0.8,
                     label=f'Top-K={top_k}')

    ax3.set_xscale('log')
    ax3.set_yscale('log')
    ax3.set_xlabel('Number of Chunks', fontsize=12, fontweight='bold')
    ax3.set_ylabel('Avg Query Latency (ms)', fontsize=12, fontweight='bold')
    ax3.set_title('Query Latency Scaling (All Top-K)', fontsize=14, fontweight='bold')
    ax3.grid(True, alpha=0.3, which='both')
    ax3.legend(fontsize=9)

    # 4-8: Individual Top-K with Power Law Fits and Error Bars
    top_k_values = sorted(metrics['query_metrics_by_topk'].keys())
    scaling_exponents = []
    r_squared_values = []

    for idx, top_k in enumerate(top_k_values[:5]):
        row = 1 + idx // 3
        col = idx % 3
        ax = fig.add_subplot(gs[row, col])

        metrics_k = metrics['query_metrics_by_topk'][top_k]
        latency_mean = np.array([m['mean'] for m in metrics_k['avg_latency']])
        latency_std = np.array([m['std'] for m in metrics_k['avg_latency']])
        latency_ci_lower = np.array([m['ci_lower'] for m in metrics_k['avg_latency']])
        latency_ci_upper = np.array([m['ci_upper'] for m in metrics_k['avg_latency']])

        # Plot with error bars (95% CI)
        ax.errorbar(chunks, latency_mean,
                   yerr=[latency_mean - latency_ci_lower, latency_ci_upper - latency_mean],
                   fmt='o', markersize=10, capsize=5, capthick=2,
                   color='#2ecc71', ecolor='#27ae60', label='Mean ± 95% CI')

        # Fit power law
        if len(chunks) > 2:
            a, b, r2 = fit_scaling_curve(chunks, latency_mean)
            x_fit = np.logspace(np.log10(chunks.min()), np.log10(chunks.max()), 100)
            y_fit = a * (x_fit ** b)
            ax.plot(x_fit, y_fit, '--', linewidth=2, color='#e74c3c',
                   label=f'O(N^{b:.3f}), R²={r2:.3f}')

            scaling_exponents.append(b)
            r_squared_values.append(r2)

            # Efficiency annotation
            efficiency = b / 1.0
            efficiency_text = f'Efficiency: {efficiency:.3f}\n'
            if efficiency < 0.6:
                efficiency_text += '(Excellent)'
                color = '#2ecc71'
            elif efficiency < 1.0:
                efficiency_text += '(Good)'
                color = '#f39c12'
            else:
                efficiency_text += '(Linear+)'
                color = '#e74c3c'

            ax.text(0.05, 0.95, efficiency_text,
                   transform=ax.transAxes, fontsize=10,
                   verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor=color, alpha=0.3))

        ax.set_xscale('log')
        ax.set_yscale('log')
        ax.set_xlabel('Number of Chunks', fontsize=11, fontweight='bold')
        ax.set_ylabel('Avg Latency (ms)', fontsize=11, fontweight='bold')
        ax.set_title(f'Query Latency Scaling (Top-K={top_k})', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3, which='both')
        ax.legend(fontsize=9, loc='lower right')

    # 9. Coefficient of Variation by Corpus Size (Top-K=3)
    ax9 = fig.add_subplot(gs[2, 2])
    top_k_3_metrics = metrics['query_metrics_by_topk'][3]
    cv_values = [m['cv'] for m in top_k_3_metrics['avg_latency']]
    n_values = [m['n'] for m in top_k_3_metrics['avg_latency']]

    colors_cv = ['#2ecc71' if cv < 5 else '#f39c12' if cv < 10 else '#e74c3c' for cv in cv_values]
    bars = ax9.bar(range(len(cv_values)), cv_values, color=colors_cv, alpha=0.7, edgecolor='black')

    ax9.set_xlabel('Corpus Size', fontsize=11, fontweight='bold')
    ax9.set_ylabel('Coefficient of Variation (%)', fontsize=11, fontweight='bold')
    ax9.set_title('Measurement Variability (Top-K=3)\nLower is Better', fontsize=12, fontweight='bold')
    ax9.set_xticks(range(len(cv_values)))
    ax9.set_xticklabels([f'{c:,}\n(n={n})' for c, n in zip(chunks, n_values)], rotation=45, ha='right', fontsize=8)
    ax9.grid(axis='y', alpha=0.3)
    ax9.axhline(y=5, color='orange', linestyle='--', linewidth=1, alpha=0.5, label='5% threshold')
    ax9.legend(fontsize=9)

    # Add value labels
    for bar, cv in zip(bars, cv_values):
        height = bar.get_height()
        ax9.text(bar.get_x() + bar.get_width()/2., height,
                f'{cv:.1f}%', ha='center', va='bottom', fontsize=9, fontweight='bold')

    fig.suptitle('FAISS Scaling Analysis with Statistical Rigor (N=3 at Max Scale)',
                 fontsize=18, fontweight='bold', y=0.995)

    plot_file = output_dir / 'scaling_analysis_with_stats.png'
    plt.savefig(plot_file, dpi=150, bbox_inches='tight')
    print(f"\n✅ Statistical scaling analysis plot saved to: {plot_file}")

    return scaling_exponents, r_squared_values

def print_statistical_summary(metrics):
    """Print detailed statistical summary."""
    print("\n" + "="*80)
    print("STATISTICAL ANALYSIS SUMMARY")
    print("="*80)

    chunks = metrics['chunk_sizes']

    print(f"\nCorpus Sizes Tested: {len(chunks)}")
    print(f"  Range: {min(chunks):,} - {max(chunks):,} chunks")
    print(f"  Scale Factor: {max(chunks) / min(chunks):.1f}x")

    # Ingestion statistics
    print(f"\n{'='*80}")
    print("INGESTION PERFORMANCE (with replicates)")
    print(f"{'='*80}")
    print(f"{'Chunks':<12} {'Mean (s)':<12} {'SD (s)':<12} {'CV%':<10} {'n':<5} {'Throughput (ch/s)':<20}")
    print("-"*80)

    for i, chunk_count in enumerate(chunks):
        ingest = metrics['ingestion_time'][i]
        throughput = metrics['ingestion_throughput'][i]
        print(f"{chunk_count:<12,} {ingest['mean']:<12.2f} {ingest['std']:<12.2f} "
              f"{ingest['cv']:<10.2f} {ingest['n']:<5} "
              f"{throughput['mean']:.1f} ± {throughput['std']:.1f}")

    # Query latency statistics (Top-K=3)
    print(f"\n{'='*80}")
    print("QUERY LATENCY STATISTICS (Top-K=3)")
    print(f"{'='*80}")
    print(f"{'Chunks':<12} {'Mean (ms)':<12} {'SD (ms)':<12} {'CV%':<10} {'95% CI':<20} {'n':<5}")
    print("-"*80)

    metrics_k3 = metrics['query_metrics_by_topk'][3]
    for i, chunk_count in enumerate(chunks):
        lat = metrics_k3['avg_latency'][i]
        ci_range = f"[{lat['ci_lower']:.2f}, {lat['ci_upper']:.2f}]"
        print(f"{chunk_count:<12,} {lat['mean']:<12.2f} {lat['std']:<12.2f} "
              f"{lat['cv']:<10.2f} {ci_range:<20} {lat['n']:<5}")

    # Highlight largest corpus statistics (with replicates)
    largest_idx = -1
    print(f"\n{'='*80}")
    print(f"REPLICATE ANALYSIS - Largest Corpus ({chunks[largest_idx]:,} chunks)")
    print(f"{'='*80}")

    largest_ingest = metrics['ingestion_time'][largest_idx]
    largest_lat = metrics_k3['avg_latency'][largest_idx]

    if largest_ingest['n'] > 1:
        print(f"\nIngestion Time (n={largest_ingest['n']}):")
        print(f"  Mean: {largest_ingest['mean']:.2f} sec")
        print(f"  Std Dev: {largest_ingest['std']:.2f} sec ({largest_ingest['cv']:.1f}% CV)")
        print(f"  Range: [{largest_ingest['min']:.2f}, {largest_ingest['max']:.2f}] sec")
        print(f"  95% CI: [{largest_ingest['ci_lower']:.2f}, {largest_ingest['ci_upper']:.2f}] sec")

        print(f"\nQuery Latency Top-K=3 (n={largest_lat['n']}):")
        print(f"  Mean: {largest_lat['mean']:.2f} ms")
        print(f"  Std Dev: {largest_lat['std']:.2f} ms ({largest_lat['cv']:.1f}% CV)")
        print(f"  Range: [{largest_lat['min']:.2f}, {largest_lat['max']:.2f}] ms")
        print(f"  95% CI: [{largest_lat['ci_lower']:.2f}, {largest_lat['ci_upper']:.2f}] ms")

        print(f"\n✓ Measurement Variability: {largest_lat['cv']:.2f}% CV")
        if largest_lat['cv'] < 5:
            print("  → Excellent reproducibility")
        elif largest_lat['cv'] < 10:
            print("  → Good reproducibility")
        else:
            print("  → Moderate reproducibility - consider more runs")
    else:
        print("  (Single run - no statistical analysis available)")

    print("\n" + "="*80)

def main():
    print("="*80)
    print("FAISS Scaling Analysis with Statistics")
    print("="*80)

    results_dir = 'results/faiss_scaling_experiment'
    if not Path(results_dir).exists():
        print(f"❌ Results directory not found: {results_dir}")
        return

    # Load results
    print("\nLoading results...")
    all_results = load_all_results(results_dir)

    if len(all_results) < 2:
        print(f"❌ Need at least 2 corpus sizes. Found: {len(all_results)}")
        return

    print(f"\n✓ Loaded results from {len(all_results)} benchmark runs")

    # Extract metrics with statistics
    print("\nCalculating statistics for replicate runs...")
    metrics = extract_metrics_with_stats(all_results)

    # Create plots
    print("\nGenerating statistical analysis plots...")
    scaling_exponents, r_squared = create_scaling_plots_with_stats(metrics, results_dir)

    # Print summary
    print_statistical_summary(metrics)

    # Save detailed JSON
    stats_file = Path(results_dir) / 'scaling_statistics.json'
    stats_data = {
        'chunk_sizes': metrics['chunk_sizes'],
        'ingestion_stats': [
            {
                'chunks': chunks,
                'time': metrics['ingestion_time'][i],
                'throughput': metrics['ingestion_throughput'][i]
            }
            for i, chunks in enumerate(metrics['chunk_sizes'])
        ],
        'query_stats_by_topk': {
            str(top_k): [
                {
                    'chunks': chunks,
                    'avg_latency': metrics['query_metrics_by_topk'][top_k]['avg_latency'][i],
                    'p95_latency': metrics['query_metrics_by_topk'][top_k]['p95_latency'][i],
                    'qps': metrics['query_metrics_by_topk'][top_k]['qps'][i]
                }
                for i, chunks in enumerate(metrics['chunk_sizes'])
            ]
            for top_k in metrics['query_metrics_by_topk'].keys()
        }
    }

    with open(stats_file, 'w') as f:
        json.dump(stats_data, f, indent=2)
    print(f"\n✅ Statistical data saved to: {stats_file}")

if __name__ == '__main__':
    main()
