"""Integration tests for Neo4j ↔ Qdrant correlation validation.

Phase 3.5.6: Re-Seed and Validate Correlation - TDD tests following RED-GREEN-REFACTOR cycle.
WBS Tasks: 3.5.6.3-3.5.6.6

These tests validate:
1. Neo4j chapter_id matches Qdrant point payload chapter_id
2. For any chapter_id: both stores have matching data
3. Hybrid search returns enriched metadata (keywords, concepts, summary)
4. End-to-end data integrity across both stores

Requirements:
- Neo4j must be running (docker-compose up neo4j)
- Qdrant must be running (docker-compose up qdrant)
- Both databases must be seeded with enriched data

Anti-Pattern Audit:
- Per Issue #12: Uses connection pooling (single client/driver instance)
- Per Issue #7/#13: Custom exceptions for connection errors
- Per CODING_PATTERNS_ANALYSIS: Type annotations, proper exception handling
- Per S1192: String literals extracted to constants
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generator

import pytest

if TYPE_CHECKING:
    pass


# Constants per CODING_PATTERNS_ANALYSIS.md (S1192 - avoid duplicated literals)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

# Collection configuration
CHAPTERS_COLLECTION = "chapters"
CHAPTER_ID_FIELD = "chapter_id"
BOOK_ID_FIELD = "book_id"

# Enriched field names per WBS 3.5.5
KEYWORDS_FIELD = "keywords"
CONCEPTS_FIELD = "concepts"
SUMMARY_FIELD = "summary"
SIMILAR_CHAPTERS_FIELD = "similar_chapters"


@dataclass
class CorrelationResult:
    """Result of correlation check between Neo4j and Qdrant."""
    
    chapter_id: str
    neo4j_exists: bool
    qdrant_exists: bool
    neo4j_title: str | None
    qdrant_title: str | None
    titles_match: bool
    
    @property
    def is_correlated(self) -> bool:
        """Check if chapter exists in both stores with matching titles."""
        return self.neo4j_exists and self.qdrant_exists and self.titles_match


@dataclass
class EnrichedSearchResult:
    """Result from enriched search query."""
    
    chapter_id: str
    title: str
    keywords: list[str]
    concepts: list[str]
    summary: str
    similar_chapters: list[dict[str, Any]]
    score: float
    
    @property
    def has_enriched_data(self) -> bool:
        """Check if result contains enriched metadata."""
        return bool(self.keywords) or bool(self.concepts) or bool(self.summary)


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


def qdrant_available() -> bool:
    """Check if Qdrant is available for testing."""
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        client.get_collections()
        return True
    except Exception:
        return False


def both_services_available() -> bool:
    """Check if both Neo4j and Qdrant are available."""
    return neo4j_available() and qdrant_available()


# Skip all tests if either service is not available
pytestmark = pytest.mark.skipif(
    not both_services_available(),
    reason="Neo4j or Qdrant not available - run docker-compose up first"
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


@pytest.fixture(scope="module")
def qdrant_client() -> Generator[Any, None, None]:
    """Create a Qdrant client for tests.
    
    Uses connection pooling pattern per Issue #12 - single client instance.
    """
    from qdrant_client import QdrantClient
    
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    yield client


class TestChapterIdCorrelation:
    """Tests for Neo4j ↔ Qdrant chapter_id correlation (WBS 3.5.6.3-3.5.6.4)."""

    def test_neo4j_has_chapters(self, neo4j_driver: Any) -> None:
        """Neo4j must have Chapter nodes before correlation can be validated.
        
        WBS 3.5.6.1: Re-seed Neo4j with chapter data.
        """
        with neo4j_driver.session() as session:
            result = session.run("MATCH (c:Chapter) RETURN count(c) as count")
            record = result.single()
            count = record["count"] if record else 0
        
        assert count > 0, "Neo4j must have Chapter nodes - run seed_neo4j.py first"

    def test_qdrant_has_chapters(self, qdrant_client: Any) -> None:
        """Qdrant must have chapter vectors before correlation can be validated.
        
        WBS 3.5.6.2: Re-seed Qdrant with enriched payloads.
        """
        try:
            collection = qdrant_client.get_collection(CHAPTERS_COLLECTION)
            count = collection.points_count
        except Exception:
            count = 0
        
        assert count > 0, "Qdrant must have chapter vectors - run seed_qdrant.py first"

    def test_chapter_ids_in_neo4j_match_qdrant_payloads(
        self, neo4j_driver: Any, qdrant_client: Any
    ) -> None:
        """For any chapter_id in Neo4j, Qdrant should have matching payload.
        
        WBS 3.5.6.3: test_chapter_id_correlation
        WBS 3.5.6.4: For any chapter_id, both stores have matching data.
        """
        # Get sample chapter_ids from Neo4j
        with neo4j_driver.session() as session:
            result = session.run(
                "MATCH (c:Chapter) RETURN c.chapter_id as chapter_id LIMIT 10"
            )
            neo4j_chapter_ids = [r["chapter_id"] for r in result if r["chapter_id"]]
        
        assert len(neo4j_chapter_ids) > 0, "No chapter_ids found in Neo4j"
        
        # Verify each chapter_id exists in Qdrant
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        missing_in_qdrant = []
        for chapter_id in neo4j_chapter_ids:
            results = qdrant_client.scroll(
                collection_name=CHAPTERS_COLLECTION,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key=CHAPTER_ID_FIELD,
                            match=MatchValue(value=chapter_id)
                        )
                    ]
                ),
                limit=1,
            )
            if not results[0]:  # results is (points, next_page_offset)
                missing_in_qdrant.append(chapter_id)
        
        assert len(missing_in_qdrant) == 0, (
            f"Chapter IDs in Neo4j not found in Qdrant: {missing_in_qdrant}"
        )

    def test_qdrant_chapter_ids_match_neo4j(
        self, neo4j_driver: Any, qdrant_client: Any
    ) -> None:
        """For any chapter_id in Qdrant payload, Neo4j should have matching node.
        
        Reverse correlation check: Qdrant → Neo4j.
        """
        # Get sample chapter_ids from Qdrant
        results = qdrant_client.scroll(
            collection_name=CHAPTERS_COLLECTION,
            limit=10,
            with_payload=True,
        )
        qdrant_chapter_ids = [
            p.payload.get(CHAPTER_ID_FIELD) 
            for p in results[0] 
            if p.payload and p.payload.get(CHAPTER_ID_FIELD)
        ]
        
        assert len(qdrant_chapter_ids) > 0, "No chapter_ids found in Qdrant"
        
        # Verify each chapter_id exists in Neo4j
        missing_in_neo4j = []
        with neo4j_driver.session() as session:
            for chapter_id in qdrant_chapter_ids:
                result = session.run(
                    "MATCH (c:Chapter {chapter_id: $chapter_id}) RETURN c",
                    chapter_id=chapter_id,
                )
                if not result.single():
                    missing_in_neo4j.append(chapter_id)
        
        assert len(missing_in_neo4j) == 0, (
            f"Chapter IDs in Qdrant not found in Neo4j: {missing_in_neo4j}"
        )

    def test_titles_match_between_stores(
        self, neo4j_driver: Any, qdrant_client: Any
    ) -> None:
        """Chapter titles should match between Neo4j and Qdrant.
        
        Data integrity check: same chapter_id should have same title.
        """
        # Get sample chapters from Qdrant with titles
        results = qdrant_client.scroll(
            collection_name=CHAPTERS_COLLECTION,
            limit=10,
            with_payload=True,
        )
        
        mismatches = []
        with neo4j_driver.session() as session:
            for point in results[0]:
                if not point.payload:
                    continue
                    
                chapter_id = point.payload.get(CHAPTER_ID_FIELD)
                qdrant_title = point.payload.get("title")
                
                if not chapter_id:
                    continue
                
                result = session.run(
                    "MATCH (c:Chapter {chapter_id: $chapter_id}) RETURN c.title as title",
                    chapter_id=chapter_id,
                )
                record = result.single()
                neo4j_title = record["title"] if record else None
                
                if qdrant_title and neo4j_title and qdrant_title != neo4j_title:
                    mismatches.append({
                        "chapter_id": chapter_id,
                        "qdrant_title": qdrant_title,
                        "neo4j_title": neo4j_title,
                    })
        
        assert len(mismatches) == 0, f"Title mismatches: {mismatches}"


class TestHybridSearchReturnsEnriched:
    """Tests for hybrid search returning enriched metadata (WBS 3.5.6.5-3.5.6.6)."""

    def test_qdrant_payloads_have_keywords(self, qdrant_client: Any) -> None:
        """Qdrant payloads should include keywords field.
        
        WBS 3.5.6.5: Search results include keywords.
        """
        results = qdrant_client.scroll(
            collection_name=CHAPTERS_COLLECTION,
            limit=10,
            with_payload=True,
        )
        
        # Check that at least some payloads have keywords
        payloads_with_keywords = [
            p for p in results[0] 
            if p.payload and KEYWORDS_FIELD in p.payload
        ]
        
        assert len(payloads_with_keywords) > 0, (
            "No Qdrant payloads have keywords field - re-seed with enriched data"
        )

    def test_qdrant_payloads_have_concepts(self, qdrant_client: Any) -> None:
        """Qdrant payloads should include concepts field.
        
        WBS 3.5.6.5: Search results include concepts.
        """
        results = qdrant_client.scroll(
            collection_name=CHAPTERS_COLLECTION,
            limit=10,
            with_payload=True,
        )
        
        # Check that at least some payloads have concepts
        payloads_with_concepts = [
            p for p in results[0] 
            if p.payload and CONCEPTS_FIELD in p.payload
        ]
        
        assert len(payloads_with_concepts) > 0, (
            "No Qdrant payloads have concepts field - re-seed with enriched data"
        )

    def test_qdrant_payloads_have_summary(self, qdrant_client: Any) -> None:
        """Qdrant payloads should include summary field.
        
        WBS 3.5.6.5: Search results include summary.
        """
        results = qdrant_client.scroll(
            collection_name=CHAPTERS_COLLECTION,
            limit=10,
            with_payload=True,
        )
        
        # Check that at least some payloads have summary
        payloads_with_summary = [
            p for p in results[0] 
            if p.payload and SUMMARY_FIELD in p.payload
        ]
        
        assert len(payloads_with_summary) > 0, (
            "No Qdrant payloads have summary field - re-seed with enriched data"
        )

    def test_qdrant_payloads_have_similar_chapters(self, qdrant_client: Any) -> None:
        """Qdrant payloads should include similar_chapters field.
        
        WBS 3.5.6.5: Search results include similar_chapters.
        """
        results = qdrant_client.scroll(
            collection_name=CHAPTERS_COLLECTION,
            limit=10,
            with_payload=True,
        )
        
        # Check that at least some payloads have similar_chapters
        payloads_with_similar = [
            p for p in results[0] 
            if p.payload and SIMILAR_CHAPTERS_FIELD in p.payload
        ]
        
        assert len(payloads_with_similar) > 0, (
            "No Qdrant payloads have similar_chapters field - re-seed with enriched data"
        )

    def test_semantic_search_returns_enriched_data(self, qdrant_client: Any) -> None:
        """Semantic search should return enriched metadata in results.
        
        WBS 3.5.6.6: End-to-end search returns enriched data.
        """
        from sentence_transformers import SentenceTransformer
        
        # Generate embedding for a sample query
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        query_embedding = model.encode("machine learning algorithms").tolist()
        
        # Perform search
        results = qdrant_client.search(
            collection_name=CHAPTERS_COLLECTION,
            query_vector=query_embedding,
            limit=5,
            with_payload=True,
        )
        
        assert len(results) > 0, "No search results returned"
        
        # Verify enriched fields in search results
        for result in results:
            payload = result.payload
            assert payload is not None, "Search result missing payload"
            
            # Check enriched fields are present
            assert KEYWORDS_FIELD in payload, f"Missing {KEYWORDS_FIELD} in search result"
            assert CONCEPTS_FIELD in payload, f"Missing {CONCEPTS_FIELD} in search result"
            assert SUMMARY_FIELD in payload, f"Missing {SUMMARY_FIELD} in search result"
            assert SIMILAR_CHAPTERS_FIELD in payload, f"Missing {SIMILAR_CHAPTERS_FIELD} in search result"

    def test_search_results_have_valid_enriched_content(self, qdrant_client: Any) -> None:
        """Search results should have non-empty enriched content.
        
        Validates enriched data is actually populated, not just present.
        """
        from sentence_transformers import SentenceTransformer
        
        # Generate embedding for a query
        model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        query_embedding = model.encode("design patterns software architecture").tolist()
        
        # Perform search
        results = qdrant_client.search(
            collection_name=CHAPTERS_COLLECTION,
            query_vector=query_embedding,
            limit=10,
            with_payload=True,
        )
        
        # At least some results should have non-empty enriched data
        results_with_content = []
        for result in results:
            payload = result.payload or {}
            keywords = payload.get(KEYWORDS_FIELD, [])
            concepts = payload.get(CONCEPTS_FIELD, [])
            summary = payload.get(SUMMARY_FIELD, "")
            
            if keywords or concepts or summary:
                results_with_content.append(result)
        
        assert len(results_with_content) > 0, (
            "No search results have populated enriched content"
        )


class TestCorrelationStats:
    """Tests for overall correlation statistics."""

    def test_count_correlation(
        self, neo4j_driver: Any, qdrant_client: Any
    ) -> None:
        """Neo4j chapter count should reasonably match Qdrant vector count.
        
        Note: Exact match not required due to potential filtering differences.
        """
        # Get Neo4j count
        with neo4j_driver.session() as session:
            result = session.run("MATCH (c:Chapter) RETURN count(c) as count")
            record = result.single()
            neo4j_count = record["count"] if record else 0
        
        # Get Qdrant count
        collection = qdrant_client.get_collection(CHAPTERS_COLLECTION)
        qdrant_count = collection.points_count
        
        # Counts should be within reasonable range (allow 10% variance)
        min_expected = min(neo4j_count, qdrant_count)
        max_expected = max(neo4j_count, qdrant_count)
        
        if min_expected > 0:
            variance = (max_expected - min_expected) / min_expected
            assert variance < 0.1, (
                f"Count variance too high: Neo4j={neo4j_count}, Qdrant={qdrant_count}"
            )

    def test_book_ids_correlation(
        self, neo4j_driver: Any, qdrant_client: Any
    ) -> None:
        """Book IDs should be consistent between Neo4j and Qdrant."""
        # Get book_ids from Neo4j
        with neo4j_driver.session() as session:
            result = session.run(
                "MATCH (b:Book) RETURN DISTINCT b.book_id as book_id"
            )
            neo4j_book_ids = {r["book_id"] for r in result if r["book_id"]}
        
        # Get book_ids from Qdrant
        results = qdrant_client.scroll(
            collection_name=CHAPTERS_COLLECTION,
            limit=1000,  # Get more to capture all books
            with_payload=[BOOK_ID_FIELD],
        )
        qdrant_book_ids = {
            p.payload.get(BOOK_ID_FIELD) 
            for p in results[0] 
            if p.payload and p.payload.get(BOOK_ID_FIELD)
        }
        
        # Check overlap
        common = neo4j_book_ids & qdrant_book_ids
        assert len(common) > 0, "No common book_ids between Neo4j and Qdrant"
        
        # Report any differences (info only, not assertion failure)
        neo4j_only = neo4j_book_ids - qdrant_book_ids
        qdrant_only = qdrant_book_ids - neo4j_book_ids
        
        if neo4j_only or qdrant_only:
            print(f"\nBook ID differences:")
            if neo4j_only:
                print(f"  Neo4j only: {neo4j_only}")
            if qdrant_only:
                print(f"  Qdrant only: {qdrant_only}")
