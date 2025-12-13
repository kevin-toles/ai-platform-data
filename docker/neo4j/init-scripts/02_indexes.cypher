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
