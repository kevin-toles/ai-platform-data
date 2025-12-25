#!/bin/bash
# Script to trigger mirror batches one at a time, waiting for each to complete

REPO="kevin-toles/code-reference-engine"
WORKFLOW="mirror-batch.yml"

# Batches to run (comment out ones already completed)
BATCHES=(
  # "game-dev-engines"      # Done
  # "game-dev-systems"      # Done
  "game-dev-rendering"
  "game-dev-physics-ai"
  # "cpp-core"              # Done
  # "backend-frameworks-1"  # Done
  # "backend-frameworks-2"  # Done
  "backend-microservices"
  "frontend"
  "infrastructure"
  "databases"
  "security-monitoring"
  "testing"
  "ml"
)

trigger_and_wait() {
  local batch=$1
  echo ""
  echo "=========================================="
  echo "Starting batch: $batch"
  echo "=========================================="
  
  # Trigger the workflow
  gh workflow run "$WORKFLOW" --repo "$REPO" -f batch="$batch"
  
  if [ $? -ne 0 ]; then
    echo "❌ Failed to trigger $batch"
    return 1
  fi
  
  # Wait a moment for the run to be created
  sleep 5
  
  # Get the latest run ID
  RUN_ID=$(gh run list --workflow="$WORKFLOW" --repo "$REPO" --limit 1 --json databaseId --jq '.[0].databaseId')
  
  echo "Run ID: $RUN_ID"
  echo "Waiting for completion..."
  
  # Wait for the run to complete
  while true; do
    STATUS=$(gh run view "$RUN_ID" --repo "$REPO" --json status,conclusion --jq '.status')
    
    if [ "$STATUS" = "completed" ]; then
      CONCLUSION=$(gh run view "$RUN_ID" --repo "$REPO" --json conclusion --jq '.conclusion')
      if [ "$CONCLUSION" = "success" ]; then
        echo "✅ $batch completed successfully"
        return 0
      else
        echo "❌ $batch failed with conclusion: $CONCLUSION"
        echo "View logs: gh run view $RUN_ID --repo $REPO --log"
        return 1
      fi
    fi
    
    echo "  Status: $STATUS (waiting...)"
    sleep 15
  done
}

# Main execution
echo "Starting mirror script for $REPO"
echo "Batches to process: ${#BATCHES[@]}"
echo ""

SUCCESS=0
FAILED=0

for batch in "${BATCHES[@]}"; do
  trigger_and_wait "$batch"
  if [ $? -eq 0 ]; then
    ((SUCCESS++))
  else
    ((FAILED++))
    echo "⚠️  Continuing to next batch despite failure..."
  fi
done

echo ""
echo "=========================================="
echo "COMPLETE"
echo "=========================================="
echo "✅ Succeeded: $SUCCESS"
echo "❌ Failed: $FAILED"
echo ""
echo "Check repo contents:"
echo "  gh api repos/$REPO/contents --jq '.[].name'"
