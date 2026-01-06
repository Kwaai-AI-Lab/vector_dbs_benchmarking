#!/usr/bin/env python3
"""
Analyze and compare pgvector IVFFlat vs HNSW index performance.

This script processes N=3 scaling results for both index types and generates:
- Performance comparison plots
- Statistical analysis
- Recommendations for index selection
"""

import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from collections import defaultdict

# Set plot style
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['figure.figsize'] = (16, 10)
plt.rcParams['font.size'] = 11

INDEX_COLORS = {
    'ivfflat': '#3498DB',  # Blue
    'hnsw': '#8E44AD',     # Amethyst Purple (matches multi-DB plots)
}

INDEX_LINESTYLES = {
    'ivfflat': '--',  # Dashed
    'hnsw': '-',      # Solid (matches multi-DB plots)
}

def load_aggregated_results(results_dir):
    """Load aggregated N=3 results from a scaling experiment directory."""
    results_file = Path(results_dir) / 'aggregated_results.json'

    if not results_file.exists():
        return None

    with open(results_file, 'r') as f:
        data = json.load(f)

    return data

def extract_scaling_metrics(results_dir):
    """Extract scaling metrics from all corpus sizes."""
    corpus_names = ['baseline', '1k', '10k', '50k']
    metrics = defaultdict(list)

    # Load the main aggregated results file
    result = load_aggregated_results(results_dir)

    if not result or 'results_by_corpus' not in result:
        return dict(metrics)

    # Extract data for each corpus
    for corpus_name in corpus_names:
        corpus_data = result['results_by_corpus'].get(corpus_name)
        if not corpus_data:
            continue

        agg = corpus_data['aggregated_metrics']

        # Extract key metrics
        if 'num_chunks' in agg and agg['num_chunks']:
            metrics['corpus_sizes'].append(agg['num_chunks']['mean'])
        else:
            # Estimate from corpus name
            size_map = {'baseline': 175, '1k': 5562, '10k': 69903, '50k': 345046}
            metrics['corpus_sizes'].append(size_map.get(corpus_name, 0))

        metrics['corpus_names'].append(corpus_name)

        # Ingestion metrics
        if 'ingestion_time' in agg and agg['ingestion_time']:
            metrics['ingestion_time_mean'].append(agg['ingestion_time']['mean'])
            metrics['ingestion_time_std'].append(agg['ingestion_time']['std'])
            metrics['ingestion_time_cv'].append(agg['ingestion_time']['cv'])

        # Query metrics
        if 'avg_latency_ms' in agg and agg['avg_latency_ms']:
            metrics['latency_mean'].append(agg['avg_latency_ms']['mean'])
            metrics['latency_std'].append(agg['avg_latency_ms']['std'])
            metrics['latency_cv'].append(agg['avg_latency_ms']['cv'])

        if 'queries_per_second' in agg and agg['queries_per_second']:
            metrics['qps_mean'].append(agg['queries_per_second']['mean'])
            metrics['qps_std'].append(agg['queries_per_second']['std'])

        # Quality metrics
        if 'avg_similarity' in agg and agg['avg_similarity']:
            metrics['similarity_mean'].append(agg['avg_similarity']['mean'])
            metrics['similarity_std'].append(agg['avg_similarity']['std'])

        # Resource metrics
        if 'cpu_avg' in agg and agg['cpu_avg']:
            metrics['cpu_mean'].append(agg['cpu_avg']['mean'])
        if 'memory_avg_mb' in agg and agg['memory_avg_mb']:
            metrics['memory_mean'].append(agg['memory_avg_mb']['mean'])

    return dict(metrics)

