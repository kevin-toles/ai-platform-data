// Neo4j Indexes for AI Platform Data
// Phase 2.1: WBS 2.1.3 - Performance indexes created on startup
//
// These indexes optimize common query patterns for the Graph RAG system.
// Per AI-ML_taxonomy_20251128.json, books are queried by tier priority.

// Book indexes for tier-based queries
CREATE INDEX book_tier IF NOT EXISTS FOR (b:Book) ON (b.tier);
CREATE INDEX book_priority IF NOT EXISTS FOR (b:Book) ON (b.priority);
CREATE INDEX book_title IF NOT EXISTS FOR (b:Book) ON (b.title);

// Chapter indexes for content retrieval
CREATE INDEX chapter_title IF NOT EXISTS FOR (c:Chapter) ON (c.title);
CREATE INDEX chapter_number IF NOT EXISTS FOR (c:Chapter) ON (c.number);
CREATE INDEX chapter_book_id IF NOT EXISTS FOR (c:Chapter) ON (c.book_id);

// Concept indexes for semantic matching
CREATE INDEX concept_name IF NOT EXISTS FOR (c:Concept) ON (c.name);
CREATE INDEX concept_tier IF NOT EXISTS FOR (c:Concept) ON (c.tier);

// Full-text index for keyword search across chapters
// Note: Full-text indexes require APOC or explicit CREATE FULLTEXT INDEX
// CREATE FULLTEXT INDEX chapter_content IF NOT EXISTS FOR (c:Chapter) ON EACH [c.content, c.summary];

// =============================================================================
// PCON-2 Additions (2026-01-01) - WBS-AGT21-24 Integration
// =============================================================================

// CodeFile indexes - for code-reference-engine integration
CREATE INDEX codefile_repo IF NOT EXISTS FOR (f:CodeFile) ON (f.repo_id);
CREATE INDEX codefile_language IF NOT EXISTS FOR (f:CodeFile) ON (f.language);

// Pattern indexes - for design pattern tracking
CREATE INDEX pattern_tier IF NOT EXISTS FOR (p:Pattern) ON (p.tier);
CREATE INDEX pattern_category IF NOT EXISTS FOR (p:Pattern) ON (p.category);

// Repository indexes - for code repository tracking
CREATE INDEX repository_name IF NOT EXISTS FOR (r:Repository) ON (r.name);
CREATE INDEX repository_language IF NOT EXISTS FOR (r:Repository) ON (r.primary_language);

// Chapter extended properties - for search_chapters() method
CREATE INDEX chapter_keywords IF NOT EXISTS FOR (c:Chapter) ON (c.keywords);
CREATE INDEX chapter_concepts IF NOT EXISTS FOR (c:Chapter) ON (c.concepts);
