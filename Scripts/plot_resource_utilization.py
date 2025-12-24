#!/usr/bin/env python3
"""
Resource Utilization Comparison Plotter

Creates comprehensive comparison plots showing resource usage (CPU, memory, disk, network)
across all databases during query operations.
"""

import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from collections import defaultdict

# Set style for publication-quality plots
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['figure.figsize'] = (16, 12)
plt.rcParams['font.size'] = 11
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['legend.fontsize'] = 10
plt.rcParams['axes.grid'] = True

# Color palette for databases
DB_COLORS = {
    'faiss': '#E74C3C',
    'chroma': '#16A085',
    'qdrant': '#3498DB',
    'weaviate': '#27AE60',
    'milvus': '#E67E22',
    'opensearch': '#7F8C8D',
}

DB_LABELS = {
    'faiss': 'FAISS',
    'chroma': 'Chroma',
    'qdrant': 'Qdrant',
    'weaviate': 'Weaviate',
    'milvus': 'Milvus',
    'opensearch': 'OpenSearch',
}

def load_resource_metrics(db_name, results_base_dir):
    """Load resource metrics from N=3 aggregated results."""
    # Try N=3 format first
    for n in [3, 5, 10]:
        results_dir = Path(results_base_dir) / f'{db_name}_scaling_n3'
        if results_dir.exists():
            metrics = []
            for corpus_dir in sorted(results_dir.glob('corpus_*')):
                agg_file = corpus_dir / 'aggregated_results.json'
                if agg_file.exists():
                    with open(agg_file, 'r') as f:
                        data = json.load(f)

                        # Extract resource metrics from statistics
                        if 'statistics' in data:
                            stats = data['statistics']
                            mean_result = data.get('mean_result', {})

                            # Get chunk count
                            chunks = mean_result.get('ingestion', {}).get('num_chunks', 0)

                            # Extract resource metrics (use top_k=3 query results)
                            query_results = mean_result.get('query_results', [])

                            # Find top_k=3 results
                            resource_data = None
                            if isinstance(query_results, list):
                                for qr in query_results:
                                    if qr.get('top_k') == 3:
                                        resource_data = qr.get('resource_metrics', {})
                                        break
                            elif isinstance(query_results, dict):
                                resource_data = query_results.get('3', {}).get('resource_metrics', {})

                            if resource_data and chunks > 0:
                                metrics.append({
                                    'chunks': chunks,
                                    'cpu_avg': resource_data.get('cpu', {}).get('avg', 0),
                                    'cpu_max': resource_data.get('cpu', {}).get('max', 0),
                                    'memory_avg': resource_data.get('memory', {}).get('avg_mb', 0),
                                    'memory_max': resource_data.get('memory', {}).get('max_mb', 0),
                                    'disk_read': resource_data.get('disk', {}).get('read_total_mb', 0),
                                    'disk_write': resource_data.get('disk', {}).get('write_total_mb', 0),
                                    'network_sent': resource_data.get('network', {}).get('sent_total_mb', 0),
                                    'network_recv': resource_data.get('network', {}).get('recv_total_mb', 0),
                                })

            if metrics:
                # Sort by chunk count
                metrics = sorted(metrics, key=lambda x: x['chunks'])
                print(f"✓ Loaded resource metrics for {DB_LABELS.get(db_name, db_name)}: {len(metrics)} corpus sizes")
                return metrics

    print(f"⚠️  No resource metrics found for {DB_LABELS.get(db_name, db_name)}")
    return None

def plot_resource_utilization_dashboard(all_metrics, output_dir):
    """Create a 2-panel resource utilization dashboard (CPU and Memory)."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # Panel 1: CPU Usage (Average)
    for db_name, metrics in all_metrics.items():
        if metrics:
            chunks = [m['chunks'] for m in metrics]
            cpu_avg = [m['cpu_avg'] for m in metrics]

            # Skip if all zeros (e.g., FAISS)
            if any(c > 0 for c in cpu_avg):
                ax1.plot(chunks, cpu_avg,
                        marker='o', linewidth=2.5, markersize=8,
                        color=DB_COLORS.get(db_name, '#000000'),
                        label=DB_LABELS.get(db_name, db_name),
                        alpha=0.8)

    ax1.set_xlabel('Corpus Size (chunks)', fontweight='bold', fontsize=11)
    ax1.set_ylabel('CPU Usage (%)', fontweight='bold', fontsize=11)
    ax1.set_title('(a) CPU Utilization During Query Operations', fontweight='bold', fontsize=12)
    ax1.legend(loc='best', framealpha=0.95, fontsize=10)
    ax1.grid(True, alpha=0.3, linestyle=':')
    ax1.set_xscale('log')
    ax1.set_ylim(bottom=0)

    # Panel 2: Memory Usage (Average)
    for db_name, metrics in all_metrics.items():
        if metrics:
            chunks = [m['chunks'] for m in metrics]
            memory_avg = [m['memory_avg'] for m in metrics]

            ax2.plot(chunks, memory_avg,
                    marker='s', linewidth=2.5, markersize=8,
                    color=DB_COLORS.get(db_name, '#000000'),
                    label=DB_LABELS.get(db_name, db_name),
                    alpha=0.8)

    ax2.set_xlabel('Corpus Size (chunks)', fontweight='bold', fontsize=11)
    ax2.set_ylabel('Memory Usage (MB)', fontweight='bold', fontsize=11)
    ax2.set_title('(b) Memory Consumption During Query Operations', fontweight='bold', fontsize=12)
    ax2.legend(loc='best', framealpha=0.95, fontsize=10)
    ax2.grid(True, alpha=0.3, linestyle=':')
    ax2.set_xscale('log')
    ax2.set_ylim(bottom=0)

    plt.tight_layout()

    output_path = Path(output_dir) / 'resource_utilization_comparison.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {output_path}")
    plt.close()

def main():
    results_base_dir = 'results'
    output_dir = Path('results/multi_database_scaling_plots')
    output_dir.mkdir(parents=True, exist_ok=True)

    print("="*60)
    print("Multi-Database Resource Utilization Plotter")
    print("="*60)
    print()

    # Load resource metrics for all databases
    databases = ['faiss', 'chroma', 'qdrant', 'weaviate', 'milvus', 'opensearch']
    all_metrics = {}

    print("Loading resource metrics...")
    for db in databases:
        metrics = load_resource_metrics(db, results_base_dir)
        if metrics:
            all_metrics[db] = metrics

    print()
    print(f"✓ Successfully loaded resource data for {len(all_metrics)} databases")
    print()

    # Generate plots
    print("Generating resource utilization plots...")
    plot_resource_utilization_dashboard(all_metrics, output_dir)

    print()
    print("="*60)
    print(f"✓ Resource utilization plots saved to: {output_dir}")
    print("="*60)

if __name__ == '__main__':
    main()
