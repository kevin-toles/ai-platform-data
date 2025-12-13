# Scripts

This directory contains database seeding and migration scripts.

## Scripts

| Script | Purpose |
|--------|---------|
| `seed_neo4j.py` | Seeds Neo4j from books/metadata + taxonomies |
| `seed_qdrant.py` | Seeds Qdrant from books/enriched (with embeddings) |
| `seed_all.py` | Orchestrates full seed |
| `validate_seed.py` | Verifies seed integrity |
| `migrate.py` | Schema migrations |

## Usage

```bash
# Full seed
poetry run seed-all

# Individual seeds
poetry run seed-neo4j
poetry run seed-qdrant

# Validation
poetry run validate-seed
```
