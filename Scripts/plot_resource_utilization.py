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
    'faiss': '#E74C3C',      # Bold Red
    'chroma': '#16A085',     # Deep Teal
    'qdrant': '#3498DB',     # Royal Blue
    'weaviate': '#9B59B6',   # Purple
    'milvus': '#2ECC71',     # Emerald Green - distinct from red/pink
    'opensearch': '#7F8C8D', # Dark Gray
    'pgvector': '#8E44AD',   # Amethyst Purple - distinct from red/orange
    'pgvector_hnsw': '#8E44AD',
    'pgvector_ivfflat': '#3498DB',
}

DB_LABELS = {
    'faiss': 'FAISS',
    'chroma': 'Chroma',
    'qdrant': 'Qdrant',
    'weaviate': 'Weaviate',
    'milvus': 'Milvus',
    'opensearch': 'OpenSearch',
    'pgvector': 'PGVector',
    'pgvector_hnsw': 'PGVector',
    'pgvector_ivfflat': 'PGVector (IVFFlat)',
}

# Line styles for enhanced differentiation
DB_LINESTYLES = {
    'faiss': '-',       # Solid - scale champion
    'chroma': '--',     # Dashed - speed champion
    'qdrant': ':',      # Dotted
    'weaviate': '-.',   # Dash-dot
    'milvus': '-',      # Solid (different color from FAISS)
    'opensearch': '--', # Dashed (different color from Chroma)
    'pgvector': '-',    # Solid (distinct magenta color)
    'pgvector_hnsw': '-',
    'pgvector_ivfflat': '--'
}

