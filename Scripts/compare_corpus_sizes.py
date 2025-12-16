#!/usr/bin/env python3
"""
Compare FAISS performance across different corpus sizes
"""

import json
import matplotlib.pyplot as plt
import numpy as np

# Load data
with open('results/faiss_experiment_001/results.json', 'r') as f:
    small_corpus = json.load(f)

with open('results/faiss_large_corpus_real_embeddings/results.json', 'r') as f:
    large_corpus = json.load(f)

# Extract metrics
small_chunks = small_corpus['ingestion']['num_chunks']
large_chunks = large_corpus['ingestion']['num_chunks']
corpus_scale = large_chunks / small_chunks

top_k_values = [1, 3, 5, 10, 20]

# Extract query metrics
small_avg_latency = [r['avg_latency_ms'] for r in small_corpus['query_results']]
large_avg_latency = [r['avg_latency_ms'] for r in large_corpus['query_results']]

small_p95_latency = [r['p95_latency_ms'] for r in small_corpus['query_results']]
large_p95_latency = [r['p95_latency_ms'] for r in large_corpus['query_results']]

small_qps = [r['queries_per_second'] for r in small_corpus['query_results']]
large_qps = [r['queries_per_second'] for r in large_corpus['query_results']]

# Calculate slowdown factors
avg_slowdown = [large / small for large, small in zip(large_avg_latency, small_avg_latency)]
p95_slowdown = [large / small for large, small in zip(large_p95_latency, small_p95_latency)]

# Create comprehensive comparison plot
fig = plt.figure(figsize=(16, 10))
gs = fig.add_gridspec(3, 3, hspace=0.3, wspace=0.3)

# 1. Average Latency Comparison (log scale)
ax1 = fig.add_subplot(gs[0, 0])
x = np.arange(len(top_k_values))
width = 0.35
ax1.bar(x - width/2, small_avg_latency, width, label=f'Small ({small_chunks:,} chunks)', color='#2ecc71')
ax1.bar(x + width/2, large_avg_latency, x + width/2, label=f'Large ({large_chunks:,} chunks)', color='#e74c3c')
ax1.set_xlabel('Top-K Value')
ax1.set_ylabel('Avg Latency (ms)')
ax1.set_title('Average Query Latency by Corpus Size')
ax1.set_xticks(x)
ax1.set_xticklabels(top_k_values)
ax1.legend()
ax1.grid(axis='y', alpha=0.3)

# 2. P95 Latency Comparison (log scale for visibility)
ax2 = fig.add_subplot(gs[0, 1])
ax2.bar(x - width/2, small_p95_latency, width, label=f'Small ({small_chunks:,} chunks)', color='#2ecc71')
ax2.bar(x + width/2, large_p95_latency, width, label=f'Large ({large_chunks:,} chunks)', color='#e74c3c', alpha=0.7)
ax2.set_xlabel('Top-K Value')
ax2.set_ylabel('P95 Latency (ms)')
ax2.set_title('P95 Query Latency by Corpus Size')
ax2.set_xticks(x)
ax2.set_xticklabels(top_k_values)
ax2.legend()
ax2.grid(axis='y', alpha=0.3)
ax2.set_yscale('log')

# 3. Throughput (QPS) Comparison
ax3 = fig.add_subplot(gs[0, 2])
ax3.bar(x - width/2, small_qps, width, label=f'Small ({small_chunks:,} chunks)', color='#2ecc71')
ax3.bar(x + width/2, large_qps, width, label=f'Large ({large_chunks:,} chunks)', color='#e74c3c')
ax3.set_xlabel('Top-K Value')
ax3.set_ylabel('Queries Per Second')
ax3.set_title('Throughput by Corpus Size')
ax3.set_xticks(x)
ax3.set_xticklabels(top_k_values)
ax3.legend()
ax3.grid(axis='y', alpha=0.3)