def plot_index_comparison(ivfflat_metrics, hnsw_metrics, output_dir):
    """Generate comparison plots for IVFFlat vs HNSW."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create 4-panel comparison figure
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # Panel A: Query Latency Scaling
    ax = axes[0, 0]
    if 'corpus_sizes' in ivfflat_metrics and 'latency_mean' in ivfflat_metrics:
        ax.errorbar(ivfflat_metrics['corpus_sizes'], ivfflat_metrics['latency_mean'],
                    yerr=ivfflat_metrics.get('latency_std', None),
                    marker='o', linewidth=2, markersize=8, capsize=5,
                    linestyle=INDEX_LINESTYLES['ivfflat'],
                    label='IVFFlat', color=INDEX_COLORS['ivfflat'])
    if 'corpus_sizes' in hnsw_metrics and 'latency_mean' in hnsw_metrics:
        ax.errorbar(hnsw_metrics['corpus_sizes'], hnsw_metrics['latency_mean'],
                    yerr=hnsw_metrics.get('latency_std', None),
                    marker='s', linewidth=2, markersize=8, capsize=5,
                    linestyle=INDEX_LINESTYLES['hnsw'],
                    label='HNSW', color=INDEX_COLORS['hnsw'])
    ax.set_xlabel('Corpus Size (chunks)', fontweight='bold', fontsize=12)
    ax.set_ylabel('Query Latency (ms)', fontweight='bold', fontsize=12)
    ax.set_title('(a) Query Latency Scaling', fontweight='bold', fontsize=13)
    ax.set_xscale('log')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    # Panel B: Throughput (QPS)
    ax = axes[0, 1]
    if 'corpus_sizes' in ivfflat_metrics and 'qps_mean' in ivfflat_metrics:
        ax.errorbar(ivfflat_metrics['corpus_sizes'], ivfflat_metrics['qps_mean'],
                    yerr=ivfflat_metrics.get('qps_std', None),
                    marker='o', linewidth=2, markersize=8, capsize=5,
                    linestyle=INDEX_LINESTYLES['ivfflat'],
                    label='IVFFlat', color=INDEX_COLORS['ivfflat'])
    if 'corpus_sizes' in hnsw_metrics and 'qps_mean' in hnsw_metrics:
        ax.errorbar(hnsw_metrics['corpus_sizes'], hnsw_metrics['qps_mean'],
                    yerr=hnsw_metrics.get('qps_std', None),
                    marker='s', linewidth=2, markersize=8, capsize=5,
                    linestyle=INDEX_LINESTYLES['hnsw'],
                    label='HNSW', color=INDEX_COLORS['hnsw'])
    ax.set_xlabel('Corpus Size (chunks)', fontweight='bold', fontsize=12)
    ax.set_ylabel('Queries Per Second', fontweight='bold', fontsize=12)
    ax.set_title('(b) Query Throughput', fontweight='bold', fontsize=13)
    ax.set_xscale('log')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    # Panel C: Ingestion Time
    ax = axes[1, 0]
    if 'corpus_sizes' in ivfflat_metrics and 'ingestion_time_mean' in ivfflat_metrics:
        ax.errorbar(ivfflat_metrics['corpus_sizes'], ivfflat_metrics['ingestion_time_mean'],
                    yerr=ivfflat_metrics.get('ingestion_time_std', None),
                    marker='o', linewidth=2, markersize=8, capsize=5,
                    linestyle=INDEX_LINESTYLES['ivfflat'],
                    label='IVFFlat', color=INDEX_COLORS['ivfflat'])
    if 'corpus_sizes' in hnsw_metrics and 'ingestion_time_mean' in hnsw_metrics:
        ax.errorbar(hnsw_metrics['corpus_sizes'], hnsw_metrics['ingestion_time_mean'],
                    yerr=hnsw_metrics.get('ingestion_time_std', None),
                    marker='s', linewidth=2, markersize=8, capsize=5,
                    linestyle=INDEX_LINESTYLES['hnsw'],
                    label='HNSW', color=INDEX_COLORS['hnsw'])
    ax.set_xlabel('Corpus Size (chunks)', fontweight='bold', fontsize=12)
    ax.set_ylabel('Ingestion Time (s)', fontweight='bold', fontsize=12)
    ax.set_title('(c) Data Ingestion Time', fontweight='bold', fontsize=13)
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    # Panel D: Retrieval Quality
    ax = axes[1, 1]
    if 'corpus_sizes' in ivfflat_metrics and 'similarity_mean' in ivfflat_metrics:
        ax.errorbar(ivfflat_metrics['corpus_sizes'], ivfflat_metrics['similarity_mean'],
                    yerr=ivfflat_metrics.get('similarity_std', None),
                    marker='o', linewidth=2, markersize=8, capsize=5,
                    linestyle=INDEX_LINESTYLES['ivfflat'],
                    label='IVFFlat', color=INDEX_COLORS['ivfflat'])
    if 'corpus_sizes' in hnsw_metrics and 'similarity_mean' in hnsw_metrics:
        ax.errorbar(hnsw_metrics['corpus_sizes'], hnsw_metrics['similarity_mean'],
                    yerr=hnsw_metrics.get('similarity_std', None),
                    marker='s', linewidth=2, markersize=8, capsize=5,
                    linestyle=INDEX_LINESTYLES['hnsw'],
                    label='HNSW', color=INDEX_COLORS['hnsw'])
    ax.set_xlabel('Corpus Size (chunks)', fontweight='bold', fontsize=12)
    ax.set_ylabel('Average Similarity Score', fontweight='bold', fontsize=12)
    ax.set_title('(d) Retrieval Quality', fontweight='bold', fontsize=13)
    ax.set_xscale('log')
    ax.set_ylim([0, 1])
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    plt.suptitle('pgvector: IVFFlat vs HNSW Index Performance Comparison (N=3)',
                 fontsize=16, fontweight='bold', y=0.995)
    plt.tight_layout()

    plot_file = output_dir / 'pgvector_index_comparison.png'
    plt.savefig(plot_file, dpi=300, bbox_inches='tight')
    print(f"✅ Comparison plot saved: {plot_file}")
    plt.close()

def generate_comparison_table(ivfflat_metrics, hnsw_metrics):
    """Generate comparison table for both index types."""

    print("\n" + "="*80)
    print("pgvector Index Performance Comparison (N=3)")
    print("="*80)

    corpus_names = ivfflat_metrics.get('corpus_names', [])

    print(f"\n{'Corpus':<12} {'Index':<10} {'Chunks':<10} {'Latency (ms)':<18} {'QPS':<15} {'Similarity':<12}")
    print("-" * 95)

    for i, corpus in enumerate(corpus_names):
        if i < len(ivfflat_metrics.get('latency_mean', [])):
            chunks = int(ivfflat_metrics['corpus_sizes'][i]) if i < len(ivfflat_metrics['corpus_sizes']) else 0
            lat_mean = ivfflat_metrics['latency_mean'][i]
            lat_std = ivfflat_metrics.get('latency_std', [0])[i] if i < len(ivfflat_metrics.get('latency_std', [])) else 0
            qps_mean = ivfflat_metrics['qps_mean'][i] if i < len(ivfflat_metrics['qps_mean']) else 0
            sim_mean = ivfflat_metrics['similarity_mean'][i] if i < len(ivfflat_metrics.get('similarity_mean', [])) else 0

            print(f"{corpus:<12} {'IVFFlat':<10} {chunks:<10} {lat_mean:>6.2f} ± {lat_std:<6.2f}  {qps_mean:>6.2f}        {sim_mean:.3f}")

        if i < len(hnsw_metrics.get('latency_mean', [])):
            chunks = int(hnsw_metrics['corpus_sizes'][i]) if i < len(hnsw_metrics['corpus_sizes']) else 0
            lat_mean = hnsw_metrics['latency_mean'][i]
            lat_std = hnsw_metrics.get('latency_std', [0])[i] if i < len(hnsw_metrics.get('latency_std', [])) else 0
            qps_mean = hnsw_metrics['qps_mean'][i] if i < len(hnsw_metrics['qps_mean']) else 0
            sim_mean = hnsw_metrics['similarity_mean'][i] if i < len(hnsw_metrics.get('similarity_mean', [])) else 0

            print(f"{'':<12} {'HNSW':<10} {chunks:<10} {lat_mean:>6.2f} ± {lat_std:<6.2f}  {qps_mean:>6.2f}        {sim_mean:.3f}")

        if i < len(corpus_names) - 1:
            print()

def main():
    """Main analysis function."""

    print("="*80)
    print("pgvector Index Comparison Analysis")
    print("="*80)

    # Load metrics for both index types
    print("\nLoading IVFFlat results...")
    ivfflat_metrics = extract_scaling_metrics('results/pgvector_ivfflat_scaling_n3')

    print("Loading HNSW results...")
    hnsw_metrics = extract_scaling_metrics('results/pgvector_hnsw_scaling_n3')

    if not ivfflat_metrics.get('corpus_sizes') and not hnsw_metrics.get('corpus_sizes'):
        print("\n❌ No results found for either index type!")
        print("Make sure scaling experiments have completed.")
        return 1

    # Generate comparison table
    if ivfflat_metrics.get('corpus_sizes') and hnsw_metrics.get('corpus_sizes'):
        generate_comparison_table(ivfflat_metrics, hnsw_metrics)

    # Generate plots
    output_dir = 'results/pgvector_index_comparison'
    plot_index_comparison(ivfflat_metrics, hnsw_metrics, output_dir)

    # Save metrics as JSON
    comparison_data = {
        'ivfflat': ivfflat_metrics,
        'hnsw': hnsw_metrics
    }

    json_file = Path(output_dir) / 'index_comparison_metrics.json'
    with open(json_file, 'w') as f:
        json.dump(comparison_data, f, indent=2, default=str)
    print(f"✅ Metrics saved: {json_file}")

    print("\n" + "="*80)
    print("Analysis complete!")
    print("="*80)

    return 0

if __name__ == '__main__':
    import sys
    sys.exit(main())
