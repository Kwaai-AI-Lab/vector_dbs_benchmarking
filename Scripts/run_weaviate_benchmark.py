#!/usr/bin/env python3
"""
Complete end-to-end benchmark for Weaviate.
Mirrors the Qdrant/pgvector workflows and writes artifacts to the results folder.
"""

import json
import time
import sys
from pathlib import Path
from typing import List
import matplotlib.pyplot as plt
import numpy as np
import os
import requests

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.vector_dbs.weaviate_adapter import WeaviateRAGBenchmark
from src.embeddings.embedding_generator import get_embedding_generator
from src.parsers.document_parser import DocumentParser, Document


# Configuration
CONFIG = {
    'corpus_path': 'Data/test_corpus/documents',
    'test_cases_path': 'Data/test_corpus/test_cases.json',
    'output_dir': 'results/weaviate_experiment_001',
    'weaviate_config': {
        'host': os.getenv('WEAVIATE_HOST', 'localhost'),
        'port': int(os.getenv('WEAVIATE_PORT', '8081')),
        'class_name': 'RAGBenchmark'
    },
    'embedding_model': 'sentence-transformers/all-MiniLM-L6-v2',
    'embedding_type': 'sentence-transformers',
    'chunk_size': 512,
    'chunk_overlap': 50,
    'chunk_strategy': 'fixed',
    'top_k_values': [1, 3, 5, 10, 20],
    'batch_size': 100
}


def load_documents(corpus_path: str) -> List[Document]:
    print(f"\nLoading documents from {corpus_path}...")
    parser = DocumentParser()
    documents = []
    corpus_dir = Path(corpus_path)
    if not corpus_dir.exists():
        raise FileNotFoundError(f"Corpus directory not found: {corpus_path}")
    txt_files = list(corpus_dir.glob("*.txt"))
    if not txt_files:
        raise FileNotFoundError(f"No .txt files found in {corpus_path}")
    for txt_file in sorted(txt_files):
        try:
            doc = parser.parse_txt(str(txt_file))
            documents.append(doc)
            print(f"  Loaded: {txt_file.name} ({len(doc.content)} chars)")
        except Exception as e:
            print(f"  Error loading {txt_file.name}: {e}")
    print(f"Loaded {len(documents)} documents")
    return documents


