# Canonical Embedding Model Configuration

> **Version:** 1.0.0  
> **Created:** 2026-01-01 (PCON-6)  
> **Status:** Active  
> **Author:** Platform Engineering

---

## Overview

This document defines the **canonical embedding model** used across the AI Coding Platform for vector similarity search. All services that generate or consume embeddings MUST use the same model to ensure dimension compatibility.

## Canonical Model

| Property | Value |
|----------|-------|
| **Model Name** | `all-MiniLM-L6-v2` |
| **Full Name** | `sentence-transformers/all-MiniLM-L6-v2` |
| **Vector Dimensions** | 384 |
| **Distance Metric** | Cosine |
| **Model Size** | ~80MB |
| **Max Sequence Length** | 256 tokens |

### Why This Model?

1. **Performance**: Good balance of speed and quality for semantic search
2. **Size**: Small enough for low-memory environments
3. **Compatibility**: Widely supported by sentence-transformers library
4. **Platform Standard**: Already defined in Qdrant collection schemas

---

## Service Configuration

### Qdrant (ai-platform-data)

**Location:** `docker/qdrant/config/collections.yaml`

```yaml
collections:
  chapters:
    vectors:
      size: 384  # all-MiniLM-L6-v2 embedding dimension
      distance: Cosine
  concepts:
    vectors:
      size: 384
      distance: Cosine
```

### semantic-search-service

**Location:** `src/core/config.py`

```python
sbert_model: str = Field(
    default="all-MiniLM-L6-v2",
    description="Sentence-BERT model for embeddings (384 dimensions)",
)
```

**Environment Variable:** `SBERT_MODEL=all-MiniLM-L6-v2`

### ai-agents

**Location:** `src/core/config.py`

```python
embedding_model: str = Field(
    default="sentence-transformers/all-MiniLM-L6-v2",
    description="Embedding model for vector search",
)
```

**Environment Variable:** `AI_AGENTS_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2`

### BookPassageClient

**Location:** `ai-agents/src/clients/book_passage.py`

```python
embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
```

---

## Verification

### Check Qdrant Collections

```bash
curl -s http://localhost:6333/collections/chapters | jq '.result.config.params.vectors.size'
# Expected: 384
```

### Check Embedding Dimensions at Runtime

```bash
# semantic-search-service
curl -s http://localhost:8081/v1/embed -X POST \
  -H "Content-Type: application/json" \
  -d '{"text": "test"}' | jq '.embedding | length'
# Expected: 384
```

### Verify Config Files

```bash
# Qdrant
grep "size: 384" /Users/kevintoles/POC/ai-platform-data/docker/qdrant/config/collections.yaml

# semantic-search-service
grep "all-MiniLM-L6-v2" /Users/kevintoles/POC/semantic-search-service/src/core/config.py

# ai-agents
grep "all-MiniLM-L6-v2" /Users/kevintoles/POC/ai-agents/src/core/config.py
```

---

## Migration Notes

### From `all-mpnet-base-v2` (768 dimensions)

If you previously used `all-mpnet-base-v2`, you must:

1. **Clear existing Qdrant collections** - dimension mismatch will cause errors
2. **Re-embed all documents** using the new model
3. **Update service configs** to use the new model

```bash
# Clear Qdrant collections
curl -X DELETE http://localhost:6333/collections/chapters
curl -X DELETE http://localhost:6333/collections/concepts

# Recreate with proper schema
# (handled automatically by Qdrant init on next restart)
```

---

## Related Documents

- [SCHEMA_REFERENCE.md](SCHEMA_REFERENCE.md) - Neo4j schema documentation
- [NEO4J_SEEDING_GUIDE.md](NEO4J_SEEDING_GUIDE.md) - Database seeding procedures
- [PLATFORM_CONSOLIDATION_WBS.md](../../Platform%20Documentation/Platform-Wide/Active/PLATFORM_CONSOLIDATION_WBS.md) - PCON-6 implementation

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-01-01 | PCON-6 | Initial documentation || 1.0.1 | 2026-01-01 | PCON-9 | Documentation finalized, linked from platform architecture docs |