#!/usr/bin/env python3
"""
Ingestion performance benchmark for FAISS.
Mirrors the ingestion workflows and writes artifacts to the results folder.
"""

import json
import time
import sys
from pathlib import Path
from typing import List, Dict
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import os

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.vector_dbs.faiss_adapter import FAISSRAGBenchmark
from src.embeddings.embedding_generator import get_embedding_generator
from src.parsers.document_parser import DocumentParser, Document


CONFIG = {
    'corpus_path': 'Data/test_corpus/documents',
    'output_dir': 'results/faiss_ingestion_experiment_001',
    'faiss_config': {
        'index_path': os.getenv('FAISS_INDEX_PATH', 'vector_stores/faiss_index'),
        'index_type': 'Flat',          # ✅ changed from FlatL2 to Flat
        'use_gpu': False,
        'nlist': 100,
        'nprobe': 10
    },
    'embedding_model': 'sentence-transformers/all-MiniLM-L6-v2',
    'embedding_type': 'sentence-transformers',
    'chunk_sizes': [256, 512, 1024],
    'batch_sizes': [50, 100],
    'doc_counts': [10, 20],
    'chunk_overlap': 50,
    'chunk_strategy': 'fixed',
    'n_runs': 1
}


def load_documents(corpus_path: str, max_docs: int = None) -> List[Document]:
    parser = DocumentParser()
    documents = []
    corpus_dir = Path(corpus_path)
    txt_files = sorted(corpus_dir.glob("*.txt"))
    if max_docs:
        txt_files = txt_files[:max_docs]
    for txt_file in txt_files:
        doc = parser.parse_txt(str(txt_file))
        documents.append(doc)
    return documents


def run_ingestion_experiment(
    benchmark: FAISSRAGBenchmark,
    documents: List[Document],
    chunk_size: int,
    batch_size: int,
    run_num: int
) -> Dict:
    benchmark.create_collection(benchmark.embedding_generator.dimension)
    benchmark.chunk_size = chunk_size
    start_time = time.time()
    ingest_result = benchmark.ingest_documents(documents, batch_size=batch_size)
    total_time = time.time() - start_time
    num_docs = len(documents)
    num_chunks = getattr(ingest_result, 'num_chunks', 0)
    total_size = sum(len(doc.content.encode('utf-8')) for doc in documents)
    parsing_time = getattr(ingest_result, 'total_parsing_time', 0)
    embedding_time = getattr(ingest_result, 'total_embedding_time', 0)
    insertion_time = getattr(ingest_result, 'total_insertion_time', 0)
    return {
        'run': run_num,
        'chunk_size': chunk_size,
        'batch_size': batch_size,
        'num_docs': num_docs,
        'num_chunks': num_chunks,
        'total_size_bytes': total_size,
        'parsing_time': parsing_time,
        'embedding_time': embedding_time,
        'insertion_time': insertion_time,
        'total_time': total_time,
        'chunks_per_second': num_chunks / total_time if total_time > 0 else 0,
        'bytes_per_second': total_size / total_time if total_time > 0 else 0,
        'docs_per_second': num_docs / total_time if total_time > 0 else 0
    }


