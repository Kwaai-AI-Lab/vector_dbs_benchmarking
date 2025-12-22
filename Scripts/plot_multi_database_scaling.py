#!/usr/bin/env python3
"""
Multi-Database Scaling Comparison Plotter

Creates comprehensive comparison plots showing all databases on the same charts:
- Query latency scaling across corpus sizes
- Throughput (QPS) scaling
- Ingestion time and throughput
- Log-log plots for complexity analysis
"""

import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from collections import defaultdict

# Set style for publication-quality plots
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
plt.rcParams['figure.figsize'] = (14, 10)
plt.rcParams['font.size'] = 11
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['legend.fontsize'] = 10
plt.rcParams['axes.grid'] = True

# Color palette for databases
DB_COLORS = {
    'faiss': '#FF6B6B',      # Red
    'chroma': '#4ECDC4',     # Teal
    'qdrant': '#45B7D1',     # Blue
    'weaviate': '#96CEB4',   # Green
    'milvus': '#FFEAA7',     # Yellow
    'opensearch': '#DFE6E9', # Gray
    'pgvector': '#A29BFE'    # Purple
}

DB_LABELS = {
    'faiss': 'FAISS',
    'chroma': 'Chroma',
    'qdrant': 'Qdrant',
    'weaviate': 'Weaviate',
    'milvus': 'Milvus',
    'opensearch': 'OpenSearch',
    'pgvector': 'PGVector'
}

def load_database_results(db_name, results_base_dir):
    """Load all scaling results for a database."""
    results_dir = Path(results_base_dir) / f'{db_name}_scaling_experiment'

    if not results_dir.exists():
        print(f"⚠️  Directory not found: {results_dir}")
        return None

    # Load from corpus_* directories
    results = []
    for corpus_dir in sorted(results_dir.glob('corpus_*')):
        results_file = corpus_dir / 'results.json'
        if results_file.exists():
            with open(results_file, 'r') as f:
                data = json.load(f)
                results.append(data)

    if results:
        print(f"✓ Loaded {len(results)} results for {DB_LABELS.get(db_name, db_name)}")
        return results

    # Try loading from scaling_statistics.json (FAISS format)
    stats_file = results_dir / 'scaling_statistics.json'
    if stats_file.exists():
        with open(stats_file, 'r') as f:
            data = json.load(f)
            print(f"✓ Loaded scaling statistics for {DB_LABELS.get(db_name, db_name)}")
            return convert_faiss_format(data)

    print(f"❌ No results found for {DB_LABELS.get(db_name, db_name)}")
    return None

def convert_faiss_format(stats_data):
    """Convert FAISS scaling_statistics.json format to standard results format."""
    results = []

    for i, chunks in enumerate(stats_data['chunk_sizes']):
        # Get ingestion stats
        ingestion_stat = stats_data['ingestion_stats'][i]

        # Create a result entry for each top-k value
        # Use top-k=3 as representative
        if '3' in stats_data['query_stats_by_topk']:
            query_stat = stats_data['query_stats_by_topk']['3'][i]

            result = {
                'ingestion': {
                    'num_chunks': chunks,
                    'total_time_sec': ingestion_stat['time']['mean']
                },
                'query_results': {
                    '3': {
                        'avg_latency_ms': query_stat['avg_latency']['mean'],
                        'p50_latency_ms': query_stat['avg_latency']['mean'],  # Use avg as proxy
                        'p95_latency_ms': query_stat['p95_latency']['mean'],
                        'queries_per_second': query_stat['qps']['mean']
                    }
                }
            }
            results.append(result)

    return results

def extract_metrics(results):
    """Extract key metrics from results list."""
    if not results:
        return None

    chunks = []
    latencies = []
    throughputs = []
    ingestion_times = []

    for result in results:
        chunk_count = result['ingestion']['num_chunks']
        chunks.append(chunk_count)

        # Ingestion metrics
        ingestion_times.append(result['ingestion']['total_time_sec'])

        # Query metrics (use top-k=3 if available)
        query_data = result.get('query_results', [])

        # Handle both list and dict formats
        if isinstance(query_data, list):
            # Find top-k=3 in list
            q = None
            for item in query_data:
                if item.get('top_k') == 3:
                    q = item
                    break
            if not q and query_data:
                q = query_data[0]  # Use first available
            q = q or {}
        elif isinstance(query_data, dict):
            # Dict format with keys like '3' or 'top_k_3'
            if '3' in query_data:
                q = query_data['3']
            elif 'top_k_3' in query_data:
                q = query_data['top_k_3']
            else:
                q = list(query_data.values())[0] if query_data else {}
        else:
            q = {}

        latencies.append(q.get('p50_latency_ms', q.get('avg_latency_ms', None)))
        throughputs.append(q.get('queries_per_second', None))

    return {
        'chunks': chunks,
        'latencies': latencies,
        'throughputs': throughputs,
        'ingestion_times': ingestion_times
    }

