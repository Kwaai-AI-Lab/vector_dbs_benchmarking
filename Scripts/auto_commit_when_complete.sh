#!/bin/bash
# Auto-commit scaling experiment results when complete

echo "Starting automated monitoring and commit script..."
echo "Will commit and push results when experiments complete."
echo ""

while true; do
    # Check if any experiments are still running
    running=$(ps aux | grep "run_scaling_experiment_generic" | grep -v grep | wc -l)

    if [ "$running" -eq 0 ]; then
        echo "$(date): All experiments complete! Starting auto-commit..."

        # Wait a few seconds to ensure files are written
        sleep 5

        # Add all new results
        git add results/qdrant_scaling_experiment/
        git add results/weaviate_scaling_experiment/
        git add results/milvus_scaling_experiment/
        git add results/opensearch_scaling_experiment/

        # Count completed benchmarks
        qdrant=$(find results/qdrant_scaling_experiment -name 'results.json' 2>/dev/null | wc -l | xargs)
        weaviate=$(find results/weaviate_scaling_experiment -name 'results.json' 2>/dev/null | wc -l | xargs)
        milvus=$(find results/milvus_scaling_experiment -name 'results.json' 2>/dev/null | wc -l | xargs)
        opensearch=$(find results/opensearch_scaling_experiment -name 'results.json' 2>/dev/null | wc -l | xargs)

        # Create commit message
        git commit -m "Add overnight scaling experiment results for 4 databases

Results:
- Qdrant: ${qdrant}/5 corpus sizes complete
- Weaviate: ${weaviate}/5 corpus sizes complete
- Milvus: ${milvus}/5 corpus sizes complete
- OpenSearch: ${opensearch}/5 corpus sizes complete

Corpus sizes tested: baseline (175), 1k (5.5K), 10k (70K), 50k (345K), full (2.2M chunks)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
"

        # Push to remote
        git push

        echo "$(date): ✓ Results committed and pushed!"
        echo ""
        echo "Summary:"
        echo "  Qdrant: ${qdrant}/5"
        echo "  Weaviate: ${weaviate}/5"
        echo "  Milvus: ${milvus}/5"
        echo "  OpenSearch: ${opensearch}/5"
        echo ""

        exit 0
    else
        echo "$(date): $running experiments still running... checking again in 5 minutes"
        sleep 300  # Check every 5 minutes
    fi
done
