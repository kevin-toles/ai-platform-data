# Neo4j Schema Reference

> **Version:** 2.0.0  
> **Updated:** 2026-01-01 (PCON-2)  
> **Author:** Platform Engineering

This document is the **canonical reference** for the Neo4j graph schema used by the AI Platform.

---

## Node Labels

### Core Nodes (Phase 1)

| Label | Primary Key | Description |
|-------|-------------|-------------|
| `Book` | `book_id` | A technical book in the taxonomy |
| `Chapter` | `chapter_id` | A chapter within a book |
| `Concept` | `concept_id` | A concept/topic that can be covered by chapters |
| `Tier` | `name` | Taxonomy tier (Tier1, Tier2, Tier3) |

### Extended Nodes (PCON-2)

| Label | Primary Key | Description |
|-------|-------------|-------------|
| `CodeFile` | `file_path` | A code file in code-reference-engine |
| `Pattern` | `name` | A design pattern |
| `Repository` | `repo_id` | A code repository |

---

## Node Properties

### Book

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `book_id` | String | ✅ | Unique identifier (e.g., "clean-code") |
| `title` | String | ✅ | Display title |
| `author` | String | ❌ | Author name(s) |
| `tier` | Integer | ✅ | Tier level (1, 2, or 3) |
| `priority` | Integer | ❌ | Priority within tier |
| `isbn` | String | ❌ | ISBN if available |

### Chapter

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `chapter_id` | String | ✅ | Unique identifier (e.g., "clean-code-ch3") |
| `book_id` | String | ✅ | Parent book ID |
| `number` | Integer | ✅ | Chapter number |
| `title` | String | ✅ | Chapter title |
| `summary` | String | ❌ | Brief summary |
| `keywords` | Array[String] | ❌ | Searchable keywords |
| `concepts` | Array[String] | ❌ | Concepts covered |
| `tier` | Integer | ❌ | Inherited from book |

### Concept

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `concept_id` | String | ✅ | Unique identifier |
| `name` | String | ✅ | Display name |
| `tier` | Integer | ❌ | Primary tier level |
| `description` | String | ❌ | Brief description |
| `aliases` | Array[String] | ❌ | Alternative names |

### CodeFile (PCON-2)

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `file_path` | String | ✅ | Unique path (e.g., "backend/ddd/repository.py") |
| `repo_id` | String | ✅ | Parent repository ID |
| `language` | String | ✅ | Programming language |
| `size_bytes` | Integer | ❌ | File size |
| `last_modified` | DateTime | ❌ | Last modification timestamp |

### Pattern (PCON-2)

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | String | ✅ | Pattern name (e.g., "Repository") |
| `category` | String | ❌ | Category (creational, structural, behavioral) |
| `tier` | Integer | ❌ | Complexity tier |
| `description` | String | ❌ | Brief description |

### Repository (PCON-2)

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `repo_id` | String | ✅ | Unique identifier |
| `name` | String | ✅ | Repository name |
| `url` | String | ❌ | GitHub URL |
| `primary_language` | String | ❌ | Main programming language |
| `description` | String | ❌ | Brief description |

---

## Relationships

### Core Relationships

| Type | Direction | Description |
|------|-----------|-------------|
| `HAS_CHAPTER` | Book → Chapter | Book contains chapter |
| `PARALLEL` | Chapter → Chapter | Same tier, related topics |
| `PERPENDICULAR` | Chapter → Chapter | Different tier, builds on concept |
| `SKIP_TIER` | Chapter → Chapter | Skips a tier level |
| `BELONGS_TO` | Book → Tier | Book belongs to tier |

### Extended Relationships (PCON-2)

| Type | Direction | Description | Properties |
|------|-----------|-------------|------------|
| `COVERS` | Chapter → Concept | Chapter covers concept | `depth`, `primary` |
| `PART_OF` | Chapter → Book | Chapter belongs to book | — |
| `IMPLEMENTED_BY` | Concept → CodeFile | Concept implemented in code | `quality`, `line_start`, `line_end` |
| `FOUND_IN` | Pattern → Repository | Pattern found in repo | `count`, `confidence` |
| `DEMONSTRATES` | CodeFile → Pattern | Code demonstrates pattern | `confidence`, `line_start`, `line_end` |

---

## Constraints

