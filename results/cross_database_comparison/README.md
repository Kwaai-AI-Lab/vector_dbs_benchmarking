# Cross-Database Performance Comparison

Comprehensive performance analysis across 5 vector databases tested with identical workloads.

## Test Configuration

- **Databases Tested:** FAISS, Chroma, Qdrant, Weaviate, Milvus, OpenSearch
- **Corpus Sizes:** 175, 5,562, 69,903, 345,046, and 2,249,072 chunks
- **Embedding Model:** sentence-transformers/all-MiniLM-L6-v2 (384 dimensions)
- **Chunking:** Fixed-size, 512 characters, 50 character overlap
- **Query Configuration:** Top-K = 3 (primary metric)
- **Hardware:** Single node, Docker containers

## Visualizations

### 1. Query Latency Scaling (`query_latency_scaling.png`)
Shows how query latency (P50) and throughput (QPS) scale with corpus size.

**Key Findings:**
- **Chroma** maintains exceptional consistency: 6-9ms across all scales (⭐ Winner)
- **FAISS** shows sub-linear scaling: only 7.9x slower for 12,852x more data
- **Qdrant, Weaviate, Milvus** show moderate degradation at 10K corpus
- **OpenSearch** fails at 50K corpus

### 2. Ingestion Comparison (`ingestion_comparison.png`)
Compares ingestion time and throughput across corpus sizes.

**Key Findings:**
- **Chroma** fastest ingestion: 310 chunks/sec at 345K chunks (⭐ Winner)
- **Qdrant** moderate speed: 134 chunks/sec
- **Weaviate** slowest: 102 chunks/sec (3x slower than Chroma)
- **Milvus** similar to Weaviate: 98 chunks/sec

### 3. Detailed 50K Comparison (`50k_detailed_comparison.png`)
Four-panel comparison at 345K chunks showing:
- Query latency: Chroma 6.4ms vs 38-48ms for others
- Query throughput: Chroma 144 QPS (6-18x faster than others)
- Ingestion time: Chroma 18.5 min (2-3x faster than others)
- Memory usage: Chroma most efficient at 8.8GB

### 4. Latency Heatmap (`latency_heatmap.png`)
Visual comparison of P50 latencies across all databases and corpus sizes.

**Patterns:**
- **Light yellow (fast):** Chroma consistently fast across all sizes
- **Orange/Red (moderate):** Qdrant, Milvus show acceptable performance
- **Dark red (slow):** Weaviate struggles at baseline/10k, Qdrant/Milvus at 10k
- **Gray (failed):** OpenSearch at 50k

## Performance Summary Table

### Query Performance (50K Corpus, 345K chunks)

| Database | P50 Latency | QPS | Winner |
|----------|-------------|-----|--------|
| **Chroma** | 6.4ms | 144 | ⭐⭐⭐ |
| **Qdrant** | 38.3ms | 23 | ⭐ |
| **Weaviate** | 48.0ms | 21 | ⭐ |
| **Milvus** | 41.3ms | 8 | - |
| **OpenSearch** | FAILED | FAILED | ❌ |

### Ingestion Performance (50K Corpus, 345K chunks)

| Database | Total Time | Throughput | Winner |
|----------|------------|------------|--------|
| **Chroma** | 18.5 min | 310 ch/s | ⭐⭐⭐ |
| **Qdrant** | 42.8 min | 134 ch/s | ⭐⭐ |
| **Weaviate** | 56.3 min | 102 ch/s | ⭐ |
| **Milvus** | 59.0 min | 98 ch/s | ⭐ |
| **OpenSearch** | FAILED | FAILED | ❌ |

### Scalability Limits

| Database | Max Proven Scale | Status |
|----------|------------------|--------|
| **FAISS** | 2.2M chunks | ✅ Success (90 min) |
| **Chroma** | 345K chunks | ⚠️ Timeout at 2.2M |
| **Qdrant** | 345K chunks | ⚠️ Timeout at 2.2M |
| **Weaviate** | 345K chunks | ⚠️ Timeout at 2.2M |
| **Milvus** | 345K chunks | ⚠️ Timeout at 2.2M |
| **OpenSearch** | 70K chunks | ❌ Failed at 345K |

## Key Insights

### 1. Clear Performance Leader: Chroma
- **6-18x faster** query throughput than competitors
- **2-3x faster** ingestion than competitors
- **Most consistent** performance across scales
- **Lowest memory** footprint (8.8GB vs 12-16GB)

### 2. FAISS: Best for Large Scale
- Only database to handle 2.2M chunks
- Excellent sub-linear scaling (O(N^0.48))
- Best choice for multi-million chunk datasets

### 3. Scalability Wall at 2.2M Chunks
- All databases except FAISS timeout at full corpus
- Suggests architectural limitations for extreme scale
- May require sharding/clustering for larger datasets

### 4. OpenSearch: Not Vector-Optimized
- Failed at 345K chunks (others succeeded)
- Designed for text search, not pure vector similarity
- Not recommended for vector-heavy workloads

## Recommendations

### By Use Case

**Real-time Applications** (< 10ms latency requirement):
- ✅ **Chroma** (6-9ms consistent)
- ✅ **FAISS** (10-12ms)
- ⚠️ Qdrant/Weaviate/Milvus (15-65ms)

**High Throughput** (> 100 QPS requirement):
- ✅ **Chroma** (144 QPS at 345K chunks)
- ✅ **FAISS** (90+ QPS at 2.2M chunks)
- ❌ Others (8-23 QPS at scale)

**Large Scale** (> 500K chunks):
- ✅ **FAISS** (proven to 2.2M)
- ⚠️ Others (unproven beyond 345K)

**Fast Ingestion** (frequent re-indexing):
- ✅ **Chroma** (310 chunks/sec)
- ⚠️ Qdrant (134 chunks/sec)
- ❌ Weaviate/Milvus (98-102 chunks/sec)

**Resource Constrained** (memory limited):
- ✅ **Chroma** (8.8GB at 345K chunks)
- ⚠️ Milvus (12.4GB)
- ❌ Qdrant/Weaviate (14.7-15.8GB)

### Overall Recommendations

**1st Choice:** Chroma (best all-around performance up to 345K chunks)
**2nd Choice:** FAISS (best for large scale > 500K chunks)
**3rd Choice:** Qdrant (good balance, proven ecosystem)

**Avoid:** OpenSearch for pure vector workloads

## Methodology

All databases tested with identical:
- Wikipedia corpus (enwiki dataset)
- Embedding model and parameters
- Chunking strategy and size
- Query workload (10 test queries, 5 top-k values)
- Hardware environment (single Docker host)
- Timeout limits (2 hours per corpus size)

Results are directly comparable and reproducible.

## Data Sources

Raw results available in:
- `results/faiss_scaling_experiment/`
- `results/chroma_scaling_experiment/`
- `results/qdrant_scaling_experiment/`
- `results/weaviate_scaling_experiment/`
- `results/milvus_scaling_experiment/`
- `results/opensearch_scaling_experiment/`

Analysis scripts:
- `scripts/create_cross_database_visualizations.py`
- `scripts/analyze_scaling_results.py`
