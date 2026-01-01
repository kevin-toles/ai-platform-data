# ai-platform-data: Technical Change Log

**Purpose**: Documents architectural decisions, schema changes, and significant updates to the data repository.

---

## Changelog

### 2025-12-31: Qwen3 Model Series Addition (CL-019)

**Summary**: Added two new Qwen3 models to the inference-service model registry, expanding code generation capabilities with both a dense model (Qwen3-8B) and a Mixture of Experts model (Qwen3-Coder-30B-A3B).

**Models Added**:

| Model | File | Size | Architecture | Use Case |
|-------|------|------|--------------|----------|
| `qwen3-8b` | Qwen3-8B-Q4_K_M.gguf | 4.7GB | Dense | General-purpose, good at code - D4v2 preset |
| `qwen3-coder-30b-a3b` | Qwen3-Coder-30B-A3B-Instruct-Q3_K_M.gguf | 14GB | MoE (128 experts, 8 active) | Standalone code generation - S10 preset |

**Qwen3-Coder-30B-A3B MoE Architecture**:
- Total Parameters: 30.5B
- Active Parameters per Token: 3.3B
- Experts: 128 total, 8 activated per inference
- Native Context: 256K (extendable to 1M)
- Quantization: Q3_K_M (~14GB)

**New Presets Added**:

| Preset | Models | Size | Mode | Description |
|--------|--------|------|------|-------------|
| `S9` | qwen3-8b | 4.7GB | single | Qwen3 8B standalone |
| `S10` | qwen3-coder-30b-a3b | 14GB | single | MoE code specialist standalone |
| `D4v2` | deepseek-r1-7b + qwen3-8b | 9.4GB | critique | Upgraded D4 with Qwen3 |

**Configuration Files Updated**:

| File | Location | Changes |
|------|----------|---------|
| `models.yaml` | ai-models/config/ | Added qwen3-8b, qwen3-coder-30b-a3b definitions |
| `presets.yaml` | inference-service/config/ | Added S9, S10, D4v2 presets |
| `ARCHITECTURE.md` | inference-service/docs/ | Updated model tables, context constraints, folder structure |
| `WBS.md` | inference-service/docs/ | Added Qwen3 model options reference |

**Source Repositories**:
- qwen3-8b: `Qwen/Qwen3-8B-GGUF`
- qwen3-coder-30b-a3b: `unsloth/Qwen3-Coder-30B-A3B-Instruct-GGUF`

**Cross-References**:
- inference-service/docs/ARCHITECTURE.md: v1.4.0
- inference-service/config/presets.yaml: 35+ presets now available

---

### 2025-12-31: Architecture Documentation Update - inference-service Integration (CL-018)

**Summary**: Updated architecture documents across repositories to include `inference-service` (port 8085) which was missing from the master platform architecture document despite being active since December 27, 2025.

**Documents Updated**:

| Document | Location | Changes |
|----------|----------|---------|
| `AI_CODING_PLATFORM_ARCHITECTURE.md` | textbooks/pending/platform/ | Added inference-service to Platform Services table, Network Topology diagram |
| `ARCHITECTURE.md` | llm-gateway/docs/ | Added inference-service to Platform Services, documented LlamaCpp provider routing |

**Platform Services (Updated)**:

| Service | Port | Role |
|---------|------|------|
| `llm-gateway` | 8080 | Router (entry point) |
| `semantic-search-service` | 8081 | Cookbook (retrieval) |
| `ai-agents` | 8082 | Expeditor (orchestration) |
| `Code-Orchestrator-Service` | 8083 | Sous Chef (ML models) |
| `audit-service` | 8084 | Auditor (validation) |
| `inference-service` | 8085 | **NEW** - Local LLM Inference |
| `ai-platform-data` | N/A | Pantry (storage) |