# 4. Slowdown Factor (Average Latency)
ax4 = fig.add_subplot(gs[1, 0])
colors = ['#e74c3c' if s > 10 else '#f39c12' if s > 8 else '#2ecc71' for s in avg_slowdown]
bars = ax4.bar(top_k_values, avg_slowdown, color=colors, alpha=0.7, edgecolor='black')
ax4.axhline(y=corpus_scale, color='red', linestyle='--', linewidth=2, label=f'Linear scaling ({corpus_scale:.0f}x)')
ax4.set_xlabel('Top-K Value')
ax4.set_ylabel('Slowdown Factor (Large / Small)')
ax4.set_title(f'Query Latency Slowdown Factor\n({large_chunks:,} / {small_chunks} = {corpus_scale:.0f}x more data)')
ax4.legend()
ax4.grid(axis='y', alpha=0.3)
# Add value labels on bars
for bar, val in zip(bars, avg_slowdown):
    height = bar.get_height()
    ax4.text(bar.get_x() + bar.get_width()/2., height,
            f'{val:.1f}x', ha='center', va='bottom', fontweight='bold')

# 5. Slowdown Factor (P95 Latency)
ax5 = fig.add_subplot(gs[1, 1])
colors = ['#e74c3c' if s > 20 else '#f39c12' if s > 10 else '#2ecc71' for s in p95_slowdown]
bars = ax5.bar(top_k_values, p95_slowdown, color=colors, alpha=0.7, edgecolor='black')
ax5.axhline(y=corpus_scale, color='red', linestyle='--', linewidth=2, label=f'Linear scaling ({corpus_scale:.0f}x)')
ax5.set_xlabel('Top-K Value')
ax5.set_ylabel('Slowdown Factor (Large / Small)')
ax5.set_title(f'P95 Latency Slowdown Factor')
ax5.legend()
ax5.grid(axis='y', alpha=0.3)
ax5.set_yscale('log')
# Add value labels on bars
for bar, val in zip(bars, p95_slowdown):
    height = bar.get_height()
    ax5.text(bar.get_x() + bar.get_width()/2., height,
            f'{val:.1f}x', ha='center', va='bottom', fontweight='bold', fontsize=9)

# 6. Scaling Efficiency (lower is better)
ax6 = fig.add_subplot(gs[1, 2])
scaling_efficiency = [s / corpus_scale for s in avg_slowdown]
colors = ['#2ecc71' if e < 0.6 else '#f39c12' if e < 1.0 else '#e74c3c' for e in scaling_efficiency]
bars = ax6.bar(top_k_values, scaling_efficiency, color=colors, alpha=0.7, edgecolor='black')
ax6.axhline(y=1.0, color='red', linestyle='--', linewidth=2, label='Linear scaling (1.0)')
ax6.set_xlabel('Top-K Value')
ax6.set_ylabel('Scaling Efficiency (slowdown / data_scale)')
ax6.set_title('Query Scaling Efficiency\n(< 1.0 = sub-linear, > 1.0 = super-linear)')
ax6.legend()
ax6.grid(axis='y', alpha=0.3)
# Add value labels
for bar, val in zip(bars, scaling_efficiency):
    height = bar.get_height()
    ax6.text(bar.get_x() + bar.get_width()/2., height,
            f'{val:.2f}', ha='center', va='bottom', fontweight='bold')

# 7. Ingestion Performance
ax7 = fig.add_subplot(gs[2, 0])
small_ingestion = small_corpus['ingestion']['total_time_sec']
large_ingestion = large_corpus['ingestion']['total_time_sec']
small_throughput = small_chunks / small_ingestion
large_throughput = large_chunks / large_ingestion
categories = ['Small Corpus', 'Large Corpus']
throughputs = [small_throughput, large_throughput]
colors_ing = ['#2ecc71', '#3498db']
bars = ax7.bar(categories, throughputs, color=colors_ing, alpha=0.7, edgecolor='black')
ax7.set_ylabel('Chunks/Second')
ax7.set_title('Ingestion Throughput')
ax7.grid(axis='y', alpha=0.3)
for bar, val in zip(bars, throughputs):
    height = bar.get_height()
    ax7.text(bar.get_x() + bar.get_width()/2., height,
            f'{val:.1f}', ha='center', va='bottom', fontweight='bold')

