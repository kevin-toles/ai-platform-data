"""Database seeding and migration scripts.

This package contains scripts for:
- seed_neo4j: Seeds Neo4j from books/metadata + taxonomies
- seed_qdrant: Seeds Qdrant from books/enriched (with embeddings)
- seed_all: Orchestrates full seed
- validate_seed: Verifies seed integrity
- migrate: Schema migrations
"""
