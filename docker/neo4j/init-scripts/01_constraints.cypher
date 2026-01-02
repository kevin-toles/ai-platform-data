// Neo4j Constraints for AI Platform Data
// Phase 2.1: WBS 2.1.3 - Constraints created on startup
// 
// This script creates uniqueness constraints for Book and Chapter nodes.
// Per TIER_RELATIONSHIP_DIAGRAM.md, books are organized by tier with
// chapter-level cross-referencing.

// Book constraints - ensure unique book_id
CREATE CONSTRAINT book_id IF NOT EXISTS FOR (b:Book) REQUIRE b.book_id IS UNIQUE;

// Chapter constraints - ensure unique chapter_id
CREATE CONSTRAINT chapter_id IF NOT EXISTS FOR (c:Chapter) REQUIRE c.chapter_id IS UNIQUE;

// Concept constraints - ensure unique concept_id
CREATE CONSTRAINT concept_id IF NOT EXISTS FOR (c:Concept) REQUIRE c.concept_id IS UNIQUE;

// Tier constraints - ensure unique tier name
CREATE CONSTRAINT tier_name IF NOT EXISTS FOR (t:Tier) REQUIRE t.name IS UNIQUE;

// =============================================================================
// PCON-2 Additions (2026-01-01) - WBS-AGT21-24 Integration
// =============================================================================

// CodeFile constraints - for code-reference-engine integration
CREATE CONSTRAINT codefile_path IF NOT EXISTS FOR (f:CodeFile) REQUIRE f.file_path IS UNIQUE;

// Pattern constraints - for design pattern tracking
CREATE CONSTRAINT pattern_name IF NOT EXISTS FOR (p:Pattern) REQUIRE p.name IS UNIQUE;

// Repository constraints - for code repository tracking
CREATE CONSTRAINT repository_id IF NOT EXISTS FOR (r:Repository) REQUIRE r.repo_id IS UNIQUE;
