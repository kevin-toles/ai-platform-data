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
