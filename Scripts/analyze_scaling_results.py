#!/usr/bin/env python3
"""
Analyze scaling experiment results and create comprehensive visualizations.

This script loads results from multiple corpus sizes and generates scaling curves,
performance analysis, and statistical summaries.
"""

import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from scipy import stats

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

def extract_metrics(all_results):
    """Extract key metrics across all corpus sizes."""
    corpus_names = []
    num_chunks = []
    ingestion_times = []
    ingestion_throughputs = []

    # Query metrics for each top-k
    query_metrics_by_topk = {}

    for result in all_results:
        data = result['data']
        corpus_names.append(result['name'])
        chunks = data['ingestion']['num_chunks']
        ingest_time = data['ingestion']['total_time_sec']

        num_chunks.append(chunks)
        ingestion_times.append(ingest_time)
        ingestion_throughputs.append(chunks / ingest_time if ingest_time > 0 else 0)

        # Extract query metrics for each top-k
        for query_result in data['query_results']:
            top_k = query_result['top_k']
            if top_k not in query_metrics_by_topk:
                query_metrics_by_topk[top_k] = {
                    'chunks': [],
                    'avg_latency': [],
                    'p50_latency': [],
                    'p95_latency': [],
                    'qps': [],
                    'avg_similarity': []
                }

            query_metrics_by_topk[top_k]['chunks'].append(chunks)
            query_metrics_by_topk[top_k]['avg_latency'].append(query_result['avg_latency_ms'])
            query_metrics_by_topk[top_k]['p50_latency'].append(query_result['p50_latency_ms'])
            query_metrics_by_topk[top_k]['p95_latency'].append(query_result['p95_latency_ms'])
            query_metrics_by_topk[top_k]['qps'].append(query_result['queries_per_second'])
            query_metrics_by_topk[top_k]['avg_similarity'].append(query_result['avg_similarity'])

    return {
        'corpus_names': corpus_names,
        'num_chunks': num_chunks,
        'ingestion_times': ingestion_times,
        'ingestion_throughputs': ingestion_throughputs,
        'query_metrics_by_topk': query_metrics_by_topk
    }

def fit_scaling_curve(x, y):
    """Fit power law curve: y = a * x^b."""
    # Log-log linear fit
    log_x = np.log(x)
    log_y = np.log(y)
    slope, intercept, r_value, p_value, std_err = stats.linregress(log_x, log_y)
    a = np.exp(intercept)
    b = slope
    r_squared = r_value ** 2
    return a, b, r_squared

