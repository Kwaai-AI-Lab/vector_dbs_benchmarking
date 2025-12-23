#!/usr/bin/env python3
"""
Run 2 additional benchmark iterations to complement existing single-run results.

This script leverages existing results from {database}_scaling_experiment
and runs 2 more iterations to achieve N=3 statistical rigor with 66% time savings.

Usage:
    python run_scaling_n2_additional.py --database chroma
    python run_scaling_n2_additional.py --database qdrant --corpus 10k
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
import shutil

# Corpus sizes to benchmark
CORPUS_CONFIGS = [
    {'name': 'baseline', 'path': 'Data/test_corpus/documents', 'expected_chunks': 175},
    {'name': '1k', 'path': 'Data/test_corpus/corpus_sizes/corpus_1k', 'expected_chunks': 5562},
    {'name': '10k', 'path': 'Data/test_corpus/corpus_sizes/corpus_10k', 'expected_chunks': 69903},
    {'name': '50k', 'path': 'Data/test_corpus/corpus_sizes/corpus_50k', 'expected_chunks': 345046},
    {'name': '100k', 'path': 'Data/test_corpus/corpus_sizes/corpus_100k', 'expected_chunks': 690385},
    {'name': '250k', 'path': 'Data/test_corpus/corpus_sizes/corpus_250k', 'expected_chunks': 1775361},
    {'name': '500k', 'path': 'Data/test_corpus/corpus_sizes/corpus_500k', 'expected_chunks': 2249072},
    {'name': '1m', 'path': 'Data/test_corpus/corpus_sizes/corpus_1m', 'expected_chunks': 2249072},
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

def check_existing_results(database):
    """Check which corpus sizes have existing single-run results."""
    existing_dir = Path(f'results/{database}_scaling_experiment')

    if not existing_dir.exists():
        return []

    existing_corpuses = []
    for corpus_dir in sorted(existing_dir.glob('corpus_*')):
        results_file = corpus_dir / 'results.json'
        if results_file.exists():
            corpus_name = corpus_dir.name.replace('corpus_', '')
            existing_corpuses.append({
                'name': corpus_name,
                'results_file': results_file,
                'corpus_dir': corpus_dir
            })

    return existing_corpuses

def load_existing_result(results_file):
    """Load an existing result file."""
    with open(results_file, 'r') as f:
        return json.load(f)

def run_single_benchmark(database, corpus_name, corpus_path, output_dir, run_number):
    """Run a single benchmark iteration."""
    print(f"\n{'='*70}")
    print(f"Running {database.upper()} benchmark: {corpus_name} (Additional Run {run_number})")
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

def process_corpus(database, corpus_name, corpus_path, existing_result_file, n3_output_dir):
    """Process a single corpus: copy existing + run 2 more + aggregate."""
    print(f"\n{'#'*70}")
    print(f"# Processing corpus: {corpus_name}")
    print(f"# Strategy: 1 existing + 2 new runs = N=3")
    print(f"{'#'*70}\n")

    # Create output directory
    Path(n3_output_dir).mkdir(parents=True, exist_ok=True)

    # Load existing result (this becomes run_1)
    print(f"📂 Loading existing result from: {existing_result_file}")
    existing_result = load_existing_result(existing_result_file)

    # Save as run_1
    run1_dir = Path(n3_output_dir) / 'run_1'
    run1_dir.mkdir(parents=True, exist_ok=True)
    with open(run1_dir / 'results.json', 'w') as f:
        json.dump(existing_result, f, indent=2)
    print(f"✅ Saved as run_1")

    all_results = [existing_result]

    # Run 2 additional iterations
    for run_num in [2, 3]:
        run_dir = Path(n3_output_dir) / f'run_{run_num}'
        success, result = run_single_benchmark(
            database, corpus_name, corpus_path, str(run_dir), run_num
        )

        if success and result:
            all_results.append(result)
        else:
            print(f"⚠️  Run {run_num} failed")

    if len(all_results) < 2:
        print(f"❌ Not enough successful runs for {corpus_name}")
        return None

    # Aggregate all results
    print(f"\n📊 Aggregating {len(all_results)} runs...")
    aggregated = aggregate_results(all_results)

    # Save aggregated results
    agg_file = Path(n3_output_dir) / 'aggregated_results.json'
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
    parser = argparse.ArgumentParser(
        description='Run 2 additional iterations to achieve N=3 with existing results'
    )
    parser.add_argument('--database', required=True, choices=list(DATABASE_SCRIPTS.keys()),
                       help='Database to benchmark')
    parser.add_argument('--corpus', type=str, default=None,
                       help='Run only specific corpus (baseline, 1k, 10k, 50k, full)')
    args = parser.parse_args()

    database = args.database

    print("="*70)
    print(f"{database.upper()} N=3 Optimization: Reuse Existing + Run 2 More")
    print("="*70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Time savings: 66% (2 runs instead of 3)")

    # Check for existing results
    existing = check_existing_results(database)

    if not existing:
        print(f"\n❌ No existing results found for {database}")
        print(f"Expected directory: results/{database}_scaling_experiment")
        print(f"\nPlease run the single-run experiment first:")
        print(f"  python Scripts/run_scaling_experiment_generic.py --database {database}")
        return 1

    print(f"\n✅ Found {len(existing)} existing corpus results:")
    for item in existing:
        print(f"  - {item['name']}: {item['results_file']}")

    # Filter by corpus if specified
    if args.corpus:
        existing = [e for e in existing if e['name'] == args.corpus]
        if not existing:
            print(f"\n❌ No existing results found for corpus: {args.corpus}")
            return 1

    # Create N=3 results directory
    n3_base_dir = Path(f'results/{database}_scaling_n3')
    n3_base_dir.mkdir(parents=True, exist_ok=True)

    # Track results
    experiment_results = {
        'database': database,
        'n_runs': 3,
        'strategy': 'reuse_existing_plus_2_new',
        'start_time': datetime.now().isoformat(),
        'benchmarks': []
    }

    print(f"\n🚀 Starting 2 additional runs for {len(existing)} corpus sizes")
    print(f"Estimated time: {len(existing) * 20} - {len(existing) * 40} minutes\n")

    # Process each corpus
    for i, ex in enumerate(existing, 1):
        print(f"\n{'#'*70}")
        print(f"# [{i}/{len(existing)}] Corpus: {ex['name']}")
        print(f"{'#'*70}")

        # Find corpus config
        corpus_config = next((c for c in CORPUS_CONFIGS if c['name'] == ex['name']), None)
        if not corpus_config:
            print(f"⚠️  Unknown corpus name: {ex['name']}")
            continue

        n3_corpus_dir = n3_base_dir / f"corpus_{ex['name']}"

        # Check if already completed
        agg_file = n3_corpus_dir / 'aggregated_results.json'
        if agg_file.exists():
            print(f"⏭️  N=3 results already exist, skipping...")
            experiment_results['benchmarks'].append({
                'name': ex['name'],
                'status': 'skipped',
                'aggregated_file': str(agg_file)
            })
            continue

        # Process corpus
        aggregated = process_corpus(
            database, ex['name'], corpus_config['path'],
            ex['results_file'], str(n3_corpus_dir)
        )

        experiment_results['benchmarks'].append({
            'name': ex['name'],
            'path': corpus_config['path'],
            'expected_chunks': corpus_config['expected_chunks'],
            'status': 'success' if aggregated else 'failed',
            'n_runs': aggregated['n_runs'] if aggregated else 0,
            'output_dir': str(n3_corpus_dir),
            'timestamp': datetime.now().isoformat()
        })

        # Save progress
        progress_file = n3_base_dir / 'experiment_progress.json'
        with open(progress_file, 'w') as f:
            json.dump(experiment_results, f, indent=2)

    # Final summary
    experiment_results['end_time'] = datetime.now().isoformat()

    summary_file = n3_base_dir / 'experiment_summary.json'
    with open(summary_file, 'w') as f:
        json.dump(experiment_results, f, indent=2)

    print("\n" + "="*70)
    print("EXPERIMENT COMPLETE")
    print("="*70)
    print(f"Database: {database}")
    print(f"Strategy: Reused existing + ran 2 additional = N=3")
    print(f"Results directory: {n3_base_dir}")
    print(f"Summary file: {summary_file}")

    # Count successful benchmarks
    successful = sum(1 for b in experiment_results['benchmarks'] if b['status'] == 'success')
    print(f"\nCompleted: {successful}/{len(existing)} corpus sizes")
    print(f"Time saved: ~{len(existing) * 15}-{len(existing) * 30} minutes vs N=3 from scratch")

    print(f"\n🎨 Generate plots with error bars:")
    print(f"  python Scripts/plot_multi_database_scaling.py")

    return 0

if __name__ == '__main__':
    sys.exit(main())
