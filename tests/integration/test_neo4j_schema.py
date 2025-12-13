"""Integration tests for Neo4j schema validation.

Phase 2.2: Neo4j Schema - TDD tests following RED-GREEN-REFACTOR cycle.

These tests validate:
1. Book node constraint (unique book_id)
2. Chapter node constraint (unique chapter_id)
3. Edge types (PARALLEL, PERPENDICULAR, SKIP_TIER)
4. Tier indexes for fast lookups

Requirements:
- Neo4j must be running (docker-compose up neo4j)
- Tests use testcontainers for isolation when available
- Falls back to environment-configured Neo4j

Anti-Pattern Audit:
- Per Issue #12: Uses connection pooling (single driver instance)
- Per Issue #42-43: Async patterns where appropriate
- Per CODING_PATTERNS_ANALYSIS: Type annotations, exception handling
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any, Generator

import pytest


# Constants per CODING_PATTERNS_ANALYSIS.md (S1192 - avoid duplicated literals)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Relationship types per TIER_RELATIONSHIP_DIAGRAM.md
class EdgeType(str, Enum):
    """Tier relationship types per TIER_RELATIONSHIP_DIAGRAM.md.
    
    All relationships are BIDIRECTIONAL - the graph is a spider web, not a tree.
    """
    PARALLEL = "PARALLEL"           # Same tier (horizontal)
    PERPENDICULAR = "PERPENDICULAR" # Adjacent tier ±1 (vertical)
    SKIP_TIER = "SKIP_TIER"         # Non-adjacent tier ±2+ (diagonal)


@dataclass
class ConstraintInfo:
    """Information about a Neo4j constraint."""
    name: str
    type: str
    entity_type: str
    labelsOrTypes: list[str]
    properties: list[str]


@dataclass
class IndexInfo:
    """Information about a Neo4j index."""
    name: str
    type: str
    entity_type: str
    labelsOrTypes: list[str]
    properties: list[str]


def neo4j_available() -> bool:
    """Check if Neo4j is available for testing."""
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        driver.close()
        return True
    except Exception:
        return False


# Skip all tests if Neo4j is not available
pytestmark = pytest.mark.skipif(
    not neo4j_available(),
    reason="Neo4j not available - run 'docker-compose up neo4j' first"
)


@pytest.fixture(scope="module")
def neo4j_driver() -> Generator[Any, None, None]:
    """Create a Neo4j driver for tests.
    
    Uses connection pooling pattern per Issue #12 - single driver instance.
    """
    from neo4j import GraphDatabase
    
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    yield driver
    driver.close()


@pytest.fixture(scope="function")
def neo4j_session(neo4j_driver: Any) -> Generator[Any, None, None]:
    """Create a Neo4j session for each test."""
    with neo4j_driver.session() as session:
        yield session


class TestBookConstraint:
    """Tests for Book node constraint (WBS 2.2.1-2.2.2)."""

    def test_book_constraint_exists(self, neo4j_session: Any) -> None:
        """2.2.1/2.2.2: Book node must have unique book_id constraint."""
        result = neo4j_session.run("SHOW CONSTRAINTS")
        constraints = list(result)
        
        # Find the book_id constraint
        book_constraints = [
            c for c in constraints 
            if "Book" in c.get("labelsOrTypes", [])
            and "book_id" in c.get("properties", [])
        ]
        
        assert len(book_constraints) > 0, (
            "Missing Book constraint - run init scripts: "
            "docker/neo4j/init-scripts/01_constraints.cypher"
        )

    def test_book_constraint_enforces_uniqueness(self, neo4j_session: Any) -> None:
        """Book constraint must enforce unique book_id values."""
        test_book_id = "test_unique_book_001"
        
        # Clean up any existing test data
        neo4j_session.run(
            "MATCH (b:Book {book_id: $book_id}) DETACH DELETE b",
            book_id=test_book_id
        )
        
        # Create first book
        neo4j_session.run(
            "CREATE (b:Book {book_id: $book_id, title: 'Test Book 1'})",
            book_id=test_book_id
        )
        
        # Attempt to create duplicate should fail
        with pytest.raises(Exception) as exc_info:
            neo4j_session.run(
                "CREATE (b:Book {book_id: $book_id, title: 'Test Book 2'})",
                book_id=test_book_id
            )
            # Force execution
            neo4j_session.run("RETURN 1").consume()
        
        # Clean up
        neo4j_session.run(
            "MATCH (b:Book {book_id: $book_id}) DETACH DELETE b",
            book_id=test_book_id
        )
        
        assert "Constraint" in str(exc_info.value) or "unique" in str(exc_info.value).lower()


class TestChapterConstraint:
    """Tests for Chapter node constraint (WBS 2.2.3-2.2.4)."""

    def test_chapter_constraint_exists(self, neo4j_session: Any) -> None:
        """2.2.3/2.2.4: Chapter node must have unique chapter_id constraint."""
        result = neo4j_session.run("SHOW CONSTRAINTS")
        constraints = list(result)
        
        chapter_constraints = [
            c for c in constraints 
            if "Chapter" in c.get("labelsOrTypes", [])
            and "chapter_id" in c.get("properties", [])
        ]
        
        assert len(chapter_constraints) > 0, (
            "Missing Chapter constraint - run init scripts"
        )

    def test_chapter_constraint_enforces_uniqueness(self, neo4j_session: Any) -> None:
        """Chapter constraint must enforce unique chapter_id values."""
        test_chapter_id = "test_unique_chapter_001"
        
        # Clean up
        neo4j_session.run(
            "MATCH (c:Chapter {chapter_id: $chapter_id}) DETACH DELETE c",
            chapter_id=test_chapter_id
        )
        
        # Create first chapter
        neo4j_session.run(
            "CREATE (c:Chapter {chapter_id: $chapter_id, title: 'Test Chapter 1'})",
            chapter_id=test_chapter_id
        )
        
        # Attempt to create duplicate should fail
        with pytest.raises(Exception) as exc_info:
            neo4j_session.run(
                "CREATE (c:Chapter {chapter_id: $chapter_id, title: 'Test Chapter 2'})",
                chapter_id=test_chapter_id
            )
            neo4j_session.run("RETURN 1").consume()
        
        # Clean up
        neo4j_session.run(
            "MATCH (c:Chapter {chapter_id: $chapter_id}) DETACH DELETE c",
            chapter_id=test_chapter_id
        )
        
        assert "Constraint" in str(exc_info.value) or "unique" in str(exc_info.value).lower()


class TestEdgeTypes:
    """Tests for tier relationship types (WBS 2.2.5-2.2.8).
    
    Per TIER_RELATIONSHIP_DIAGRAM.md:
    - PARALLEL: Same tier level (bidirectional)
    - PERPENDICULAR: Adjacent tier ±1 (bidirectional)
    - SKIP_TIER: Non-adjacent tier ±2+ (bidirectional)
    """

    def test_edge_type_enum_exists(self) -> None:
        """2.2.5: EdgeType enum must exist with all relationship types."""
        assert hasattr(EdgeType, "PARALLEL")
        assert hasattr(EdgeType, "PERPENDICULAR")
        assert hasattr(EdgeType, "SKIP_TIER")

    def test_parallel_relationship_can_be_created(self, neo4j_session: Any) -> None:
        """2.2.6: PARALLEL relationship type must be creatable."""
        # Create test nodes
        neo4j_session.run("""
            MERGE (c1:Chapter {chapter_id: 'test_parallel_ch1', tier: 1})
            MERGE (c2:Chapter {chapter_id: 'test_parallel_ch2', tier: 1})
            MERGE (c1)-[:PARALLEL]->(c2)
        """)
        
        # Verify relationship exists
        result = neo4j_session.run("""
            MATCH (c1:Chapter {chapter_id: 'test_parallel_ch1'})-[r:PARALLEL]->(c2:Chapter {chapter_id: 'test_parallel_ch2'})
            RETURN type(r) as rel_type
        """)
        records = list(result)
        
        # Clean up
        neo4j_session.run("""
            MATCH (c:Chapter) WHERE c.chapter_id STARTS WITH 'test_parallel_'
            DETACH DELETE c
        """)
        
        assert len(records) == 1
        assert records[0]["rel_type"] == "PARALLEL"

    def test_perpendicular_relationship_can_be_created(self, neo4j_session: Any) -> None:
        """2.2.7: PERPENDICULAR relationship type must be creatable."""
        # Create test nodes with adjacent tiers
        neo4j_session.run("""
            MERGE (c1:Chapter {chapter_id: 'test_perp_ch1', tier: 1})
            MERGE (c2:Chapter {chapter_id: 'test_perp_ch2', tier: 2})
            MERGE (c1)-[:PERPENDICULAR]->(c2)
        """)
        
        # Verify relationship
        result = neo4j_session.run("""
            MATCH (c1:Chapter {chapter_id: 'test_perp_ch1'})-[r:PERPENDICULAR]->(c2:Chapter {chapter_id: 'test_perp_ch2'})
            RETURN type(r) as rel_type, c1.tier as tier1, c2.tier as tier2
        """)
        records = list(result)
        
        # Clean up
        neo4j_session.run("""
            MATCH (c:Chapter) WHERE c.chapter_id STARTS WITH 'test_perp_'
            DETACH DELETE c
        """)
        
        assert len(records) == 1
        assert records[0]["rel_type"] == "PERPENDICULAR"
        assert abs(records[0]["tier1"] - records[0]["tier2"]) == 1  # Adjacent tiers

    def test_skip_tier_relationship_can_be_created(self, neo4j_session: Any) -> None:
        """2.2.8: SKIP_TIER relationship type must be creatable."""
        # Create test nodes with non-adjacent tiers (tier 1 and tier 3)
        neo4j_session.run("""
            MERGE (c1:Chapter {chapter_id: 'test_skip_ch1', tier: 1})
            MERGE (c2:Chapter {chapter_id: 'test_skip_ch2', tier: 3})
            MERGE (c1)-[:SKIP_TIER]->(c2)
        """)
        
        # Verify relationship
        result = neo4j_session.run("""
            MATCH (c1:Chapter {chapter_id: 'test_skip_ch1'})-[r:SKIP_TIER]->(c2:Chapter {chapter_id: 'test_skip_ch2'})
            RETURN type(r) as rel_type, c1.tier as tier1, c2.tier as tier2
        """)
        records = list(result)
        
        # Clean up
        neo4j_session.run("""
            MATCH (c:Chapter) WHERE c.chapter_id STARTS WITH 'test_skip_'
            DETACH DELETE c
        """)
        
        assert len(records) == 1
        assert records[0]["rel_type"] == "SKIP_TIER"
        assert abs(records[0]["tier1"] - records[0]["tier2"]) >= 2  # Non-adjacent tiers

    def test_relationships_are_bidirectional(self, neo4j_session: Any) -> None:
        """All relationships must be traversable in both directions (spider web model)."""
        # Create bidirectional test case
        neo4j_session.run("""
            MERGE (c1:Chapter {chapter_id: 'test_bidir_ch1', tier: 1})
            MERGE (c2:Chapter {chapter_id: 'test_bidir_ch2', tier: 1})
            MERGE (c1)-[:PARALLEL]->(c2)
            MERGE (c2)-[:PARALLEL]->(c1)
        """)
        
        # Query in both directions
        result_forward = neo4j_session.run("""
            MATCH (c1:Chapter {chapter_id: 'test_bidir_ch1'})-[:PARALLEL]->(c2:Chapter {chapter_id: 'test_bidir_ch2'})
            RETURN count(*) as count
        """)
        result_backward = neo4j_session.run("""
            MATCH (c2:Chapter {chapter_id: 'test_bidir_ch2'})-[:PARALLEL]->(c1:Chapter {chapter_id: 'test_bidir_ch1'})
            RETURN count(*) as count
        """)
        
        forward_count = list(result_forward)[0]["count"]
        backward_count = list(result_backward)[0]["count"]
        
        # Clean up
        neo4j_session.run("""
            MATCH (c:Chapter) WHERE c.chapter_id STARTS WITH 'test_bidir_'
            DETACH DELETE c
        """)
        
        assert forward_count == 1, "Forward traversal must work"
        assert backward_count == 1, "Backward traversal must work (bidirectional)"


class TestTierIndexes:
    """Tests for tier indexes (WBS 2.2.9)."""

    def test_book_tier_index_exists(self, neo4j_session: Any) -> None:
        """2.2.9: Book tier index must exist for fast lookups."""
        result = neo4j_session.run("SHOW INDEXES")
        indexes = list(result)
        
        tier_indexes = [
            idx for idx in indexes 
            if "Book" in idx.get("labelsOrTypes", [])
            and "tier" in idx.get("properties", [])
        ]
        
        assert len(tier_indexes) > 0, (
            "Missing Book tier index - run init scripts: "
            "docker/neo4j/init-scripts/02_indexes.cypher"
        )

    def test_book_priority_index_exists(self, neo4j_session: Any) -> None:
        """Book priority index must exist for tier-priority queries."""
        result = neo4j_session.run("SHOW INDEXES")
        indexes = list(result)
        
        priority_indexes = [
            idx for idx in indexes 
            if "Book" in idx.get("labelsOrTypes", [])
            and "priority" in idx.get("properties", [])
        ]
        
        assert len(priority_indexes) > 0, "Missing Book priority index"

    def test_chapter_tier_lookup_performance(self, neo4j_session: Any) -> None:
        """Tier lookups should use indexes (EXPLAIN shows IndexSeek)."""
        # Create test data
        neo4j_session.run("""
            MERGE (b:Book {book_id: 'test_perf_book', tier: 'architecture', priority: 1})
        """)
        
        # Get query plan
        result = neo4j_session.run("""
            EXPLAIN MATCH (b:Book {tier: 'architecture'}) RETURN b
        """)
        plan = result.consume().plan
        
        # Clean up
        neo4j_session.run("""
            MATCH (b:Book {book_id: 'test_perf_book'}) DETACH DELETE b
        """)
        
        # Check that the plan uses an index (not a full scan)
        plan_str = str(plan)
        # Index usage indicated by "NodeIndexSeek" or similar
        uses_index = "Index" in plan_str or "index" in plan_str.lower()
        assert uses_index, f"Query should use tier index. Plan: {plan_str}"


class TestConceptConstraint:
    """Tests for Concept node constraint."""

    def test_concept_constraint_exists(self, neo4j_session: Any) -> None:
        """Concept node must have unique concept_id constraint."""
        result = neo4j_session.run("SHOW CONSTRAINTS")
        constraints = list(result)
        
        concept_constraints = [
            c for c in constraints 
            if "Concept" in c.get("labelsOrTypes", [])
            and "concept_id" in c.get("properties", [])
        ]
        
        assert len(concept_constraints) > 0, "Missing Concept constraint"


class TestTierConstraint:
    """Tests for Tier node constraint."""

    def test_tier_constraint_exists(self, neo4j_session: Any) -> None:
        """Tier node must have unique name constraint."""
        result = neo4j_session.run("SHOW CONSTRAINTS")
        constraints = list(result)
        
        tier_constraints = [
            c for c in constraints 
            if "Tier" in c.get("labelsOrTypes", [])
            and "name" in c.get("properties", [])
        ]
        
        assert len(tier_constraints) > 0, "Missing Tier name constraint"


class TestTierRelationshipDiagramCompliance:
    """REFACTOR: Validate schema against TIER_RELATIONSHIP_DIAGRAM.md (WBS 2.2.10)."""

    def test_spider_web_model_supported(self, neo4j_session: Any) -> None:
        """Schema must support the spider web traversal model.
        
        Per TIER_RELATIONSHIP_DIAGRAM.md:
        'Relationships are BIDIRECTIONAL - concepts flow in ANY direction'
        'A single annotation may traverse: T1 → T2 → T3 → T1 → T2'
        """
        # Create a spider web pattern
        neo4j_session.run("""
            // Create tier nodes
            MERGE (t1:Tier {name: 'test_tier_1'})
            MERGE (t2:Tier {name: 'test_tier_2'})
            MERGE (t3:Tier {name: 'test_tier_3'})
            
            // Create chapters in each tier
            MERGE (c1:Chapter {chapter_id: 'test_web_ch1', tier: 1})
            MERGE (c2:Chapter {chapter_id: 'test_web_ch2', tier: 2})
            MERGE (c3:Chapter {chapter_id: 'test_web_ch3', tier: 3})
            MERGE (c4:Chapter {chapter_id: 'test_web_ch4', tier: 1})
            
            // Create spider web relationships
            MERGE (c1)-[:PERPENDICULAR]->(c2)  // T1 → T2
            MERGE (c2)-[:PERPENDICULAR]->(c3)  // T2 → T3
            MERGE (c3)-[:SKIP_TIER]->(c4)      // T3 → T1 (skip tier back)
            MERGE (c4)-[:PARALLEL]->(c1)       // T1 → T1 (parallel)
        """)
        
        # Traverse the web: T1 → T2 → T3 → T1 → T1
        result = neo4j_session.run("""
            MATCH path = (start:Chapter {chapter_id: 'test_web_ch1'})
                -[:PERPENDICULAR]->(c2)
                -[:PERPENDICULAR]->(c3)
                -[:SKIP_TIER]->(c4)
                -[:PARALLEL]->(end)
            RETURN length(path) as hops, [n IN nodes(path) | n.chapter_id] as chapters
        """)
        records = list(result)
        
        # Clean up
        neo4j_session.run("""
            MATCH (c:Chapter) WHERE c.chapter_id STARTS WITH 'test_web_'
            DETACH DELETE c
        """)
        neo4j_session.run("""
            MATCH (t:Tier) WHERE t.name STARTS WITH 'test_tier_'
            DETACH DELETE t
        """)
        
        assert len(records) == 1, "Spider web path must be traversable"
        assert records[0]["hops"] == 4, "Path should have 4 hops"

    def test_all_three_relationship_types_coexist(self, neo4j_session: Any) -> None:
        """All three relationship types must be usable in the same query."""
        # Create test structure with all relationship types
        neo4j_session.run("""
            MERGE (c1:Chapter {chapter_id: 'test_coexist_ch1', tier: 1})
            MERGE (c2:Chapter {chapter_id: 'test_coexist_ch2', tier: 1})
            MERGE (c3:Chapter {chapter_id: 'test_coexist_ch3', tier: 2})
            MERGE (c4:Chapter {chapter_id: 'test_coexist_ch4', tier: 3})
            
            MERGE (c1)-[:PARALLEL]->(c2)
            MERGE (c1)-[:PERPENDICULAR]->(c3)
            MERGE (c1)-[:SKIP_TIER]->(c4)
        """)
        
        # Query all relationship types from one node
        result = neo4j_session.run("""
            MATCH (c1:Chapter {chapter_id: 'test_coexist_ch1'})-[r]->(target)
            RETURN type(r) as rel_type, target.chapter_id as target_id
            ORDER BY rel_type
        """)
        records = list(result)
        
        # Clean up
        neo4j_session.run("""
            MATCH (c:Chapter) WHERE c.chapter_id STARTS WITH 'test_coexist_'
            DETACH DELETE c
        """)
        
        rel_types = {r["rel_type"] for r in records}
        assert "PARALLEL" in rel_types, "PARALLEL relationship must exist"
        assert "PERPENDICULAR" in rel_types, "PERPENDICULAR relationship must exist"
        assert "SKIP_TIER" in rel_types, "SKIP_TIER relationship must exist"
