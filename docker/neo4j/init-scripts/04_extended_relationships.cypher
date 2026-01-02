// Extended Relationship Types for WBS-AGT21-24 Integration
// PCON-2 (2026-01-01) - Platform Consolidation
//
// This file documents relationship types used by the UnifiedRetriever
// for cross-referencing between books, code, and patterns.
//
// =============================================================================
// EXISTING RELATIONSHIPS (from 03_relationship_types.cypher)
// =============================================================================
// HAS_CHAPTER: Book → Chapter
// PARALLEL: Chapter → Chapter (same tier, related topics)
// PERPENDICULAR: Chapter → Chapter (different tier, builds on concept)
// SKIP_TIER: Chapter → Chapter (skips a tier level)
//
// =============================================================================
// NEW RELATIONSHIPS FOR UNIFIED RETRIEVER
// =============================================================================

// COVERS: Chapter → Concept
// -----------------------------------------------------------------------------
// Indicates that a chapter covers/discusses a particular concept.
// Used by: BookPassageClient, UnifiedRetriever
// Direction: (chapter:Chapter)-[:COVERS]->(concept:Concept)
// Properties:
//   - depth: How deeply the concept is covered (1=mention, 2=explanation, 3=deep-dive)
//   - primary: Boolean, is this the primary coverage of this concept?
//
// Example:
//   MATCH (ch:Chapter {title: "Functions"})-[:COVERS]->(c:Concept {name: "Single Responsibility"})
//   WHERE r.depth >= 2

// PART_OF: Chapter → Book
// -----------------------------------------------------------------------------
// Inverse of HAS_CHAPTER. Allows traversing from chapter back to book.
// Used by: BookPassageClient, citation generation
// Direction: (chapter:Chapter)-[:PART_OF]->(book:Book)
// Properties: None (relationship is structural)
//
// Note: This is the inverse of HAS_CHAPTER. Both may exist for bidirectional traversal.
// Example:
//   MATCH (ch:Chapter)-[:PART_OF]->(b:Book)
//   RETURN b.title as book, ch.title as chapter

// IMPLEMENTED_BY: Concept → CodeFile
// -----------------------------------------------------------------------------
// Links a concept to code files that implement or demonstrate it.
// Used by: CodeReferenceClient, UnifiedRetriever
// Direction: (concept:Concept)-[:IMPLEMENTED_BY]->(file:CodeFile)
// Properties:
//   - quality: How well does this implementation demonstrate the concept (1-5)
//   - language: Programming language of the implementation
//   - line_start: Starting line number of relevant code
//   - line_end: Ending line number of relevant code
//
// Example:
//   MATCH (c:Concept {name: "Repository Pattern"})-[:IMPLEMENTED_BY]->(f:CodeFile)
//   WHERE f.language = 'python'
//   RETURN f.file_path, r.quality

// FOUND_IN: Pattern → Repository
// -----------------------------------------------------------------------------
// Links a design pattern to repositories where it's found.
// Used by: CodeReferenceClient
// Direction: (pattern:Pattern)-[:FOUND_IN]->(repo:Repository)
// Properties:
//   - count: Number of occurrences in the repository
//   - confidence: Confidence score of pattern detection (0.0-1.0)
//
// Example:
//   MATCH (p:Pattern {name: "Factory"})-[:FOUND_IN]->(r:Repository)
//   WHERE r.confidence > 0.8
//   RETURN r.name, r.count

// DEMONSTRATES: CodeFile → Pattern
// -----------------------------------------------------------------------------
// Links a code file to patterns it demonstrates.
// Used by: Pattern analysis
// Direction: (file:CodeFile)-[:DEMONSTRATES]->(pattern:Pattern)
// Properties:
//   - confidence: Confidence score of pattern detection (0.0-1.0)
//   - line_start: Starting line number
//   - line_end: Ending line number
//
// Example:
//   MATCH (f:CodeFile)-[:DEMONSTRATES]->(p:Pattern)
//   WHERE f.language = 'python' AND r.confidence > 0.7
//   RETURN f.file_path, p.name

// =============================================================================
// RELATIONSHIP VALIDATION QUERIES
// =============================================================================
// Use these queries to validate relationships are properly formed:
//
// Check COVERS relationships:
//   MATCH (ch:Chapter)-[r:COVERS]->(c:Concept)
//   RETURN count(r) as covers_count
//
// Check IMPLEMENTED_BY relationships:
//   MATCH (c:Concept)-[r:IMPLEMENTED_BY]->(f:CodeFile)
//   RETURN count(r) as implemented_by_count
//
// Check orphaned CodeFiles (no IMPLEMENTED_BY incoming):
//   MATCH (f:CodeFile)
//   WHERE NOT ()-[:IMPLEMENTED_BY]->(f)
//   RETURN count(f) as orphaned_files