def load_resource_metrics(db_name, results_base_dir):
    """Load resource metrics from N=10, N=5, or N=3 aggregated results (in that priority order)."""
    # Try N=10, N=5, N=3 format (highest first)
    for n in [10, 5, 3]:
        results_dir = Path(results_base_dir) / f'{db_name}_scaling_n{n}'
        if results_dir.exists():
            metrics = []

            # Special handling for FAISS: last 3 corpus dirs are N=3 repeats of same experiment
            corpus_dirs = sorted(results_dir.glob('corpus_*'))

            # For FAISS, identify N=3 repeats by finding directories with same chunk count
            if db_name == 'faiss':
                # Load all corpus sizes and their chunk counts
                corpus_data = []
                for corpus_dir in corpus_dirs:
                    agg_file = corpus_dir / 'aggregated_results.json'
                    if agg_file.exists():
                        with open(agg_file, 'r') as f:
                            data = json.load(f)
                            mean_result = data.get('mean_result', {})
                            chunks = mean_result.get('ingestion', {}).get('num_chunks', 0)
                            corpus_data.append((corpus_dir, chunks, data))

                # Group by chunk count
                chunk_groups = defaultdict(list)
                for corpus_dir, chunks, data in corpus_data:
                    chunk_groups[chunks].append((corpus_dir, data))

                # Find the largest chunk count with 3 repetitions (N=3)
                n3_chunk_count = None
                n3_dirs = []
                for chunks, dirs_data in sorted(chunk_groups.items(), reverse=True):
                    if len(dirs_data) >= 3:
                        n3_chunk_count = chunks
                        n3_dirs = dirs_data
                        break

                if n3_chunk_count and n3_dirs:
                    # Extract resource metrics from the N=3 repeats
                    n3_metrics = []
                    for corpus_dir, data in n3_dirs:
                        mean_result = data.get('mean_result', {})
                        query_results = mean_result.get('query_results', [])
                        resource_data = None
                        if isinstance(query_results, list):
                            for qr in query_results:
                                if qr.get('top_k') == 3:
                                    resource_data = qr.get('resource_metrics', {})
                                    break

                        if resource_data:
                            n3_metrics.append({
                                'cpu_avg': resource_data.get('cpu', {}).get('avg', 0),
                                'memory_avg': resource_data.get('memory', {}).get('avg_mb', 0),
                            })

                    cpu_values = [m['cpu_avg'] for m in n3_metrics if m['cpu_avg'] > 0]
                    mem_values = [m['memory_avg'] for m in n3_metrics]

                    if cpu_values:
                        # Process all other unique corpus sizes
                        n3_dir_names = [str(d[0]) for d in n3_dirs]
                        for corpus_dir, chunks, data in corpus_data:
                            if str(corpus_dir) not in n3_dir_names:
                                mean_result = data.get('mean_result', {})
                                query_results = mean_result.get('query_results', [])
                                resource_data = None
                                if isinstance(query_results, list):
                                    for qr in query_results:
                                        if qr.get('top_k') == 3:
                                            resource_data = qr.get('resource_metrics', {})
                                            break

                                if resource_data and chunks > 0:
                                    metrics.append({
                                        'chunks': chunks,
                                        'cpu_avg': resource_data.get('cpu', {}).get('avg', 0),
                                        'cpu_std': 0,
                                        'memory_avg': resource_data.get('memory', {}).get('avg_mb', 0),
                                        'memory_std': 0,
                                    })

                        # Add the N=3 aggregated point
                        metrics.append({
                            'chunks': n3_chunk_count,
                            'cpu_avg': np.mean(cpu_values),
                            'cpu_std': np.std(cpu_values, ddof=1),
                            'memory_avg': np.mean(mem_values),
                            'memory_std': np.std(mem_values, ddof=1),
                        })

                        metrics = sorted(metrics, key=lambda x: x['chunks'])
                        print(f"✓ Loaded resource metrics for {DB_LABELS.get(db_name, db_name)}: {len(metrics)} corpus sizes (last point is N={n} at {n3_chunk_count} chunks)")
                        return metrics

            # Standard processing for non-FAISS or if special case doesn't apply
            for corpus_dir in corpus_dirs:
                agg_file = corpus_dir / 'aggregated_results.json'
                if agg_file.exists():
                    with open(agg_file, 'r') as f:
                        data = json.load(f)
                        if 'statistics' in data:
                            stats = data['statistics']
                            mean_result = data.get('mean_result', {})
                            chunks = mean_result.get('ingestion', {}).get('num_chunks', 0)
                            query_results = mean_result.get('query_results', [])

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
                                    'cpu_std': 0,
                                    'memory_avg': resource_data.get('memory', {}).get('avg_mb', 0),
                                    'memory_std': 0,
                                })

            if metrics:
                metrics = sorted(metrics, key=lambda x: x['chunks'])
                print(f"✓ Loaded resource metrics for {DB_LABELS.get(db_name, db_name)}: {len(metrics)} corpus sizes (N={n})")
                return metrics

    print(f"⚠️  No resource metrics found for {DB_LABELS.get(db_name, db_name)}")
    return None

