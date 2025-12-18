#!/usr/bin/env python3
"""
Create comprehensive cross-database performance comparison visualizations.

Generates:
1. Query latency scaling curves
2. Ingestion time comparison
3. Throughput comparison
4. Resource usage comparison
"""

import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple

# Set style for publication-quality plots
plt.style.use('seaborn-v0_8-darkgrid')
plt.rcParams['figure.figsize'] = (14, 10)
plt.rcParams['font.size'] = 10
plt.rcParams['axes.titlesize'] = 12
plt.rcParams['axes.labelsize'] = 11
plt.rcParams['legend.fontsize'] = 10

# Database colors for consistent visualization
DB_COLORS = {
    'FAISS': '#1f77b4',
    'Chroma': '#ff7f0e',
    'Qdrant': '#2ca02c',
    'Weaviate': '#d62728',
    'Milvus': '#9467bd',
    'OpenSearch': '#8c564b'
}

# Corpus configurations
CORPUS_SIZES = [
    ('baseline', 175),
    ('1k', 5562),
    ('10k', 69903),
    ('50k', 345046),
]

def load_database_results(db_name: str) -> Dict:
    """Load all results for a database across corpus sizes."""
    results = {}
    for corpus_name, chunks in CORPUS_SIZES:
        path = Path(f'results/{db_name.lower()}_scaling_experiment/corpus_{corpus_name}/results.json')
        if path.exists():
            with open(path, 'r') as f:
                results[corpus_name] = json.load(f)
    return results

def extract_metrics(results: Dict, metric_path: List[str]) -> List[Tuple[int, float]]:
    """Extract metric values across corpus sizes.

    Args:
        results: Database results dict
        metric_path: Path to metric (e.g., ['ingestion', 'total_time_sec'])

    Returns:
        List of (num_chunks, value) tuples
    """
    data = []
    for corpus_name, chunks in CORPUS_SIZES:
        if corpus_name in results:
            value = results[corpus_name]
            for key in metric_path:
                if isinstance(value, list):
                    # Handle query_results array - find top_k=3
                    for item in value:
                        if item.get('top_k') == 3:
                            value = item
                            break
                value = value.get(key, None)
                if value is None:
                    break
            if value is not None:
                data.append((chunks, value))
    return data

