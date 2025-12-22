#!/usr/bin/env python3
"""
Run N=3 scaling benchmarks across multiple corpus sizes for statistical rigor.

This script runs each benchmark 3 times and aggregates results with mean/std.

Usage:
    python run_scaling_experiment_n3.py --database chroma
    python run_scaling_experiment_n3.py --database qdrant --runs 5
"""

import os
import sys
import json
import subprocess
import time
import argparse
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Corpus sizes to benchmark (optimized: 5 sizes covering 175 -> 2.2M chunks)
CORPUS_CONFIGS = [
    {'name': 'baseline', 'path': 'Data/test_corpus/documents', 'expected_chunks': 175},
    {'name': '1k', 'path': 'Data/test_corpus/corpus_sizes/corpus_1k', 'expected_chunks': 5562},
    {'name': '10k', 'path': 'Data/test_corpus/corpus_sizes/corpus_10k', 'expected_chunks': 69903},
    {'name': '50k', 'path': 'Data/test_corpus/corpus_sizes/corpus_50k', 'expected_chunks': 345046},
    {'name': 'full', 'path': 'Data/test_corpus/corpus_sizes/corpus_full', 'expected_chunks': 2249072},
]

# Database benchmark scripts
DATABASE_SCRIPTS = {
    'faiss': 'Scripts/run_faiss_benchmark.py',
    'chroma': 'Scripts/run_chroma_benchmark.py',
    'qdrant': 'Scripts/run_qdrant_benchmark.py',
    'weaviate': 'Scripts/run_weaviate_benchmark.py',
    'milvus': 'Scripts/run_milvus_benchmark.py',
    'opensearch': 'Scripts/run_opensearch_benchmark.py',
}

def check_corpus_exists(corpus_path):
    """Check if corpus directory exists and has files."""
    path = Path(corpus_path)
    if not path.exists():
        return False
    files = list(path.glob('*.xml')) + list(path.glob('*.txt'))
    return len(files) > 0

