// Neo4j Relationship Types for AI Platform Data
// Phase 2.2: WBS 2.2.6-2.2.8 - Tier relationship types
//
// Per TIER_RELATIONSHIP_DIAGRAM.md, all relationships are BIDIRECTIONAL.
// The graph forms a "spider web" model, not a tree.
//
// Relationship Types:
//   PARALLEL:       Same tier level (horizontal traversal)
//   PERPENDICULAR:  Adjacent tier ±1 (vertical traversal)
//   SKIP_TIER:      Non-adjacent tier ±2+ (diagonal traversal)
//
// Usage: These are used to connect Chapter nodes for cross-referencing.
// Example: Chapter in Tier 1 can have PERPENDICULAR relationship to Chapter in Tier 2

// Note: Neo4j doesn't require explicit relationship type creation.
// Relationship types are created implicitly when first used.
// This file documents the relationship types and provides examples.

// Example: Create PARALLEL relationship (same tier)
// MATCH (c1:Chapter {tier: 1}), (c2:Chapter {tier: 1})
// WHERE c1.chapter_id <> c2.chapter_id
// CREATE (c1)-[:PARALLEL {
//     created_at: datetime(),
//     relevance_score: 0.85
// }]->(c2);

// Example: Create PERPENDICULAR relationship (adjacent tiers)
// MATCH (c1:Chapter {tier: 1}), (c2:Chapter {tier: 2})
// CREATE (c1)-[:PERPENDICULAR {
//     created_at: datetime(),
//     direction: 'theory_to_implementation'
// }]->(c2);

// Example: Create SKIP_TIER relationship (non-adjacent tiers)
// MATCH (c1:Chapter {tier: 1}), (c3:Chapter {tier: 3})
// CREATE (c1)-[:SKIP_TIER {
//     created_at: datetime(),
//     tier_gap: 2
// }]->(c3);

// Verification query: Check all relationship types in use
// CALL db.relationshipTypes() YIELD relationshipType
// RETURN relationshipType;

// Verification query: Count relationships by type
// MATCH ()-[r]->()
// RETURN type(r) as rel_type, count(*) as count
// ORDER BY count DESC;
