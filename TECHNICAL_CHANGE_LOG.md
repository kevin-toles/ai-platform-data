# ai-platform-data: Technical Change Log

**Purpose**: Documents architectural decisions, schema changes, and significant updates to the data repository.

---

## Changelog

### 2025-12-18: WBS 3.5.2 Data Transfer & Validation Complete (CL-010)

**Phase**: 3.5.2 Data Pipeline - Data Transfer & Validation

**TDD Methodology Applied**:
- ✅ Phase 0: Document Analysis (AI_CODING_PLATFORM_ARCHITECTURE, CODING_PATTERNS_ANALYSIS)
- ✅ RED: `test_all_books_have_chapters` already existed and was failing
- ✅ GREEN: Transferred 12 re-processed books from llm-document-enhancer
- ✅ GREEN: All 47 books now have chapters (1,922 total chapters)
- ✅ REFACTOR: Created `scripts/validate_raw_books.py` CLI tool

**Changes Made**:

| File | Change |
|------|--------|
| `tests/unit/test_chapter_segmentation.py` | Updated to handle schema's anyOf (number OR chapter_number) |
| `scripts/validate_raw_books.py` | NEW - CLI tool for validating raw book JSON files |
| `books/raw/*.json` | 12 books updated with populated chapters from llm-document-enhancer |

**Schema Compliance Fix**:
- `book_raw.schema.json` defines chapter identifier as `anyOf: [number, chapter_number]`
- Updated test to support both formats (legacy `chapter_number` + current `number`)
- Legacy books (`Learning Python Ed6`, `Python Cookbook 3rd`) use `chapter_number`

**Validation Results**:
```
📚 Raw Books Validation Summary
┌────────────────┬───────┐
│ Metric         │ Value │
├────────────────┼───────┤
│ Total Books    │ 47    │
│ Total Chapters │ 1922  │
│ Passed         │ 47    │
│ Failed         │ 0     │
└────────────────┴───────┘
✅ All books validated successfully!
```

**Books Transferred (12)**:
- Architecture Patterns with Python (13 chapters)
- Building Microservices (12 chapters)
- Building Python Microservices with FastAPI (46 chapters)
- Fluent Python 2nd (50 chapters)
- Microservice APIs Using Python Flask FastAPI (43 chapters)
- Microservice Architecture (18 chapters)
- Microservices Up and Running (32 chapters)
- Python Architecture Patterns (16 chapters)
- Python Data Analysis 3rd (13 chapters)
- Python Distilled (39 chapters)
- Python Essential Reference 4th (26 chapters)
- Python Microservices Development (38 chapters)

---

### 2025-12-13: Data Pipeline Workflow Clarification (CL-009)

**Phase**: 3.5 Data Pipeline Completion

**Issue**: WBS Phase 3.5 originally implied that `ai-platform-data` would run chapter segmentation directly. This conflicted with the established separation of concerns.

**Decision**: **Process in Enhancer → Transfer → Validate Pattern**

**Workflow Established**:
```
┌─────────────────────────┐     Manual      ┌─────────────────────────┐
│  llm-document-enhancer  │ ──────────────► │    ai-platform-data     │
│                         │    Transfer     │                         │
│  • PDF → JSON           │                 │  • Validate data        │
│  • Chapter segmentation │                 │  • Store in books/raw/  │
│  • Metadata enrichment  │                 │  • Seed to databases    │
│  • Similar chapters     │                 │  • Serve to platform    │
└─────────────────────────┘                 └─────────────────────────┘
```

**ai-platform-data Responsibilities:**
- ✅ Validate incoming JSON files against schemas
- ✅ Store validated files in `books/raw/` and `books/enriched/`
- ✅ Seed Neo4j and Qdrant databases
- ✅ Serve data to platform services
- ❌ NOT responsible for: PDF processing, segmentation, enrichment

**Current Status:**
- ✅ All 47 books have chapters populated (1,922 total)
- ✅ 12 previously empty books re-processed and transferred
- `books/enriched/` is empty (enrichment not yet run)

**Books Needing Re-Processing** (to be done in llm-document-enhancer):
1. Architecture Patterns with Python.json
2. Building Microservices.json
3. Building Python Microservices with FastAPI.json
4. Fluent Python 2nd.json
5. Microservice APIs Using Python Flask FastAPI.json
6. Microservice Architecture.json
7. Microservices Up and Running.json
8. Python Architecture Patterns.json
9. Python Data Analysis 3rd.json
10. Python Distilled.json
11. Python Essential Reference 4th.json
12. Python Microservices Development.json

**Validation Tests Created**:
- `tests/unit/test_chapter_segmentation.py` - Validates all books have chapters
- More validation tests to be added per WBS 3.5.2

**WBS Reference**: AI_CODING_PLATFORM_WBS.md v1.5.0

---

### 2025-12-13: Enrichment Scalability - Full Corpus Pattern (CL-008)

**Phase**: 3.7 Incremental/Delta Enrichment Pipeline

**Issue**: Enriched book data (`similar_chapters`) was computed per taxonomy, creating scalability issues:
- Different enriched files needed per taxonomy
- Adding new book required O(n²) re-enrichment
- Storage: 47 books × t taxonomies = 47t files