def run_single_benchmark(database, corpus_name, corpus_path, output_dir, run_number):
    """Run a single benchmark iteration."""
    print(f"\n{'='*70}")
    print(f"Running {database.upper()} benchmark: {corpus_name} (Run {run_number})")
    print(f"Corpus path: {corpus_path}")
    print(f"Output dir: {output_dir}")
    print(f"{'='*70}\n")

    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Get benchmark script
    script = DATABASE_SCRIPTS.get(database)
    if not script:
        print(f"❌ Unknown database: {database}")
        return False, None

    if not Path(script).exists():
        print(f"❌ Benchmark script not found: {script}")
        return False, None

    # Build command
    cmd = [
        'python', script,
        '--corpus', corpus_path,
        '--output', output_dir,
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

    # Query metrics (use top-k=3 as standard)
    if 'query_results' in results:
        query_data = results['query_results']

        # Handle both list and dict formats
        q = None
        if isinstance(query_data, list):
            for item in query_data:
                if item.get('top_k') == 3:
                    q = item
                    break
            if not q and query_data:
                q = query_data[0]
        elif isinstance(query_data, dict):
            if '3' in query_data:
                q = query_data['3']
            elif 'top_k_3' in query_data:
                q = query_data['top_k_3']
            else:
                q = list(query_data.values())[0] if query_data else {}

        if q:
            metrics['p50_latency_ms'] = q.get('p50_latency_ms', q.get('avg_latency_ms', None))
            metrics['p95_latency_ms'] = q.get('p95_latency_ms', None)
            metrics['queries_per_second'] = q.get('queries_per_second', None)

    return metrics

def aggregate_results(all_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate N results with mean and std."""
    if not all_results:
        return None

    # Extract metrics from each run
    metrics_list = [extract_metrics(r) for r in all_results]

    # Calculate statistics for each metric
    aggregated = {
        'n_runs': len(all_results),
        'individual_runs': all_results,
        'statistics': {}
    }

    # Get all metric keys
    all_keys = set()
    for m in metrics_list:
        all_keys.update(m.keys())

    # Calculate mean and std for each metric
    for key in all_keys:
        values = [m.get(key) for m in metrics_list if m.get(key) is not None]

        if values:
            aggregated['statistics'][key] = {
                'mean': float(np.mean(values)),
                'std': float(np.std(values)),
                'min': float(np.min(values)),
                'max': float(np.max(values)),
                'values': values,
                'n': len(values)
            }

    # Add representative result structure (using mean values)
    rep_result = all_results[0].copy()  # Use first run as template

    # Update with mean values
    if 'ingestion' in rep_result:
        if 'total_time_sec' in aggregated['statistics']:
            rep_result['ingestion']['total_time_sec'] = aggregated['statistics']['total_time_sec']['mean']

    if 'query_results' in rep_result:
        query_data = rep_result['query_results']

        # Update the appropriate query result entry
        if isinstance(query_data, list):
            for item in query_data:
                if item.get('top_k') == 3:
                    if 'p50_latency_ms' in aggregated['statistics']:
                        item['p50_latency_ms'] = aggregated['statistics']['p50_latency_ms']['mean']
                    if 'p95_latency_ms' in aggregated['statistics']:
                        item['p95_latency_ms'] = aggregated['statistics']['p95_latency_ms']['mean']
                    if 'queries_per_second' in aggregated['statistics']:
                        item['queries_per_second'] = aggregated['statistics']['queries_per_second']['mean']
        elif isinstance(query_data, dict):
            for key in ['3', 'top_k_3']:
                if key in query_data:
                    if 'p50_latency_ms' in aggregated['statistics']:
                        query_data[key]['p50_latency_ms'] = aggregated['statistics']['p50_latency_ms']['mean']
                    if 'p95_latency_ms' in aggregated['statistics']:
                        query_data[key]['p95_latency_ms'] = aggregated['statistics']['p95_latency_ms']['mean']
                    if 'queries_per_second' in aggregated['statistics']:
                        query_data[key]['queries_per_second'] = aggregated['statistics']['queries_per_second']['mean']

    aggregated['mean_result'] = rep_result

    return aggregated

def run_n_benchmarks(database, corpus_name, corpus_path, base_output_dir, n_runs):
    """Run N iterations of the same benchmark and aggregate results."""
    print(f"\n{'#'*70}")
    print(f"# Starting N={n_runs} benchmark for {corpus_name}")
    print(f"{'#'*70}\n")

    all_results = []
    successful_runs = 0

    for run_num in range(1, n_runs + 1):
        run_output_dir = Path(base_output_dir) / f"run_{run_num}"
        success, results = run_single_benchmark(
            database, corpus_name, corpus_path, str(run_output_dir), run_num
        )

        if success and results:
            all_results.append(results)
            successful_runs += 1
        else:
            print(f"⚠️  Run {run_num} failed or produced no results")

    print(f"\n{'='*70}")
    print(f"Completed {successful_runs}/{n_runs} successful runs for {corpus_name}")
    print(f"{'='*70}\n")

    if successful_runs == 0:
        return None

    # Aggregate results
    aggregated = aggregate_results(all_results)

    # Save aggregated results
    agg_file = Path(base_output_dir) / 'aggregated_results.json'
    with open(agg_file, 'w') as f:
        json.dump(aggregated, f, indent=2)

    print(f"✅ Saved aggregated results: {agg_file}")

    # Print summary statistics
    if aggregated and 'statistics' in aggregated:
        print(f"\n📊 Summary Statistics for {corpus_name}:")
        stats = aggregated['statistics']

        if 'p50_latency_ms' in stats:
            s = stats['p50_latency_ms']
            print(f"  P50 Latency: {s['mean']:.2f} ± {s['std']:.2f} ms (n={s['n']})")

        if 'queries_per_second' in stats:
            s = stats['queries_per_second']
            print(f"  Throughput:  {s['mean']:.1f} ± {s['std']:.1f} QPS (n={s['n']})")

        if 'ingestion_time' in stats:
            s = stats['ingestion_time']
            print(f"  Ingestion:   {s['mean']:.1f} ± {s['std']:.1f} sec (n={s['n']})")

    return aggregated

def main():
    parser = argparse.ArgumentParser(description='Run N=3 scaling experiment for statistical rigor')
    parser.add_argument('--database', required=True, choices=list(DATABASE_SCRIPTS.keys()),
                       help='Database to benchmark')
    parser.add_argument('--runs', type=int, default=3,
                       help='Number of runs per corpus size (default: 3)')
    parser.add_argument('--corpus', type=str, default=None,
                       help='Run only specific corpus (baseline, 1k, 10k, 50k, full)')
    args = parser.parse_args()

    database = args.database
    n_runs = args.runs

    print("="*70)
    print(f"{database.upper()} N={n_runs} Scaling Experiment")
    print("="*70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Statistical rigor: {n_runs} runs per corpus size")

    # Create results directory
    results_dir = Path(f'results/{database}_scaling_n{n_runs}')
    results_dir.mkdir(parents=True, exist_ok=True)

    # Track results
    experiment_results = {
        'database': database,
        'n_runs': n_runs,
        'start_time': datetime.now().isoformat(),
        'benchmarks': []
    }

    # Determine which corpuses to run
    if args.corpus:
        selected_corpuses = [c for c in CORPUS_CONFIGS if c['name'] == args.corpus]
        if not selected_corpuses:
            print(f"❌ Unknown corpus: {args.corpus}")
            return 1
    else:
        # Check which corpuses exist
        selected_corpuses = []
        for config in CORPUS_CONFIGS:
            if check_corpus_exists(config['path']):
                selected_corpuses.append(config)
                print(f"✓ Found corpus: {config['name']} ({config['path']})")
            else:
                print(f"✗ Missing corpus: {config['name']} ({config['path']})")

    print(f"\nFound {len(selected_corpuses)} / {len(CORPUS_CONFIGS)} corpus datasets")

    if len(selected_corpuses) == 0:
        print("❌ No corpus datasets found. Run create_corpus_sizes.py first.")
        return 1

    print(f"\nProceeding with {len(selected_corpuses)} benchmarks × {n_runs} runs = {len(selected_corpuses) * n_runs} total runs")
    print(f"Estimated time: {len(selected_corpuses) * n_runs * 15} - {len(selected_corpuses) * n_runs * 30} minutes")

    # Run benchmarks
    for i, config in enumerate(selected_corpuses, 1):
        print(f"\n{'#'*70}")
        print(f"# [{i}/{len(selected_corpuses)}] Processing corpus: {config['name']}")
        print(f"{'#'*70}")

        corpus_output_dir = results_dir / f"corpus_{config['name']}"

        # Check if already completed
        agg_file = corpus_output_dir / 'aggregated_results.json'
        if agg_file.exists():
            print(f"⏭️  Aggregated results already exist, skipping...")
            with open(agg_file, 'r') as f:
                agg_data = json.load(f)
            experiment_results['benchmarks'].append({
                'name': config['name'],
                'path': config['path'],
                'status': 'skipped',
                'aggregated_file': str(agg_file)
            })
            continue

        # Run N benchmarks and aggregate
        aggregated = run_n_benchmarks(
            database, config['name'], config['path'],
            str(corpus_output_dir), n_runs
        )

        experiment_results['benchmarks'].append({
            'name': config['name'],
            'path': config['path'],
            'expected_chunks': config['expected_chunks'],
            'status': 'success' if aggregated else 'failed',
            'n_successful_runs': aggregated['n_runs'] if aggregated else 0,
            'output_dir': str(corpus_output_dir),
            'timestamp': datetime.now().isoformat()
        })

        # Save progress
        progress_file = results_dir / 'experiment_progress.json'
        with open(progress_file, 'w') as f:
            json.dump(experiment_results, f, indent=2)

    # Final summary
    experiment_results['end_time'] = datetime.now().isoformat()

    summary_file = results_dir / 'experiment_summary.json'
    with open(summary_file, 'w') as f:
        json.dump(experiment_results, f, indent=2)

    print("\n" + "="*70)
    print("EXPERIMENT COMPLETE")
    print("="*70)
    print(f"Database: {database}")
    print(f"N runs per corpus: {n_runs}")
    print(f"Results directory: {results_dir}")
    print(f"Summary file: {summary_file}")

    # Count successful benchmarks
    successful = sum(1 for b in experiment_results['benchmarks'] if b['status'] == 'success')
    print(f"\nCompleted: {successful}/{len(selected_corpuses)} corpus sizes")
    print(f"Total successful runs: {sum(b.get('n_successful_runs', 0) for b in experiment_results['benchmarks'])}")

    return 0

if __name__ == '__main__':
    sys.exit(main())
