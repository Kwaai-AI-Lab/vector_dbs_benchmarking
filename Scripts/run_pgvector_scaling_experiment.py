#!/usr/bin/env python3
"""
Run scaling benchmarks for pgvector with both IVFFlat and HNSW indices.

This script tests pgvector performance across multiple corpus sizes with N=3 runs.
"""

import os
import sys
import json
import subprocess
import time
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Corpus sizes to benchmark
CORPUS_CONFIGS = [
    {'name': 'baseline', 'path': 'Data/test_corpus/documents', 'expected_chunks': 175},
    {'name': '1k', 'path': 'Data/test_corpus/corpus_sizes/corpus_1k', 'expected_chunks': 5562},
    {'name': '10k', 'path': 'Data/test_corpus/corpus_sizes/corpus_10k', 'expected_chunks': 69903},
    {'name': '50k', 'path': 'Data/test_corpus/corpus_sizes/corpus_50k', 'expected_chunks': 345046},
]

INDEX_TYPES = ['ivfflat', 'hnsw']
N_RUNS = 3

def check_corpus_exists(corpus_path):
    """Check if corpus directory exists and has files."""
    path = Path(corpus_path)
    if not path.exists():
        return False
    files = list(path.glob('*.xml')) + list(path.glob('*.txt'))
    return len(files) > 0

def run_single_benchmark(corpus_name, corpus_path, index_type, output_dir, run_number):
    """Run a single benchmark iteration."""
    print(f"\n{'='*70}")
    print(f"Running pgvector ({index_type}) benchmark: {corpus_name} (Run {run_number})")
    print(f"Corpus path: {corpus_path}")
    print(f"Output dir: {output_dir}")
    print(f"{'='*70}\n")

    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    script = 'Scripts/run_pgvector_benchmark.py'

    # Build command
    cmd = [
        'python', script,
        '--corpus', corpus_path,
        '--output', output_dir,
        '--index-type', index_type,
    ]

    # Run benchmark
    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=7200  # 2 hour timeout
        )

        end_time = time.time()
        duration = end_time - start_time

        # Save output
        log_file = Path(output_dir) / 'benchmark.log'
        with open(log_file, 'w') as f:
            f.write(f"Command: {' '.join(cmd)}\n")
            f.write(f"Duration: {duration:.2f}s\n")
            f.write(f"Return code: {result.returncode}\n\n")
            f.write("STDOUT:\n")
            f.write(result.stdout)
            f.write("\n\nSTDERR:\n")
            f.write(result.stderr)

        if result.returncode == 0:
            print(f"✅ Benchmark completed successfully in {duration/60:.1f} minutes")

            # Load results
            results_file = Path(output_dir) / 'results.json'
            if results_file.exists():
                with open(results_file, 'r') as f:
                    results = json.load(f)
                return True, results
            else:
                print(f"⚠️  Results file not found: {results_file}")
                return True, None
        else:
            print(f"❌ Benchmark failed with return code {result.returncode}")
            print(f"See log: {log_file}")
            return False, None

    except subprocess.TimeoutExpired:
        print(f"❌ Benchmark timed out after 2 hours")
        return False, None
    except Exception as e:
        print(f"❌ Benchmark failed with error: {e}")
        return False, None

def extract_metrics(results: Dict[str, Any]) -> Dict[str, float]:
    """Extract key metrics from a single run's results."""
    metrics = {}

    # Ingestion metrics
    if 'ingestion' in results:
        metrics['ingestion_time'] = results['ingestion'].get('total_time_sec', None)
        metrics['num_chunks'] = results['ingestion'].get('num_chunks', None)
        metrics['embedding_time'] = results['ingestion'].get('embedding_time_sec', None)
        metrics['insertion_time'] = results['ingestion'].get('insertion_time_sec', None)

    # Query metrics (use top-k=3 as standard)
    if 'query_results' in results:
        query_data = results['query_results']

        # Find top-k=3 result
        q = None
        for item in query_data:
            if item.get('top_k') == 3:
                q = item
                break

        if q:
            metrics['avg_latency_ms'] = q.get('avg_latency_ms', None)
            metrics['p50_latency_ms'] = q.get('p50_latency_ms', None)
            metrics['p95_latency_ms'] = q.get('p95_latency_ms', None)
            metrics['queries_per_second'] = q.get('queries_per_second', None)
            metrics['avg_similarity'] = q.get('avg_similarity', None)
            metrics['avg_top1_similarity'] = q.get('avg_top1_similarity', None)

            # Resource metrics
            if 'resource_metrics' in q and q['resource_metrics']:
                rm = q['resource_metrics']
                if 'cpu' in rm:
                    metrics['cpu_avg'] = rm['cpu'].get('avg', None)
                if 'memory' in rm:
                    metrics['memory_avg_mb'] = rm['memory'].get('avg_mb', None)

    return metrics

