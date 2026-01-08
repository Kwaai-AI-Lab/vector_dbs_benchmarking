#!/usr/bin/env python3
"""
Run 7 additional benchmark iterations to increase from N=3 to N=10 for statistical rigor.

This script leverages existing N=3 results and runs 7 more iterations (runs 4-10)
to achieve N=10 statistical rigor.

Usage:
    # Run all databases and all corpus sizes
    python run_scaling_n7_additional.py

    # Run specific database only
    python run_scaling_n7_additional.py --database chroma

    # Run specific database and corpus
    python run_scaling_n7_additional.py --database chroma --corpus 10k

    # Resume from a specific run number
    python run_scaling_n7_additional.py --database chroma --start-run 5
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
from typing import List, Dict, Any, Optional
import shutil

# Corpus sizes configuration
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
    'pgvector': 'Scripts/run_pgvector_benchmark.py',
}

def find_n3_results(database: str) -> List[Dict[str, Any]]:
    """Find existing N=3 results for a database."""
    # Try both regular naming and pgvector variants
    possible_dirs = [
        f'results/{database}_scaling_n3',
        f'results/{database}_hnsw_scaling_n3',  # for pgvector
        f'results/{database}_ivfflat_scaling_n3',  # for pgvector
    ]

    n3_results = []

    for n3_dir in possible_dirs:
        n3_path = Path(n3_dir)
        if not n3_path.exists():
            continue

        for corpus_dir in sorted(n3_path.glob('corpus_*')):
            aggregated_file = corpus_dir / 'aggregated_results.json'
            if not aggregated_file.exists():
                continue

            corpus_name = corpus_dir.name.replace('corpus_', '')

            # Verify we have 3 run directories
            run_dirs = sorted(corpus_dir.glob('run_*'))
            if len(run_dirs) < 3:
                print(f"⚠️  Warning: {corpus_dir} has only {len(run_dirs)} runs")
                continue

            n3_results.append({
                'name': corpus_name,
                'n3_corpus_dir': corpus_dir,
                'aggregated_file': aggregated_file,
                'n_existing_runs': len(run_dirs),
                'source_dir': n3_dir
            })

    return n3_results

def load_existing_runs(corpus_dir: Path) -> List[Dict[str, Any]]:
    """Load all existing run results from a corpus directory."""
    results = []
    for run_dir in sorted(corpus_dir.glob('run_*')):
        results_file = run_dir / 'results.json'
        if results_file.exists():
            with open(results_file, 'r') as f:
                results.append(json.load(f))
    return results

def run_single_benchmark(database: str, corpus_name: str, corpus_path: str,
                        output_dir: str, run_number: int) -> tuple[bool, Optional[Dict]]:
    """Run a single benchmark iteration."""
    print(f"\n{'='*70}")
    print(f"Running {database.upper()} benchmark: {corpus_name} (Run {run_number}/10)")
    print(f"Corpus path: {corpus_path}")
    print(f"Output dir: {output_dir}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
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
                'n': len(values),
                'cv_percent': float(np.std(values) / np.mean(values) * 100) if np.mean(values) > 0 else 0
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

def process_corpus(database: str, corpus_info: Dict, start_run: int = 4,
                   target_runs: int = 10) -> Optional[Dict]:
    """Process a single corpus: copy existing N=3 + run additional runs to reach N=10."""
    corpus_name = corpus_info['name']

    print(f"\n{'#'*70}")
    print(f"# Processing corpus: {corpus_name}")
    print(f"# Strategy: {corpus_info['n_existing_runs']} existing + {target_runs - corpus_info['n_existing_runs']} new runs = N={target_runs}")
    print(f"{'#'*70}\n")

    # Find corpus config
    corpus_config = next((c for c in CORPUS_CONFIGS if c['name'] == corpus_name), None)
    if not corpus_config:
        print(f"❌ Unknown corpus name: {corpus_name}")
        return None

    # Create N=10 output directory
    n10_base_dir = Path(f'results/{database}_scaling_n10')
    n10_corpus_dir = n10_base_dir / f'corpus_{corpus_name}'
    n10_corpus_dir.mkdir(parents=True, exist_ok=True)

    # Copy existing runs if not already present
    existing_n3_runs = load_existing_runs(corpus_info['n3_corpus_dir'])

    for i, result in enumerate(existing_n3_runs, 1):
        run_dir = n10_corpus_dir / f'run_{i}'
        results_file = run_dir / 'results.json'

        if not results_file.exists():
            run_dir.mkdir(parents=True, exist_ok=True)
            with open(results_file, 'w') as f:
                json.dump(result, f, indent=2)
            print(f"✅ Copied existing run_{i}")
        else:
            print(f"⏭️  run_{i} already exists")

    all_results = existing_n3_runs.copy()

    # Run additional iterations
    for run_num in range(start_run, target_runs + 1):
        run_dir = n10_corpus_dir / f'run_{run_num}'
        results_file = run_dir / 'results.json'

        # Check if already completed
        if results_file.exists():
            print(f"⏭️  run_{run_num} already exists, loading...")
            with open(results_file, 'r') as f:
                result = json.load(f)
            all_results.append(result)
            continue

        # Run benchmark
        success, result = run_single_benchmark(
            database, corpus_name, corpus_config['path'],
            str(run_dir), run_num
        )

        if success and result:
            all_results.append(result)
            print(f"✅ Completed run_{run_num}")
        else:
            print(f"❌ Run {run_num} failed")
            # Continue anyway to allow partial results

    print(f"\n📊 Collected {len(all_results)}/{target_runs} successful runs for {corpus_name}")

    if len(all_results) < 3:
        print(f"❌ Not enough successful runs for {corpus_name} (need at least 3)")
        return None

    # Aggregate all results
    print(f"\n📊 Aggregating {len(all_results)} runs...")
    aggregated = aggregate_results(all_results)

    # Save aggregated results
    agg_file = n10_corpus_dir / 'aggregated_results.json'
    with open(agg_file, 'w') as f:
        json.dump(aggregated, f, indent=2)

    print(f"✅ Saved aggregated results: {agg_file}")

    # Print summary statistics
    if aggregated and 'statistics' in aggregated:
        print(f"\n📊 Summary Statistics for {corpus_name} (N={len(all_results)}):")
        stats = aggregated['statistics']

        if 'p50_latency_ms' in stats:
            s = stats['p50_latency_ms']
            print(f"  P50 Latency: {s['mean']:.2f} ± {s['std']:.2f} ms (CV={s['cv_percent']:.1f}%, n={s['n']})")

        if 'queries_per_second' in stats:
            s = stats['queries_per_second']
            print(f"  Throughput:  {s['mean']:.1f} ± {s['std']:.1f} QPS (CV={s['cv_percent']:.1f}%, n={s['n']})")

        if 'ingestion_time' in stats:
            s = stats['ingestion_time']
            print(f"  Ingestion:   {s['mean']:.1f} ± {s['std']:.1f} sec (CV={s['cv_percent']:.1f}%, n={s['n']})")

    return aggregated

def main():
    parser = argparse.ArgumentParser(
        description='Run 7 additional iterations to increase from N=3 to N=10'
    )
    parser.add_argument('--database', type=str, default=None,
                       help='Specific database to process (default: all)')
    parser.add_argument('--corpus', type=str, default=None,
                       help='Specific corpus to process (default: all)')
    parser.add_argument('--start-run', type=int, default=4,
                       help='Starting run number (default: 4)')
    parser.add_argument('--target-runs', type=int, default=10,
                       help='Target number of total runs (default: 10)')
    args = parser.parse_args()

    print("="*70)
    print(f"N={args.target_runs} Statistical Rigor Upgrade")
    print("="*70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Strategy: Reuse existing N=3 + run {args.target_runs - 3} additional = N={args.target_runs}")
    print("="*70)

    # Determine which databases to process
    if args.database:
        databases = [args.database] if args.database in DATABASE_SCRIPTS else []
        if not databases:
            print(f"❌ Unknown database: {args.database}")
            print(f"Available: {', '.join(DATABASE_SCRIPTS.keys())}")
            return 1
    else:
        databases = list(DATABASE_SCRIPTS.keys())

    # Track overall progress
    overall_start = time.time()
    overall_stats = {
        'start_time': datetime.now().isoformat(),
        'databases': []
    }

    # Process each database
    for db_idx, database in enumerate(databases, 1):
        print(f"\n{'#'*70}")
        print(f"# [{db_idx}/{len(databases)}] Processing database: {database.upper()}")
        print(f"{'#'*70}\n")

        # Find N=3 results
        n3_corpuses = find_n3_results(database)

        if not n3_corpuses:
            print(f"⚠️  No N=3 results found for {database}, skipping...")
            continue

        print(f"✅ Found {len(n3_corpuses)} corpus sizes with N=3 results:")
        for corp in n3_corpuses:
            print(f"  - {corp['name']}: {corp['n_existing_runs']} runs in {corp['source_dir']}")

        # Filter by corpus if specified
        if args.corpus:
            n3_corpuses = [c for c in n3_corpuses if c['name'] == args.corpus]
            if not n3_corpuses:
                print(f"⚠️  Corpus {args.corpus} not found for {database}, skipping...")
                continue

        db_results = {
            'database': database,
            'corpuses_processed': []
        }

        # Process each corpus
        for corp_idx, corpus_info in enumerate(n3_corpuses, 1):
            print(f"\n{'='*70}")
            print(f"  [{corp_idx}/{len(n3_corpuses)}] Corpus: {corpus_info['name']}")
            print(f"{'='*70}")

            corpus_start = time.time()

            aggregated = process_corpus(
                database, corpus_info,
                start_run=args.start_run,
                target_runs=args.target_runs
            )

            corpus_duration = time.time() - corpus_start

            db_results['corpuses_processed'].append({
                'name': corpus_info['name'],
                'status': 'success' if aggregated else 'failed',
                'n_runs': aggregated['n_runs'] if aggregated else 0,
                'duration_minutes': corpus_duration / 60,
                'timestamp': datetime.now().isoformat()
            })

        overall_stats['databases'].append(db_results)

        # Save progress after each database
        progress_file = Path('results/n10_upgrade_progress.json')
        with open(progress_file, 'w') as f:
            json.dump(overall_stats, f, indent=2)

    # Final summary
    overall_duration = time.time() - overall_start
    overall_stats['end_time'] = datetime.now().isoformat()
    overall_stats['total_duration_hours'] = overall_duration / 3600

    summary_file = Path('results/n10_upgrade_summary.json')
    with open(summary_file, 'w') as f:
        json.dump(overall_stats, f, indent=2)

    print("\n" + "="*70)
    print("UPGRADE TO N=10 COMPLETE")
    print("="*70)
    print(f"Total duration: {overall_duration/3600:.1f} hours")
    print(f"Summary file: {summary_file}")

    # Count totals
    total_corpuses = sum(len(db['corpuses_processed']) for db in overall_stats['databases'])
    successful_corpuses = sum(
        sum(1 for c in db['corpuses_processed'] if c['status'] == 'success')
        for db in overall_stats['databases']
    )

    print(f"\nProcessed: {successful_corpuses}/{total_corpuses} corpus sizes successfully")
    print(f"\n🎨 Generate plots with enhanced N=10 statistics:")
    print(f"  python Scripts/plot_multi_database_scaling.py")

    return 0

if __name__ == '__main__':
    sys.exit(main())