def plot_query_latency_scaling():
    """Create query latency scaling curves."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    databases = ['FAISS', 'Chroma', 'Qdrant', 'Weaviate', 'Milvus', 'OpenSearch']

    # Plot 1: P50 Latency
    for db in databases:
        results = load_database_results(db)
        if results:
            data = extract_metrics(results, ['query_results', 'p50_latency_ms'])
            if data:
                chunks, latencies = zip(*data)
                ax1.plot(chunks, latencies, 'o-', label=db, color=DB_COLORS.get(db),
                        linewidth=2, markersize=8)

    ax1.set_xlabel('Number of Chunks', fontsize=12, fontweight='bold')
    ax1.set_ylabel('P50 Query Latency (ms)', fontsize=12, fontweight='bold')
    ax1.set_title('Query Latency Scaling (Top-K=3, Median)', fontsize=14, fontweight='bold')
    ax1.set_xscale('log')
    ax1.set_yscale('log')
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='best', framealpha=0.9)

    # Plot 2: Queries Per Second
    for db in databases:
        results = load_database_results(db)
        if results:
            data = extract_metrics(results, ['query_results', 'queries_per_second'])
            if data:
                chunks, qps = zip(*data)
                ax2.plot(chunks, qps, 'o-', label=db, color=DB_COLORS.get(db),
                        linewidth=2, markersize=8)

    ax2.set_xlabel('Number of Chunks', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Queries Per Second', fontsize=12, fontweight='bold')
    ax2.set_title('Throughput Scaling (Top-K=3)', fontsize=14, fontweight='bold')
    ax2.set_xscale('log')
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='best', framealpha=0.9)

    plt.tight_layout()
    output_path = 'results/cross_database_comparison/query_latency_scaling.png'
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {output_path}")
    plt.close()

def plot_ingestion_comparison():
    """Create ingestion time comparison."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    databases = ['Chroma', 'Qdrant', 'Weaviate', 'Milvus', 'OpenSearch']

    # Plot 1: Total Ingestion Time
    for db in databases:
        results = load_database_results(db)
        if results:
            data = extract_metrics(results, ['ingestion', 'total_time_sec'])
            if data:
                chunks, times = zip(*data)
                ax1.plot(chunks, times, 'o-', label=db, color=DB_COLORS.get(db),
                        linewidth=2, markersize=8)

    ax1.set_xlabel('Number of Chunks', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Ingestion Time (seconds)', fontsize=12, fontweight='bold')
    ax1.set_title('Ingestion Time Scaling', fontsize=14, fontweight='bold')
    ax1.set_xscale('log')
    ax1.set_yscale('log')
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='best', framealpha=0.9)

    # Plot 2: Ingestion Throughput (chunks/sec)
    for db in databases:
        results = load_database_results(db)
        if results:
            throughput_data = []
            for corpus_name, num_chunks in CORPUS_SIZES:
                if corpus_name in results:
                    total_time = results[corpus_name]['ingestion']['total_time_sec']
                    throughput = num_chunks / total_time
                    throughput_data.append((num_chunks, throughput))

            if throughput_data:
                chunks, throughput = zip(*throughput_data)
                ax2.plot(chunks, throughput, 'o-', label=db, color=DB_COLORS.get(db),
                        linewidth=2, markersize=8)

    ax2.set_xlabel('Number of Chunks', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Ingestion Throughput (chunks/sec)', fontsize=12, fontweight='bold')
    ax2.set_title('Ingestion Throughput Scaling', fontsize=14, fontweight='bold')
    ax2.set_xscale('log')
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='best', framealpha=0.9)

    plt.tight_layout()
    output_path = 'results/cross_database_comparison/ingestion_comparison.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {output_path}")
    plt.close()

def plot_50k_detailed_comparison():
    """Create detailed comparison at 50K corpus size."""
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))

    databases = ['Chroma', 'Qdrant', 'Weaviate', 'Milvus']

    # Collect metrics for 50K corpus
    metrics = {
        'latency': [],
        'qps': [],
        'ingestion': [],
        'memory': []
    }

    for db in databases:
        path = Path(f'results/{db.lower()}_scaling_experiment/corpus_50k/results.json')
        if path.exists():
            with open(path, 'r') as f:
                data = json.load(f)

                # Find top_k=3 query results
                for qr in data['query_results']:
                    if qr['top_k'] == 3:
                        metrics['latency'].append((db, qr['p50_latency_ms']))
                        metrics['qps'].append((db, qr['queries_per_second']))
                        metrics['memory'].append((db, qr['resource_metrics']['memory']['avg_mb']))
                        break

                metrics['ingestion'].append((db, data['ingestion']['total_time_sec']))

    # Plot 1: Query Latency
    if metrics['latency']:
        dbs, values = zip(*metrics['latency'])
        colors = [DB_COLORS.get(db) for db in dbs]
        bars = ax1.bar(dbs, values, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)
        ax1.set_ylabel('P50 Latency (ms)', fontsize=11, fontweight='bold')
        ax1.set_title('Query Latency at 345K Chunks', fontsize=12, fontweight='bold')
        ax1.grid(True, axis='y', alpha=0.3)
        # Add value labels on bars
        for bar in bars:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}ms', ha='center', va='bottom', fontsize=9)

    # Plot 2: Queries Per Second
    if metrics['qps']:
        dbs, values = zip(*metrics['qps'])
        colors = [DB_COLORS.get(db) for db in dbs]
        bars = ax2.bar(dbs, values, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)
        ax2.set_ylabel('Queries Per Second', fontsize=11, fontweight='bold')
        ax2.set_title('Query Throughput at 345K Chunks', fontsize=12, fontweight='bold')
        ax2.grid(True, axis='y', alpha=0.3)
        for bar in bars:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}', ha='center', va='bottom', fontsize=9)

    # Plot 3: Ingestion Time
    if metrics['ingestion']:
        dbs, values = zip(*metrics['ingestion'])
        values_min = [v/60 for v in values]  # Convert to minutes
        colors = [DB_COLORS.get(db) for db in dbs]
        bars = ax3.bar(dbs, values_min, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)
        ax3.set_ylabel('Ingestion Time (minutes)', fontsize=11, fontweight='bold')
        ax3.set_title('Ingestion Time for 345K Chunks', fontsize=12, fontweight='bold')
        ax3.grid(True, axis='y', alpha=0.3)
        for bar in bars:
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}m', ha='center', va='bottom', fontsize=9)

    # Plot 4: Memory Usage
    if metrics['memory']:
        dbs, values = zip(*metrics['memory'])
        values_gb = [v/1024 for v in values]  # Convert to GB
        colors = [DB_COLORS.get(db) for db in dbs]
        bars = ax4.bar(dbs, values_gb, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)
        ax4.set_ylabel('Memory Usage (GB)', fontsize=11, fontweight='bold')
        ax4.set_title('Average Memory During Queries', fontsize=12, fontweight='bold')
        ax4.grid(True, axis='y', alpha=0.3)
        for bar in bars:
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.2f}GB', ha='center', va='bottom', fontsize=9)

    plt.tight_layout()
    output_path = 'results/cross_database_comparison/50k_detailed_comparison.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {output_path}")
    plt.close()

