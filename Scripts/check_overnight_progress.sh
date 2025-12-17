#!/bin/bash
# Quick status check for overnight scaling experiments

echo "======================================================================"
echo "OVERNIGHT SCALING EXPERIMENTS - STATUS CHECK"
echo "======================================================================"
echo ""

# Check if processes are still running
echo "Running processes:"
running=$(ps aux | grep "run_scaling_experiment_generic" | grep -v grep | wc -l | xargs)
echo "  Active experiments: $running / 4"
echo ""

# Check completion status
echo "Completion status:"
for db in qdrant weaviate milvus opensearch; do
  completed=$(find results/${db}_scaling_experiment -name 'results.json' 2>/dev/null | wc -l | xargs)
  echo "  $db: $completed / 5 corpus sizes"
done
echo ""

# Check for recent activity
echo "Most recent completions:"
find results/*_scaling_experiment -name 'results.json' -exec ls -lh {} \; 2>/dev/null | \
  tail -5 | awk '{print "  " $9 " (" $6, $7, $8 ")"}'
echo ""

# Estimate time remaining
echo "Estimated completion:"
if [ "$running" -gt 0 ]; then
  echo "  Experiments still running..."
  echo "  Check back in 1-2 hours or run this script again"
else
  echo "  ✓ All experiments complete!"
  echo "  Ready for cross-database analysis"
fi
echo ""

# Show any recent errors
echo "Recent errors (if any):"
errors=$(find results/*_scaling_experiment -name 'benchmark.log' -exec grep -l "❌" {} \; 2>/dev/null | wc -l | xargs)
echo "  Failed benchmarks: $errors"
if [ "$errors" -gt 0 ]; then
  echo "  (Check individual benchmark.log files for details)"
fi
echo ""

echo "======================================================================"
echo "For detailed logs: tail -f /tmp/{qdrant,weaviate,milvus,opensearch}_scaling.log"
echo "======================================================================"