def plot_query_latency_comparison(all_data, output_dir):
    """Plot query latency comparison across all databases."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # Linear scale plot
    for db_name, metrics in all_data.items():
        if metrics and metrics['latencies'] and any(l is not None for l in metrics['latencies']):
            # Filter out None values
            valid_indices = [i for i, l in enumerate(metrics['latencies']) if l is not None]
            chunks = [metrics['chunks'][i] for i in valid_indices]
            latencies = [metrics['latencies'][i] for i in valid_indices]

            ax1.plot(chunks, latencies,
                    marker='o', linewidth=2, markersize=8,
                    color=DB_COLORS.get(db_name, '#000000'),
                    label=DB_LABELS.get(db_name, db_name))

    ax1.set_xlabel('Corpus Size (chunks)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Query Latency P50 (ms)', fontsize=12, fontweight='bold')
    ax1.set_title('Query Latency Scaling - Linear Scale', fontsize=14, fontweight='bold')
    ax1.legend(loc='best', framealpha=0.9)
    ax1.grid(True, alpha=0.3)
    ax1.set_xscale('log')

    # Log-log scale plot for complexity analysis
    for db_name, metrics in all_data.items():
        if metrics and metrics['latencies'] and any(l is not None for l in metrics['latencies']):
            valid_indices = [i for i, l in enumerate(metrics['latencies']) if l is not None and l > 0]
            chunks = [metrics['chunks'][i] for i in valid_indices]
            latencies = [metrics['latencies'][i] for i in valid_indices]

            if len(chunks) > 1:
                ax2.loglog(chunks, latencies,
                          marker='o', linewidth=2, markersize=8,
                          color=DB_COLORS.get(db_name, '#000000'),
                          label=DB_LABELS.get(db_name, db_name))

                # Fit power law and display exponent
                if len(chunks) >= 3:
                    log_chunks = np.log10(chunks)
                    log_latencies = np.log10(latencies)
                    coeffs = np.polyfit(log_chunks, log_latencies, 1)
                    alpha = coeffs[0]

                    # Add text annotation
                    mid_idx = len(chunks) // 2
                    ax2.text(chunks[mid_idx], latencies[mid_idx] * 1.2,
                            f'α≈{alpha:.2f}',
                            fontsize=9, color=DB_COLORS.get(db_name, '#000000'),
                            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.7))

    ax2.set_xlabel('Corpus Size (chunks) [log scale]', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Query Latency P50 (ms) [log scale]', fontsize=12, fontweight='bold')
    ax2.set_title('Query Latency Scaling - Log-Log Scale (O(N^α))', fontsize=14, fontweight='bold')
    ax2.legend(loc='best', framealpha=0.9)
    ax2.grid(True, alpha=0.3, which='both')

    plt.tight_layout()
    output_path = Path(output_dir) / 'multi_db_query_latency_comparison.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {output_path}")
    plt.close()

def plot_throughput_comparison(all_data, output_dir):
    """Plot throughput (QPS) comparison across all databases."""
    fig, ax = plt.subplots(1, 1, figsize=(14, 8))

    for db_name, metrics in all_data.items():
        if metrics and metrics['throughputs'] and any(t is not None for t in metrics['throughputs']):
            valid_indices = [i for i, t in enumerate(metrics['throughputs']) if t is not None]
            chunks = [metrics['chunks'][i] for i in valid_indices]
            throughputs = [metrics['throughputs'][i] for i in valid_indices]

            ax.plot(chunks, throughputs,
                   marker='o', linewidth=2, markersize=8,
                   color=DB_COLORS.get(db_name, '#000000'),
                   label=DB_LABELS.get(db_name, db_name))

    ax.set_xlabel('Corpus Size (chunks)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Throughput (Queries Per Second)', fontsize=12, fontweight='bold')
    ax.set_title('Query Throughput Scaling Across Databases', fontsize=14, fontweight='bold')
    ax.legend(loc='best', framealpha=0.9)
    ax.grid(True, alpha=0.3)
    ax.set_xscale('log')

    plt.tight_layout()
    output_path = Path(output_dir) / 'multi_db_throughput_comparison.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {output_path}")
    plt.close()

def plot_ingestion_comparison(all_data, output_dir):
    """Plot ingestion time and throughput comparison."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # Ingestion time
    for db_name, metrics in all_data.items():
        if metrics and metrics['ingestion_times']:
            chunks = metrics['chunks']
            times = [t / 60 for t in metrics['ingestion_times']]  # Convert to minutes

            ax1.plot(chunks, times,
                    marker='o', linewidth=2, markersize=8,
                    color=DB_COLORS.get(db_name, '#000000'),
                    label=DB_LABELS.get(db_name, db_name))

    ax1.set_xlabel('Corpus Size (chunks)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Ingestion Time (minutes)', fontsize=12, fontweight='bold')
    ax1.set_title('Ingestion Time Scaling', fontsize=14, fontweight='bold')
    ax1.legend(loc='best', framealpha=0.9)
    ax1.grid(True, alpha=0.3)
    ax1.set_xscale('log')

    # Ingestion throughput (chunks/sec)
    for db_name, metrics in all_data.items():
        if metrics and metrics['ingestion_times']:
            chunks = metrics['chunks']
            throughputs = [c / t for c, t in zip(chunks, metrics['ingestion_times'])]

            ax2.plot(chunks, throughputs,
                    marker='o', linewidth=2, markersize=8,
                    color=DB_COLORS.get(db_name, '#000000'),
                    label=DB_LABELS.get(db_name, db_name))

    ax2.set_xlabel('Corpus Size (chunks)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Ingestion Throughput (chunks/sec)', fontsize=12, fontweight='bold')
    ax2.set_title('Ingestion Throughput Consistency', fontsize=14, fontweight='bold')
    ax2.legend(loc='best', framealpha=0.9)
    ax2.grid(True, alpha=0.3)
    ax2.set_xscale('log')

    plt.tight_layout()
    output_path = Path(output_dir) / 'multi_db_ingestion_comparison.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {output_path}")
    plt.close()

