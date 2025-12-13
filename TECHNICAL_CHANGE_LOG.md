# ai-platform-data: Technical Change Log

**Purpose**: Documents architectural decisions, schema changes, and significant updates to the data repository.

---

## Changelog

### 2025-12-13: Initial Repository Setup (CL-001)

**Phase**: 1.1 ai-platform-data Scaffolding

**Actions**:
- Created repository structure per AI_CODING_PLATFORM_WBS.md specification
- Configured Poetry with Python 3.11+, jsonschema, pydantic dependencies
- Created placeholder directories for books/, taxonomies/, schemas/, scripts/

**Commit**: `2848980`

---

### 2025-12-13: JSON Schema Definition Complete (CL-002)

**Phase**: 1.3 JSON Schema Definition

**Schemas Created**:

| Schema | Purpose | Tests |
|--------|---------|-------|
| `book_raw.schema.json` | Raw textbook content structure | 8 |
| `book_metadata.schema.json` | Enriched metadata with tier info | 8 |
| `book_enriched.schema.json` | Full enrichment with embeddings | 7 |
| `taxonomy.schema.json` | Tier structure and relationships | 9 |

**TDD Results**: 32 tests passing (RED → GREEN → REFACTOR complete)

**Commit**: `51b5247`

---

### 2025-12-13: Taxonomy Registry for User-Directed Selection (CL-003)

**Issue**: Clarification on taxonomy usage - system houses multiple taxonomies but user specifies which to use at runtime.

**Decision**: Option C - Flexible user-directed selection with discovery mechanism

**Files Created**:

| File | Purpose |
|------|---------|
| `schemas/taxonomy_registry.schema.json` | Validates registry structure |
| `taxonomies/taxonomy_registry.json` | Lists available taxonomies with metadata |

**Key Design Principles**:
1. User specifies taxonomy at runtime (prompt/config/API)
2. System does NOT auto-select taxonomy
3. Registry provides discovery with metadata (tier_count, book_count, domains)
4. `default_taxonomy` field for convenience, always user-overridable

**Usage Examples**:
- Prompt: *"Use taxonomy `ai-ml-2024`"*
- Config: `taxonomy_id: ai-ml-2024`
- API: `POST /api/search?taxonomy=ai-ml-2024`

**TDD Results**: 10 new tests, 42 total passing

**Commit**: `0796e87`

---

### 2025-12-13: Phase 1.4 Data Migration Complete (CL-004)

**Phase**: 1.4 Data Migration

**Actions**:
- Created scalable migration script with `MigrationConfig` dataclass
- Migrated 47 books from `llm-document-enhancer` to `books/raw/`
- Updated `book_raw.schema.json` for flexible format support

**Scalability Patterns Applied** (per CODING_PATTERNS_ANALYSIS.md):
- `MigrationConfig` dataclass for batch_size, source_dir, target_dir
- Generator pattern: `migrate_books_batch()` yields `MigrationResult`
- Streaming validation for memory efficiency with 10K+ files
- Dynamic counts (no hardcoded "47")

**Schema Updates**:
- Added `anyOf` for `chapter_number` vs `number` field variants
- Added `additionalProperties: true` for flexibility
- Supports `PyMuPDF_fallback` extraction method

**Files Created**:

| File | Purpose |
|------|---------|
| `scripts/migrate_raw_books.py` | Scalable batch migration |
| `tests/unit/test_migration.py` | 22 migration tests |

**TDD Results**: 22 new tests, 64 total passing

**Commit**: `17ba2ec`

---

### 2025-12-13: Phase 2.1 Docker Configuration (CL-005)

**Phase**: 2.1 Docker Configuration

**Actions**:
- Created 37 TDD tests for Docker infrastructure validation
- Created Neo4j init scripts (constraints + indexes)
- Created Qdrant collection configuration
- Validated security patterns per Comp_Static_Analysis_Report

**Files Created**:

| File | Purpose |
|------|---------|
| `tests/unit/test_docker_compose.py` | 37 tests for Docker config validation |
| `docker/neo4j/init-scripts/01_constraints.cypher` | Book, Chapter, Concept, Tier constraints |
| `docker/neo4j/init-scripts/02_indexes.cypher` | Performance indexes for tier/priority queries |
| `docker/qdrant/config/collections.yaml` | chapters, concepts, keywords collections |

