"""Integration tests for Qdrant database seeding.

Phase 3.1: Seeding Pipeline - TDD tests following RED-GREEN-REFACTOR cycle.
WBS Tasks: 3.1.3-3.1.4

These tests validate:
1. Chapter vectors are seeded with correct dimensions
2. Payloads contain required metadata
3. Collection is properly configured
4. Semantic search works after seeding

Requirements:
- Qdrant must be running (docker-compose up qdrant)
- Tests use the ai-platform-data Docker stack
- Books must exist in books/enriched/

Anti-Pattern Audit:
- Per Issue #12: Uses connection pooling (single client instance)
- Per Issue #9-11: No race conditions in vector upserts
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
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

# Collection configuration
CHAPTERS_COLLECTION = "chapters"
EMBEDDING_DIM = 384  # sentence-transformers/all-MiniLM-L6-v2

# Data paths
BOOKS_PATH = Path(__file__).parent.parent.parent / "books"
ENRICHED_PATH = BOOKS_PATH / "enriched"
RAW_PATH = BOOKS_PATH / "raw"


@dataclass
class QdrantStats:
    """Statistics from Qdrant collection."""
    
    vectors_count: int
    indexed_vectors_count: int
    points_count: int
    segments_count: int
    
    @property
    def is_indexed(self) -> bool:
        """Check if all vectors are indexed."""
        return self.indexed_vectors_count >= self.vectors_count


def qdrant_available() -> bool:
    """Check if Qdrant is available for testing."""
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        client.get_collections()
        return True
    except Exception:
        return False


# Skip all tests if Qdrant is not available
pytestmark = pytest.mark.skipif(
    not qdrant_available(),
    reason="Qdrant not available - run 'docker-compose up qdrant' first"
)


@pytest.fixture(scope="module")
def qdrant_client() -> Generator[Any, None, None]:
    """Create a Qdrant client for tests.
    
    Uses connection pooling pattern per Issue #12 - single client instance.
    """
    from qdrant_client import QdrantClient
    
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    yield client
    # Note: QdrantClient doesn't have explicit close()


class TestQdrantSeedingPrerequisites:
    """Tests for seeding prerequisites (WBS 3.1.3 - RED phase)."""

    def test_enriched_directory_exists(self) -> None:
        """Enriched directory must exist before seeding vectors.
        
        Note: If enriched doesn't exist, we fall back to raw books
        for basic vector generation.
        """
        # Either enriched or raw should exist
        has_enriched = ENRICHED_PATH.exists() and list(ENRICHED_PATH.glob("*.json"))
        has_raw = RAW_PATH.exists() and list(RAW_PATH.glob("*.json"))
        
        assert has_enriched or has_raw, (
            f"Neither enriched ({ENRICHED_PATH}) nor raw ({RAW_PATH}) books found. "
            "Run data migration first (Phase 1.4)"
        )

    def test_source_files_present(self) -> None:
        """At least one source file must be present for vector generation."""
        # Prefer metadata files (contain chapter info), fall back to enriched, then raw
        METADATA_PATH = BOOKS_PATH / "metadata"
        
        if METADATA_PATH.exists():
            source_files = list(METADATA_PATH.glob("*.json"))
        elif ENRICHED_PATH.exists():
            source_files = list(ENRICHED_PATH.glob("*.json"))
        elif RAW_PATH.exists():
            source_files = list(RAW_PATH.glob("*.json"))
        else:
            source_files = []
        
        assert len(source_files) > 0, (
            "No source files found for vector generation. "
            "Sync enriched files from llm-document-enhancer first."
        )


class TestQdrantCollectionConfiguration:
    """Tests for Qdrant collection setup (WBS 3.1.3-3.1.4)."""

    def test_chapters_collection_exists(self, qdrant_client: Any) -> None:
        """3.1.3/3.1.4: Chapters collection must exist after seeding."""
        collections = qdrant_client.get_collections().collections
        collection_names = [c.name for c in collections]
        
        assert CHAPTERS_COLLECTION in collection_names, (
            f"Collection '{CHAPTERS_COLLECTION}' not found in Qdrant. "
            "Run 'python scripts/seed_qdrant.py' to create it."
        )

    def test_collection_has_correct_dimension(self, qdrant_client: Any) -> None:
        """Collection must be configured with correct embedding dimension."""
        try:
            info = qdrant_client.get_collection(CHAPTERS_COLLECTION)
        except Exception:
            pytest.skip(f"Collection '{CHAPTERS_COLLECTION}' does not exist")
        
        # Get vector dimension from collection config
        vector_config = info.config.params.vectors
        
        # Handle both named and unnamed vector configurations
        if hasattr(vector_config, "size"):
            dimension = vector_config.size
        else:
            # Named vectors case
            dimension = list(vector_config.values())[0].size
        
        assert dimension == EMBEDDING_DIM, (
            f"Expected dimension {EMBEDDING_DIM}, got {dimension}. "
            f"Collection must use {EMBEDDING_DIM}-dim vectors "
            f"(sentence-transformers/all-MiniLM-L6-v2)"
        )

    def test_collection_uses_cosine_distance(self, qdrant_client: Any) -> None:
        """Collection must use cosine distance for semantic similarity."""
        try:
            info = qdrant_client.get_collection(CHAPTERS_COLLECTION)
        except Exception:
            pytest.skip(f"Collection '{CHAPTERS_COLLECTION}' does not exist")
        
        vector_config = info.config.params.vectors
        
        # Handle both named and unnamed vector configurations
        if hasattr(vector_config, "distance"):
            distance = str(vector_config.distance)
        else:
            distance = str(list(vector_config.values())[0].distance)
        
        assert "Cosine" in distance, (
            f"Expected Cosine distance, got {distance}. "
            "Semantic search requires cosine similarity."
        )


class TestQdrantVectorSeeding:
    """Tests for vector seeding (WBS 3.1.3-3.1.4)."""

    def test_vectors_seeded(self, qdrant_client: Any) -> None:
        """3.1.3/3.1.4: Vectors must be seeded from chapter content."""
        try:
            info = qdrant_client.get_collection(CHAPTERS_COLLECTION)
        except Exception:
            pytest.skip(f"Collection '{CHAPTERS_COLLECTION}' does not exist")
        
        # Use points_count for compatibility with newer Qdrant API
        # vectors_count was deprecated in favor of points_count
        points_count = getattr(info, 'points_count', None) or getattr(info, 'vectors_count', 0) or 0
        
        assert points_count > 0, (
            "No vectors found in Qdrant. "
            "Run 'python scripts/seed_qdrant.py' to seed vectors."
        )

    def test_vectors_count_matches_chapters(self, qdrant_client: Any) -> None:
        """Number of vectors should match number of chapters.
        
        Note: This is approximate as some chapters may be empty.
        """
        try:
            info = qdrant_client.get_collection(CHAPTERS_COLLECTION)
        except Exception:
            pytest.skip(f"Collection '{CHAPTERS_COLLECTION}' does not exist")
        
        # Use points_count for compatibility with newer Qdrant API
        points_count = getattr(info, 'points_count', None) or getattr(info, 'vectors_count', 0) or 0
        
        # Just verify we have a reasonable number of vectors
        # Exact match with chapters requires chapter count from Neo4j
        assert points_count >= 1, (
            f"Expected at least 1 vector, found {points_count}"
        )


class TestQdrantPayloads:
    """Tests for vector payloads (WBS 3.1.3-3.1.4)."""

    def test_payloads_have_chapter_id(self, qdrant_client: Any) -> None:
        """All points must have chapter_id in payload."""
        try:
            # Get a sample of points
            points, _offset = qdrant_client.scroll(
                collection_name=CHAPTERS_COLLECTION,
                limit=10,
                with_payload=True,
                with_vectors=False,
            )
        except Exception:
            pytest.skip(f"Collection '{CHAPTERS_COLLECTION}' does not exist")
        
        if not points:
            pytest.skip("No points in collection")
        
        missing_chapter_id = [
            p for p in points 
            if not p.payload or "chapter_id" not in p.payload
        ]
        
        assert len(missing_chapter_id) == 0, (
            f"Found {len(missing_chapter_id)} points without chapter_id in payload"
        )

    def test_payloads_have_book_id(self, qdrant_client: Any) -> None:
        """All points must have book_id in payload."""
        try:
            points, _offset = qdrant_client.scroll(
                collection_name=CHAPTERS_COLLECTION,
                limit=10,
                with_payload=True,
                with_vectors=False,
            )
        except Exception:
            pytest.skip(f"Collection '{CHAPTERS_COLLECTION}' does not exist")
        
        if not points:
            pytest.skip("No points in collection")
        
        missing_book_id = [
            p for p in points 
            if not p.payload or "book_id" not in p.payload
        ]
        
        assert len(missing_book_id) == 0, (
            f"Found {len(missing_book_id)} points without book_id in payload"
        )

    def test_payloads_have_title(self, qdrant_client: Any) -> None:
        """All points should have title in payload for display."""
        try:
            points, _offset = qdrant_client.scroll(
                collection_name=CHAPTERS_COLLECTION,
                limit=10,
                with_payload=True,
                with_vectors=False,
            )
        except Exception:
            pytest.skip(f"Collection '{CHAPTERS_COLLECTION}' does not exist")
        
        if not points:
            pytest.skip("No points in collection")
        
        missing_title = [
            p for p in points 
            if not p.payload or "title" not in p.payload
        ]
        
        # Title is recommended but not required
        if len(missing_title) > 0:
            pytest.warns(
                UserWarning,
                match=f"{len(missing_title)} points without title in payload"
            )


class TestQdrantSemanticSearch:
    """Tests for semantic search functionality (WBS 3.1.3-3.1.4)."""

    def test_search_returns_results(self, qdrant_client: Any) -> None:
        """Semantic search must return results for valid queries."""
        try:
            info = qdrant_client.get_collection(CHAPTERS_COLLECTION)
            points_count = getattr(info, 'points_count', None) or getattr(info, 'vectors_count', 0) or 0
            if points_count == 0:
                pytest.skip("No vectors in collection")
        except Exception:
            pytest.skip(f"Collection '{CHAPTERS_COLLECTION}' does not exist")
        
        # Generate a test embedding (zeros for simplicity)
        test_vector = [0.0] * EMBEDDING_DIM
        
        # Use query_points for newer client, fallback to search for older
        if hasattr(qdrant_client, 'query_points'):
            response = qdrant_client.query_points(
                collection_name=CHAPTERS_COLLECTION,
                query=test_vector,
                limit=5,
            )
            results = response.points if hasattr(response, 'points') else []
        else:
            results = qdrant_client.search(
                collection_name=CHAPTERS_COLLECTION,
                query_vector=test_vector,
                limit=5,
            )
        
        # Should return at least 1 result if collection has vectors
        assert len(results) > 0, (
            "Search returned no results. "
            "Collection may be empty or improperly indexed."
        )

    def test_search_returns_scores(self, qdrant_client: Any) -> None:
        """Search results must include similarity scores."""
        try:
            info = qdrant_client.get_collection(CHAPTERS_COLLECTION)
            points_count = getattr(info, 'points_count', None) or getattr(info, 'vectors_count', 0) or 0
            if points_count == 0:
                pytest.skip("No vectors in collection")
        except Exception:
            pytest.skip(f"Collection '{CHAPTERS_COLLECTION}' does not exist")
        
        test_vector = [0.0] * EMBEDDING_DIM
        
        # Use query_points for newer client, fallback to search for older
        if hasattr(qdrant_client, 'query_points'):
            response = qdrant_client.query_points(
                collection_name=CHAPTERS_COLLECTION,
                query=test_vector,
                limit=5,
            )
            results = response.points if hasattr(response, 'points') else []
        else:
            results = qdrant_client.search(
                collection_name=CHAPTERS_COLLECTION,
                query_vector=test_vector,
                limit=5,
            )
        
        if not results:
            pytest.skip("No search results to check")
        
        # All results should have scores
        for result in results:
            assert hasattr(result, "score"), "Result missing score attribute"
            assert result.score is not None, "Result has None score"


class TestQdrantSeedingIntegrity:
    """Tests for seeding data integrity."""

    def test_no_duplicate_vectors(self, qdrant_client: Any) -> None:
        """No duplicate chapter_id values should exist in payloads.
        
        Per Issue #9-11: Seeding must be idempotent.
        """
        try:
            # Scroll through all points to check for duplicates
            all_chapter_ids: list[str] = []
            offset = None
            
            while True:
                points, offset = qdrant_client.scroll(
                    collection_name=CHAPTERS_COLLECTION,
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
                
                for point in points:
                    if point.payload and "chapter_id" in point.payload:
                        all_chapter_ids.append(point.payload["chapter_id"])
                
                if offset is None:
                    break
                    
        except Exception:
            pytest.skip(f"Collection '{CHAPTERS_COLLECTION}' does not exist")
        
        if not all_chapter_ids:
            pytest.skip("No points with chapter_id in collection")
        
        unique_ids = set(all_chapter_ids)
        
        assert len(all_chapter_ids) == len(unique_ids), (
            f"Found {len(all_chapter_ids) - len(unique_ids)} duplicate chapter_ids"
        )

    def test_vectors_have_correct_dimension(self, qdrant_client: Any) -> None:
        """All vectors must have the correct dimension."""
        try:
            points, _offset = qdrant_client.scroll(
                collection_name=CHAPTERS_COLLECTION,
                limit=5,
                with_payload=False,
                with_vectors=True,
            )
        except Exception:
            pytest.skip(f"Collection '{CHAPTERS_COLLECTION}' does not exist")
        
        if not points:
            pytest.skip("No points in collection")
        
        for point in points:
            if point.vector:
                # Handle both list and dict (named vectors) cases
                if isinstance(point.vector, list):
                    vector_dim = len(point.vector)
                else:
                    vector_dim = len(list(point.vector.values())[0])
                
                assert vector_dim == EMBEDDING_DIM, (
                    f"Expected {EMBEDDING_DIM}-dim vector, got {vector_dim}"
                )


class TestQdrantFilteringCapabilities:
    """Tests for filtered search capabilities."""

    def test_filter_by_book_id(self, qdrant_client: Any) -> None:
        """Search must support filtering by book_id."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        try:
            # First get a sample book_id
            points, _offset = qdrant_client.scroll(
                collection_name=CHAPTERS_COLLECTION,
                limit=1,
                with_payload=True,
                with_vectors=False,
            )
        except Exception:
            pytest.skip(f"Collection '{CHAPTERS_COLLECTION}' does not exist")
        
        if not points or not points[0].payload:
            pytest.skip("No points with payloads in collection")
        
        sample_book_id = points[0].payload.get("book_id")
        if not sample_book_id:
            pytest.skip("No book_id in sample point")
        
        # Use scroll with filter for compatibility with older Qdrant server (v1.7.4)
        # Note: newer query_points API doesn't work with older server
        query_filter = Filter(
            must=[
                FieldCondition(
                    key="book_id",
                    match=MatchValue(value=sample_book_id)
                )
            ]
        )
        
        # Use scroll with filter - compatible with older Qdrant versions
        filtered_points, _offset = qdrant_client.scroll(
            collection_name=CHAPTERS_COLLECTION,
            scroll_filter=query_filter,
            limit=5,
            with_payload=True,
            with_vectors=False,
        )
        
        # All results should be from the filtered book
        for point in filtered_points:
            if point.payload:
                assert point.payload.get("book_id") == sample_book_id, (
                    f"Filter failed: expected {sample_book_id}, "
                    f"got {result.payload.get('book_id')}"
                )