def aggregate_runs(all_metrics: List[Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    """Aggregate metrics across N runs (mean and std)."""
    if not all_metrics:
        return {}

    aggregated = {}

    # Get all metric keys
    metric_keys = set()
    for m in all_metrics:
        metric_keys.update(m.keys())

    # Calculate mean and std for each metric
    for key in metric_keys:
        values = [m[key] for m in all_metrics if key in m and m[key] is not None]
        if values:
            aggregated[key] = {
                'mean': float(np.mean(values)),
                'std': float(np.std(values)),
                'min': float(np.min(values)),
                'max': float(np.max(values)),
                'cv': float(np.std(values) / np.mean(values) * 100) if np.mean(values) > 0 else 0
            }
        else:
            aggregated[key] = None

    return aggregated

def main():
    """Run scaling experiment."""

    print("="*70)
    print("pgvector Scaling Experiment (N=3)")
    print("Testing both IVFFlat and HNSW indices")
    print("="*70)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Run experiments for each index type
    for index_type in INDEX_TYPES:
        print(f"\n\n{'#'*70}")
        print(f"# INDEX TYPE: {index_type.upper()}")
        print(f"{'#'*70}\n")

        base_output_dir = f'results/pgvector_{index_type}_scaling_n3'
        Path(base_output_dir).mkdir(parents=True, exist_ok=True)

        all_corpus_results = {}

        for corpus_config in CORPUS_CONFIGS:
            corpus_name = corpus_config['name']
            corpus_path = corpus_config['path']

            print(f"\n{'='*70}")
            print(f"Corpus: {corpus_name} ({corpus_path})")
            print(f"{'='*70}")

            # Check if corpus exists
            if not check_corpus_exists(corpus_path):
                print(f"⚠️  Corpus not found: {corpus_path}")
                print(f"Skipping {corpus_name}")
                continue

            # Run N times
            run_results = []
            for run_num in range(1, N_RUNS + 1):
                output_dir = f'{base_output_dir}/corpus_{corpus_name}/run_{run_num}'

                success, results = run_single_benchmark(
                    corpus_name, corpus_path, index_type, output_dir, run_num
                )

                if success and results:
                    metrics = extract_metrics(results)
                    run_results.append(metrics)

                    print(f"\nRun {run_num} metrics:")
                    print(f"  Ingestion time: {metrics.get('ingestion_time', 'N/A'):.2f}s")
                    print(f"  Chunks: {metrics.get('num_chunks', 'N/A')}")
                    print(f"  Avg latency: {metrics.get('avg_latency_ms', 'N/A'):.2f}ms")
                    print(f"  QPS: {metrics.get('queries_per_second', 'N/A'):.2f}")
                else:
                    print(f"⚠️  Run {run_num} failed")

            # Aggregate results for this corpus
            if run_results:
                aggregated = aggregate_runs(run_results)
                all_corpus_results[corpus_name] = {
                    'n_runs': len(run_results),
                    'aggregated_metrics': aggregated,
                    'raw_runs': run_results
                }

                print(f"\n{'='*70}")
                print(f"Aggregated results for {corpus_name} (N={len(run_results)}):")
                print(f"{'='*70}")
                if aggregated.get('num_chunks'):
                    print(f"  Chunks: {aggregated['num_chunks']['mean']:.0f}")
                if aggregated.get('ingestion_time'):
                    ing = aggregated['ingestion_time']
                    print(f"  Ingestion time: {ing['mean']:.2f}s ± {ing['std']:.2f}s (CV={ing['cv']:.1f}%)")
                if aggregated.get('avg_latency_ms'):
                    lat = aggregated['avg_latency_ms']
                    print(f"  Avg latency: {lat['mean']:.2f}ms ± {lat['std']:.2f}ms (CV={lat['cv']:.1f}%)")
                if aggregated.get('queries_per_second'):
                    qps = aggregated['queries_per_second']
                    print(f"  QPS: {qps['mean']:.2f} ± {qps['std']:.2f} (CV={qps['cv']:.1f}%)")

        # Save aggregated results
        summary_file = Path(base_output_dir) / 'aggregated_results.json'
        with open(summary_file, 'w') as f:
            json.dump({
                'database': 'pgvector',
                'index_type': index_type,
                'timestamp': timestamp,
                'n_runs': N_RUNS,
                'results_by_corpus': all_corpus_results
            }, f, indent=2)

        print(f"\n✅ Results saved to: {summary_file}")

    print("\n" + "="*70)
    print("Scaling experiment complete!")
    print("="*70)
    print(f"\nResults directories:")
    for index_type in INDEX_TYPES:
        print(f"  - results/pgvector_{index_type}_scaling_n3/")

if __name__ == '__main__':
    main()
