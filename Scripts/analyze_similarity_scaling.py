#!/usr/bin/env python3
"""
Analyze how retrieval quality (similarity scores) scales with corpus size.

Shows whether FAISS maintains retrieval accuracy as the corpus grows.
"""

import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from scipy import stats
from collections import defaultdict

def load_results(results_dir):
    """Load all benchmark results."""
    results_dir = Path(results_dir)
    all_results = []

    for corpus_dir in sorted(results_dir.glob('corpus_*')):
        results_file = corpus_dir / 'results.json'
        if results_file.exists():
            with open(results_file, 'r') as f:
                data = json.load(f)
                chunks = data['ingestion']['num_chunks']
                all_results.append({
                    'name': corpus_dir.name,
                    'chunks': chunks,
                    'data': data
                })

    # Sort by chunk count
    all_results.sort(key=lambda x: x['chunks'])
    return all_results

def extract_similarity_metrics(all_results):
    """Extract similarity scores for each corpus size and top-k."""
    # Group by chunk count for replicates
    grouped = defaultdict(list)
    for result in all_results:
        chunks = result['chunks']
        grouped[chunks].append(result)

    chunk_sizes = sorted(grouped.keys())

    # Store metrics by top-k
    metrics = {
        'chunk_sizes': chunk_sizes,
        'corpus_names': [],
        'top_k_values': set()
    }

    similarity_by_topk = defaultdict(lambda: {'avg': [], 'top1': [], 'min': []})

    for chunks in chunk_sizes:
        runs = grouped[chunks]
        metrics['corpus_names'].append(runs[0]['name'])

        # Collect metrics across replicates
        for run in runs:
            for qr in run['data']['query_results']:
                top_k = qr['top_k']
                metrics['top_k_values'].add(top_k)
                similarity_by_topk[top_k]['avg'].append(qr['avg_similarity'])
                similarity_by_topk[top_k]['top1'].append(qr['avg_top1_similarity'])
                similarity_by_topk[top_k]['min'].append(qr['min_similarity'])

    # Calculate stats for each chunk size
    metrics['similarity_by_topk'] = {}
    for top_k in sorted(metrics['top_k_values']):
        chunk_metrics = {'avg': [], 'top1': [], 'min': []}

        idx = 0
        for chunks in chunk_sizes:
            n_runs = len(grouped[chunks])

            for metric in ['avg', 'top1', 'min']:
                values = similarity_by_topk[top_k][metric][idx:idx+n_runs]
                chunk_metrics[metric].append({
                    'mean': np.mean(values),
                    'std': np.std(values, ddof=1) if len(values) > 1 else 0,
                    'n': len(values)
                })

            idx += n_runs

        metrics['similarity_by_topk'][top_k] = chunk_metrics

    metrics['top_k_values'] = sorted(metrics['top_k_values'])
    return metrics