def plot_combined_dashboard(all_data, output_dir):
    """Create a comprehensive 4-panel dashboard."""
    fig = plt.figure(figsize=(18, 12))
    gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.3)

    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[1, 0])
    ax4 = fig.add_subplot(gs[1, 1])

    # Panel 1: Query Latency (log-x scale)
    for db_name, metrics in all_data.items():
        if metrics and metrics['latencies'] and any(l is not None for l in metrics['latencies']):
            valid_indices = [i for i, l in enumerate(metrics['latencies']) if l is not None]
            chunks = [metrics['chunks'][i] for i in valid_indices]
            latencies = [metrics['latencies'][i] for i in valid_indices]

            ax1.plot(chunks, latencies,
                    marker='o', linewidth=2, markersize=6,
                    color=DB_COLORS.get(db_name, '#000000'),
                    label=DB_LABELS.get(db_name, db_name))

    ax1.set_xlabel('Corpus Size (chunks)', fontweight='bold')
    ax1.set_ylabel('Query Latency P50 (ms)', fontweight='bold')
    ax1.set_title('A) Query Latency Scaling', fontweight='bold', fontsize=13)
    ax1.legend(loc='best', framealpha=0.9, fontsize=9)
    ax1.grid(True, alpha=0.3)
    ax1.set_xscale('log')

    # Panel 2: Throughput
    for db_name, metrics in all_data.items():
        if metrics and metrics['throughputs'] and any(t is not None for t in metrics['throughputs']):
            valid_indices = [i for i, t in enumerate(metrics['throughputs']) if t is not None]
            chunks = [metrics['chunks'][i] for i in valid_indices]
            throughputs = [metrics['throughputs'][i] for i in valid_indices]

            ax2.plot(chunks, throughputs,
                    marker='o', linewidth=2, markersize=6,
                    color=DB_COLORS.get(db_name, '#000000'),
                    label=DB_LABELS.get(db_name, db_name))

    ax2.set_xlabel('Corpus Size (chunks)', fontweight='bold')
    ax2.set_ylabel('Throughput (QPS)', fontweight='bold')
    ax2.set_title('B) Query Throughput Scaling', fontweight='bold', fontsize=13)
    ax2.legend(loc='best', framealpha=0.9, fontsize=9)
    ax2.grid(True, alpha=0.3)
    ax2.set_xscale('log')

    # Panel 3: Ingestion Time
    for db_name, metrics in all_data.items():
        if metrics and metrics['ingestion_times']:
            chunks = metrics['chunks']
            times = [t / 60 for t in metrics['ingestion_times']]

            ax3.plot(chunks, times,
                    marker='o', linewidth=2, markersize=6,
                    color=DB_COLORS.get(db_name, '#000000'),
                    label=DB_LABELS.get(db_name, db_name))

    ax3.set_xlabel('Corpus Size (chunks)', fontweight='bold')
    ax3.set_ylabel('Ingestion Time (minutes)', fontweight='bold')
    ax3.set_title('C) Ingestion Time Scaling', fontweight='bold', fontsize=13)
    ax3.legend(loc='best', framealpha=0.9, fontsize=9)
    ax3.grid(True, alpha=0.3)
    ax3.set_xscale('log')

    # Panel 4: Ingestion Throughput
    for db_name, metrics in all_data.items():
        if metrics and metrics['ingestion_times']:
            chunks = metrics['chunks']
            throughputs = [c / t for c, t in zip(chunks, metrics['ingestion_times'])]

            ax4.plot(chunks, throughputs,
                    marker='o', linewidth=2, markersize=6,
                    color=DB_COLORS.get(db_name, '#000000'),
                    label=DB_LABELS.get(db_name, db_name))

    ax4.set_xlabel('Corpus Size (chunks)', fontweight='bold')
    ax4.set_ylabel('Ingestion Throughput (chunks/sec)', fontweight='bold')
    ax4.set_title('D) Ingestion Throughput Consistency', fontweight='bold', fontsize=13)
    ax4.legend(loc='best', framealpha=0.9, fontsize=9)
    ax4.grid(True, alpha=0.3)
    ax4.set_xscale('log')

    fig.suptitle('Multi-Database Scaling Comparison Dashboard',
                 fontsize=16, fontweight='bold', y=0.995)

    output_path = Path(output_dir) / 'multi_db_scaling_dashboard.png'
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"✓ Saved: {output_path}")
    plt.close()