def main():
    print("="*70)
    print("FAISS Ingestion Performance Benchmark")
    print("="*70)

    print("\n[1/6] Setting up...")
    output_dir = Path(CONFIG['output_dir'])
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / 'config.json', 'w') as f:
        json.dump(CONFIG, f, indent=2)

    print("\n[2/6] Loading test corpus...")
    all_documents = load_documents(CONFIG['corpus_path'])
    print(f"Loaded {len(all_documents)} documents")

    print("\n[3/6] Initializing embedding generator...")
    embedding_gen = get_embedding_generator(
        CONFIG['embedding_type'],
        model_name=CONFIG['embedding_model'],
        dimension=384
    )

    print("\n[4/6] Initializing FAISS...")
    benchmark = FAISSRAGBenchmark(
        db_config=CONFIG['faiss_config'],
        embedding_generator=embedding_gen,
        chunk_size=CONFIG['chunk_sizes'][0],
        chunk_overlap=CONFIG['chunk_overlap'],
        chunk_strategy=CONFIG['chunk_strategy']
    )
    benchmark.connect()

    print("\n[5/6] Running ingestion experiments...")
    print(f"Configurations to test: {len(CONFIG['chunk_sizes'])} chunk sizes × "
          f"{len(CONFIG['batch_sizes'])} batch sizes × "
          f"{len(CONFIG['doc_counts'])} doc counts × "
          f"{CONFIG['n_runs']} runs")

    all_results = []
    total_experiments = (len(CONFIG['chunk_sizes']) * len(CONFIG['batch_sizes']) *
                         len(CONFIG['doc_counts']) * CONFIG['n_runs'])
    experiment_num = 0

    for chunk_size in CONFIG['chunk_sizes']:
        for batch_size in CONFIG['batch_sizes']:
            for doc_count in CONFIG['doc_counts']:
                documents = all_documents[:doc_count]
                for run in range(CONFIG['n_runs']):
                    experiment_num += 1
                    print(f"\n  [{experiment_num}/{total_experiments}] "
                          f"chunk_size={chunk_size}, batch_size={batch_size}, "
                          f"docs={doc_count}, run={run+1}/{CONFIG['n_runs']}")
                    try:
                        result = run_ingestion_experiment(
                            benchmark, documents, chunk_size, batch_size, run+1
                        )
                        all_results.append(result)
                        print(f"    ✓ {result['num_chunks']} chunks in {result['total_time']:.2f}s "
                              f"({result['chunks_per_second']:.1f} chunks/s)")
                    except Exception as e:
                        print(f"    ✗ Failed: {e}")
                        continue

    print("\n[6/6] Exporting results...")
    df = pd.DataFrame(all_results)
    agg_df = df.groupby(['chunk_size', 'batch_size', 'num_docs']).agg({
        'num_chunks': 'mean',
        'total_size_bytes': 'mean',
        'parsing_time': 'mean',
        'embedding_time': 'mean',
        'insertion_time': 'mean',
        'total_time': 'mean',
        'chunks_per_second': 'mean',
        'bytes_per_second': 'mean',
        'docs_per_second': 'mean'
    }).reset_index()

    with open(output_dir / 'results.json', 'w') as f:
        json.dump({
            'config': CONFIG,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_experiments': len(all_results),
            'raw_results': all_results,
            'aggregated_results': agg_df.to_dict('records')
        }, f, indent=2, default=str)
    df.to_csv(output_dir / 'results.csv', index=False)
    print(f"✅ Results saved to: {output_dir}")

    print("\nGenerating visualizations...")
    generate_plots(agg_df, output_dir)

    print("\n" + "="*70)
    print("INGESTION BENCHMARK COMPLETE (FAISS)")
    print("="*70)
    print(f"\n📁 Results: {output_dir}")
    print(f"📊 Plots: {output_dir}/*.png")
    return 0


