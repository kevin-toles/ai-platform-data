# ai-platform-data (Pantry)

**Kitchen Brigade Role**: Pantry - Centralized data repository for the AI Coding Platform

## Overview

This repository serves as the **single source of truth** for all reference materials, taxonomies, and database configurations used across the AI Coding Platform services.

## Directory Structure

```
ai-platform-data/
├── books/
│   ├── raw/                     ← 47 JSON texts (source textbooks)
│   ├── metadata/                ← Extracted metadata (title, author, chapters)
│   └── enriched/                ← LLM-enhanced (keywords, concepts, summaries)
├── taxonomies/
│   ├── AI-ML_taxonomy.json      ← Tier structure (T1/T2/T3), 24+ books
│   └── domain_taxonomy.json     ← Domain classifications
├── schemas/
│   ├── book_raw.schema.json
│   ├── book_metadata.schema.json
│   ├── book_enriched.schema.json
│   └── taxonomy.schema.json
├── docker/
│   ├── docker-compose.yml       ← Canonical Neo4j + Qdrant definitions
│   ├── neo4j/
│   │   ├── init-scripts/        ← Cypher constraints/indexes
│   │   └── plugins/             ← APOC, GDS if needed
│   └── qdrant/
│       └── config/              ← Collection schemas
├── scripts/
│   ├── seed_neo4j.py            ← Seeds from books/metadata + taxonomies
│   ├── seed_qdrant.py           ← Seeds from books/enriched (with embeddings)
│   ├── seed_all.py              ← Orchestrates full seed
│   ├── validate_seed.py         ← Verifies seed integrity
│   └── migrate.py               ← Schema migrations
├── src/
│   ├── validators/              ← JSON schema validation
│   └── embeddings/              ← Embedding generation utilities
├── tests/
│   ├── unit/                    ← Schema validation tests
│   └── integration/             ← DB seeding tests
└── .github/workflows/
    ├── ci.yml                   ← Run tests on PR
    ├── sync-to-databases.yml    ← CI/CD sync on merge
    └── seed-databases.yml       ← Manual/scheduled full reseed
```

## Data Flow

```
textbooks/ (47 JSON) → books/raw/ → books/metadata/ → books/enriched/
                                          ↓                  ↓
                                     seed_neo4j.py      seed_qdrant.py
                                          ↓                  ↓
                                      Neo4j:7687        Qdrant:6333
                                    (Graph + Tiers)   (Vector Search)
```

## Kitchen Brigade Integration

| Service | Port | Role | Data Consumed |
|---------|------|------|---------------|
| llm-gateway | 8080 | Router | taxonomies/ |
| semantic-search-service | 8081 | Cookbook | books/enriched/, Neo4j, Qdrant |
| ai-agents | 8082 | Expeditor | books/metadata/ |
| Code-Orchestrator-Service | 8083 | Sous Chef | books/enriched/ |
| audit-service | 8084 | Auditor | schemas/, taxonomies/ |

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Poetry

### Setup

```bash
# Install dependencies
poetry install

# Start databases
docker compose -f docker/docker-compose.yml up -d

# Seed databases
python scripts/seed_all.py

# Validate seed
python scripts/validate_seed.py
```

### Running Tests

```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests (requires running databases)
pytest tests/integration/ -v

# All tests
pytest -v
```

## Schema Validation

All data files are validated against JSON schemas in `schemas/`:

```bash
# Validate a raw book
python -m src.validators.validate books/raw/my_book.json --schema schemas/book_raw.schema.json
```

## Database Connections

| Database | Port | Purpose |
|----------|------|---------|
| Neo4j | 7474 (HTTP), 7687 (Bolt) | Graph traversal, tier relationships |
| Qdrant | 6333 (HTTP), 6334 (gRPC) | Vector search, semantic similarity |
| Redis | 6379 | Session cache, rate limiting |

## References

- [AI_CODING_PLATFORM_ARCHITECTURE.md](../textbooks/pending/platform/AI_CODING_PLATFORM_ARCHITECTURE.md)
- [AI_CODING_PLATFORM_WBS.md](../textbooks/pending/platform/AI_CODING_PLATFORM_WBS.md)
- [TIER_RELATIONSHIP_DIAGRAM.md](../textbooks/TIER_RELATIONSHIP_DIAGRAM.md)

## License

MIT
