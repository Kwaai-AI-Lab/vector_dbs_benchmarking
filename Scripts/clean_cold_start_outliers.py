#!/usr/bin/env python3
"""
Detect and clean cold-start patterns where first N runs are significantly slower.

This specifically targets ingestion_time and latency metrics where the first
2-3 runs show 3× or more slowdown compared to later runs.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Any
import numpy as np
from datetime import datetime

def detect_cold_start_pattern(values: List[float], threshold_multiplier: float = 3.0) -> List[int]:
    """
    Detect if first N values are outliers compared to the tail of the list.

    Returns indices of cold-start outliers (typically first 1-3 values).
    """
    if len(values) < 5:
        return []

    # Check if first 1, 2, or 3 values are consistently much higher
    # than the remaining values

    best_outliers = []
    best_cv_improvement = 0

    for n_outliers in [1, 2, 3]:
        if n_outliers >= len(values) - 2:  # Need at least 3 remaining values
            continue

        first_n = values[:n_outliers]
        remaining = values[n_outliers:]

        mean_first = np.mean(first_n)
        mean_remaining = np.mean(remaining)

        # Check if first N are at least threshold_multiplier× the remaining mean
        if mean_first >= threshold_multiplier * mean_remaining:
            # Calculate CV improvement
            cv_before = np.std(values, ddof=0) / np.mean(values) * 100
            cv_after = np.std(remaining, ddof=0) / np.mean(remaining) * 100
            cv_improvement = cv_before - cv_after

            if cv_improvement > best_cv_improvement:
                best_cv_improvement = cv_improvement
                best_outliers = list(range(n_outliers))

    # Only return if we get significant CV improvement (> 15pp)
    if best_cv_improvement > 15:
        return best_outliers

    return []

def calculate_statistics(values: List[float]) -> Dict[str, float]:
    """Calculate mean, std, min, max, cv% for a list of values."""
    if not values:
        return {
            'mean': 0.0,
            'std': 0.0,
            'min': 0.0,
            'max': 0.0,
            'cv_percent': 0.0,
            'n': 0,
            'values': []
        }

    mean_val = np.mean(values)
    std_val = np.std(values, ddof=0)
    cv_percent = (std_val / mean_val * 100) if mean_val != 0 else 0.0

    return {
        'mean': float(mean_val),
        'std': float(std_val),
        'min': float(np.min(values)),
        'max': float(np.max(values)),
        'cv_percent': float(cv_percent),
        'n': len(values),
        'values': values
    }

def clean_aggregated_results(agg_file_path: Path) -> Dict[str, Any]:
    """
    Clean cold-start patterns from metrics.
    """
    with open(agg_file_path, 'r') as f:
        data = json.load(f)

    report = {
        'file': str(agg_file_path),
        'metrics_cleaned': {},
        'outliers_removed': 0,
        'original_n': data.get('n_runs', 0),
        'cleaned_n': data.get('n_runs', 0)
    }

    if 'statistics' not in data or not data['statistics']:
        report['status'] = 'no_statistics'
        return report

    statistics = data['statistics']

    # Target high-CV metrics that might have cold-start patterns
    target_metrics = [(m, s) for m, s in statistics.items()
                      if s.get('cv_percent', 0) > 40 and 'values' in s and len(s['values']) >= 5]

    for metric, metric_data in target_metrics:
        values = metric_data['values']

        # Detect cold-start pattern
        outlier_indices = detect_cold_start_pattern(values)

        if outlier_indices:
            outlier_values = [values[i] for i in outlier_indices]
            before_stats = metric_data.copy()
            after_values = [v for i, v in enumerate(values) if i not in outlier_indices]
            after_stats = calculate_statistics(after_values)

            cv_improvement = before_stats['cv_percent'] - after_stats['cv_percent']

            if len(after_values) >= 3:  # Ensure we keep at least 3 values
                report['metrics_cleaned'][metric] = {
                    'outlier_indices': outlier_indices,
                    'outlier_values': outlier_values,
                    'pattern': 'cold_start',
                    'before': {
                        'mean': before_stats['mean'],
                        'std': before_stats['std'],
                        'cv_percent': before_stats['cv_percent'],
                        'n': before_stats['n']
                    },
                    'after': {
                        'mean': after_stats['mean'],
                        'std': after_stats['std'],
                        'cv_percent': after_stats['cv_percent'],
                        'n': after_stats['n']
                    },
                    'cv_improvement': cv_improvement
                }

                report['outliers_removed'] += len(outlier_indices)
                data['statistics'][metric] = after_stats

    if report['metrics_cleaned']:
        min_n = min(report['metrics_cleaned'][m]['after']['n']
                   for m in report['metrics_cleaned'])
        report['cleaned_n'] = min_n

        # Update cleaning metadata
        if 'outlier_cleaning' in data:
            data['outlier_cleaning']['cold_start_pass'] = {
                'cleaned_at': datetime.now().isoformat(),
                'method': 'cold_start_detection',
                'metrics_cleaned': list(report['metrics_cleaned'].keys()),
                'total_outliers': report['outliers_removed']
            }
        else:
            data['outlier_cleaning'] = {
                'cleaned_at': datetime.now().isoformat(),
                'method': 'cold_start_detection',
                'metrics_cleaned': list(report['metrics_cleaned'].keys()),
                'total_outliers_detected': report['outliers_removed']
            }

        report['status'] = 'cleaned'
        with open(agg_file_path, 'w') as f:
            json.dump(data, f, indent=2)
    else:
        report['status'] = 'no_cold_start'

    return report

def main():
    """Main execution function."""
    results_dir = Path('/Users/rezarassool/Source/vector_dbs_benchmarking/results')
    databases = ['faiss', 'chroma', 'qdrant', 'weaviate', 'milvus', 'opensearch', 'pgvector']

    all_reports = []
    total_files = 0
    total_cleaned = 0
    total_outliers = 0

    print("=" * 80)
    print("Cold-Start Pattern Detection and Cleaning")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Method: Detect first N runs ≥3× slower than remaining runs")
    print(f"Target: Metrics with CV > 40%")
    print("=" * 80)
    print()

    for database in databases:
        db_dir = results_dir / f'{database}_scaling_n10'

        if not db_dir.exists():
            continue

        print(f"\n📊 Processing {database.upper()}")
        print("-" * 80)

        corpus_dirs = sorted([d for d in db_dir.iterdir() if d.is_dir() and d.name.startswith('corpus_')])

        for corpus_dir in corpus_dirs:
            corpus_name = corpus_dir.name.replace('corpus_', '')
            agg_file = corpus_dir / 'aggregated_results.json'

            if not agg_file.exists():
                continue

            total_files += 1
            report = clean_aggregated_results(agg_file)
            all_reports.append(report)

            if report['status'] == 'cleaned':
                total_cleaned += 1
                total_outliers += report['outliers_removed']

                print(f"  ✓ {corpus_name}: Cleaned {len(report['metrics_cleaned'])} metrics, "
                      f"removed first {report['outliers_removed']} runs (cold-start)")

                for metric, details in report['metrics_cleaned'].items():
                    print(f"    • {metric}:")
                    print(f"      - Removed first {len(details['outlier_indices'])} runs: {[f'{v:.1f}' for v in details['outlier_values']]}")
                    print(f"      - CV: {details['before']['cv_percent']:.1f}% → "
                          f"{details['after']['cv_percent']:.1f}% (↓{details['cv_improvement']:.1f}pp)")
                    print(f"      - Mean: {details['before']['mean']:.1f} → "
                          f"{details['after']['mean']:.1f}")

            elif report['status'] == 'no_cold_start':
                print(f"  ✓ {corpus_name}: No cold-start patterns detected")

    print()
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"Total files processed: {total_files}")
    print(f"Files cleaned: {total_cleaned}")
    print(f"Total cold-start runs removed: {total_outliers}")
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    report_file = results_dir / 'n10_cold_start_cleaning_report.json'
    with open(report_file, 'w') as f:
        json.dump({
            'cleaned_at': datetime.now().isoformat(),
            'summary': {
                'total_files': total_files,
                'files_cleaned': total_cleaned,
                'total_outliers_removed': total_outliers
            },
            'details': all_reports
        }, f, indent=2)

    print(f"\nDetailed report saved to: {report_file}")

    return 0

if __name__ == '__main__':
    sys.exit(main())
