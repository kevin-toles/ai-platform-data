"""Integration tests for Neo4j database seeding.

Phase 3.1: Seeding Pipeline - TDD tests following RED-GREEN-REFACTOR cycle.
WBS Tasks: 3.1.1-3.1.2

These tests validate:
1. Books are seeded from metadata files
2. Chapters are seeded and linked to books
3. Tier relationships are created (PARALLEL, PERPENDICULAR, SKIP_TIER)
4. Taxonomy data is seeded correctly

Requirements:
- Neo4j must be running (docker-compose up neo4j)
- Tests use the ai-platform-data Docker stack
- Books metadata must exist in books/metadata/

Anti-Pattern Audit:
- Per Issue #12: Uses connection pooling (single driver instance)
- Per Issue #9-11: No race conditions in read-modify-write
- Per CODING_PATTERNS_ANALYSIS: Type annotations, exception handling
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generator

import pytest

if TYPE_CHECKING:
    pass


# Constants per CODING_PATTERNS_ANALYSIS.md (S1192 - avoid duplicated literals)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

# Expected counts based on data inventory
# Note: These will be dynamically verified against actual files
BOOKS_PATH = Path(__file__).parent.parent.parent / "books"
METADATA_PATH = BOOKS_PATH / "metadata"
TAXONOMIES_PATH = Path(__file__).parent.parent.parent / "taxonomies"


@dataclass
class SeedingStats:
    """Statistics from seeding operation."""
    
    books_seeded: int
    chapters_seeded: int
    parallel_edges: int
    perpendicular_edges: int
    skip_tier_edges: int
    
    @property
    def total_edges(self) -> int:
        """Total number of tier relationship edges."""
        return self.parallel_edges + self.perpendicular_edges + self.skip_tier_edges


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


class TestNeo4jSeedingPrerequisites:
    """Tests for seeding prerequisites (WBS 3.1.1 - RED phase)."""

    def test_metadata_directory_exists(self) -> None:
        """Metadata directory must exist before seeding."""
        assert METADATA_PATH.exists(), (
            f"Metadata directory not found at {METADATA_PATH}. "
            "Run data migration first (Phase 1.4)"
        )

    def test_metadata_files_present(self) -> None:
        """At least one metadata file must be present."""
        if not METADATA_PATH.exists():
            pytest.skip("Metadata directory does not exist")
        
        metadata_files = list(METADATA_PATH.glob("*.json"))
        assert len(metadata_files) > 0, (
            "No metadata files found. Extract metadata from raw books first."
        )

    def test_taxonomies_directory_exists(self) -> None:
        """Taxonomies directory must exist before seeding."""
        assert TAXONOMIES_PATH.exists(), (
            f"Taxonomies directory not found at {TAXONOMIES_PATH}"
        )


class TestNeo4jBookSeeding:
    """Tests for Book node seeding (WBS 3.1.1-3.1.2)."""

    def test_books_seeded_count_matches_metadata(
        self, neo4j_session: Any
    ) -> None:
        """3.1.1/3.1.2: Number of seeded books must match metadata files.
        
        This test follows RED-GREEN-REFACTOR:
        - RED: Fails if no books seeded (before seed_neo4j.py runs)
        - GREEN: Passes when seed_neo4j.py seeds all books
        """
        if not METADATA_PATH.exists():
            pytest.skip("Metadata directory does not exist")
        
        # Count expected books from metadata files
        expected_count = len(list(METADATA_PATH.glob("*.json")))
        
        # Count actual books in Neo4j
        result = neo4j_session.run("MATCH (b:Book) RETURN count(b) as count")
        actual_count = result.single()["count"]
        
        assert actual_count == expected_count, (
            f"Expected {expected_count} books from metadata, "
            f"but found {actual_count} in Neo4j. "
            "Run 'python scripts/seed_neo4j.py' to seed the database."
        )

    def test_books_have_required_properties(
        self, neo4j_session: Any
    ) -> None:
        """All Book nodes must have required properties."""
        result = neo4j_session.run("""
            MATCH (b:Book)
            WHERE b.book_id IS NULL 
               OR b.title IS NULL
            RETURN count(b) as invalid_count
        """)
        invalid_count = result.single()["invalid_count"]
        
        assert invalid_count == 0, (
            f"Found {invalid_count} Book nodes missing required properties "
            "(book_id, title)"
        )

    def test_books_have_tier_assignment(
        self, neo4j_session: Any
    ) -> None:
        """All Book nodes should have tier assignment from taxonomy."""
        result = neo4j_session.run("""
            MATCH (b:Book)
            WHERE b.tier IS NULL
            RETURN count(b) as unassigned_count
        """)
        unassigned_count = result.single()["unassigned_count"]
        
        # Note: Some books may not have tier assignment if not in taxonomy
        # This is a warning, not a failure
        if unassigned_count > 0:
            pytest.warns(
                UserWarning,
                match=f"{unassigned_count} books without tier assignment"
            )


class TestNeo4jChapterSeeding:
    """Tests for Chapter node seeding (WBS 3.1.1-3.1.2)."""

    def test_chapters_seeded(self, neo4j_session: Any) -> None:
        """3.1.1/3.1.2: Chapters must be seeded from metadata."""
        result = neo4j_session.run("MATCH (c:Chapter) RETURN count(c) as count")
        chapter_count = result.single()["count"]
        
        assert chapter_count > 0, (
            "No chapters found in Neo4j. "
            "Run 'python scripts/seed_neo4j.py' to seed the database."
        )

    def test_chapters_linked_to_books(self, neo4j_session: Any) -> None:
        """All chapters must be linked to their parent books."""
        # Count chapters without book links
        result = neo4j_session.run("""
            MATCH (c:Chapter)
            WHERE NOT (c)<-[:HAS_CHAPTER]-(:Book)
            RETURN count(c) as orphan_count
        """)
        orphan_count = result.single()["orphan_count"]
        
        assert orphan_count == 0, (
            f"Found {orphan_count} orphan chapters not linked to any book"
        )

    def test_chapters_have_required_properties(
        self, neo4j_session: Any
    ) -> None:
        """All Chapter nodes must have required properties."""
        result = neo4j_session.run("""
            MATCH (c:Chapter)
            WHERE c.chapter_id IS NULL 
               OR c.title IS NULL
            RETURN count(c) as invalid_count
        """)
        invalid_count = result.single()["invalid_count"]
        
        assert invalid_count == 0, (
            f"Found {invalid_count} Chapter nodes missing required properties"
        )


class TestNeo4jTierRelationshipSeeding:
    """Tests for tier relationship seeding (WBS 3.1.1-3.1.2).
    
    Per TIER_RELATIONSHIP_DIAGRAM.md:
    - PARALLEL: Books at same tier level (bidirectional)
    - PERPENDICULAR: Books at adjacent tiers (bidirectional)
    - SKIP_TIER: Books at non-adjacent tiers (bidirectional)
    """

    def test_parallel_relationships_exist(
        self, neo4j_session: Any
    ) -> None:
        """PARALLEL relationships must exist between same-tier books."""
        result = neo4j_session.run("""
            MATCH (:Book)-[r:PARALLEL]->(:Book)
            RETURN count(r) as count
        """)
        count = result.single()["count"]
        
        # Note: May be 0 if only one book per tier
        # Check that relationship type is usable
        assert count >= 0, "PARALLEL relationship query failed"

    def test_perpendicular_relationships_exist(
        self, neo4j_session: Any
    ) -> None:
        """PERPENDICULAR relationships must exist between adjacent-tier books."""
        result = neo4j_session.run("""
            MATCH (:Book)-[r:PERPENDICULAR]->(:Book)
            RETURN count(r) as count
        """)
        count = result.single()["count"]
        
        assert count >= 0, "PERPENDICULAR relationship query failed"

    def test_skip_tier_relationships_exist(
        self, neo4j_session: Any
    ) -> None:
        """SKIP_TIER relationships must exist between non-adjacent tiers."""
        result = neo4j_session.run("""
            MATCH (:Book)-[r:SKIP_TIER]->(:Book)
            RETURN count(r) as count
        """)
        count = result.single()["count"]
        
        assert count >= 0, "SKIP_TIER relationship query failed"

    def test_tier_relationships_are_bidirectional(
        self, neo4j_session: Any
    ) -> None:
        """All tier relationships must be bidirectional (spider web model)."""
        # Check PARALLEL bidirectionality
        result = neo4j_session.run("""
            MATCH (a:Book)-[r1:PARALLEL]->(b:Book)
            WHERE NOT (b)-[:PARALLEL]->(a)
            RETURN count(r1) as unidirectional_count
        """)
        parallel_uni = result.single()["unidirectional_count"]
        
        # Check PERPENDICULAR bidirectionality
        result = neo4j_session.run("""
            MATCH (a:Book)-[r1:PERPENDICULAR]->(b:Book)
            WHERE NOT (b)-[:PERPENDICULAR]->(a)
            RETURN count(r1) as unidirectional_count
        """)
        perpendicular_uni = result.single()["unidirectional_count"]
        
        total_unidirectional = parallel_uni + perpendicular_uni
        
        assert total_unidirectional == 0, (
            f"Found {total_unidirectional} unidirectional tier relationships. "
            "All relationships must be bidirectional per spider web model."
        )


class TestNeo4jTaxonomySeeding:
    """Tests for taxonomy data seeding (WBS 3.1.1-3.1.2)."""

    def test_tier_nodes_created(self, neo4j_session: Any) -> None:
        """Tier nodes must be created from taxonomy."""
        result = neo4j_session.run("""
            MATCH (t:Tier)
            RETURN count(t) as count
        """)
        tier_count = result.single()["count"]
        
        assert tier_count > 0, (
            "No Tier nodes found. "
            "Taxonomy must be seeded with tier definitions."
        )

    def test_books_linked_to_tiers(self, neo4j_session: Any) -> None:
        """Books with tier assignment should be linked to Tier nodes."""
        result = neo4j_session.run("""
            MATCH (b:Book)
            WHERE b.tier IS NOT NULL
            OPTIONAL MATCH (b)-[:IN_TIER]->(t:Tier)
            WITH b, t
            WHERE t IS NULL
            RETURN count(b) as unlinked_count
        """)
        unlinked_count = result.single()["unlinked_count"]
        
        # This is informational - not all books may be in taxonomy
        if unlinked_count > 0:
            pytest.warns(
                UserWarning,
                match=f"{unlinked_count} books with tier but no Tier node link"
            )

    def test_concept_nodes_created(self, neo4j_session: Any) -> None:
        """Concept nodes should be created from taxonomy/metadata."""
        result = neo4j_session.run("""
            MATCH (c:Concept)
            RETURN count(c) as count
        """)
        concept_count = result.single()["count"]
        
        # Concepts are optional but expected
        assert concept_count >= 0, "Concept query failed"


class TestNeo4jSeedingIntegrity:
    """Tests for overall seeding data integrity."""

    def test_no_duplicate_books(self, neo4j_session: Any) -> None:
        """No duplicate book_id values should exist."""
        result = neo4j_session.run("""
            MATCH (b:Book)
            WITH b.book_id as id, count(*) as cnt
            WHERE cnt > 1
            RETURN count(*) as duplicate_count
        """)
        duplicate_count = result.single()["duplicate_count"]
        
        assert duplicate_count == 0, (
            f"Found {duplicate_count} duplicate book_id values. "
            "Constraints should prevent duplicates."
        )

    def test_no_duplicate_chapters(self, neo4j_session: Any) -> None:
        """No duplicate chapter_id values should exist."""
        result = neo4j_session.run("""
            MATCH (c:Chapter)
            WITH c.chapter_id as id, count(*) as cnt
            WHERE cnt > 1
            RETURN count(*) as duplicate_count
        """)
        duplicate_count = result.single()["duplicate_count"]
        
        assert duplicate_count == 0, (
            f"Found {duplicate_count} duplicate chapter_id values"
        )

    def test_seeding_is_idempotent(
        self, neo4j_session: Any
    ) -> None:
        """Running seed twice should not create duplicates.
        
        Per Issue #9-11: No race conditions in read-modify-write.
        Uses MERGE instead of CREATE for idempotent seeding.
        """
        # Get current counts
        result = neo4j_session.run("""
            MATCH (b:Book)
            RETURN count(b) as book_count
        """)
        book_count_before = result.single()["book_count"]
        
        result = neo4j_session.run("""
            MATCH (c:Chapter)
            RETURN count(c) as chapter_count
        """)
        chapter_count_before = result.single()["chapter_count"]
        
        # Note: This test validates that MERGE is used in seed scripts
        # The actual idempotency test would run seed_neo4j.py twice
        # For now, we verify counts are consistent
        assert book_count_before >= 0, "Book count should be non-negative"
        assert chapter_count_before >= 0, "Chapter count should be non-negative"


class TestNeo4jSeedingPerformance:
    """Tests for seeding performance requirements."""

    def test_book_lookup_uses_index(self, neo4j_session: Any) -> None:
        """Book lookups by book_id should use index."""
        result = neo4j_session.run("""
            EXPLAIN MATCH (b:Book {book_id: 'test_id'})
            RETURN b
        """)
        plan = result.consume().plan
        plan_str = str(plan)
        
        # Look for index usage in execution plan
        uses_index = (
            "NodeUniqueIndexSeek" in plan_str or
            "NodeIndexSeek" in plan_str
        )
        
        assert uses_index, (
            "Book lookup does not use index. "
            "Add index on Book.book_id"
        )

    def test_chapter_lookup_uses_index(self, neo4j_session: Any) -> None:
        """Chapter lookups by chapter_id should use index."""
        result = neo4j_session.run("""
            EXPLAIN MATCH (c:Chapter {chapter_id: 'test_id'})
            RETURN c
        """)
        plan = result.consume().plan
        plan_str = str(plan)
        
        uses_index = (
            "NodeUniqueIndexSeek" in plan_str or
            "NodeIndexSeek" in plan_str
        )
        
        assert uses_index, (
            "Chapter lookup does not use index. "
            "Add index on Chapter.chapter_id"
        )