**Decision**: Compute `similar_chapters` against FULL corpus, filter at query-time

**Impact on this Repository**:

| Component | Change |
|-----------|--------|
| `books/enriched/*.json` | `similar_chapters` now references ANY book in corpus, not taxonomy-limited |
| `scripts/enrich_new_book.py` | NEW: Delta enrichment script for incremental updates |
| `books/enriched/` count | Stays at 47 (one per book, not per taxonomy) |

**Schema Implications**:
- `book_enriched.schema.json` unchanged (already supports flexible `similar_chapters`)
- `similar_chapters[].book` can reference any book, filtered at query-time

**Query-Time Filtering**:
```python
# API call with taxonomy filter
POST /v1/search/similar-chapters
{
    "chapter_id": "arch_patterns_ch4",
    "taxonomy": "AI-ML_taxonomy"  # Filter similar_chapters by books in this taxonomy
}
```

**Benefits for ai-platform-data**:
1. Single enriched file per book (not per taxonomy)
2. Adding new book = O(n) delta update, not O(n²) full re-run
3. Taxonomy changes don't require re-enrichment

---

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

### 2025-12-13: Taxonomy-Agnostic Architecture Decision (CL-007)

**Issue**: Original design baked taxonomy tier information into seeded data, requiring re-seeding whenever:
- A new taxonomy was added
- An existing taxonomy was modified
- A user wanted to use a different taxonomy

**Conflict Assessment** (per GUIDELINES_AI_Engineering Section 4.8):

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| **A** | Tier baked into metadata | Simple seeding | Re-seed on any taxonomy change |
| **B** | Separate tier collection per taxonomy | Clean isolation | Data duplication, complex queries |
| **C** | Taxonomy as query-time overlay | No re-seeding ever, flexible | Slightly more complex queries |

**Decision**: **Option C - Taxonomy as Query-Time Overlay**

**Rationale**:
1. **Zero Re-Seeding**: Adding/modifying taxonomies requires NO database operations
2. **Multi-Tenant Support**: Different teams can use different taxonomies simultaneously
3. **User-Directed**: Users specify taxonomy via prompt/API at runtime
4. **Same Book, Different Views**: Book can have different tier/priority in different taxonomies

**Architecture Change**:

```
BEFORE (Tier Baked In):
┌─────────────────────────────────────────────────────────────┐
│  Metadata Extraction                                         │
│  book.json → extract_metadata.py → metadata with tier=3     │
│                                    ↓                         │
│  Seeding                          tier baked into payload   │
│                                    ↓                         │
│  Query                            results have fixed tier    │
│                                                              │
│  ❌ Change taxonomy = re-seed everything                     │
└─────────────────────────────────────────────────────────────┘

AFTER (Query-Time Overlay):
┌─────────────────────────────────────────────────────────────┐
│  Metadata Extraction                                         │
│  book.json → extract_metadata.py → metadata (NO tier)       │
│                                    ↓                         │
│  Seeding                          tier-agnostic payloads    │
│                                    ↓                         │
│  Query (with taxonomy parameter)                             │
│  1. Search Qdrant (taxonomy-agnostic)                       │
│  2. Load taxonomy from taxonomies/ directory                │
│  3. Apply tier mapping at query time                        │
│  4. Return results with tier attached                        │
│                                                              │
│  ✅ Change taxonomy = just edit JSON file, immediate effect │
└─────────────────────────────────────────────────────────────┘
```

**Files Affected**:

| File | Change |
|------|--------|
| `scripts/extract_metadata.py` | Remove tier assignment, make taxonomy-agnostic |
| `scripts/seed_neo4j.py` | Remove tier from Book/Chapter nodes |
| `scripts/seed_qdrant.py` | Remove tier from payloads |
| `taxonomies/` | Remains source of taxonomy files (query-time loaded) |

**API Contract**:

```python
# Search WITHOUT taxonomy (returns all results, no tier info)
POST /v1/search/hybrid
{"query": "rate limiting"}

# Search WITH taxonomy (query-time overlay, no re-seeding!)
POST /v1/search/hybrid
{
    "query": "rate limiting",
    "taxonomy": "AI-ML_taxonomy",    # Loaded from taxonomies/ at query time
    "tier_filter": [1, 2]            # Only return tier 1 and 2 books
}
```

**WBS Impact**:
- Added Phase 3.6: Taxonomy Registry & Query-Time Resolution
- Updated Phase 4 APIs to accept `taxonomy` and `tier_filter` parameters
- Total duration increased from 26.5 to 27.5 days

---

## Document Priority Reference

Changes follow this priority hierarchy:

| Priority | Document | Location |
|----------|----------|----------|
| 1 | GUIDELINES_AI_Engineering_Building_Applications_AIML_LLM_ENHANCED.md | `/textbooks/Guidelines/` |
| 2 | ARCHITECTURE.md (llm-gateway) | `/llm-gateway/docs/` |
| 3 | AI-ML_taxonomy_20251128.json | `/textbooks/Taxonomies/` |
| 4 | CODING_PATTERNS_ANALYSIS.md | `/textbooks/Guidelines/` |
