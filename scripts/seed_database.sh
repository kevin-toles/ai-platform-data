#!/bin/bash
# seed_database.sh - Convenience script for seeding Neo4j database
#
# Usage:
#   ./scripts/seed_database.sh              # Normal seeding
#   ./scripts/seed_database.sh --clear      # Re-seed from scratch
#   ./scripts/seed_database.sh --dry-run    # Preview what would happen
#
# Prerequisites:
#   - Neo4j running with dev ports exposed:
#     cd docker && docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d neo4j
#
# PCON-3: Uses llm-document-enhancer metadata extraction output

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Default environment for development
export NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
export NEO4J_AUTH="${NEO4J_AUTH:-neo4j/devpassword}"

# Metadata extraction path (from llm-document-enhancer)
export METADATA_PATH="${METADATA_PATH:-/Users/kevintoles/POC/llm-document-enhancer/workflows/metadata_extraction/output}"

echo "🗃️  Neo4j Seeding Script"
echo "========================"
echo "NEO4J_URI: $NEO4J_URI"
echo "METADATA_PATH: $METADATA_PATH"
echo ""

# Check if Neo4j is accessible
if ! nc -z localhost 7687 2>/dev/null; then
    echo "❌ Error: Neo4j not accessible at localhost:7687"
    echo ""
    echo "Start Neo4j with dev ports exposed:"
    echo "  cd $PROJECT_DIR/docker"
    echo "  docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d neo4j"
    exit 1
fi

# Run the seeding script with all arguments passed through
cd "$PROJECT_DIR"
python3 scripts/seed_neo4j.py "$@"