def plot_resource_utilization_dashboard(all_metrics, output_dir):
    """Create a 2-panel resource utilization dashboard (CPU and Memory)."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # Calculate error bars using CV from FAISS measurements (25.11%)
    # Based on 3 runs of FAISS at 2.2M corpus: mean=11.54%, std=2.90%, CV=25.11%
    CV_PERCENT = 25.11

    # Panel 1: CPU Usage (Average) with error bars and polynomial trend lines
    for db_name, metrics in all_metrics.items():
        if metrics:
            # Filter out data points with 0 CPU utilization
            filtered_data = [(m['chunks'], m['cpu_avg'], m.get('cpu_std', 0), m['memory_avg'], m.get('memory_std', 0))
                           for m in metrics if m['cpu_avg'] > 0]

            if not filtered_data:
                continue

            chunks, cpu_avg, cpu_std, _, _ = zip(*filtered_data)
            chunks = list(chunks)
            cpu_avg = list(cpu_avg)
            cpu_std = list(cpu_std)

            # Use actual std if available (from N=3), otherwise use CV-based estimate
            cpu_err = [std if std > 0 else c * (CV_PERCENT / 100.0)
                      for c, std in zip(cpu_avg, cpu_std)]

            color = DB_COLORS.get(db_name, '#000000')

            # Plot data points with error bars (no connecting lines)
            ax1.errorbar(chunks, cpu_avg, yerr=cpu_err,
                    fmt='o', markersize=8,
                    color=color,
                    alpha=0.8, capsize=4, capthick=1.5,
                    linestyle='none', label='_nolegend_')

            # Fit and plot polynomial trend line (degree 2 for smooth curve)
            if len(chunks) >= 3:
                # Use log scale for x to handle wide range
                log_chunks = np.log10(chunks)
                degree = min(2, len(chunks) - 1)  # Use degree 2 or less if not enough points
                coeffs = np.polyfit(log_chunks, cpu_avg, degree)
                poly = np.poly1d(coeffs)

                # Generate smooth curve
                log_chunks_smooth = np.linspace(min(log_chunks), max(log_chunks), 100)
                chunks_smooth = 10 ** log_chunks_smooth
                cpu_smooth = poly(log_chunks_smooth)

                # Plot trend line
                ax1.plot(chunks_smooth, cpu_smooth,
                        linewidth=2.5, color=color,
                        linestyle=DB_LINESTYLES.get(db_name, '-'),
                        label=DB_LABELS.get(db_name, db_name),
                        alpha=0.9)

    ax1.set_xlabel('Corpus Size (chunks)', fontweight='bold', fontsize=11)
    ax1.set_ylabel('CPU Usage (%)', fontweight='bold', fontsize=11)
    ax1.set_title('(a) CPU Utilization During Query Operations', fontweight='bold', fontsize=12)
    ax1.legend(loc='best', framealpha=0.95, fontsize=10)
    ax1.grid(True, alpha=0.3, linestyle=':')
    ax1.set_xscale('log')
    ax1.set_ylim(bottom=0)

    # Panel 2: Memory Usage (Average) with error bars and polynomial trend lines
    for db_name, metrics in all_metrics.items():
        if metrics:
            # Filter out data points with 0 CPU utilization (same filter as CPU panel)
            filtered_data = [(m['chunks'], m['memory_avg'], m.get('memory_std', 0))
                           for m in metrics if m['cpu_avg'] > 0]

            if not filtered_data:
                continue

            chunks, memory_avg, memory_std = zip(*filtered_data)
            chunks = list(chunks)
            memory_avg = list(memory_avg)
            memory_std = list(memory_std)

            # Use actual std if available (from N=3), otherwise use CV-based estimate
            memory_err = [std if std > 0 else m * (CV_PERCENT / 100.0)
                         for m, std in zip(memory_avg, memory_std)]

            color = DB_COLORS.get(db_name, '#000000')

            # Plot data points with error bars (no connecting lines)
            ax2.errorbar(chunks, memory_avg, yerr=memory_err,
                    fmt='s', markersize=8,
                    color=color,
                    alpha=0.8, capsize=4, capthick=1.5,
                    linestyle='none', label='_nolegend_')

            # Fit and plot polynomial trend line (degree 2 for smooth curve)
            if len(chunks) >= 3:
                # Use log scale for x to handle wide range
                log_chunks = np.log10(chunks)
                degree = min(2, len(chunks) - 1)  # Use degree 2 or less if not enough points
                coeffs = np.polyfit(log_chunks, memory_avg, degree)
                poly = np.poly1d(coeffs)

                # Generate smooth curve
                log_chunks_smooth = np.linspace(min(log_chunks), max(log_chunks), 100)
                chunks_smooth = 10 ** log_chunks_smooth
                memory_smooth = poly(log_chunks_smooth)

                # Plot trend line
                ax2.plot(chunks_smooth, memory_smooth,
                        linewidth=2.5, color=color,
                        linestyle=DB_LINESTYLES.get(db_name, '-'),
                        label=DB_LABELS.get(db_name, db_name),
                        alpha=0.9)

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
    databases = ['faiss', 'chroma', 'qdrant', 'weaviate', 'milvus', 'opensearch', 'pgvector_hnsw']
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
