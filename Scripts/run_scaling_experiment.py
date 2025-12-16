#!/usr/bin/env python3
"""
Run FAISS benchmarks across multiple corpus sizes to analyze scaling behavior.

This script runs the FAISS benchmark on datasets of varying sizes and collects
results for scaling analysis.
"""

import os
import sys
import json
import subprocess
import time
from pathlib import Path
from datetime import datetime

# Corpus sizes to benchmark
CORPUS_CONFIGS = [
    {'name': 'baseline', 'path': 'Data/test_corpus/documents', 'expected_chunks': 175},
    {'name': '1k', 'path': 'Data/test_corpus/corpus_sizes/corpus_1k', 'expected_chunks': 1000},
    {'name': '10k', 'path': 'Data/test_corpus/corpus_sizes/corpus_10k', 'expected_chunks': 10000},
    {'name': '50k', 'path': 'Data/test_corpus/corpus_sizes/corpus_50k', 'expected_chunks': 50000},
    {'name': '100k', 'path': 'Data/test_corpus/corpus_sizes/corpus_100k', 'expected_chunks': 100000},
    {'name': '250k', 'path': 'Data/test_corpus/corpus_sizes/corpus_250k', 'expected_chunks': 250000},
    {'name': '500k', 'path': 'Data/test_corpus/corpus_sizes/corpus_500k', 'expected_chunks': 500000},
    {'name': '1m', 'path': 'Data/test_corpus/corpus_sizes/corpus_1m', 'expected_chunks': 1000000},
    {'name': 'full', 'path': 'Data/test_corpus/corpus_sizes/corpus_full', 'expected_chunks': 2249072},
]

def check_corpus_exists(corpus_path):
    """Check if corpus directory exists and has files."""
    path = Path(corpus_path)
    if not path.exists():
        return False
    files = list(path.glob('*.xml')) + list(path.glob('*.txt'))
    return len(files) > 0

def run_benchmark(corpus_name, corpus_path, output_dir):
    """Run FAISS benchmark for a specific corpus size."""
    print(f"\n{'='*70}")
    print(f"Running benchmark: {corpus_name}")
    print(f"Corpus path: {corpus_path}")
    print(f"Output dir: {output_dir}")
    print(f"{'='*70}\n")

    # Create output directory
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Build command
    cmd = [
        'python', 'Scripts/run_faiss_benchmark.py',
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
    print("="*70)
    print("FAISS Scaling Experiment")
    print("="*70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Create results directory
    results_dir = Path('results/faiss_scaling_experiment')
    results_dir.mkdir(parents=True, exist_ok=True)

    # Track results
    experiment_results = {
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
        return

    # Confirm before starting
    print(f"\nThis will run {len(available_corpuses)} benchmarks.")
    print("Estimated time: 1-3 hours depending on corpus sizes")
    print("\nProceeding automatically...")
    # Skip confirmation for non-interactive mode
    # response = input("\nProceed? (y/n): ")
    # if response.lower() != 'y':
    #     print("Cancelled.")
    #     return

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
        success = run_benchmark(config['name'], config['path'], str(output_dir))

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
    print("Scaling Experiment Complete!")
    print("="*70)

    successful = sum(1 for b in experiment_results['benchmarks'] if b['status'] == 'success')
    failed = sum(1 for b in experiment_results['benchmarks'] if b['status'] == 'failed')
    skipped = sum(1 for b in experiment_results['benchmarks'] if b['status'] == 'skipped')

    print(f"\nResults:")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    print(f"  Skipped: {skipped}")
    print(f"\nSummary saved to: {summary_file}")

if __name__ == '__main__':
    main()