def create_scaling_plots(metrics, output_dir):
    """Create comprehensive scaling analysis plots."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    chunks = np.array(metrics['num_chunks'])
    ingestion_times = np.array(metrics['ingestion_times'])
    ingestion_throughputs = np.array(metrics['ingestion_throughputs'])

    # Create main figure with 3x3 grid
    fig = plt.figure(figsize=(20, 16))
    gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

    # 1. Ingestion Time vs Corpus Size (log-log)
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.loglog(chunks, ingestion_times, 'o-', markersize=10, linewidth=2, color='#2ecc71', label='Actual')
    a, b, r2 = fit_scaling_curve(chunks, ingestion_times)
    x_fit = np.logspace(np.log10(chunks.min()), np.log10(chunks.max()), 100)
    y_fit = a * (x_fit ** b)
    ax1.loglog(x_fit, y_fit, '--', linewidth=2, color='#e74c3c', label=f'Fit: O(N^{b:.2f}), R²={r2:.3f}')
    ax1.set_xlabel('Number of Chunks', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Ingestion Time (sec)', fontsize=12, fontweight='bold')
    ax1.set_title('Ingestion Time Scaling', fontsize=14, fontweight='bold')
    ax1.grid(True, alpha=0.3, which='both')
    ax1.legend(fontsize=10)

    # 2. Ingestion Throughput vs Corpus Size
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.semilogx(chunks, ingestion_throughputs, 'o-', markersize=10, linewidth=2, color='#3498db')
    ax2.set_xlabel('Number of Chunks', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Throughput (chunks/sec)', fontsize=12, fontweight='bold')
    ax2.set_title('Ingestion Throughput Scaling', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    avg_throughput = np.mean(ingestion_throughputs)
    ax2.axhline(y=avg_throughput, color='red', linestyle='--', linewidth=2,
                label=f'Average: {avg_throughput:.0f} ch/s')
    ax2.legend(fontsize=10)

    # 3. Query Latency Scaling (Average) - Multiple Top-K
    ax3 = fig.add_subplot(gs[0, 2])
    colors = ['#e74c3c', '#f39c12', '#2ecc71', '#3498db', '#9b59b6']
    for i, (top_k, metrics_k) in enumerate(sorted(metrics['query_metrics_by_topk'].items())):
        chunks_k = np.array(metrics_k['chunks'])
        latency_k = np.array(metrics_k['avg_latency'])
        ax3.loglog(chunks_k, latency_k, 'o-', markersize=8, linewidth=2,
                   color=colors[i % len(colors)], label=f'Top-K={top_k}')
    ax3.set_xlabel('Number of Chunks', fontsize=12, fontweight='bold')
    ax3.set_ylabel('Avg Query Latency (ms)', fontsize=12, fontweight='bold')
    ax3.set_title('Query Latency Scaling (All Top-K)', fontsize=14, fontweight='bold')
    ax3.grid(True, alpha=0.3, which='both')
    ax3.legend(fontsize=9)

    # 4-8: Individual Top-K Scaling Curves with Fit
    top_k_values = sorted(metrics['query_metrics_by_topk'].keys())
    for idx, top_k in enumerate(top_k_values[:5]):  # Plot first 5 top-k values
        row = 1 + idx // 3
        col = idx % 3
        ax = fig.add_subplot(gs[row, col])

        metrics_k = metrics['query_metrics_by_topk'][top_k]
        chunks_k = np.array(metrics_k['chunks'])
        latency_k = np.array(metrics_k['avg_latency'])

        # Plot actual data
        ax.loglog(chunks_k, latency_k, 'o', markersize=10, color='#2ecc71', label='Actual')

        # Fit power law
        if len(chunks_k) > 2:
            a, b, r2 = fit_scaling_curve(chunks_k, latency_k)
            x_fit = np.logspace(np.log10(chunks_k.min()), np.log10(chunks_k.max()), 100)
            y_fit = a * (x_fit ** b)
            ax.loglog(x_fit, y_fit, '--', linewidth=2, color='#e74c3c',
                     label=f'Fit: O(N^{b:.3f})\nR²={r2:.3f}')

            # Add scaling efficiency annotation
            ideal_linear = 1.0
            efficiency = b / ideal_linear
            efficiency_text = f'Efficiency: {efficiency:.3f}\n'
            if efficiency < 0.6:
                efficiency_text += '(Excellent sub-linear)'
            elif efficiency < 1.0:
                efficiency_text += '(Good sub-linear)'
            elif efficiency < 1.2:
                efficiency_text += '(Near-linear)'
            else:
                efficiency_text += '(Super-linear)'

            ax.text(0.05, 0.95, efficiency_text,
                   transform=ax.transAxes, fontsize=9,
                   verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        ax.set_xlabel('Number of Chunks', fontsize=11, fontweight='bold')
        ax.set_ylabel('Avg Latency (ms)', fontsize=11, fontweight='bold')
        ax.set_title(f'Query Latency Scaling (Top-K={top_k})', fontsize=12, fontweight='bold')
        ax.grid(True, alpha=0.3, which='both')
        ax.legend(fontsize=9, loc='lower right')

    # 9. Scaling Exponents Comparison
    ax9 = fig.add_subplot(gs[2, 2])
    exponents = []
    r_squared_values = []
    topk_labels = []
    for top_k in sorted(metrics['query_metrics_by_topk'].keys()):
        metrics_k = metrics['query_metrics_by_topk'][top_k]
        chunks_k = np.array(metrics_k['chunks'])
        latency_k = np.array(metrics_k['avg_latency'])
        if len(chunks_k) > 2:
            _, b, r2 = fit_scaling_curve(chunks_k, latency_k)
            exponents.append(b)
            r_squared_values.append(r2)
            topk_labels.append(f'k={top_k}')

    x_pos = np.arange(len(topk_labels))
    bars = ax9.bar(x_pos, exponents, color=['#2ecc71' if e < 0.6 else '#f39c12' if e < 1.0 else '#e74c3c'
                                              for e in exponents], alpha=0.7, edgecolor='black')
    ax9.axhline(y=1.0, color='red', linestyle='--', linewidth=2, label='Linear (1.0)')
    ax9.set_xlabel('Top-K Value', fontsize=11, fontweight='bold')
    ax9.set_ylabel('Scaling Exponent (b)', fontsize=11, fontweight='bold')
    ax9.set_title('Scaling Exponents by Top-K\n(Lower is Better)', fontsize=12, fontweight='bold')
    ax9.set_xticks(x_pos)
    ax9.set_xticklabels(topk_labels)
    ax9.grid(axis='y', alpha=0.3)
    ax9.legend(fontsize=9)

    # Add value labels on bars
    for bar, exp, r2 in zip(bars, exponents, r_squared_values):
        height = bar.get_height()
        ax9.text(bar.get_x() + bar.get_width()/2., height,
                f'{exp:.3f}\nR²={r2:.2f}',
                ha='center', va='bottom', fontsize=8, fontweight='bold')

    fig.suptitle('FAISS Scaling Analysis: Performance vs Corpus Size',
                 fontsize=18, fontweight='bold', y=0.995)

    plot_file = output_dir / 'scaling_analysis.png'
    plt.savefig(plot_file, dpi=150, bbox_inches='tight')
    print(f"\n✅ Scaling analysis plot saved to: {plot_file}")

    return exponents, r_squared_values, topk_labels

def print_summary(metrics, exponents, r_squared_values, topk_labels):
    """Print summary statistics."""
    print("\n" + "="*70)
    print("SCALING ANALYSIS SUMMARY")
    print("="*70)

    print(f"\nCorpus Sizes Tested: {len(metrics['num_chunks'])}")
    print(f"  Range: {min(metrics['num_chunks']):,} - {max(metrics['num_chunks']):,} chunks")
    print(f"  Scale Factor: {max(metrics['num_chunks']) / min(metrics['num_chunks']):.1f}x")

    print(f"\nIngestion Performance:")
    print(f"  Average throughput: {np.mean(metrics['ingestion_throughputs']):.0f} chunks/sec")
    print(f"  Std deviation: {np.std(metrics['ingestion_throughputs']):.0f} chunks/sec")

    print(f"\nQuery Latency Scaling Exponents:")
    print(f"  {'Top-K':<10} {'Exponent':<12} {'R²':<10} {'Interpretation'}")
    print(f"  {'-'*60}")
    for label, exp, r2 in zip(topk_labels, exponents, r_squared_values):
        if exp < 0.6:
            interp = "Excellent sub-linear"
        elif exp < 1.0:
            interp = "Good sub-linear"
        elif exp < 1.2:
            interp = "Near-linear"
        else:
            interp = "Super-linear (concerning)"
        print(f"  {label:<10} {exp:<12.3f} {r2:<10.3f} {interp}")

    avg_exponent = np.mean(exponents)
    print(f"\n  Average Exponent: {avg_exponent:.3f}")
    print(f"  Interpretation: ", end="")
    if avg_exponent < 0.6:
        print("FAISS shows excellent sub-linear scaling")
    elif avg_exponent < 1.0:
        print("FAISS shows good sub-linear scaling")
    elif avg_exponent < 1.2:
        print("FAISS shows near-linear scaling")
    else:
        print("FAISS shows super-linear scaling (needs investigation)")

    print("\n" + "="*70)

def main():
    print("="*70)
    print("FAISS Scaling Analysis")
    print("="*70)

    results_dir = 'results/faiss_scaling_experiment'
    if not Path(results_dir).exists():
        print(f"❌ Results directory not found: {results_dir}")
        print("Run the scaling experiment first.")
        return

    # Load all results
    print("\nLoading results...")
    all_results = load_all_results(results_dir)

    if len(all_results) < 2:
        print(f"❌ Need at least 2 corpus sizes for scaling analysis. Found: {len(all_results)}")
        return

    print(f"\n✓ Loaded results from {len(all_results)} corpus sizes")

    # Extract metrics
    print("\nExtracting metrics...")
    metrics = extract_metrics(all_results)

    # Create plots
    print("\nGenerating scaling analysis plots...")
    exponents, r_squared_values, topk_labels = create_scaling_plots(metrics, results_dir)

    # Print summary
    print_summary(metrics, exponents, r_squared_values, topk_labels)

    # Save detailed results
    analysis_file = Path(results_dir) / 'scaling_analysis.json'
    analysis_data = {
        'corpus_sizes': metrics['num_chunks'],
        'ingestion_metrics': {
            'times_sec': metrics['ingestion_times'],
            'throughputs_chunks_per_sec': metrics['ingestion_throughputs'],
            'avg_throughput': float(np.mean(metrics['ingestion_throughputs'])),
            'std_throughput': float(np.std(metrics['ingestion_throughputs']))
        },
        'scaling_exponents': {
            topk_labels[i]: {
                'exponent': float(exponents[i]),
                'r_squared': float(r_squared_values[i])
            }
            for i in range(len(topk_labels))
        },
        'average_exponent': float(np.mean(exponents))
    }

    with open(analysis_file, 'w') as f:
        json.dump(analysis_data, f, indent=2)
    print(f"\n✅ Detailed analysis saved to: {analysis_file}")

if __name__ == '__main__':
    main()
