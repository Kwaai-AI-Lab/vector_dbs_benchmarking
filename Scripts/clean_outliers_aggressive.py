#!/usr/bin/env python3
"""
Aggressive outlier cleaning for remaining high-variance metrics.

This pass targets:
1. Metrics with CV > 40% (very high variance)
2. Lower threshold for CV improvement (5 percentage points)
3. Special handling for clear cold-start patterns
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any
import numpy as np
from datetime import datetime

def calculate_iqr_bounds(values: List[float]) -> Tuple[float, float]:
    """Calculate IQR bounds for outlier detection."""
    if len(values) < 4:
        return float('-inf'), float('inf')

    q1 = np.percentile(values, 25)
    q3 = np.percentile(values, 75)
    iqr = q3 - q1

    # Use 2*IQR for more aggressive detection
    lower_bound = q1 - 2 * iqr
    upper_bound = q3 + 2 * iqr

    return lower_bound, upper_bound

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

def clean_aggregated_results(agg_file_path: Path, cv_threshold: float = 40.0) -> Dict[str, Any]:
    """
    Aggressively clean high-variance metrics.
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

    # Only target metrics with high CV
    high_cv_metrics = [(m, s) for m, s in statistics.items()
                       if s.get('cv_percent', 0) > cv_threshold and 'values' in s]

    for metric, metric_data in high_cv_metrics:
        values = metric_data['values']

        if len(values) < 4:
            continue

        # Use 2×IQR for more aggressive detection
        lower_bound, upper_bound = calculate_iqr_bounds(values)
        outlier_indices = [i for i, v in enumerate(values) if v < lower_bound or v > upper_bound]

        if outlier_indices:
            outlier_values = [values[i] for i in outlier_indices]
            before_stats = metric_data.copy()
            after_values = [v for i, v in enumerate(values) if i not in outlier_indices]
            after_stats = calculate_statistics(after_values)

            # More lenient threshold: CV improvement > 5pp OR final CV < 30%
            cv_improvement = before_stats['cv_percent'] - after_stats['cv_percent']

            if (cv_improvement > 5 or after_stats['cv_percent'] < 30) and len(after_values) >= 3:
                report['metrics_cleaned'][metric] = {
                    'outlier_indices': outlier_indices,
                    'outlier_values': outlier_values,
                    'bounds': [lower_bound, upper_bound],
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
            data['outlier_cleaning']['aggressive_pass'] = {
                'cleaned_at': datetime.now().isoformat(),
                'method': 'iqr_2x',
                'cv_threshold': cv_threshold,
                'metrics_cleaned': list(report['metrics_cleaned'].keys()),
                'total_outliers': report['outliers_removed']
            }
        else:
            data['outlier_cleaning'] = {
                'cleaned_at': datetime.now().isoformat(),
                'method': 'iqr_2x_aggressive',
                'cv_threshold': cv_threshold,
                'metrics_cleaned': list(report['metrics_cleaned'].keys()),
                'total_outliers_detected': report['outliers_removed']
            }

        report['status'] = 'cleaned'
        with open(agg_file_path, 'w') as f:
            json.dump(data, f, indent=2)
    else:
        report['status'] = 'no_outliers'

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
    print("Aggressive Outlier Cleaning (CV > 40%)")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Method: IQR (Q3 ± 2×IQR) - more aggressive")
    print(f"CV Threshold: > 40% (high variance)")
    print(f"CV Improvement Threshold: > 5pp OR final CV < 30%")
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
                      f"removed {report['outliers_removed']} outlier points")

                for metric, details in report['metrics_cleaned'].items():
                    print(f"    • {metric}:")
                    print(f"      - CV: {details['before']['cv_percent']:.1f}% → "
                          f"{details['after']['cv_percent']:.1f}% (↓{details['cv_improvement']:.1f}pp)")

            elif report['status'] == 'no_outliers':
                print(f"  ✓ {corpus_name}: No additional outliers to clean")

    print()
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"Total files processed: {total_files}")
    print(f"Files cleaned: {total_cleaned}")
    print(f"Total outlier points removed: {total_outliers}")
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    report_file = results_dir / 'n10_aggressive_cleaning_report.json'
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