**inference-service Details**:
- Backend: llama-cpp-python + Metal (Mac), vLLM + CUDA (future)
- API: OpenAI-compatible (`/v1/chat/completions`)
- Access: Internal only (called by llm-gateway via llamacpp provider)
- Models: phi-4, deepseek-r1-7b, qwen2.5-7b, llama-3.2-3b, phi-3-medium-128k, granite-8b-code-128k

**Cross-References**:
- inference-service/docs/ARCHITECTURE.md: v1.3.0 (source of truth for inference-service)
- llm-gateway/src/providers/llamacpp.py: LlamaCpp provider implementation

---

### 2025-12-31: Model Configuration Single Source of Truth (CL-017)

**Summary**: Resolved configuration drift between `ai-models` and `inference-service` repos. Established **inference-service** as the single owner of all model configuration, with ai-models becoming storage-only.

**Conflict Analysis**:

| Issue | Description |
|-------|-------------|
| Duplicate Config | `models.yaml` existed in both repos with different values |
| Maintenance Burden | `gpu_layers` had to be updated in two places |
| Drift Risk | Path formats differed (`phi-4-Q4_K_S.gguf` vs `phi-4/phi-4-Q4_K_S.gguf`) |
| Principle Violation | Violated Single Source of Truth (SSOT) |

**Resolution (Option A Adopted)**:

| Action | File | Result |
|--------|------|--------|
| **DELETE** | `ai-models/config/models.yaml` | Removed duplicate |
| **DELETE** | `ai-models/config/configs.yaml` | Removed duplicate (presets) |
| **UPDATE** | `ai-models/README.md` | Clarified storage-only role |
| **UPDATE** | `inference-service/docs/ARCHITECTURE.md` | Documented ownership |
| **KEEP** | `ai-models/scripts/download_models.py` | Self-contained (has own MODELS dict) |

**New Architecture**:

| Repo | Responsibility | Config Files |
|------|----------------|--------------|
| **inference-service** | Runtime config (models, presets, gpu_layers) | `config/models.yaml`, `config/presets.yaml` |
| **ai-models** | Storage (model files, downloads) | None (storage-only) |

**Cross-References**:
- Building Microservices (Newman): "Service autonomy - can you deploy by itself?"
- Beyond 12-Factor App (Hoffman): "Externalize configuration per service"
- AI_CODING_PLATFORM_ARCHITECTURE.md: Kitchen Brigade - each service owns its domain

**Document Priority Applied**: Resolved per document hierarchy (Priority 1-5)

---

### 2025-12-29: Protocol Integration Architecture - Phase 2 (CL-016)

**Summary**: Created Protocol Integration Architecture document for A2A (Agent-to-Agent) and MCP (Model Context Protocol) integration as Phase 2 of the Agent Architecture Evolution. All features are behind feature flags for safe experimentation.

**Documents Created**:

| Document | Location | Purpose |
|----------|----------|---------|
| `PROTOCOL_INTEGRATION_ARCHITECTURE.md` | ai-agents/docs/ | Phase 2 architecture for A2A + MCP |

**Architecture Evolution Phases**:

| Phase | Focus | Status | Document |
|-------|-------|--------|----------|
| Phase 1 | Agent Functions + ADK Patterns | ✅ Complete | AGENT_FUNCTIONS_ARCHITECTURE.md |
| Phase 2 | Protocol Integration (A2A + MCP) | 🚧 Design | PROTOCOL_INTEGRATION_ARCHITECTURE.md |
| Phase 3 | Full ADK Migration | 📋 Planned | ADK_MIGRATION_GUIDE.md |

**Feature Flags Introduced**:
```bash
# A2A Protocol
AGENTS_A2A_ENABLED=false
AGENTS_A2A_AGENT_CARD_ENABLED=false
AGENTS_A2A_STREAMING_ENABLED=false

# MCP Protocol
AGENTS_MCP_ENABLED=false
AGENTS_MCP_SERVER_ENABLED=false
AGENTS_MCP_TOOLBOX_QDRANT=false
AGENTS_MCP_TOOLBOX_NEO4J=false
```