def plot_latency_heatmap():
    """Create latency heatmap across databases and corpus sizes."""
    databases = ['Chroma', 'Qdrant', 'Weaviate', 'Milvus', 'OpenSearch']
    corpus_names = ['baseline', '1k', '10k', '50k']

    # Create latency matrix
    latency_matrix = []
    for db in databases:
        row = []
        results = load_database_results(db)
        for corpus_name in corpus_names:
            if corpus_name in results:
                for qr in results[corpus_name]['query_results']:
                    if qr['top_k'] == 3:
                        row.append(qr['p50_latency_ms'])
                        break
            else:
                row.append(np.nan)
        latency_matrix.append(row)

    latency_matrix = np.array(latency_matrix)

    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(latency_matrix, cmap='YlOrRd', aspect='auto')

    # Set ticks and labels
    ax.set_xticks(np.arange(len(corpus_names)))
    ax.set_yticks(np.arange(len(databases)))
    ax.set_xticklabels(corpus_names)
    ax.set_yticklabels(databases)

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('P50 Latency (ms)', rotation=270, labelpad=20, fontweight='bold')

    # Add text annotations
    for i in range(len(databases)):
        for j in range(len(corpus_names)):
            if not np.isnan(latency_matrix[i, j]):
                text = ax.text(j, i, f'{latency_matrix[i, j]:.1f}',
                             ha="center", va="center", color="black", fontsize=9, fontweight='bold')

    ax.set_title('Query Latency Heatmap (P50, Top-K=3)', fontsize=14, fontweight='bold', pad=20)
    ax.set_xlabel('Corpus Size', fontsize=12, fontweight='bold')
    ax.set_ylabel('Database', fontsize=12, fontweight='bold')

    plt.tight_layout()
    output_path = 'results/cross_database_comparison/latency_heatmap.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {output_path}")
    plt.close()

def main():
    print("=" * 70)
    print("CREATING CROSS-DATABASE PERFORMANCE VISUALIZATIONS")
    print("=" * 70)
    print()

    print("Generating visualizations...")

    plot_query_latency_scaling()
    plot_ingestion_comparison()
    plot_50k_detailed_comparison()
    plot_latency_heatmap()

    print()
    print("=" * 70)
    print("✓ All visualizations created successfully!")
    print("=" * 70)
    print()
    print("Output directory: results/cross_database_comparison/")
    print("  - query_latency_scaling.png")
    print("  - ingestion_comparison.png")
    print("  - 50k_detailed_comparison.png")
    print("  - latency_heatmap.png")
    print()

if __name__ == '__main__':
    main()