```cypher
// Core constraints
CREATE CONSTRAINT book_id IF NOT EXISTS FOR (b:Book) REQUIRE b.book_id IS UNIQUE;
CREATE CONSTRAINT chapter_id IF NOT EXISTS FOR (c:Chapter) REQUIRE c.chapter_id IS UNIQUE;
CREATE CONSTRAINT concept_id IF NOT EXISTS FOR (c:Concept) REQUIRE c.concept_id IS UNIQUE;
CREATE CONSTRAINT tier_name IF NOT EXISTS FOR (t:Tier) REQUIRE t.name IS UNIQUE;

// PCON-2 constraints
CREATE CONSTRAINT codefile_path IF NOT EXISTS FOR (f:CodeFile) REQUIRE f.file_path IS UNIQUE;
CREATE CONSTRAINT pattern_name IF NOT EXISTS FOR (p:Pattern) REQUIRE p.name IS UNIQUE;
CREATE CONSTRAINT repository_id IF NOT EXISTS FOR (r:Repository) REQUIRE r.repo_id IS UNIQUE;
```

---

## Indexes

```cypher
// Book indexes
CREATE INDEX book_tier IF NOT EXISTS FOR (b:Book) ON (b.tier);
CREATE INDEX book_priority IF NOT EXISTS FOR (b:Book) ON (b.priority);
CREATE INDEX book_title IF NOT EXISTS FOR (b:Book) ON (b.title);

// Chapter indexes
CREATE INDEX chapter_title IF NOT EXISTS FOR (c:Chapter) ON (c.title);
CREATE INDEX chapter_number IF NOT EXISTS FOR (c:Chapter) ON (c.number);
CREATE INDEX chapter_book_id IF NOT EXISTS FOR (c:Chapter) ON (c.book_id);
CREATE INDEX chapter_keywords IF NOT EXISTS FOR (c:Chapter) ON (c.keywords);
CREATE INDEX chapter_concepts IF NOT EXISTS FOR (c:Chapter) ON (c.concepts);

// Concept indexes
CREATE INDEX concept_name IF NOT EXISTS FOR (c:Concept) ON (c.name);
CREATE INDEX concept_tier IF NOT EXISTS FOR (c:Concept) ON (c.tier);

// PCON-2 indexes
CREATE INDEX codefile_repo IF NOT EXISTS FOR (f:CodeFile) ON (f.repo_id);
CREATE INDEX codefile_language IF NOT EXISTS FOR (f:CodeFile) ON (f.language);
CREATE INDEX pattern_tier IF NOT EXISTS FOR (p:Pattern) ON (p.tier);
CREATE INDEX pattern_category IF NOT EXISTS FOR (p:Pattern) ON (p.category);
CREATE INDEX repository_name IF NOT EXISTS FOR (r:Repository) ON (r.name);
CREATE INDEX repository_language IF NOT EXISTS FOR (r:Repository) ON (r.primary_language);
```

---

## Example Queries

### Find chapters covering a concept

```cypher
MATCH (ch:Chapter)-[:COVERS]->(c:Concept {name: "Repository Pattern"})
RETURN ch.book_id as book, ch.number as chapter, ch.title
ORDER BY ch.tier
```

### Find code implementing a concept

```cypher
MATCH (c:Concept {name: "Factory Pattern"})-[r:IMPLEMENTED_BY]->(f:CodeFile)
WHERE r.quality >= 4
RETURN f.file_path, f.language, r.quality
ORDER BY r.quality DESC
LIMIT 10
```

### Find related chapters (spider-web traversal)

```cypher
MATCH (start:Chapter {chapter_id: "clean-code-ch3"})
MATCH (start)-[:PARALLEL|PERPENDICULAR*1..2]-(related:Chapter)
RETURN DISTINCT related.book_id as book, related.title as title
```

### Search chapters by keywords

```cypher
MATCH (c:Chapter)
WHERE ANY(keyword IN c.keywords WHERE toLower(keyword) CONTAINS 'factory')
RETURN c.book_id, c.number, c.title, c.keywords
LIMIT 20
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-11-28 | Initial schema (Book, Chapter, Concept, Tier) |
| 2.0.0 | 2026-01-01 | PCON-2: Added CodeFile, Pattern, Repository nodes and relationships || 2.0.1 | 2026-01-01 | PCON-9: Documentation finalized, linked from platform architecture docs |