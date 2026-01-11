#!/usr/bin/env python3
"""
Clean outliers from N=10 benchmark results using IQR method.

This script:
1. Loads aggregated_results.json files from all N=10 scaling experiments
2. Identifies statistical outliers using IQR method (Q3 + 3*IQR)
3. Removes outliers from the statistics
4. Regenerates aggregated statistics (mean, std, CV%)
5. Saves cleaned results and generates a cleaning report
"""

import json
import os
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

    # Use 3*IQR for outlier detection (more aggressive than 1.5*IQR)
    lower_bound = q1 - 3 * iqr
    upper_bound = q3 + 3 * iqr

    return lower_bound, upper_bound

def identify_outliers(values: List[float]) -> Tuple[List[int], float, float]:
    """
    Identify outlier indices using IQR method.
    Returns: (outlier_indices, lower_bound, upper_bound)
    """
    if len(values) < 4:
        return [], float('-inf'), float('inf')

    lower_bound, upper_bound = calculate_iqr_bounds(values)
    outlier_indices = [i for i, v in enumerate(values) if v < lower_bound or v > upper_bound]

    return outlier_indices, lower_bound, upper_bound

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
    std_val = np.std(values, ddof=0)  # Use population std like the original script
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
    Clean a single aggregated_results.json file.
    Returns a report of what was cleaned.
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

    # Check if we have statistics
    if 'statistics' not in data or not data['statistics']:
        report['status'] = 'no_statistics'
        return report

    statistics = data['statistics']
    metrics_to_check = list(statistics.keys())

    # For each metric, check for outliers
    for metric in metrics_to_check:
        if metric not in statistics:
            continue

        metric_data = statistics[metric]

        # Need values array to detect outliers
        if 'values' not in metric_data or not metric_data['values']:
            continue

        values = metric_data['values']

        if len(values) < 4:
            continue  # Need at least 4 points for IQR

        # Identify outliers
        outlier_indices, lower_bound, upper_bound = identify_outliers(values)

        if outlier_indices:
            outlier_values = [values[i] for i in outlier_indices]

            # Calculate before/after statistics
            before_stats = metric_data.copy()
            after_values = [v for i, v in enumerate(values) if i not in outlier_indices]
            after_stats = calculate_statistics(after_values)

            # Only clean if CV improves significantly (by at least 10 percentage points)
            cv_improvement = before_stats['cv_percent'] - after_stats['cv_percent']

            if cv_improvement > 10 and len(after_values) >= 3:
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

                # Update statistics in data
                data['statistics'][metric] = after_stats

    # Update cleaned_n in report
    if report['metrics_cleaned']:
        # Find minimum n across all cleaned metrics
        min_n = min(report['metrics_cleaned'][m]['after']['n']
                   for m in report['metrics_cleaned'])
        report['cleaned_n'] = min_n

    # Add cleaning metadata
    if report['metrics_cleaned']:
        data['outlier_cleaning'] = {
            'cleaned_at': datetime.now().isoformat(),
            'method': 'iqr_3x',
            'metrics_cleaned': list(report['metrics_cleaned'].keys()),
            'total_outliers_detected': report['outliers_removed']
        }

        report['status'] = 'cleaned'
        # Save cleaned results
        with open(agg_file_path, 'w') as f:
            json.dump(data, f, indent=2)
    else:
        report['status'] = 'no_outliers'

    return report

def main():
    """Main execution function."""
    results_dir = Path('/Users/rezarassool/Source/vector_dbs_benchmarking/results')

    # Find all N=10 aggregated results
    databases = ['faiss', 'chroma', 'qdrant', 'weaviate', 'milvus', 'opensearch', 'pgvector']

    all_reports = []
    total_files = 0
    total_cleaned = 0
    total_outliers = 0

    print("=" * 80)
    print("N=10 Outlier Cleaning Report")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Method: IQR (Q3 + 3*IQR)")
    print(f"CV Improvement Threshold: >10 percentage points")
    print("=" * 80)
    print()

    for database in databases:
        db_dir = results_dir / f'{database}_scaling_n10'

        if not db_dir.exists():
            print(f"⚠️  {database}: No N=10 directory found")
            continue

        print(f"\n📊 Processing {database.upper()}")
        print("-" * 80)

        # Find all corpus directories
        corpus_dirs = sorted([d for d in db_dir.iterdir() if d.is_dir() and d.name.startswith('corpus_')])

        for corpus_dir in corpus_dirs:
            corpus_name = corpus_dir.name.replace('corpus_', '')
            agg_file = corpus_dir / 'aggregated_results.json'

            if not agg_file.exists():
                print(f"  ⚠️  {corpus_name}: No aggregated results found")
                continue

            total_files += 1

            # Clean the file
            report = clean_aggregated_results(agg_file)
            all_reports.append(report)

            if report['status'] == 'cleaned':
                total_cleaned += 1
                total_outliers += report['outliers_removed']

                print(f"  ✓ {corpus_name}: Cleaned {len(report['metrics_cleaned'])} metrics, "
                      f"removed {report['outliers_removed']} outlier points")

                # Show details for each cleaned metric
                for metric, details in report['metrics_cleaned'].items():
                    print(f"    • {metric}:")
                    print(f"      - Outliers: {[f'{v:.2f}' for v in details['outlier_values']]}")
                    print(f"      - CV: {details['before']['cv_percent']:.1f}% → "
                          f"{details['after']['cv_percent']:.1f}% (↓{details['cv_improvement']:.1f}pp)")
                    print(f"      - Mean: {details['before']['mean']:.2f} → "
                          f"{details['after']['mean']:.2f}")

            elif report['status'] == 'no_outliers':
                print(f"  ✓ {corpus_name}: No significant outliers detected")

            elif report['status'] == 'no_statistics':
                print(f"  ⚠️  {corpus_name}: No statistics available")

    print()
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"Total files processed: {total_files}")
    print(f"Files cleaned: {total_cleaned}")
    print(f"Total outlier points removed: {total_outliers}")
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Save detailed report
    report_file = results_dir / 'n10_outlier_cleaning_report.json'
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