def generate_plots(df: pd.DataFrame, output_dir: Path):
    df_full = df[df['num_docs'] == 20]
    if df_full.empty:
        df_full = df[df['num_docs'] == df['num_docs'].max()]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    ax = axes[0, 0]
    for batch_size in sorted(df_full['batch_size'].unique()):
        data = df_full[df_full['batch_size'] == batch_size]
        ax.plot(data['chunk_size'], data['total_time'], marker='o', label=f'Batch={batch_size}', linewidth=2)
    ax.set_xlabel('Chunk Size (characters)'); ax.set_ylabel('Total Ingestion Time (s)'); ax.set_title('Ingestion Time vs Chunk Size')
    ax.legend(); ax.grid(True, alpha=0.3)

    ax = axes[0, 1]
    for batch_size in sorted(df_full['batch_size'].unique()):
        data = df_full[df_full['batch_size'] == batch_size]
        ax.plot(data['chunk_size'], data['chunks_per_second'], marker='s', label=f'Batch={batch_size}', linewidth=2)
    ax.set_xlabel('Chunk Size (characters)'); ax.set_ylabel('Throughput (chunks/s)'); ax.set_title('Throughput vs Chunk Size')
    ax.legend(); ax.grid(True, alpha=0.3)

    ax = axes[1, 0]
    chunk_size = 512; batch_size = 100
    data = df_full[(df_full['chunk_size'] == chunk_size) & (df_full['batch_size'] == batch_size)]
    if not data.empty:
        phases = ['parsing_time', 'embedding_time', 'insertion_time']
        values = [data[phase].values[0] for phase in phases]
        labels = ['Parsing', 'Embedding', 'Insertion']
        colors = ['#2E86AB', '#A23B72', '#F18F01']
        ax.bar(labels, values, color=colors, alpha=0.8)
        ax.set_ylabel('Time (seconds)'); ax.set_title(f'Ingestion Phase Breakdown\n(chunk={chunk_size}, batch={batch_size})')
        ax.grid(True, alpha=0.3, axis='y')

    ax = axes[1, 1]
    chunk_size = 512
    data = df_full[df_full['chunk_size'] == chunk_size]
    ax.plot(data['batch_size'], data['total_time'], marker='o', linewidth=2, markersize=8, color='#2E86AB')
    ax.set_xlabel('Batch Size'); ax.set_ylabel('Total Ingestion Time (s)'); ax.set_title(f'Batch Size Impact\n(chunk_size={chunk_size})')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plot_file = output_dir / 'ingestion_performance.png'
    plt.savefig(plot_file, dpi=300, bbox_inches='tight')
    print(f"✅ Main plot saved to: {plot_file}")
    plt.close()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    chunk_size = 512; batch_size = 100
    data = df[(df['chunk_size'] == chunk_size) & (df['batch_size'] == batch_size)]
    ax1.plot(data['num_docs'], data['total_time'], marker='o', linewidth=2, markersize=8, color='#2E86AB')
    ax1.set_xlabel('Number of Documents'); ax1.set_ylabel('Total Ingestion Time (s)'); ax1.set_title('Scaling with Document Count')
    ax1.grid(True, alpha=0.3)
    ax2.plot(data['num_docs'], data['num_chunks'], marker='s', linewidth=2, markersize=8, color='#A23B72')
    ax2.set_xlabel('Number of Documents'); ax2.set_ylabel('Number of Chunks Created'); ax2.set_title('Chunks vs Documents')
    ax2.grid(True, alpha=0.3)
    plt.tight_layout()
    plot_file = output_dir / 'scaling_performance.png'
    plt.savefig(plot_file, dpi=300, bbox_inches='tight')
    print(f"✅ Scaling plot saved to: {plot_file}")
    plt.close()

    fig, ax = plt.subplots(figsize=(10, 8))
    pivot = df_full.pivot_table(values='total_time', index='chunk_size', columns='batch_size')
    im = ax.imshow(pivot.values, cmap='YlOrRd', aspect='auto')
    ax.set_xticks(range(len(pivot.columns))); ax.set_yticks(range(len(pivot.index)))
    ax.set_xticklabels(pivot.columns); ax.set_yticklabels(pivot.index)
    ax.set_xlabel('Batch Size'); ax.set_ylabel('Chunk Size'); ax.set_title('Ingestion Time Heatmap (seconds)')
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            ax.text(j, i, f'{pivot.values[i, j]:.2f}', ha="center", va="center", color="black", fontsize=9)
    plt.colorbar(im, ax=ax, label='Time (seconds)')
    plt.tight_layout()
    plot_file = output_dir / 'ingestion_heatmap.png'
    plt.savefig(plot_file, dpi=300, bbox_inches='tight')
    print(f"✅ Heatmap saved to: {plot_file}")
    plt.close()


if __name__ == '__main__':
    sys.exit(main())