def create_similarity_scaling_plot(metrics, output_dir):
    """Create comprehensive similarity scaling visualization."""
    output_dir = Path(output_dir)

    chunks = np.array(metrics['chunk_sizes'])
    top_k_values = metrics['top_k_values']

    # Create figure
    fig = plt.figure(figsize=(18, 12))
    gs = fig.add_gridspec(3, 3, hspace=0.35, wspace=0.3)

    colors = ['#e74c3c', '#f39c12', '#2ecc71', '#3498db', '#9b59b6']

    # 1. Average Similarity vs Corpus Size (All Top-K)
    ax1 = fig.add_subplot(gs[0, 0])
    for i, top_k in enumerate(top_k_values):
        sim_data = metrics['similarity_by_topk'][top_k]['avg']
        means = [s['mean'] for s in sim_data]
        stds = [s['std'] for s in sim_data]

        ax1.errorbar(chunks, means, yerr=stds,
                     fmt='o-', markersize=6, linewidth=2, capsize=4,
                     color=colors[i % len(colors)], label=f'Top-K={top_k}')

    ax1.set_xscale('log')
    ax1.set_xlabel('Corpus Size (chunks)', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Average Similarity', fontsize=12, fontweight='bold')
    ax1.set_title('Retrieval Quality vs Corpus Size\n(All Top-K Values)',
                  fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend(fontsize=9, loc='lower left')
    ax1.set_ylim([0.4, 0.7])

    # 2. Top-1 Similarity vs Corpus Size
    ax2 = fig.add_subplot(gs[0, 1])
    for i, top_k in enumerate(top_k_values):
        sim_data = metrics['similarity_by_topk'][top_k]['top1']
        means = [s['mean'] for s in sim_data]
        stds = [s['std'] for s in sim_data]

        ax2.errorbar(chunks, means, yerr=stds,
                     fmt='o-', markersize=6, linewidth=2, capsize=4,
                     color=colors[i % len(colors)], label=f'Top-K={top_k}')

    ax2.set_xscale('log')
    ax2.set_xlabel('Corpus Size (chunks)', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Top-1 Similarity', fontsize=12, fontweight='bold')
    ax2.set_title('Best Result Quality vs Corpus Size\n(Top-1 Similarity)',
                  fontsize=13, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.legend(fontsize=9, loc='lower left')
    ax2.set_ylim([0.4, 0.7])

    # 3. Quality Degradation Analysis (Top-K=3)
    ax3 = fig.add_subplot(gs[0, 2])
    top_k_3_avg = metrics['similarity_by_topk'][3]['avg']
    means = np.array([s['mean'] for s in top_k_3_avg])
    stds = np.array([s['std'] for s in top_k_3_avg])

    baseline_sim = means[0]
    degradation = (baseline_sim - means) / baseline_sim * 100

    bars = ax3.bar(range(len(chunks)), degradation,
                   color=['#2ecc71' if d < 5 else '#f39c12' if d < 10 else '#e74c3c'
                          for d in degradation],
                   alpha=0.7, edgecolor='black')

    ax3.set_xlabel('Corpus Size', fontsize=12, fontweight='bold')
    ax3.set_ylabel('Quality Degradation (%)', fontsize=12, fontweight='bold')
    ax3.set_title('Quality Degradation from Baseline\n(Top-K=3)',
                  fontsize=13, fontweight='bold')
    ax3.set_xticks(range(len(chunks)))
    ax3.set_xticklabels([f'{c:,}' for c in chunks], rotation=45, ha='right', fontsize=8)
    ax3.grid(axis='y', alpha=0.3)
    ax3.axhline(y=0, color='green', linestyle='--', linewidth=2, alpha=0.5)
    ax3.axhline(y=5, color='orange', linestyle='--', linewidth=1, alpha=0.5, label='5% threshold')
    ax3.legend(fontsize=9)

    # Add value labels
    for bar, deg in zip(bars, degradation):
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2., height,
                f'{deg:.1f}%', ha='center', va='bottom', fontsize=8, fontweight='bold')

    # 4-6: Similarity by Top-K for specific corpus sizes
    corpus_indices = [0, len(chunks)//2, -1]  # baseline, middle, largest
    corpus_labels = ['Baseline', 'Medium', 'Largest']

    for plot_idx, (corpus_idx, label) in enumerate(zip(corpus_indices, corpus_labels)):
        row = 1 + plot_idx // 3
        col = plot_idx % 3
        ax = fig.add_subplot(gs[row, col])

        chunk_count = chunks[corpus_idx]
        corpus_name = metrics['corpus_names'][corpus_idx]

        avg_sims = []
        top1_sims = []
        min_sims = []
        avg_stds = []

        for top_k in top_k_values:
            avg_sims.append(metrics['similarity_by_topk'][top_k]['avg'][corpus_idx]['mean'])
            top1_sims.append(metrics['similarity_by_topk'][top_k]['top1'][corpus_idx]['mean'])
            min_sims.append(metrics['similarity_by_topk'][top_k]['min'][corpus_idx]['mean'])
            avg_stds.append(metrics['similarity_by_topk'][top_k]['avg'][corpus_idx]['std'])

        x = np.arange(len(top_k_values))
        width = 0.25

        ax.bar(x - width, avg_sims, width, label='Avg Similarity',
               color='#3498db', alpha=0.8, edgecolor='black')
        ax.bar(x, top1_sims, width, label='Top-1 Similarity',
               color='#2ecc71', alpha=0.8, edgecolor='black')
        ax.bar(x + width, min_sims, width, label='Min Similarity',
               color='#e74c3c', alpha=0.8, edgecolor='black')

        ax.set_xlabel('Top-K Value', fontsize=11, fontweight='bold')
        ax.set_ylabel('Similarity Score', fontsize=11, fontweight='bold')
        ax.set_title(f'{label} Corpus\n({chunk_count:,} chunks)',
                    fontsize=12, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(top_k_values)
        ax.legend(fontsize=8)
        ax.grid(axis='y', alpha=0.3)
        ax.set_ylim([0.4, 0.7])

    # 7. Quality Consistency Across Scales (CV%)
    ax7 = fig.add_subplot(gs[2, 0])

    # Calculate CV for Top-K=3 across all corpus sizes
    cv_values = [s['std'] / s['mean'] * 100 if s['mean'] > 0 else 0
                 for s in metrics['similarity_by_topk'][3]['avg']]
    n_values = [s['n'] for s in metrics['similarity_by_topk'][3]['avg']]

    colors_cv = ['#2ecc71' if cv < 2 else '#f39c12' if cv < 5 else '#e74c3c'
                 for cv in cv_values]
    bars = ax7.bar(range(len(cv_values)), cv_values, color=colors_cv,
                   alpha=0.7, edgecolor='black')

    ax7.set_xlabel('Corpus Size', fontsize=11, fontweight='bold')
    ax7.set_ylabel('Coefficient of Variation (%)', fontsize=11, fontweight='bold')
    ax7.set_title('Quality Measurement Consistency\n(Top-K=3, Lower is Better)',
                  fontsize=12, fontweight='bold')
    ax7.set_xticks(range(len(cv_values)))
    ax7.set_xticklabels([f'{c:,}\n(n={n})' for c, n in zip(chunks, n_values)],
                        rotation=45, ha='right', fontsize=8)
    ax7.grid(axis='y', alpha=0.3)
    ax7.axhline(y=2, color='green', linestyle='--', linewidth=1, alpha=0.5)
    ax7.axhline(y=5, color='orange', linestyle='--', linewidth=1, alpha=0.5)

    for bar, cv in zip(bars, cv_values):
        if cv > 0:
            height = bar.get_height()
            ax7.text(bar.get_x() + bar.get_width()/2., height,
                    f'{cv:.1f}%', ha='center', va='bottom', fontsize=8, fontweight='bold')

    # 8. Similarity Range Analysis
    ax8 = fig.add_subplot(gs[2, 1])

    # For Top-K=3, show range of similarities
    for i, chunks_val in enumerate(chunks):
        avg_data = metrics['similarity_by_topk'][3]['avg'][i]
        top1_data = metrics['similarity_by_topk'][3]['top1'][i]
        min_data = metrics['similarity_by_topk'][3]['min'][i]

        avg_mean = avg_data['mean']
        range_low = min_data['mean']
        range_high = top1_data['mean']

        ax8.plot([i, i], [range_low, range_high], 'o-', linewidth=2, markersize=8,
                color='#3498db')
        ax8.plot(i, avg_mean, 's', markersize=10, color='#e74c3c',
                label='Average' if i == 0 else '')

    ax8.set_xlabel('Corpus Size', fontsize=11, fontweight='bold')
    ax8.set_ylabel('Similarity Score', fontsize=11, fontweight='bold')
    ax8.set_title('Similarity Range by Corpus Size\n(Top-K=3: Min to Top-1)',
                  fontsize=12, fontweight='bold')
    ax8.set_xticks(range(len(chunks)))
    ax8.set_xticklabels([f'{c:,}' for c in chunks], rotation=45, ha='right', fontsize=8)
    ax8.grid(True, alpha=0.3)
    ax8.legend(fontsize=9)
    ax8.set_ylim([0.4, 0.7])

    # 9. Summary Statistics Table
    ax9 = fig.add_subplot(gs[2, 2])
    ax9.axis('off')

    # Calculate summary stats
    baseline_avg = metrics['similarity_by_topk'][3]['avg'][0]['mean']
    largest_avg = metrics['similarity_by_topk'][3]['avg'][-1]['mean']
    total_degradation = (baseline_avg - largest_avg) / baseline_avg * 100

    summary_data = [
        ['Metric', 'Baseline', 'Largest', 'Change'],
        ['Chunks', f"{chunks[0]:,}", f"{chunks[-1]:,}", f"{chunks[-1]/chunks[0]:.0f}x"],
        ['Avg Sim', f"{baseline_avg:.3f}", f"{largest_avg:.3f}",
         f"{total_degradation:.1f}%↓"],
        ['Top-1 Sim',
         f"{metrics['similarity_by_topk'][3]['top1'][0]['mean']:.3f}",
         f"{metrics['similarity_by_topk'][3]['top1'][-1]['mean']:.3f}",
         f"{(metrics['similarity_by_topk'][3]['top1'][0]['mean'] - metrics['similarity_by_topk'][3]['top1'][-1]['mean']) / metrics['similarity_by_topk'][3]['top1'][0]['mean'] * 100:.1f}%↓"],
        ['', '', '', ''],
        ['Quality Assessment', '', '', ''],
        ['Degradation:', f'{total_degradation:.1f}%',
         'Excellent' if total_degradation < 5 else 'Good' if total_degradation < 10 else 'Moderate', ''],
    ]

    table = ax9.table(cellText=summary_data, cellLoc='left', loc='center',
                      colWidths=[0.35, 0.22, 0.22, 0.21])
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 2.5)

    # Style header
    for i in range(4):
        table[(0, i)].set_facecolor('#3498db')
        table[(0, i)].set_text_props(weight='bold', color='white')

    # Style summary section
    for i in range(4):
        table[(5, i)].set_facecolor('#2ecc71')
        table[(5, i)].set_text_props(weight='bold')

    ax9.set_title('Quality Scaling Summary\n(Top-K=3)',
                  fontweight='bold', fontsize=12, pad=20)

    fig.suptitle('FAISS Retrieval Quality Scaling Analysis\nSemantic Similarity Across Corpus Sizes',
                 fontsize=16, fontweight='bold', y=0.995)

    plot_file = output_dir / 'similarity_scaling_analysis.png'
    plt.savefig(plot_file, dpi=150, bbox_inches='tight')
    print(f"\n✅ Similarity scaling plot saved to: {plot_file}")

def print_similarity_summary(metrics):
    """Print summary of quality scaling."""
    chunks = metrics['chunk_sizes']

    print("\n" + "="*80)
    print("RETRIEVAL QUALITY SCALING SUMMARY (Top-K=3)")
    print("="*80)

    baseline_avg = metrics['similarity_by_topk'][3]['avg'][0]['mean']

    print(f"\n{'Corpus Size':<15} {'Avg Similarity':<18} {'Degradation':<15} {'Assessment'}")
    print("-"*80)

    for i, chunk_count in enumerate(chunks):
        avg_sim = metrics['similarity_by_topk'][3]['avg'][i]['mean']
        std_sim = metrics['similarity_by_topk'][3]['avg'][i]['std']
        deg = (baseline_avg - avg_sim) / baseline_avg * 100

        if deg < 5:
            assessment = "✓ Excellent"
        elif deg < 10:
            assessment = "✓ Good"
        else:
            assessment = "⚠ Moderate"

        print(f"{chunk_count:<15,} {avg_sim:.3f} ± {std_sim:.3f}      "
              f"{deg:>6.1f}%       {assessment}")

    print("\n" + "="*80)
    largest_avg = metrics['similarity_by_topk'][3]['avg'][-1]['mean']
    total_deg = (baseline_avg - largest_avg) / baseline_avg * 100

    print(f"\nOverall Quality Impact:")
    print(f"  Scale: {chunks[0]:,} → {chunks[-1]:,} chunks ({chunks[-1]/chunks[0]:.0f}x)")
    print(f"  Similarity: {baseline_avg:.3f} → {largest_avg:.3f}")
    print(f"  Total degradation: {total_deg:.1f}%")

    if total_deg < 5:
        print(f"  ✓ EXCELLENT - Quality maintained at scale")
    elif total_deg < 10:
        print(f"  ✓ GOOD - Minimal quality impact")
    else:
        print(f"  ⚠ MODERATE - Noticeable quality degradation")

    print("="*80)

def main():
    print("="*80)
    print("FAISS Similarity Scaling Analysis")
    print("="*80)

    results_dir = 'results/faiss_scaling_experiment'
    if not Path(results_dir).exists():
        print(f"❌ Results directory not found: {results_dir}")
        return

    print("\nLoading results...")
    all_results = load_results(results_dir)

    if len(all_results) < 2:
        print(f"❌ Need at least 2 corpus sizes. Found: {len(all_results)}")
        return

    print(f"✓ Loaded {len(all_results)} benchmark runs")

    print("\nExtracting similarity metrics...")
    metrics = extract_similarity_metrics(all_results)

    print("\nGenerating similarity scaling visualizations...")
    create_similarity_scaling_plot(metrics, results_dir)

    print_similarity_summary(metrics)

    print("\n✅ Analysis complete!")

if __name__ == '__main__':
    main()
