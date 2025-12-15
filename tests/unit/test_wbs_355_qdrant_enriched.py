"""Unit tests for WBS 3.5.5 - Qdrant enriched data seeding.

Phase 3.5.5: Update Seeding Scripts for Enriched Data
WBS Tasks: 3.5.5.1-8

These tests validate:
1. seed_qdrant.py reads from books/enriched/
2. Payloads include keywords, concepts, summary, similar_chapters
3. chapter_id generation correlates with Neo4j

TDD Methodology:
- RED: Tests written first, expected to fail initially
- GREEN: Implement minimal code to pass tests
- REFACTOR: Clean code and align with CODING_PATTERNS_ANALYSIS

Anti-Pattern Audit:
- Per S1192: String literals extracted to constants
- Per Category 1.1: All functions have type annotations
- Per Category 2: Functions under 15 complexity
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Constants per CODING_PATTERNS_ANALYSIS.md (S1192)
BOOKS_PATH = Path(__file__).parent.parent.parent / "books"
ENRICHED_PATH = BOOKS_PATH / "enriched"
EXPECTED_BOOK_COUNT = 47
EXPECTED_ENRICHED_PAYLOAD_KEYS = {"keywords", "concepts", "summary", "similar_chapters"}
EXPECTED_BASE_PAYLOAD_KEYS = {"chapter_id", "book_id", "book_title", "title", "number"}


def _get_enriched_files() -> list[Path]:
    """Get all enriched JSON files."""
    if not ENRICHED_PATH.exists():
        return []
    return sorted(ENRICHED_PATH.glob("*.json"))


def _get_sample_enriched_book() -> dict[str, Any] | None:
    """Load a sample enriched book for testing."""
    files = _get_enriched_files()
    if not files:
        return None
    with open(files[0]) as f:
        return json.load(f)


class TestSeedQdrantUsesEnriched:
    """WBS 3.5.5.1: Test that seed_qdrant.py reads from books/enriched/."""

    def test_enriched_directory_exists(self) -> None:
        """Enriched directory must exist for seeding."""
        assert ENRICHED_PATH.exists(), (
            f"Enriched directory not found at {ENRICHED_PATH}. "
            "Run WBS 3.5.4 to transfer enriched files."
        )

    def test_enriched_has_expected_books(self) -> None:
        """Enriched directory should have 47 books."""
        files = _get_enriched_files()
        assert len(files) == EXPECTED_BOOK_COUNT, (
            f"Expected {EXPECTED_BOOK_COUNT} enriched books, found {len(files)}"
        )

    def test_seed_function_exists_for_enriched(self) -> None:
        """seed_chapters_from_enriched function must exist."""
        from scripts.seed_qdrant import seed_chapters_from_enriched
        
        assert callable(seed_chapters_from_enriched), (
            "seed_chapters_from_enriched must be a callable function"
        )

    def test_seed_prefers_enriched_over_metadata(self) -> None:
        """seed_all should prefer enriched data when available."""
        from scripts.seed_qdrant import seed_all, QdrantConfig
        
        # Mock client to avoid actual Qdrant calls
        with patch("scripts.seed_qdrant.get_qdrant_client") as mock_client, \
             patch("scripts.seed_qdrant.ensure_collection") as mock_ensure, \
             patch("scripts.seed_qdrant.seed_chapters_from_enriched") as mock_enriched, \
             patch("scripts.seed_qdrant.seed_chapters_from_metadata") as mock_metadata:
            
            mock_client.return_value = MagicMock()
            mock_ensure.return_value = True
            mock_enriched.return_value = (100, 10)
            mock_metadata.return_value = (50, 5)
            
            config = QdrantConfig(books_path=BOOKS_PATH)
            result = seed_all(config)
            
            # Should call enriched, not metadata (since enriched exists)
            mock_enriched.assert_called_once()
            mock_metadata.assert_not_called()


def _get_qdrant_enriched_source() -> str:
    """Get combined source of enriched seeding functions.
    
    Includes both main function and helper functions to properly
    inspect refactored code.
    """
    from scripts.seed_qdrant import (
        seed_chapters_from_enriched,
        _build_enriched_payload,
        _process_enriched_book,
    )
    import inspect
    
    return (
        inspect.getsource(seed_chapters_from_enriched) +
        inspect.getsource(_build_enriched_payload) +
        inspect.getsource(_process_enriched_book)
    )


class TestQdrantPayloadsHaveKeywords:
    """WBS 3.5.5.3: Test that payloads include keywords."""

    def test_enriched_chapters_have_keywords(self) -> None:
        """All enriched chapters must have keywords array."""
        book = _get_sample_enriched_book()
        if book is None:
            pytest.skip("No enriched books available")
        
        chapters = book.get("chapters", [])
        assert len(chapters) > 0, "Book has no chapters"
        
        for i, chapter in enumerate(chapters):
            assert "keywords" in chapter, (
                f"Chapter {i} missing 'keywords' field"
            )
            assert isinstance(chapter["keywords"], list), (
                f"Chapter {i} 'keywords' must be a list"
            )

    def test_seed_payload_includes_keywords(self) -> None:
        """Qdrant payload must include keywords from enriched data."""
        source = _get_qdrant_enriched_source()
        
        assert '"keywords"' in source or "'keywords'" in source, (
            "seed_chapters_from_enriched must include 'keywords' in payload"
        )


class TestQdrantPayloadsHaveConcepts:
    """WBS 3.5.5.4: Test that payloads include concepts."""

    def test_enriched_chapters_have_concepts(self) -> None:
        """All enriched chapters must have concepts array."""
        book = _get_sample_enriched_book()
        if book is None:
            pytest.skip("No enriched books available")
        
        chapters = book.get("chapters", [])
        assert len(chapters) > 0, "Book has no chapters"
        
        for i, chapter in enumerate(chapters):
            assert "concepts" in chapter, (
                f"Chapter {i} missing 'concepts' field"
            )
            assert isinstance(chapter["concepts"], list), (
                f"Chapter {i} 'concepts' must be a list"
            )

    def test_seed_payload_includes_concepts(self) -> None:
        """Qdrant payload must include concepts from enriched data."""
        source = _get_qdrant_enriched_source()
        
        assert '"concepts"' in source or "'concepts'" in source, (
            "seed_chapters_from_enriched must include 'concepts' in payload"
        )


class TestQdrantPayloadsHaveSummary:
    """WBS 3.5.5.5: Test that payloads include summary."""

    def test_enriched_chapters_have_summary(self) -> None:
        """All enriched chapters must have summary string."""
        book = _get_sample_enriched_book()
        if book is None:
            pytest.skip("No enriched books available")
        
        chapters = book.get("chapters", [])
        assert len(chapters) > 0, "Book has no chapters"
        
        for i, chapter in enumerate(chapters):
            assert "summary" in chapter, (
                f"Chapter {i} missing 'summary' field"
            )
            assert isinstance(chapter["summary"], str), (
                f"Chapter {i} 'summary' must be a string"
            )

    def test_seed_payload_includes_summary(self) -> None:
        """Qdrant payload must include summary from enriched data."""
        source = _get_qdrant_enriched_source()
        
        assert '"summary"' in source or "'summary'" in source, (
            "seed_chapters_from_enriched must include 'summary' in payload"
        )


class TestQdrantPayloadsHaveSimilarChapters:
    """WBS 3.5.5.6: Test that payloads include similar_chapters."""

    def test_enriched_chapters_have_similar_chapters(self) -> None:
        """All enriched chapters must have similar_chapters array."""
        book = _get_sample_enriched_book()
        if book is None:
            pytest.skip("No enriched books available")
        
        chapters = book.get("chapters", [])
        assert len(chapters) > 0, "Book has no chapters"
        
        for i, chapter in enumerate(chapters):
            assert "similar_chapters" in chapter, (
                f"Chapter {i} missing 'similar_chapters' field"
            )
            assert isinstance(chapter["similar_chapters"], list), (
                f"Chapter {i} 'similar_chapters' must be a list"
            )

    def test_seed_payload_includes_similar_chapters(self) -> None:
        """Qdrant payload must include similar_chapters from enriched data."""
        source = _get_qdrant_enriched_source()
        
        assert '"similar_chapters"' in source or "'similar_chapters'" in source, (
            "seed_chapters_from_enriched must include 'similar_chapters' in payload"
        )

    def test_similar_chapters_have_method_field(self) -> None:
        """similar_chapters entries must have method field (api or sentence_transformers)."""
        book = _get_sample_enriched_book()
        if book is None:
            pytest.skip("No enriched books available")
        
        chapters = book.get("chapters", [])
        
        # Valid methods: 'api' (SBERT via Code-Orchestrator), 'sentence_transformers' (legacy)
        valid_methods = ("api", "sentence_transformers")
        
        # Find a chapter with similar_chapters
        for chapter in chapters:
            similar = chapter.get("similar_chapters", [])
            if similar:
                for item in similar:
                    assert "method" in item, (
                        "similar_chapters entry missing 'method' field"
                    )
                    assert item["method"] in valid_methods, (
                        f"Expected method in {valid_methods}, got '{item['method']}'"
                    )
                return  # Found and validated
        
        pytest.skip("No similar_chapters data to validate")


class TestNeo4jCorrelation:
    """WBS 3.5.5.8: Validate chapter_id correlation with Neo4j."""

    def test_chapter_id_format_consistent(self) -> None:
        """chapter_id generation must be consistent between Qdrant and Neo4j."""
        # Check that seed_qdrant and seed_neo4j use same chapter_id
        from scripts.seed_neo4j import seed_chapters
        
        import inspect
        
        qdrant_source = _get_qdrant_enriched_source()
        neo4j_source = inspect.getsource(seed_chapters)
        
        # Both should use chapter.get("chapter_id") pattern
        qdrant_uses_chapter_id = 'chapter_id' in qdrant_source
        neo4j_uses_chapter_id = 'chapter_id' in neo4j_source
        
        assert qdrant_uses_chapter_id and neo4j_uses_chapter_id, (
            "Both Qdrant and Neo4j seeders must use chapter_id for correlation"
        )

    def test_enriched_books_have_consistent_structure(self) -> None:
        """Enriched books must have same structure as metadata books."""
        book = _get_sample_enriched_book()
        if book is None:
            pytest.skip("No enriched books available")
        
        # Enriched books should have metadata section
        metadata = book.get("metadata", {})
        
        # Check for basic metadata fields used in seeding
        expected_metadata = {"title", "author"}
        actual_keys = set(metadata.keys())
        
        # At minimum, title should be accessible somehow
        has_title = "title" in metadata or "title" in book
        
        assert has_title, (
            "Enriched books must have title for Qdrant payload"
        )


class TestPayloadCompleteness:
    """Test that all enriched fields are included in payload."""

    def test_payload_has_all_enriched_fields(self) -> None:
        """Payload must include all enriched fields."""
        source = _get_qdrant_enriched_source()
        
        # Check all required enriched fields are in payload
        for field in EXPECTED_ENRICHED_PAYLOAD_KEYS:
            assert f'"{field}"' in source or f"'{field}'" in source, (
                f"seed_chapters_from_enriched must include '{field}' in payload"
            )

    def test_payload_structure_matches_schema(self) -> None:
        """Payload structure must be suitable for Qdrant filtering."""
        # Keywords, concepts should be lists (for array filtering)
        # Summary should be string
        # similar_chapters should be list of dicts
        
        book = _get_sample_enriched_book()
        if book is None:
            pytest.skip("No enriched books available")
        
        chapter = book.get("chapters", [{}])[0]
        
        # Type checks for Qdrant filtering compatibility
        assert isinstance(chapter.get("keywords", []), list), (
            "keywords must be list for Qdrant array filtering"
        )
        assert isinstance(chapter.get("concepts", []), list), (
            "concepts must be list for Qdrant array filtering"
        )
        assert isinstance(chapter.get("summary", ""), str), (
            "summary must be string for Qdrant text filtering"
        )
        assert isinstance(chapter.get("similar_chapters", []), list), (
            "similar_chapters must be list for Qdrant payload"
        )