**Anti-Pattern Audit** (per Comp_Static_Analysis Issues #1-3, #17-20):
- ✅ No hardcoded passwords in docker-compose.yml
- ✅ Environment variable substitution pattern used
- ✅ Health checks defined for all services
- ✅ Redis has no auth in dev (correct pattern for local dev)

**Docker Services**:

| Service | Image | Ports | Purpose |
|---------|-------|-------|---------|
| neo4j | neo4j:5.15-community | 7474, 7687 | Graph database |
| qdrant | qdrant/qdrant:v1.7.4 | 6333, 6334 | Vector database |
| redis | redis:7-alpine | 6379 | Session storage |

**TDD Results**: 37 new tests, 101 total passing

**Commit**: `956c97e`

---

### 2025-12-13: Phase 2.2 Neo4j Schema (CL-006)

**Phase**: 2.2 Neo4j Schema

**Actions**:
- Created graph models module (`src/graph/__init__.py`) with EdgeType enum
- Created 17 integration tests for Neo4j schema validation
- Created 19 unit tests for graph models
- Documented PARALLEL/PERPENDICULAR/SKIP_TIER relationship types

**TIER_RELATIONSHIP_DIAGRAM.md Compliance**:

| Relationship | Definition | Validated |
|--------------|------------|-----------|
| PARALLEL | Same tier level (diff=0) | ✅ |
| PERPENDICULAR | Adjacent tiers (±1) | ✅ |
| SKIP_TIER | Non-adjacent tiers (±2+) | ✅ |

**Spider Web Model Support**:
- All relationships bidirectional (◄────►)
- Non-linear traversal: T1 → T2 → T3 → T1 supported
- PathResult dataclass for multi-hop queries

**Files Created**:

| File | Purpose |
|------|---------|
| `src/graph/__init__.py` | EdgeType enum, TraversalResult, PathResult dataclasses |
| `docker/neo4j/init-scripts/03_relationship_types.cypher` | Relationship type documentation |
| `tests/integration/test_neo4j_schema.py` | 17 integration tests (requires Neo4j) |
| `tests/unit/test_graph_models.py` | 19 unit tests for graph models |

**Graph Models**:

| Class | Purpose |
|-------|---------|
| EdgeType | Enum: PARALLEL, PERPENDICULAR, SKIP_TIER |
| NavigationDirection | Enum: UPWARD, DOWNWARD, LATERAL |
| TraversalResult | Single chapter traversal with edge type + score |
| PathResult | Multi-hop path through spider web graph |

**Anti-Pattern Audit** (per Comp_Static_Analysis, CODING_PATTERNS_ANALYSIS.md):
- ✅ EdgeType inherits from `str` for JSON serialization
- ✅ `to_dict()` methods return JSON-serializable dicts
- ✅ `get_edge_type_for_tier_diff()` utility for tier-based edge selection
- ✅ Dataclasses with frozen=False for Neo4j result mapping

**TDD Results**: 19 new tests, 120 total passing

---

## Schema Reference

| Schema | Version | Last Updated |
|--------|---------|--------------|
| book_raw.schema.json | draft-07 | 2025-12-13 |
| book_metadata.schema.json | draft-07 | 2025-12-13 |
| book_enriched.schema.json | draft-07 | 2025-12-13 |
| taxonomy.schema.json | draft-07 | 2025-12-13 |
| taxonomy_registry.schema.json | draft-07 | 2025-12-13 |

---

## Document Priority Reference

Changes follow this priority hierarchy:

| Priority | Document | Location |
|----------|----------|----------|
| 1 | GUIDELINES_AI_Engineering_Building_Applications_AIML_LLM_ENHANCED.md | `/textbooks/Guidelines/` |
| 2 | ARCHITECTURE.md (llm-gateway) | `/llm-gateway/docs/` |
| 3 | AI-ML_taxonomy_20251128.json | `/textbooks/Taxonomies/` |
| 4 | CODING_PATTERNS_ANALYSIS.md | `/textbooks/Guidelines/` |