def main():
    print("="*70)
    print("Weaviate Vector Database Benchmark")
    print("="*70)

    # Output directory
    print("\n[1/7] Setting up output directory...")
    output_dir = Path(CONFIG['output_dir'])
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")
    with open(output_dir / 'config.json', 'w') as f:
        json.dump(CONFIG, f, indent=2)

    # Load data
    print("\n[2/7] Loading test data...")
    documents = load_documents(CONFIG['corpus_path'])
    test_cases_path = Path(CONFIG['test_cases_path'])
    if not test_cases_path.exists():
        raise FileNotFoundError(f"Test cases file not found: {CONFIG['test_cases_path']}")
    with open(test_cases_path) as f:
        test_cases = json.load(f)
    print(f"Loaded {len(test_cases)} test cases")

    # Embeddings
    print("\n[3/7] Initializing embedding generator...")
    print(f"Model: {CONFIG['embedding_model']}")
    print(f"Type: {CONFIG['embedding_type']}")
    embedding_gen = get_embedding_generator(
        CONFIG['embedding_type'],
        model_name=CONFIG['embedding_model'],
        dimension=384
    )

    # Weaviate benchmark init
    print("\n[4/7] Initializing Weaviate...")
    wc = CONFIG['weaviate_config']
    print(f"Host: {wc['host']}:{wc['port']} class={wc['class_name']}")

    # Preflight: verify the HTTP readiness endpoint to catch port/protocol mismatches
    try:
        url = f"http://{wc['host']}:{wc['port']}/v1/.well-known/ready"
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            print(f"⚠️  Weaviate readiness check returned {resp.status_code} from {url}")
            print("   If another service is bound to this port, set WEAVIATE_PORT to the correct host port.")
            return 1
    except Exception as e:
        print(f"⚠️  Readiness check failed at http://{wc['host']}:{wc['port']}: {e}")
        print("   Ensure docker port mapping matches this host:port, or export WEAVIATE_PORT accordingly.")
        return 1
    benchmark = WeaviateRAGBenchmark(
        db_config=CONFIG['weaviate_config'],
        embedding_generator=embedding_gen,
        chunk_size=CONFIG['chunk_size'],
        chunk_overlap=CONFIG['chunk_overlap'],
        chunk_strategy=CONFIG['chunk_strategy']
    )

    # Connect
    try:
        benchmark.connect()
    except Exception as e:
        print(f"\n❌ Failed to connect to Weaviate: {e}")
        print("\nMake sure Weaviate is running:")
        print("  docker compose up -d weaviate")
        return 1

    # Create class/collection
    print(f"\n[5/8] Creating collection...")
    try:
        benchmark.create_collection(embedding_gen.dimension)
        print(f"✅ Class '{wc['class_name']}' created")
    except Exception as e:
        print(f"❌ Collection creation failed: {e}")
        benchmark.disconnect()
        return 1

    # Ingest
    print(f"\n[6/8] Ingesting {len(documents)} documents...")
    print(f"Chunk size: {CONFIG['chunk_size']}, Overlap: {CONFIG['chunk_overlap']}")
    print(f"Strategy: {CONFIG['chunk_strategy']}")
    ingest_start = time.time()
    try:
        ingest_result = benchmark.ingest_documents(documents, batch_size=CONFIG['batch_size'])
        ingest_time = time.time() - ingest_start
        num_docs = len(documents)
        num_chunks = getattr(ingest_result, 'num_chunks', 0)
        parsing_time = getattr(ingest_result, 'parsing_time', getattr(ingest_result, 'total_parsing_time', 0))
        embedding_time = getattr(ingest_result, 'embedding_time', getattr(ingest_result, 'total_embedding_time', 0))
        insertion_time = getattr(ingest_result, 'insertion_time', getattr(ingest_result, 'total_insertion_time', 0))
        print(f"✅ Ingestion completed in {ingest_time:.2f}s")
        print(f"   Documents: {num_docs}")
        print(f"   Chunks created: {num_chunks}")
        print(f"   Parsing time: {parsing_time:.2f}s")
        print(f"   Embedding time: {embedding_time:.2f}s")
        print(f"   Insertion time: {insertion_time:.2f}s")
    except Exception as e:
        print(f"❌ Ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        benchmark.disconnect()
        return 1

    # Queries across top-k
    print(f"\n[7/8] Running query latency benchmark...")
    print(f"Test cases: {len(test_cases)}")
    print(f"Top-k values: {CONFIG['top_k_values']}")
    results = []
    for top_k in CONFIG['top_k_values']:
        print(f"\n  Testing top_k={top_k}...")
        latencies = []
        for i, tc in enumerate(test_cases, 1):
            try:
                start = time.time()
                query_embedding = embedding_gen.generate_embedding(tc['query'])
                result_ids, query_time = benchmark.query(query_embedding, top_k=top_k)
                latency = (time.time() - start) * 1000
                latencies.append(latency)
                if i % 5 == 0 or i == len(test_cases):
                    print(f"    Query {i}/{len(test_cases)}: {latency:.2f}ms, {len(result_ids)} results")
            except Exception as e:
                print(f"    Query {i} failed: {e}")
                import traceback
                if i == 1:
                    traceback.print_exc()
                continue

        if latencies:
            latencies_sorted = sorted(latencies)
            avg_latency = np.mean(latencies)
            p50_latency = latencies_sorted[len(latencies)//2]
            p95_latency = latencies_sorted[int(len(latencies)*0.95)]
            p99_latency = latencies_sorted[int(len(latencies)*0.99)]
            min_latency = min(latencies)
            max_latency = max(latencies)

            result = {
                'top_k': top_k,
                'num_queries': len(latencies),
                'avg_latency_ms': float(avg_latency),
                'p50_latency_ms': float(p50_latency),
                'p95_latency_ms': float(p95_latency),
                'p99_latency_ms': float(p99_latency),
                'min_latency_ms': float(min_latency),
                'max_latency_ms': float(max_latency),
                'queries_per_second': 1000.0 / avg_latency if avg_latency > 0 else 0
            }
            results.append(result)
            print(f"    Avg: {avg_latency:.2f}ms, P50: {p50_latency:.2f}ms, P95: {p95_latency:.2f}ms, QPS: {result['queries_per_second']:.2f}")

    # Disconnect
    benchmark.disconnect()

    if not results:
        print("\n❌ No successful queries! Check Weaviate connection and data.")
        return 1

    # Export and plot
    print(f"\n[8/8] Exporting results and generating visualizations...")
    results_data = {
        'database': 'weaviate',
        'config': CONFIG,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'ingestion': {
            'total_time_sec': ingest_time,
            'num_documents': num_docs,
            'num_chunks': num_chunks,
            'parsing_time_sec': parsing_time,
            'embedding_time_sec': embedding_time,
            'insertion_time_sec': insertion_time
        },
        'query_results': results
    }
    results_file = output_dir / 'results.json'
    with open(results_file, 'w') as f:
        json.dump(results_data, f, indent=2)
    print(f"✅ Results saved to: {results_file}")

    top_k_vals = [r['top_k'] for r in results]
    avg_latencies = [r['avg_latency_ms'] for r in results]
    p95_latencies = [r['p95_latency_ms'] for r in results]
    qps_values = [r['queries_per_second'] for r in results]

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    ax1 = axes[0]
    ax1.plot(top_k_vals, avg_latencies, marker='o', linewidth=2, markersize=8, label='Average', color='#2E86AB')
    ax1.plot(top_k_vals, p95_latencies, marker='s', linewidth=2, markersize=6, label='P95', color='#A23B72', linestyle='--')
    ax1.set_xlabel('Top-K Value', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Query Latency (ms)', fontsize=11, fontweight='bold')
    ax1.set_title('Query Latency vs Top-K', fontsize=12, fontweight='bold')
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.legend(fontsize=9)
    ax1.set_xticks(top_k_vals)

    ax2 = axes[1]
    ax2.plot(top_k_vals, qps_values, marker='o', linewidth=2, markersize=8, color='#F18F01')
    ax2.set_xlabel('Top-K Value', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Queries Per Second', fontsize=11, fontweight='bold')
    ax2.set_title('Throughput vs Top-K', fontsize=12, fontweight='bold')
    ax2.grid(True, alpha=0.3, linestyle='--')
    ax2.set_xticks(top_k_vals)

    ax3 = axes[2]
    ax3.bar([str(k) for k in top_k_vals], avg_latencies, color='#06A77D', alpha=0.8)
    ax3.set_xlabel('Top-K', fontsize=11, fontweight='bold')
    ax3.set_ylabel('Average Latency (ms)', fontsize=11, fontweight='bold')
    ax3.set_title('Average Latency by Top-K', fontsize=12, fontweight='bold')
    ax3.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plot_file = output_dir / 'performance_quality.png'
    plt.savefig(plot_file, dpi=300, bbox_inches='tight')
    print(f"✅ Performance plot saved to: {plot_file}")

    print("\n" + "="*70)
    print("BENCHMARK COMPLETE (Weaviate)")
    print("="*70)
    print(f"\nDatabase: weaviate")
    print(f"Documents: {num_docs}")
    print(f"Chunks: {num_chunks}")
    print(f"Ingestion time: {ingest_time:.2f}s")
    print(f"\nQuery Performance:")
    print(f"{'Top-K':<8} {'Avg (ms)':<12} {'P95 (ms)':<12} {'QPS':<10}")
    print("-" * 50)
    for r in results:
        print(f"{r['top_k']:<8} {r['avg_latency_ms']:<12.2f} {r['p95_latency_ms']:<12.2f} {r['queries_per_second']:<10.2f}")

    print(f"\n📊 Results: {results_file}")
    print(f"📈 Plot: {plot_file}")

    return 0


if __name__ == '__main__':
    sys.exit(main())


