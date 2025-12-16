#!/usr/bin/env python3
"""
Create multiple corpus datasets at different scales for scaling experiments.

This script extracts subsets of the Wikipedia XML corpus to create datasets
of varying sizes: 1K, 10K, 50K, 100K, 250K, 500K, 1M, and 2.2M chunks.
"""

import xml.etree.ElementTree as ET
import os
import sys
from pathlib import Path

# Target corpus sizes (approximate number of chunks)
# With chunk_size=512, overlap=50, average article creates ~10-15 chunks
CORPUS_SIZES = [
    ('1k', 100),      # ~100 articles → ~1,000 chunks
    ('10k', 800),     # ~800 articles → ~10,000 chunks
    ('50k', 4000),    # ~4,000 articles → ~50,000 chunks
    ('100k', 8000),   # ~8,000 articles → ~100,000 chunks
    ('250k', 20000),  # ~20,000 articles → ~250,000 chunks
    ('500k', 40000),  # ~40,000 articles → ~500,000 chunks
    ('1m', 80000),    # ~80,000 articles → ~1,000,000 chunks
    ('full', None),   # All articles → ~2,249,072 chunks
]

def count_wikipedia_pages(xml_file):
    """Count total number of pages in Wikipedia XML dump."""
    print(f"Counting pages in {xml_file}...")
    count = 0
    for event, elem in ET.iterparse(xml_file, events=('end',)):
        if elem.tag.endswith('page'):
            count += 1
            if count % 10000 == 0:
                print(f"  Counted {count:,} pages...")
            elem.clear()
    print(f"Total pages: {count:,}")
    return count

def extract_wikipedia_subset(xml_file, output_file, max_pages):
    """Extract first N pages from Wikipedia XML dump."""
    print(f"\nExtracting {max_pages:,} pages to {output_file}...")

    # Create namespace map
    namespace = {'wiki': 'http://www.mediawiki.org/xml/export-0.10/'}

    # Parse and extract
    context = ET.iterparse(xml_file, events=('start', 'end'))
    context = iter(context)
    event, root = next(context)

    pages_extracted = 0

    # Start output file
    with open(output_file, 'w', encoding='utf-8') as out:
        # Write XML header
        out.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        out.write('<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.10/">\n')

        for event, elem in context:
            if event == 'end' and elem.tag.endswith('page'):
                if pages_extracted < max_pages:
                    # Write page element
                    page_str = ET.tostring(elem, encoding='unicode')
                    out.write(page_str + '\n')
                    pages_extracted += 1

                    if pages_extracted % 1000 == 0:
                        print(f"  Extracted {pages_extracted:,} / {max_pages:,} pages...")

                    elem.clear()
                else:
                    break

        # Write XML footer
        out.write('</mediawiki>\n')

    print(f"✅ Extracted {pages_extracted:,} pages to {output_file}")
    return pages_extracted

def create_corpus_directories():
    """Create corpus directories for different sizes."""
    base_dir = Path('Data/test_corpus')
    corpus_sizes_dir = base_dir / 'corpus_sizes'
    corpus_sizes_dir.mkdir(parents=True, exist_ok=True)

    print("="*70)
    print("Creating Multiple Corpus Sizes for Scaling Experiment")
    print("="*70)

    # Source Wikipedia file
    source_xml = base_dir / 'documents_large_single' / 'enwiki-latest-pages-articles1.xml'

    if not source_xml.exists():
        print(f"❌ Error: Source file not found: {source_xml}")
        return

    print(f"\nSource: {source_xml}")
    print(f"Output: {corpus_sizes_dir}/")

    # Create datasets for each size
    for size_name, num_pages in CORPUS_SIZES:
        if num_pages is None:
            # Full corpus - create symlink
            output_dir = corpus_sizes_dir / f'corpus_{size_name}'
            output_dir.mkdir(exist_ok=True)
            output_file = output_dir / 'enwiki-subset.xml'

            if output_file.exists():
                output_file.unlink()

            print(f"\n[{size_name}] Creating symlink to full corpus...")
            output_file.symlink_to(source_xml.resolve())
            print(f"✅ [{size_name}] Symlink created")
        else:
            # Extract subset
            output_dir = corpus_sizes_dir / f'corpus_{size_name}'
            output_dir.mkdir(exist_ok=True)
            output_file = output_dir / 'enwiki-subset.xml'

            if output_file.exists():
                print(f"\n[{size_name}] Output file already exists, skipping...")
                continue

            print(f"\n[{size_name}] Extracting {num_pages:,} pages...")
            extract_wikipedia_subset(source_xml, output_file, num_pages)

    print("\n" + "="*70)
    print("Corpus Creation Complete!")
    print("="*70)
    print(f"\nCreated corpus datasets in: {corpus_sizes_dir}/")
    print("\nDirectory structure:")
    for size_name, num_pages in CORPUS_SIZES:
        corpus_dir = corpus_sizes_dir / f'corpus_{size_name}'
        if corpus_dir.exists():
            xml_file = corpus_dir / 'enwiki-subset.xml'
            if xml_file.exists():
                size_mb = xml_file.stat().st_size / (1024 * 1024)
                if num_pages:
                    print(f"  corpus_{size_name:6s}: {num_pages:6,} pages (~{size_mb:6.1f} MB)")
                else:
                    print(f"  corpus_{size_name:6s}: all pages (~{size_mb:6.1f} MB)")

if __name__ == '__main__':
    create_corpus_directories()
