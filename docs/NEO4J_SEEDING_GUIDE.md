# Neo4j Database Seeding Guide

> **Version:** 1.0.0  
> **Created:** 2026-01-01  
> **Last Updated:** 2026-01-01  
> **Status:** Active

---

## Overview

This guide documents the process for seeding and re-seeding the Neo4j graph database with book/chapter metadata. The seeding pipeline is designed to be **repeatable** and **idempotent**, allowing you to refresh the database whenever upstream metadata changes.

---

## Quick Start

```bash
# Navigate to ai-platform-data
cd /Users/kevintoles/POC/ai-platform-data

# Preview what will be seeded (no changes made)
./scripts/seed_database.sh --dry-run

# Seed fresh data (clears existing, then seeds)
./scripts/seed_database.sh --clear

# Add to existing data (no clear)
./scripts/seed_database.sh
```

---

## Prerequisites

### 1. Neo4j Container Running

The canonical Neo4j container must be running with ports exposed:

```bash
cd /Users/kevintoles/POC/ai-platform-data/docker
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d neo4j
```

**Verify:**
```bash
docker ps --filter "name=ai-platform-neo4j" --format "{{.Status}}"
# Should show: Up X minutes (healthy)
```

### 2. Python Environment

```bash
cd /Users/kevintoles/POC/ai-platform-data
source .venv/bin/activate  # or create: python -m venv .venv
pip install neo4j          # if not installed
```

### 3. Metadata Extraction Output

The seeding script reads from the llm-document-enhancer metadata extraction output:

```
/Users/kevintoles/POC/llm-document-enhancer/workflows/metadata_extraction/output/
├── book_001_metadata.json
├── book_002_metadata.json
├── ...
└── book_256_metadata.json
```

---

## Data Source

### Location

**Default Path:**  
`/Users/kevintoles/POC/llm-document-enhancer/workflows/metadata_extraction/output`

This can be overridden via environment variable:

```bash
METADATA_PATH=/path/to/custom/output ./scripts/seed_database.sh
```

### File Format

Each metadata JSON file contains:

```json
{
  "book_id": "clean-code",
  "title": "Clean Code: A Handbook of Agile Software Craftsmanship",
  "author": "Robert C. Martin",
  "tier": 2,
  "chapters": [
    {
      "chapter_number": 1,
      "title": "Clean Code",
      "keywords": ["readability", "maintainability", "craftsmanship"],
      "concepts": ["code quality", "professional development"],
      "summary": "Introduction to the principles of writing clean code..."
    },
    {
      "chapter_number": 2,
      "title": "Meaningful Names",
      "keywords": ["naming", "variables", "functions", "classes"],
      "concepts": ["intention-revealing names", "avoid disinformation"],
      "summary": "Guidelines for choosing meaningful names..."
    }
  ]
}
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `book_id` | string | Unique identifier for the book |
| `title` | string | Book title |
| `chapters` | array | List of chapter objects |
| `chapters[].chapter_number` | int | Chapter number |
| `chapters[].title` | string | Chapter title |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `author` | string | null | Book author |
| `tier` | int | 2 | Tier level (1-3) |
| `chapters[].keywords` | array | [] | Keywords for the chapter |
| `chapters[].concepts` | array | [] | Concepts covered in the chapter |
| `chapters[].summary` | string | null | Chapter summary |

---

## Seeding Commands

### Convenience Script

The recommended way to run seeding:

```bash
./scripts/seed_database.sh [OPTIONS]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--clear` | Clear all existing data before seeding |
| `--dry-run` | Show what would be done without making changes |
| `-v`, `--verbose` | Enable verbose output |
| `--help` | Show help message |

### Direct Python Script

For more control, run the Python script directly:

```bash
cd /Users/kevintoles/POC/ai-platform-data