# 8. Ingestion Time Breakdown (Large Corpus)
ax8 = fig.add_subplot(gs[2, 1])
ing = large_corpus['ingestion']
breakdown = {
    'Parsing': ing['parsing_time_sec'],
    'Embedding': ing['embedding_time_sec'],
    'Insertion': ing['insertion_time_sec']
}
colors_breakdown = ['#3498db', '#e74c3c', '#2ecc71']
wedges, texts, autotexts = ax8.pie(breakdown.values(), labels=breakdown.keys(), autopct='%1.1f%%',
                                     colors=colors_breakdown, startangle=90)
ax8.set_title('Large Corpus Ingestion Time Breakdown')

# 9. Summary Statistics Table
ax9 = fig.add_subplot(gs[2, 2])
ax9.axis('off')
summary_data = [
    ['Metric', 'Small', 'Large', 'Ratio'],
    ['Chunks', f'{small_chunks:,}', f'{large_chunks:,}', f'{corpus_scale:.0f}x'],
    ['Ingestion Time', f'{small_ingestion:.2f}s', f'{large_ingestion/60:.1f}min', f'{large_ingestion/small_ingestion:.0f}x'],
    ['Ingestion Rate', f'{small_throughput:.0f} ch/s', f'{large_throughput:.0f} ch/s', f'{large_throughput/small_throughput:.2f}x'],
    ['Avg Latency (k=3)', f'{small_avg_latency[1]:.1f}ms', f'{large_avg_latency[1]:.1f}ms', f'{avg_slowdown[1]:.1f}x'],
    ['Avg Latency (k=10)', f'{small_avg_latency[3]:.1f}ms', f'{large_avg_latency[3]:.1f}ms', f'{avg_slowdown[3]:.1f}x'],
    ['QPS (k=3)', f'{small_qps[1]:.0f}', f'{large_qps[1]:.0f}', f'{small_qps[1]/large_qps[1]:.1f}x'],
]

table = ax9.table(cellText=summary_data, cellLoc='center', loc='center',
                  colWidths=[0.3, 0.25, 0.25, 0.2])
table.auto_set_font_size(False)
table.set_fontsize(9)
table.scale(1, 2)

# Style header row
for i in range(4):
    table[(0, i)].set_facecolor('#3498db')
    table[(0, i)].set_text_props(weight='bold', color='white')

# Alternate row colors
for i in range(1, len(summary_data)):
    for j in range(4):
        if i % 2 == 0:
            table[(i, j)].set_facecolor('#ecf0f1')

ax9.set_title('Performance Summary', fontweight='bold', fontsize=12, pad=20)

# Overall title
fig.suptitle('FAISS Performance Scaling: Small vs Large Corpus Comparison',
             fontsize=16, fontweight='bold', y=0.995)

plt.savefig('results/faiss_corpus_size_comparison.png', dpi=150, bbox_inches='tight')
print("✅ Comparison chart saved to: results/faiss_corpus_size_comparison.png")

# Print summary statistics
print("\n" + "="*70)
print("FAISS CORPUS SIZE SCALING ANALYSIS")
print("="*70)
print(f"\nCorpus Scale: {corpus_scale:.0f}x increase ({small_chunks:,} → {large_chunks:,} chunks)")
print(f"\nIngestion:")
print(f"  Small: {small_ingestion:.2f}s ({small_throughput:.0f} chunks/sec)")
print(f"  Large: {large_ingestion/60:.1f}min ({large_throughput:.0f} chunks/sec)")
print(f"  Throughput improvement: {large_throughput/small_throughput:.2f}x")

print(f"\nQuery Latency Slowdown (excluding Top-K=1 anomaly):")
for i, k in enumerate(top_k_values[1:], 1):  # Skip Top-K=1
    print(f"  Top-K={k:2d}: {avg_slowdown[i]:.2f}x slower (scaling efficiency: {scaling_efficiency[i]:.4f})")

print(f"\nScaling Efficiency: {np.mean(scaling_efficiency[1:]):.4f} (average for Top-K ≥ 3)")
print(f"  < 1.0 = Sub-linear (GOOD - better than expected)")
print(f"  = 1.0 = Linear (EXPECTED)")
print(f"  > 1.0 = Super-linear (BAD - worse than expected)")

print(f"\n⚠️  Top-K=1 Anomaly: {avg_slowdown[0]:.1f}x slowdown (P95: {p95_slowdown[0]:.1f}x)")
print("="*70)