def main():
    """Main execution function."""
    results_base_dir = Path(__file__).parent.parent / 'results'
    output_dir = results_base_dir / 'multi_database_scaling_plots'
    output_dir.mkdir(exist_ok=True)

    print("=" * 60)
    print("Multi-Database Scaling Comparison Plotter")
    print("=" * 60)
    print()

    # Databases to compare
    databases = ['faiss', 'chroma', 'qdrant', 'weaviate', 'milvus', 'opensearch']

    # Load all data
    print("Loading database results...")
    all_data = {}
    for db_name in databases:
        results = load_database_results(db_name, results_base_dir)
        if results:
            metrics = extract_metrics(results)
            if metrics:
                all_data[db_name] = metrics

    print()
    print(f"✓ Successfully loaded data for {len(all_data)} databases")
    print()

    if not all_data:
        print("❌ No data found to plot!")
        return

    # Generate plots
    print("Generating comparison plots...")
    print()

    plot_query_latency_comparison(all_data, output_dir)
    plot_throughput_comparison(all_data, output_dir)
    plot_ingestion_comparison(all_data, output_dir)
    plot_combined_dashboard(all_data, output_dir)

    print()
    print("=" * 60)
    print(f"✓ All plots saved to: {output_dir}")
    print("=" * 60)
    print()
    print("Generated plots:")
    print("  1. multi_db_query_latency_comparison.png (linear & log-log)")
    print("  2. multi_db_throughput_comparison.png")
    print("  3. multi_db_ingestion_comparison.png")
    print("  4. multi_db_scaling_dashboard.png (4-panel overview)")

if __name__ == '__main__':
    main()