# With environment variables
NEO4J_URI=bolt://localhost:7687 \
NEO4J_AUTH=neo4j/devpassword \
python scripts/seed_neo4j.py --use-metadata-extraction --clear -v
```

**Python Script Options:**

| Option | Description |
|--------|-------------|
| `--use-metadata-extraction` | Use llm-document-enhancer output (default) |
| `--no-metadata-extraction` | Use legacy books/ directory |
| `--clear` | Clear database before seeding |
| `--dry-run` | Show stats without making changes |
| `-v`, `--verbose` | Enable verbose logging |

---

## What Gets Seeded

### Node Types

| Node | Count (typical) | Description |
|------|-----------------|-------------|
| `Book` | ~300 | One per book metadata file |
| `Chapter` | ~8,000 | All chapters from all books |
| `Concept` | ~1,000 | Unique concepts extracted from chapters |
| `Tier` | 6 | Static tier hierarchy (Tiers 1-3, both perspectives) |

### Relationship Types

| Relationship | Count (typical) | Description |
|--------------|-----------------|-------------|
| `HAS_CHAPTER` | ~8,000 | Book → Chapter |
| `COVERS` | ~4,000 | Chapter → Concept |
| `PARALLEL` | ~63,000 | Tier ↔ Tier (same level) |
| `PERPENDICULAR` | ~28,000 | Tier ↔ Tier (different level) |

### Chapter Properties

Each `Chapter` node includes:

```cypher
(:Chapter {
  chapter_id: "clean-code-ch-1",
  book_id: "clean-code",
  number: 1,
  title: "Clean Code",
  keywords: ["readability", "maintainability"],
  concepts: ["code quality", "professional development"],
  summary: "Introduction to...",
  tier: 2
})
```

---

## Re-seeding Workflow

### When to Re-seed

Re-seed the database when:

1. **New books added** to metadata extraction output
2. **Metadata updated** (keywords, concepts, summaries)
3. **Schema changes** require fresh data
4. **Data corruption** or inconsistency detected

### Standard Re-seed Process

```bash
# 1. Verify Neo4j is running
docker ps --filter "name=ai-platform-neo4j"

# 2. Preview changes (optional)
./scripts/seed_database.sh --dry-run

# 3. Clear and re-seed
./scripts/seed_database.sh --clear

# 4. Verify results
docker exec ai-platform-neo4j cypher-shell -u neo4j -p devpassword \
  "MATCH (n) RETURN labels(n)[0] as type, count(*) as count ORDER BY count DESC"
```

### Expected Output

```
Database Statistics:
  Books: 303
  Chapters: 8381
  Concepts: 1042
  Tiers: 6
  HAS_CHAPTER relationships: 8381
  COVERS relationships: 4400
  PARALLEL relationships: 63086
  PERPENDICULAR relationships: 28420
```

---

## Troubleshooting

### Connection Refused

```
Error: Unable to connect to Neo4j at bolt://localhost:7687
```

**Solution:** Ensure Neo4j is running with ports exposed:

```bash
cd /Users/kevintoles/POC/ai-platform-data/docker
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d neo4j
```

### Authentication Failed

```
Error: The client is unauthorized due to authentication failure
```

**Solution:** Use the correct password (`devpassword` for local dev):

```bash
NEO4J_AUTH=neo4j/devpassword ./scripts/seed_database.sh
```

### No Metadata Files Found

```
Warning: No metadata files found in /path/to/output
```

**Solution:** Verify the metadata extraction pipeline has run:

```bash
ls -la /Users/kevintoles/POC/llm-document-enhancer/workflows/metadata_extraction/output/
```

### Constraint Violations

```
Error: Node with id X already exists with label 'Book'
```

**Solution:** Use `--clear` to remove existing data first:

```bash
./scripts/seed_database.sh --clear
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j connection URI |
| `NEO4J_AUTH` | `neo4j/devpassword` | Neo4j credentials (user/pass) |
| `METADATA_PATH` | `...llm-document-enhancer/.../output` | Path to metadata JSON files |

---

## Integration with Upstream Pipeline

### Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA FLOW                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. PDF Books                                                        │
│     └─→ llm-document-enhancer                                        │
│          └─→ workflows/metadata_extraction/output/*.json             │
│               └─→ seed_neo4j.py                                      │
│                    └─→ ai-platform-neo4j (Book, Chapter, Concept)    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Automation

To automate re-seeding after metadata extraction:

```bash
#!/bin/bash
# run_extraction_and_seed.sh

# Run metadata extraction
cd /Users/kevintoles/POC/llm-document-enhancer
python -m workflows.metadata_extraction.run

# Re-seed database
cd /Users/kevintoles/POC/ai-platform-data
./scripts/seed_database.sh --clear
```

---

## Schema Reference

For complete schema documentation including constraints, indexes, and relationship types, see:

- [SCHEMA_REFERENCE.md](SCHEMA_REFERENCE.md) - Full Neo4j schema documentation

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-01 | Initial guide created during PCON-3 |
