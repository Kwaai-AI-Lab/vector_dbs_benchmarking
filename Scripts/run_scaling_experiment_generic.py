#!/usr/bin/env python3
"""
Run scaling benchmarks across multiple corpus sizes for any database.

Usage:
    python run_scaling_experiment_generic.py --database chroma
    python run_scaling_experiment_generic.py --database qdrant
"""

import os
import sys
import json
import subprocess
import time
import argparse
from pathlib import Path
from datetime import datetime

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

def run_benchmark(database, corpus_name, corpus_path, output_dir):
    """Run benchmark for a specific corpus size."""
    print(f"\n{'='*70}")
    print(f"Running {database.upper()} benchmark: {corpus_name}")
    print(f"Corpus path: {corpus_path}")
    print(f"Output dir: {output_dir}")
    print(f"{'='*70}\n")

    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Get benchmark script
    script = DATABASE_SCRIPTS.get(database)
    if not script:
        print(f"❌ Unknown database: {database}")
        return False

    if not Path(script).exists():
        print(f"❌ Benchmark script not found: {script}")
        return False

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
            return True
        else:
            print(f"❌ Benchmark failed with return code {result.returncode}")
            print(f"See log: {log_file}")
            return False

    except subprocess.TimeoutExpired:
        print(f"❌ Benchmark timed out after 2 hours")
        return False
    except Exception as e:
        print(f"❌ Benchmark failed with error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Run scaling experiment for any database')
    parser.add_argument('--database', required=True, choices=list(DATABASE_SCRIPTS.keys()),
                       help='Database to benchmark')
    args = parser.parse_args()

    database = args.database

    print("="*70)
    print(f"{database.upper()} Scaling Experiment")
    print("="*70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Corpus sizes: {len(CORPUS_CONFIGS)}")
    print(f"Estimated time: 1.5-2 hours")

    # Create results directory
    results_dir = Path(f'results/{database}_scaling_experiment')
    results_dir.mkdir(parents=True, exist_ok=True)

    # Track results
    experiment_results = {
        'database': database,
        'start_time': datetime.now().isoformat(),
        'benchmarks': []
    }

    # Check which corpuses exist
    available_corpuses = []
    for config in CORPUS_CONFIGS:
        if check_corpus_exists(config['path']):
            available_corpuses.append(config)
            print(f"✓ Found corpus: {config['name']} ({config['path']})")
        else:
            print(f"✗ Missing corpus: {config['name']} ({config['path']})")

    print(f"\nFound {len(available_corpuses)} / {len(CORPUS_CONFIGS)} corpus datasets")

    if len(available_corpuses) == 0:
        print("❌ No corpus datasets found. Run create_corpus_sizes.py first.")
        return 1

    print(f"\nProceeding with {len(available_corpuses)} benchmarks...")

    # Run benchmarks
    for i, config in enumerate(available_corpuses, 1):
        print(f"\n[{i}/{len(available_corpuses)}] Processing: {config['name']}")

        output_dir = results_dir / f"corpus_{config['name']}"

        # Check if already completed
        results_file = output_dir / 'results.json'
        if results_file.exists():
            print(f"⏭️  Results already exist, skipping...")
            with open(results_file, 'r') as f:
                result_data = json.load(f)
            experiment_results['benchmarks'].append({
                'name': config['name'],
                'path': config['path'],
                'status': 'skipped',
                'result_file': str(results_file)
            })
            continue

        # Run benchmark
        success = run_benchmark(database, config['name'], config['path'], str(output_dir))

        experiment_results['benchmarks'].append({
            'name': config['name'],
            'path': config['path'],
            'expected_chunks': config['expected_chunks'],
            'status': 'success' if success else 'failed',
            'output_dir': str(output_dir),
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
    print(f"{database.upper()} Scaling Experiment Complete!")
    print("="*70)

    successful = sum(1 for b in experiment_results['benchmarks'] if b['status'] == 'success')
    failed = sum(1 for b in experiment_results['benchmarks'] if b['status'] == 'failed')
    skipped = sum(1 for b in experiment_results['benchmarks'] if b['status'] == 'skipped')

    print(f"\nResults:")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    print(f"  Skipped: {skipped}")
    print(f"\nSummary saved to: {summary_file}")

    return 0 if failed == 0 else 1

if __name__ == '__main__':
    sys.exit(main())
