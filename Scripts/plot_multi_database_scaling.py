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

# Color palette for databases - optimized for differentiation and colorblind accessibility
DB_COLORS = {
    'faiss': '#E74C3C',      # Bold Red - stands out for importance
    'chroma': '#16A085',     # Deep Teal - distinct from blue
    'qdrant': '#3498DB',     # Royal Blue - clear and bright
    'weaviate': '#9B59B6',   # Purple - distinct from teal/green
    'milvus': '#2ECC71',     # Emerald Green - highly distinct from red/pink
    'opensearch': '#7F8C8D', # Dark Gray - improved contrast
    'pgvector': '#8E44AD',    # Amethyst Purple - distinct from red/orange
    'pgvector_hnsw': '#8E44AD',  # Amethyst Purple - HNSW index
    'pgvector_ivfflat': '#3498DB'  # Blue - IVFFlat index
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
    'pgvector_ivfflat': 'PGVector (IVFFlat)'
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

def load_database_results(db_name, results_base_dir):
    """Load all scaling results for a database (single or N-run format)."""
    # First try highest N format (prefer N=10 > N=5 > N=3)
    for n in [10, 5, 3]:  # Check for N=10, N=5, N=3 (highest first)
        results_dir = Path(results_base_dir) / f'{db_name}_scaling_n{n}'
        if results_dir.exists():
            results = []
            for corpus_dir in sorted(results_dir.glob('corpus_*')):
                agg_file = corpus_dir / 'aggregated_results.json'
                if agg_file.exists():
                    with open(agg_file, 'r') as f:
                        data = json.load(f)
                        results.append(data)

            # Only use N=3 data if we have at least 4 corpus sizes (indicates completion)
            # Otherwise fall back to single-run data to show full scaling curve
            if results and len(results) >= 4:
                print(f"✓ Loaded {len(results)} N={n} aggregated results for {DB_LABELS.get(db_name, db_name)}")
                return results
            elif results:
                print(f"⚠️  Found incomplete N={n} data for {DB_LABELS.get(db_name, db_name)} ({len(results)} corpus sizes), falling back to single-run data")

    # Fall back to single-run format (e.g., chroma_scaling_experiment)
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
    """Extract key metrics from results list (handles both single-run and N-run aggregated data)."""
    if not results:
        return None

    chunks = []
    latencies = []
    throughputs = []
    ingestion_times = []

    # Error bars (standard deviations) - only populated for N-run data
    latencies_std = []
    throughputs_std = []
    ingestion_times_std = []

    for result in results:
        # Check if this is aggregated N-run data
        is_aggregated = 'statistics' in result and 'mean_result' in result

        if is_aggregated:
            # Extract from aggregated statistics
            stats = result['statistics']
            mean_result = result['mean_result']

            chunk_count = mean_result['ingestion']['num_chunks']
            chunks.append(chunk_count)

            # Ingestion metrics with std
            if 'ingestion_time' in stats:
                ingestion_times.append(stats['ingestion_time']['mean'])
                ingestion_times_std.append(stats['ingestion_time']['std'])
            else:
                ingestion_times.append(mean_result['ingestion']['total_time_sec'])
                ingestion_times_std.append(0)

            # Query metrics with std
            if 'p50_latency_ms' in stats:
                latencies.append(stats['p50_latency_ms']['mean'])
                latencies_std.append(stats['p50_latency_ms']['std'])
            else:
                latencies.append(None)
                latencies_std.append(0)

            if 'queries_per_second' in stats:
                throughputs.append(stats['queries_per_second']['mean'])
                throughputs_std.append(stats['queries_per_second']['std'])
            else:
                throughputs.append(None)
                throughputs_std.append(0)
        else:
            # Extract from single-run data
            chunk_count = result['ingestion']['num_chunks']
            chunks.append(chunk_count)

            # Ingestion metrics
            ingestion_times.append(result['ingestion']['total_time_sec'])
            ingestion_times_std.append(0)  # No std for single run

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
            latencies_std.append(0)

            throughputs.append(q.get('queries_per_second', None))
            throughputs_std.append(0)

    # Sort all data by chunk size (ascending order) to ensure proper plotting
    sorted_data = sorted(
        zip(chunks, latencies, throughputs, ingestion_times, latencies_std, throughputs_std, ingestion_times_std),
        key=lambda x: x[0]
    )

    if sorted_data:
        chunks_sorted, latencies_sorted, throughputs_sorted, ingestion_times_sorted, \
            latencies_std_sorted, throughputs_std_sorted, ingestion_times_std_sorted = zip(*sorted_data)
    else:
        chunks_sorted = latencies_sorted = throughputs_sorted = ingestion_times_sorted = []
        latencies_std_sorted = throughputs_std_sorted = ingestion_times_std_sorted = []

    return {
        'chunks': list(chunks_sorted),
        'latencies': list(latencies_sorted),
        'throughputs': list(throughputs_sorted),
        'ingestion_times': list(ingestion_times_sorted),
        'latencies_std': list(latencies_std_sorted),
        'throughputs_std': list(throughputs_std_sorted),
        'ingestion_times_std': list(ingestion_times_std_sorted),
        'has_error_bars': any(std > 0 for std in latencies_std_sorted + throughputs_std_sorted + ingestion_times_std_sorted)
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
                    linestyle=DB_LINESTYLES.get(db_name, '-'),
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
                          linestyle=DB_LINESTYLES.get(db_name, '-'),
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
                   linestyle=DB_LINESTYLES.get(db_name, '-'),
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
                    linestyle=DB_LINESTYLES.get(db_name, '-'),
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
                    linestyle=DB_LINESTYLES.get(db_name, '-'),
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
    """Create a comprehensive 4-panel dashboard for research paper."""
    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(2, 2, hspace=0.35, wspace=0.3)

    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[1, 0])
    ax4 = fig.add_subplot(gs[1, 1])

    # Panel 1: Query Latency (log-log with power-law exponents and trend lines)
    for db_name, metrics in all_data.items():
        if metrics and metrics['latencies'] and any(l is not None for l in metrics['latencies']):
            valid_indices = [i for i, l in enumerate(metrics['latencies']) if l is not None]
            chunks = [metrics['chunks'][i] for i in valid_indices]
            latencies = [metrics['latencies'][i] for i in valid_indices]
            latencies_std = [metrics['latencies_std'][i] for i in valid_indices] if metrics.get('has_error_bars') else None

            color = DB_COLORS.get(db_name, '#000000')

            # Plot data points with error bars (no connecting lines)
            if latencies_std and any(s > 0 for s in latencies_std):
                ax1.errorbar(chunks, latencies, yerr=latencies_std,
                           fmt='o', markersize=8,
                           color=color,
                           alpha=0.8, capsize=4, capthick=1.5,
                           linestyle='none', label='_nolegend_')
            else:
                ax1.plot(chunks, latencies,
                        marker='o', markersize=8,
                        color=color,
                        linestyle='none',
                        alpha=0.8, label='_nolegend_')

            # Fit and plot polynomial trend line
            if len(chunks) >= 3:
                log_chunks = np.log10(chunks)
                log_latencies = np.log10(latencies)

                # Linear fit for power-law exponent
                coeffs_linear = np.polyfit(log_chunks, log_latencies, 1)
                alpha_exp = coeffs_linear[0]

                # Polynomial fit for smooth curve (degree 2 in log space)
                degree = min(2, len(chunks) - 1)
                coeffs = np.polyfit(log_chunks, log_latencies, degree)
                poly = np.poly1d(coeffs)

                # Generate smooth curve
                log_chunks_smooth = np.linspace(min(log_chunks), max(log_chunks), 100)
                chunks_smooth = 10 ** log_chunks_smooth
                latencies_smooth = 10 ** poly(log_chunks_smooth)

                # Plot trend line
                ax1.plot(chunks_smooth, latencies_smooth,
                        linewidth=2.5, color=color,
                        linestyle=DB_LINESTYLES.get(db_name, '-'),
                        label=DB_LABELS.get(db_name, db_name),
                        alpha=0.9)

                # Add power-law exponent annotation
                ax1.text(chunks[-1] * 1.15, latencies[-1],
                        f'α={alpha_exp:.2f}',
                        fontsize=9, color=color,
                        verticalalignment='center',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8, edgecolor='none'))

    ax1.set_xlabel('Corpus Size (chunks)', fontweight='bold', fontsize=11)
    ax1.set_ylabel('Query Latency P50 (ms)', fontweight='bold', fontsize=11)
    ax1.set_title('(a) Query Latency Scaling with Complexity Exponents', fontweight='bold', fontsize=12)
    ax1.legend(loc='upper left', framealpha=0.95, fontsize=9)
    ax1.grid(True, alpha=0.3, which='both', linestyle=':')
    ax1.set_xscale('log')
    ax1.set_yscale('log')

    # Add explicit axis ticks for better readability on log-log scale
    from matplotlib.ticker import LogLocator, NullFormatter

    # Y-axis (latency) ticks - show major ticks at powers of 10
    ax1.yaxis.set_major_locator(LogLocator(base=10, numticks=15))
    ax1.yaxis.set_minor_locator(LogLocator(base=10, subs=np.arange(2, 10) * 0.1, numticks=100))
    ax1.yaxis.set_minor_formatter(NullFormatter())

    # X-axis (corpus size) ticks - show key corpus sizes
    ax1.xaxis.set_major_locator(LogLocator(base=10, numticks=12))

    # Set y-axis upper limit to 10^2 (100ms) as requested
    # Keep lower limit auto-scaled to show all data points
    ax1.set_ylim(top=100)
    ax1.autoscale(enable=True, axis='x', tight=False)

    # Panel 2: Throughput (QPS) with polynomial trend lines
    for db_name, metrics in all_data.items():
        if metrics and metrics['throughputs'] and any(t is not None for t in metrics['throughputs']):
            valid_indices = [i for i, t in enumerate(metrics['throughputs']) if t is not None]
            chunks = [metrics['chunks'][i] for i in valid_indices]
            throughputs = [metrics['throughputs'][i] for i in valid_indices]
            throughputs_std = [metrics['throughputs_std'][i] for i in valid_indices] if metrics.get('has_error_bars') else None

            color = DB_COLORS.get(db_name, '#000000')

            # Plot data points with error bars (no connecting lines)
            if throughputs_std and any(s > 0 for s in throughputs_std):
                ax2.errorbar(chunks, throughputs, yerr=throughputs_std,
                           fmt='s', markersize=8,
                           color=color,
                           alpha=0.8, capsize=4, capthick=1.5,
                           linestyle='none', label='_nolegend_')
            else:
                ax2.plot(chunks, throughputs,
                        marker='s', markersize=8,
                        color=color,
                        linestyle='none',
                        alpha=0.8, label='_nolegend_')

            # Fit and plot polynomial trend line
            if len(chunks) >= 3:
                log_chunks = np.log10(chunks)
                degree = min(2, len(chunks) - 1)
                coeffs = np.polyfit(log_chunks, throughputs, degree)
                poly = np.poly1d(coeffs)

                # Generate smooth curve
                log_chunks_smooth = np.linspace(min(log_chunks), max(log_chunks), 100)
                chunks_smooth = 10 ** log_chunks_smooth
                throughputs_smooth = poly(log_chunks_smooth)

                # Plot trend line
                ax2.plot(chunks_smooth, throughputs_smooth,
                        linewidth=2.5, color=color,
                        linestyle=DB_LINESTYLES.get(db_name, '-'),
                        label=DB_LABELS.get(db_name, db_name),
                        alpha=0.9)

    ax2.set_xlabel('Corpus Size (chunks)', fontweight='bold', fontsize=11)
    ax2.set_ylabel('Throughput (Queries/sec)', fontweight='bold', fontsize=11)
    ax2.set_title('(b) Query Throughput Scaling', fontweight='bold', fontsize=12)
    ax2.legend(loc='best', framealpha=0.95, fontsize=9)
    ax2.grid(True, alpha=0.3, linestyle=':')
    ax2.set_xscale('log')
    ax2.axhline(y=100, color='gray', linestyle='--', linewidth=1, alpha=0.5, label='100 QPS threshold')

    # Panel 3: Ingestion Time with polynomial trend lines
    for db_name, metrics in all_data.items():
        if metrics and metrics['ingestion_times']:
            chunks = metrics['chunks']
            times = [t / 60 for t in metrics['ingestion_times']]
            times_std = [t / 60 for t in metrics['ingestion_times_std']] if metrics.get('has_error_bars') else None

            color = DB_COLORS.get(db_name, '#000000')

            # Plot data points with error bars (no connecting lines)
            if times_std and any(s > 0 for s in times_std):
                ax3.errorbar(chunks, times, yerr=times_std,
                           fmt='D', markersize=8,
                           color=color,
                           alpha=0.8, capsize=4, capthick=1.5,
                           linestyle='none', label='_nolegend_')
            else:
                ax3.plot(chunks, times,
                        marker='D', markersize=8,
                        color=color,
                        linestyle='none',
                        alpha=0.8, label='_nolegend_')

            # Fit and plot polynomial trend line (log-log space)
            if len(chunks) >= 3:
                log_chunks = np.log10(chunks)
                log_times = np.log10(times)
                degree = min(2, len(chunks) - 1)
                coeffs = np.polyfit(log_chunks, log_times, degree)
                poly = np.poly1d(coeffs)

                # Generate smooth curve
                log_chunks_smooth = np.linspace(min(log_chunks), max(log_chunks), 100)
                chunks_smooth = 10 ** log_chunks_smooth
                times_smooth = 10 ** poly(log_chunks_smooth)

                # Plot trend line
                ax3.plot(chunks_smooth, times_smooth,
                        linewidth=2.5, color=color,
                        linestyle=DB_LINESTYLES.get(db_name, '-'),
                        label=DB_LABELS.get(db_name, db_name),
                        alpha=0.9)

    ax3.set_xlabel('Corpus Size (chunks)', fontweight='bold', fontsize=11)
    ax3.set_ylabel('Ingestion Time (minutes)', fontweight='bold', fontsize=11)
    ax3.set_title('(c) Data Ingestion Time', fontweight='bold', fontsize=12)
    ax3.legend(loc='upper left', framealpha=0.95, fontsize=9)
    ax3.grid(True, alpha=0.3, linestyle=':')
    ax3.set_xscale('log')
    ax3.set_yscale('log')

    # Panel 4: Ingestion Throughput Consistency with polynomial trend lines
    for db_name, metrics in all_data.items():
        if metrics and metrics['ingestion_times']:
            chunks = metrics['chunks']
            throughputs = [c / t for c, t in zip(chunks, metrics['ingestion_times'])]

            # Calculate error bars for throughput (error propagation: σ_rate = rate * σ_time / time)
            throughputs_std = None
            if metrics.get('has_error_bars') and any(s > 0 for s in metrics['ingestion_times_std']):
                throughputs_std = [
                    (c / t) * (t_std / t) if t > 0 and t_std > 0 else 0
                    for c, t, t_std in zip(chunks, metrics['ingestion_times'], metrics['ingestion_times_std'])
                ]

            color = DB_COLORS.get(db_name, '#000000')

            # Plot data points with error bars (no connecting lines)
            if throughputs_std and any(s > 0 for s in throughputs_std):
                ax4.errorbar(chunks, throughputs, yerr=throughputs_std,
                           fmt='^', markersize=8,
                           color=color,
                           alpha=0.8, capsize=4, capthick=1.5,
                           linestyle='none', label='_nolegend_')
            else:
                ax4.plot(chunks, throughputs,
                        marker='^', markersize=8,
                        color=color,
                        linestyle='none',
                        alpha=0.8, label='_nolegend_')

            # Fit and plot polynomial trend line
            if len(chunks) >= 3:
                log_chunks = np.log10(chunks)
                degree = min(2, len(chunks) - 1)
                coeffs = np.polyfit(log_chunks, throughputs, degree)
                poly = np.poly1d(coeffs)

                # Generate smooth curve
                log_chunks_smooth = np.linspace(min(log_chunks), max(log_chunks), 100)
                chunks_smooth = 10 ** log_chunks_smooth
                throughputs_smooth = poly(log_chunks_smooth)

                # Plot trend line
                ax4.plot(chunks_smooth, throughputs_smooth,
                        linewidth=2.5, color=color,
                        linestyle=DB_LINESTYLES.get(db_name, '-'),
                        label=DB_LABELS.get(db_name, db_name),
                        alpha=0.9)

            # Calculate and display coefficient of variation
            if len(throughputs) > 1:
                cv = (np.std(throughputs) / np.mean(throughputs)) * 100
                # Annotate at the rightmost point
                ax4.text(chunks[-1] * 1.15, throughputs[-1],
                        f'CV={cv:.1f}%',
                        fontsize=8, color=color,
                        verticalalignment='center',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8, edgecolor='none'))

    ax4.set_xlabel('Corpus Size (chunks)', fontweight='bold', fontsize=11)
    ax4.set_ylabel('Ingestion Rate (chunks/sec)', fontweight='bold', fontsize=11)
    ax4.set_title('(d) Ingestion Throughput Consistency', fontweight='bold', fontsize=12)
    ax4.legend(loc='center', framealpha=0.95, fontsize=9)
    ax4.grid(True, alpha=0.3, linestyle=':')
    ax4.set_xscale('log')

    # Overall title
    fig.suptitle('Multi-Database Scaling Performance Comparison',
                 fontsize=14, fontweight='bold', y=0.995)

    output_path = Path(output_dir) / 'figure_4panel_scaling_comparison.png'
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
    databases = ['faiss', 'chroma', 'qdrant', 'weaviate', 'milvus', 'opensearch', 'pgvector']

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