**No-Conflict Analysis**:
- ✅ A2A is a protocol layer—does not replace agent functions
- ✅ MCP standardizes tool interfaces—wraps existing tools
- ✅ Both are opt-in via feature flags—zero impact on Phase 1
- ✅ Agent functions remain the execution unit

**A2A Integration Highlights**:
- Agent Cards expose service capabilities at `/.well-known/agent-card.json`
- 8 agent functions mapped to A2A Skills
- A2A Task lifecycle maps to pipeline execution states
- Streaming via SSE for task updates

**MCP Integration Highlights**:
- MCP Server: Expose agent functions as MCP tools for external clients
- MCP Client: Consume MCP Toolbox for Qdrant, Neo4j, Redis operations
- Standardized tool interface for cross-platform compatibility

**Implementation Timeline** (6 weeks):
- Week 1: Feature Flags + Agent Card
- Week 2: MCP Server
- Week 3: MCP Client (Qdrant Toolbox)
- Week 4: A2A Task Lifecycle
- Week 5: A2A Streaming
- Week 6: Integration Testing

**Cross-References**:
- [PROTOCOL_INTEGRATION_ARCHITECTURE.md](../ai-agents/docs/PROTOCOL_INTEGRATION_ARCHITECTURE.md) - Phase 2 design
- [AGENT_FUNCTIONS_ARCHITECTURE.md](../ai-agents/docs/AGENT_FUNCTIONS_ARCHITECTURE.md) - Phase 1 foundation
- [A2A Protocol Spec](https://a2a-protocol.org/latest/specification/) - External reference
- [MCP Documentation](https://modelcontextprotocol.io/) - External reference

**Deviations from Original Architecture**: None - Protocol layer is additive

---

### 2025-12-29: ADK Pattern Integration - Agent Functions Architecture (CL-015)

**Summary**: Integrated Google Agent Development Kit (ADK) patterns into the Agent Functions Architecture using Option C (Cherry-Pick Patterns) approach. Created migration guide for future full ADK adoption (Option A).

**Documents Updated**:

| Document | Location | Changes |
|----------|----------|---------|
| `AGENT_FUNCTIONS_ARCHITECTURE.md` | ai-agents/docs/ | v1.0.0 → v1.1.0: Added ADK Pattern Integration section |
| `ADK_MIGRATION_GUIDE.md` | ai-agents/docs/ | NEW: Full Option A migration roadmap |

**Option C Patterns Adopted**:

| ADK Pattern | Platform Implementation | Benefit |
|-------------|-------------------------|---------|
| State Prefixes (`temp:`, `user:`, `app:`) | Cache key conventions | Industry standard, clear scope |
| Artifact Conventions | Versioned artifact naming | Consistent versioning |
| AgentTool Pattern | Agent function as callable | ADK compatibility |
| Workflow Agent Mapping | Pipeline → SequentialAgent | Future migration path |

**State Prefix Mapping**:
```
temp:  → handoff_cache (pipeline-local, discarded after completion)
user:  → compression_cache (Redis, 24h TTL, cross-session)
app:   → artifact_store (Qdrant/Neo4j, permanent)
```

**Architecture Alignment**:
- ✅ Kitchen Brigade: No role changes, patterns enhance existing architecture
- ✅ Stateless executors: ADK's shared session state aligns with our caching philosophy
- ✅ Gateway-First: External requests still route through llm-gateway:8080
- ✅ CODING_PATTERNS_ANALYSIS: `**kwargs` ABC pattern used for flexible signatures

**Future Migration Path** (Option A - Documented, Not Implemented):
- Phase 1: Foundation (2-3 weeks) - ADK adapter layer
- Phase 2: Workflow Agents (2-3 weeks) - SequentialAgent, ParallelAgent, LoopAgent
- Phase 3: State Migration (1-2 weeks) - Full prefix adoption
- Phase 4: Full Integration (2 weeks) - Legacy deprecation
- Total: 7-10 weeks when team resources available

**Cross-References**:
- [AGENT_FUNCTIONS_ARCHITECTURE.md](../ai-agents/docs/AGENT_FUNCTIONS_ARCHITECTURE.md) - Current Option C implementation
- [ADK_MIGRATION_GUIDE.md](../ai-agents/docs/ADK_MIGRATION_GUIDE.md) - Future Option A roadmap
- [Google ADK Documentation](https://google.github.io/adk-docs/) - External reference

**Deviations from Original Architecture**: None - Option C enhances without changing service boundaries

---

### 2025-12-18: EEP-6 Diagram Similarity - Data Schema Impact (CL-014)

**Summary**: EEP-6 Diagram Similarity was implemented in Code-Orchestrator-Service. This change has potential future impact on the enriched data schema stored in ai-platform-data.

**Impact Assessment**:

| Aspect | Impact | Notes |
|--------|--------|-------|
| Current Schema | None | EEP-6 does not modify existing enriched files |
| Future Schema | Planned | `diagram_references` field may be added to enriched chapters |
| Seeder Updates | None Required | No changes to `seed_qdrant.py` or `seed_neo4j.py` |

**Potential Future Schema Extension**:
```json
{
  "chapters": [{
    "title": "Chapter 1",
    "keywords": [...],
    "concepts": [...],
    "similar_chapters": [...],
    "diagram_references": [
      {
        "type": "FIGURE",
        "caption": "Figure 3.1: System Architecture",
        "context": "...",
        "line_number": 42
      }
    ]
  }]
}
```

**Architecture Alignment**:
- ✅ Kitchen Brigade: ai-platform-data remains storage-only (Pantry role)
- ✅ Processing happens in Code-Orchestrator-Service (Sous Chef role)
- ✅ No code changes required in this repository for EEP-6

**Deviations from Original Architecture**: None

---

### 2025-12-15: Data Pipeline Fix - Naming Convention & Script Deletion (CL-013)

**Issue**: WBS 3.5.6 correlation tests failed due to incompatible book_id/chapter_id formats between Neo4j and Qdrant.

**Root Cause**: `scripts/extract_metadata.py` creates IDs incompatible with llm-document-enhancer output.

```
extract_metadata.py:    a_philosophy_of_software_design_e5927c5e
llm-document-enhancer:  A Philosophy of Software Design_metadata.json
                        ↑ Completely different naming schemes!
```

**Decisions Made**:

| Decision | Choice |
|----------|--------|
| extract_metadata.py | **DELETE** - creates incompatible IDs |
| File naming | `{Book Title}_metadata_enriched.json` |
| Seeder updates | Read from new naming convention |

**Changes Planned** (per `DATA_PIPELINE_FIX_WBS.md`):

| Phase | Change | Status |
|-------|--------|--------|
| D1.2.1 | Delete `scripts/extract_metadata.py` | ✅ DONE |
| D2.2.2 | Update `validate_enriched_books.py` for new naming | ✅ DONE |
| D2.2.3 | Update `seed_qdrant.py` for new naming | ⏭️ SKIPPED (uses `*.json` glob, works as-is) |
| D2.2.4 | Update `seed_neo4j.py` for new naming | ⏭️ SKIPPED (reads from metadata/, not enriched/) |
| D3.1.2 | Create `scripts/sync_from_enhancer.py` | ✅ DONE |

**D3.1 Implementation Details** (2025-12-16):
- Created `tests/unit/test_sync_from_enhancer.py` (TDD RED→GREEN)
- Created `scripts/sync_from_enhancer.py` with:
  - Source path validation (directory exists, contains enriched files)
  - File renaming: `{Book}_enriched.json` → `{Book}_metadata_enriched.json`
  - Checksum verification post-copy
  - `--dry-run` flag for preview mode
  - Rich CLI output with verbose option
- 26 tests pass (TDD GREEN phase complete)
- Full test suite: 206 passed, 8 failed (D2.2 RED expected), 66 skipped
- Anti-pattern audit: S1192 (constants), S3776 (decomposed), S1172 (underscore prefixes)

**D2.2 Implementation Details** (2025-12-16):
- Created `tests/unit/test_d22_naming_convention_validation.py` (TDD RED phase)
- Updated `validate_enriched_books.py`:
  - Added `enrichment_metadata` to `REQUIRED_TOP_LEVEL_KEYS`
  - Added `REQUIRED_PROVENANCE_FIELDS` constant (8 fields)
  - Added `_validate_enrichment_metadata()` function
  - Added `_validate_naming_convention()` function
  - Updated `validate_book()` to call new validation functions
- Tests in RED state (expected - files lack provenance until D3 migration)
- Full test suite: 165 passed, 8 failed (D2.2 tests), 1 skipped

**Why seed scripts don't need changes**:
- `seed_qdrant.py`: Uses `glob("*.json")` which matches any naming convention
- `seed_neo4j.py`: Reads from `books/metadata/`, not `books/enriched/`

**D1 Implementation Details** (2025-12-15):
- Verified no imports of `extract_metadata` across codebase
- Verified no CI/CD workflows reference the script
- Deleted `scripts/extract_metadata.py`
- Updated `test_qdrant_seeding.py` error message (line 130)
- All 162 tests pass after deletion

**Why extract_metadata.py Must Be Deleted**:
1. Creates `generate_book_id()` with snake_case + hash format
2. Duplicates functionality already in llm-document-enhancer
3. Violates "Single Source of Truth" architecture principle
4. Root cause of Neo4j/Qdrant data mismatch

**Enrichment Provenance Standard** (new):
All enriched files must include:
```json
{
  "enrichment_metadata": {
    "taxonomy_id": "ai-ml-2024",
    "taxonomy_version": "1.0.0",
    "taxonomy_checksum": "sha256:...",
    "source_metadata_file": "{Book}_metadata.json"
  }
}
```

**Architecture Alignment**:
- ✅ ai-platform-data = Storage/Validation only (Pantry)
- ✅ llm-document-enhancer = Processing (Extraction, Enrichment)
- ✅ Single Source: All data flows from llm-document-enhancer → ai-platform-data

**Anti-Pattern Audit**:
- Verified against `CODING_PATTERNS_ANALYSIS.md`
- New sync script will follow S1192, S3776, S1172 guidelines

**Reference**: `DATA_PIPELINE_FIX_WBS.md` in textbooks/pending/platform/

---

### 2025-12-19: WBS 3.5.5 Update Seeding Scripts for Enriched Data (CL-012)

**Phase**: 3.5.5 Data Pipeline - Qdrant Seeding with Enriched Payloads

**TDD Methodology Applied**:
- ✅ Phase 0: Document Analysis (seed_qdrant.py, seed_neo4j.py, AI_CODING_PLATFORM_ARCHITECTURE)
- ✅ RED: Created `test_wbs_355_qdrant_enriched.py` with 17 tests - 4 failed initially
- ✅ GREEN: Updated `seed_chapters_from_enriched()` payload to include all enriched fields
- ✅ REFACTOR: Extracted helper functions to reduce cognitive complexity (S3776)

**Changes Made**:

| File | Change |
|------|--------|
| `tests/unit/test_wbs_355_qdrant_enriched.py` | NEW - 17 TDD tests for enriched Qdrant seeding |
| `scripts/seed_qdrant.py` | MODIFIED - Added enriched fields to payload, extracted helpers |

**SonarQube Compliance**:
- ✅ S1192: Added `JSON_GLOB_PATTERN = "*.json"` constant (was duplicated 4 times)
- ✅ S1192: Added `MAX_CONTENT_LENGTH = 8000` constant
- ✅ S3776: Extracted `_build_enriched_payload()` helper (cognitive complexity 17 → <15)
- ✅ S3776: Extracted `_process_enriched_book()` helper
- ✅ Unused variable: Renamed `config` to `_config` with noqa comment

**Enriched Payload Structure**:
```python
payload = {
    "chapter_id": chapter_id,
    "book_id": book_id,
    "book_title": book.get("metadata", {}).get("title", ""),
    "title": chapter.get("title", ""),
    "number": chapter.get("number") or chapter.get("chapter_number"),
    "tier": book.get("metadata", {}).get("tier"),
    # NEW enriched fields from WBS 3.5.3/3.5.4
    "keywords": chapter.get("keywords", []),
    "concepts": chapter.get("concepts", []),
    "summary": chapter.get("summary", ""),
    "similar_chapters": chapter.get("similar_chapters", []),
}
```

**Test Results**:
```
tests/unit/test_wbs_355_qdrant_enriched.py - 17 passed
Full suite: 151 passed, 1 skipped in 8.36s
```

**Cross-Reference**: 
- Enriched data from WBS 3.5.4 (CL-011) now flows to Qdrant payloads
- Similar chapters use SBERT method per CL-029 in llm-document-enhancer
- Neo4j correlation validated via test (same enriched source)

**WBS Reference**: AI_CODING_PLATFORM_WBS.md v1.5.0 (Phase 3.5.5.1-8)

---

### 2025-12-19: WBS 3.5.4 Enriched Data Transfer & Validation Complete (CL-011)

**Phase**: 3.5.4 Data Pipeline - Enriched Data Transfer & Validation

**TDD Methodology Applied**:
- ✅ Phase 0: Document Analysis (AI_CODING_PLATFORM_ARCHITECTURE, WBS specifications)
- ✅ RED: Created `test_wbs_354_enriched_validation.py` with 10 tests - all failed (directory empty)
- ✅ GREEN: Transferred 47 enriched books from llm-document-enhancer
- ✅ REFACTOR: Created `scripts/validate_enriched_books.py` CLI tool

**Changes Made**:

| File | Change |
|------|--------|
| `tests/unit/test_wbs_354_enriched_validation.py` | NEW - 10 validation tests for enriched books |
| `scripts/validate_enriched_books.py` | NEW - CLI tool for validating enriched book JSON files |
| `books/enriched/*.json` | 47 files transferred from llm-document-enhancer |

**Validation Results**:
```
📚 WBS 3.5.4 Enriched Book Validation Report
┌────────────────┬───────┐
│ Metric         │ Value │
├────────────────┼───────┤
│ Total Books    │ 47    │
│ Expected Books │ 47    │
│ Passed         │ 47    │
│ Failed         │ 0     │
│ Total Issues   │ 0     │
└────────────────┴───────┘
✓ Book count matches expected: 47
✓ All validations passed!
```

**Enriched Data Structure Validated**:
- ✅ Top-level keys: `metadata`, `chapters`, `pages`, `enrichment`
- ✅ All chapters have `keywords` (list)
- ✅ All chapters have `concepts` (list)
- ✅ All chapters have `summary` (string)
- ✅ All chapters have `similar_chapters` (list)
- ✅ All `similar_chapters` entries have `method: "sentence_transformers"` (SBERT)

**Cross-Reference**: 
- Enriched data produced by llm-document-enhancer WBS 3.5.3 pipeline
- `similar_chapters` uses SBERT (`all-MiniLM-L6-v2`) per CL-029 in llm-document-enhancer
- 9,614 total similar chapter links across 47 books

**WBS Reference**: AI_CODING_PLATFORM_WBS.md v1.5.0 (Phase 3.5.4.1-9)

---

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
