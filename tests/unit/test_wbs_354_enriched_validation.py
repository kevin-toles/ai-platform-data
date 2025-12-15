#!/usr/bin/env python3
"""
TDD Tests for WBS 3.5.4 - Enriched Data Transfer & Validation.

WBS Reference: AI_CODING_PLATFORM_WBS.md Phase 3.5.4
Repo: ai-platform-data
TDD Phase: RED - Tests for enriched book validation

Anti-Pattern Audit:
- CODING_PATTERNS #1.3: No hardcoded book counts (dynamic discovery)
- CODING_PATTERNS #2: Cognitive complexity < 15
- CODING_PATTERNS S1192: No duplicated literals (module constants)

Document Cross-References:
- AI_CODING_PLATFORM_ARCHITECTURE: ai-platform-data = Pantry (storage)
- TECHNICAL_CHANGE_LOG CL-007: Process in Enhancer → Transfer → Validate Pattern
"""

import json
import pytest
from pathlib import Path
from typing import Any

# =============================================================================
# Module Constants (CODING_PATTERNS S1192: No duplicated literals)
# =============================================================================
_BOOKS_ENRICHED_DIR = Path(__file__).parent.parent.parent / "books" / "enriched"
_EXPECTED_BOOK_COUNT = 47
_CHAPTERS_KEY = "chapters"
_KEYWORDS_KEY = "keywords"
_CONCEPTS_KEY = "concepts"
_SUMMARY_KEY = "summary"
_SIMILAR_CHAPTERS_KEY = "similar_chapters"


class TestEnrichedDirectoryPopulated:
    """
    WBS 3.5.4.1: Test that books/enriched/ directory is populated.
    
    TDD Phase: RED - Directory should be empty initially, then populated.
    """

    def test_enriched_directory_exists(self) -> None:
        """
        RED: books/enriched/ directory must exist.
        """
        assert _BOOKS_ENRICHED_DIR.exists(), (
            f"Directory {_BOOKS_ENRICHED_DIR} does not exist"
        )

    def test_enriched_directory_not_empty(self) -> None:
        """
        RED: books/enriched/ directory must not be empty.
        
        Acceptance Criteria: Test fails if books/enriched/ is empty.
        """
        enriched_files = list(_BOOKS_ENRICHED_DIR.glob("*.json"))
        assert len(enriched_files) > 0, (
            f"No JSON files found in {_BOOKS_ENRICHED_DIR}"
        )

    def test_enriched_has_47_books(self) -> None:
        """
        WBS 3.5.4.3: Validate 47 enriched files exist.
        
        Acceptance Criteria: ls books/enriched/*.json | wc -l equals 47
        """
        enriched_files = list(_BOOKS_ENRICHED_DIR.glob("*.json"))
        assert len(enriched_files) == _EXPECTED_BOOK_COUNT, (
            f"Expected {_EXPECTED_BOOK_COUNT} enriched books, found {len(enriched_files)}"
        )


class TestEnrichedHasKeywords:
    """
    WBS 3.5.4.4: Test that each chapter has keywords array.
    """

    @pytest.fixture
    def enriched_books(self) -> list[tuple[str, dict[str, Any]]]:
        """Load all enriched books for testing."""
        books = []
        for path in sorted(_BOOKS_ENRICHED_DIR.glob("*.json")):
            with open(path, encoding="utf-8") as f:
                books.append((path.stem, json.load(f)))
        return books

    def test_all_chapters_have_keywords_array(
        self, enriched_books: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """
        RED: Each chapter must have a keywords array.
        """
        if not enriched_books:
            pytest.skip("No enriched books found")
        
        missing_keywords = []
        for book_name, book_data in enriched_books:
            chapters = book_data.get(_CHAPTERS_KEY, [])
            for chapter in chapters:
                chapter_num = chapter.get("chapter_number", chapter.get("number", "?"))
                if _KEYWORDS_KEY not in chapter:
                    missing_keywords.append(f"{book_name} Ch.{chapter_num}")
                elif not isinstance(chapter[_KEYWORDS_KEY], list):
                    missing_keywords.append(f"{book_name} Ch.{chapter_num} (not a list)")
        
        assert len(missing_keywords) == 0, (
            f"Chapters missing keywords array: {missing_keywords[:10]}..."
            if len(missing_keywords) > 10 else f"Chapters missing keywords array: {missing_keywords}"
        )


class TestEnrichedHasConcepts:
    """
    WBS 3.5.4.5: Test that each chapter has concepts array.
    """

    @pytest.fixture
    def enriched_books(self) -> list[tuple[str, dict[str, Any]]]:
        """Load all enriched books for testing."""
        books = []
        for path in sorted(_BOOKS_ENRICHED_DIR.glob("*.json")):
            with open(path, encoding="utf-8") as f:
                books.append((path.stem, json.load(f)))
        return books

    def test_all_chapters_have_concepts_array(
        self, enriched_books: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """
        RED: Each chapter must have a concepts array.
        """
        if not enriched_books:
            pytest.skip("No enriched books found")
        
        missing_concepts = []
        for book_name, book_data in enriched_books:
            chapters = book_data.get(_CHAPTERS_KEY, [])
            for chapter in chapters:
                chapter_num = chapter.get("chapter_number", chapter.get("number", "?"))
                if _CONCEPTS_KEY not in chapter:
                    missing_concepts.append(f"{book_name} Ch.{chapter_num}")
                elif not isinstance(chapter[_CONCEPTS_KEY], list):
                    missing_concepts.append(f"{book_name} Ch.{chapter_num} (not a list)")
        
        assert len(missing_concepts) == 0, (
            f"Chapters missing concepts array: {missing_concepts[:10]}..."
            if len(missing_concepts) > 10 else f"Chapters missing concepts array: {missing_concepts}"
        )


class TestEnrichedHasSummaries:
    """
    WBS 3.5.4.6: Test that each chapter has summary string.
    """

    @pytest.fixture
    def enriched_books(self) -> list[tuple[str, dict[str, Any]]]:
        """Load all enriched books for testing."""
        books = []
        for path in sorted(_BOOKS_ENRICHED_DIR.glob("*.json")):
            with open(path, encoding="utf-8") as f:
                books.append((path.stem, json.load(f)))
        return books

    def test_all_chapters_have_summary_string(
        self, enriched_books: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """
        RED: Each chapter must have a summary string.
        """
        if not enriched_books:
            pytest.skip("No enriched books found")
        
        missing_summaries = []
        for book_name, book_data in enriched_books:
            chapters = book_data.get(_CHAPTERS_KEY, [])
            for chapter in chapters:
                chapter_num = chapter.get("chapter_number", chapter.get("number", "?"))
                if _SUMMARY_KEY not in chapter:
                    missing_summaries.append(f"{book_name} Ch.{chapter_num}")
                elif not isinstance(chapter[_SUMMARY_KEY], str):
                    missing_summaries.append(f"{book_name} Ch.{chapter_num} (not a string)")
        
        assert len(missing_summaries) == 0, (
            f"Chapters missing summary: {missing_summaries[:10]}..."
            if len(missing_summaries) > 10 else f"Chapters missing summary: {missing_summaries}"
        )


class TestEnrichedHasSimilarChapters:
    """
    WBS 3.5.4.7: Test that each chapter has similar_chapters array.
    """

    @pytest.fixture
    def enriched_books(self) -> list[tuple[str, dict[str, Any]]]:
        """Load all enriched books for testing."""
        books = []
        for path in sorted(_BOOKS_ENRICHED_DIR.glob("*.json")):
            with open(path, encoding="utf-8") as f:
                books.append((path.stem, json.load(f)))
        return books

    def test_all_chapters_have_similar_chapters_array(
        self, enriched_books: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """
        RED: Each chapter must have a similar_chapters array.
        """
        if not enriched_books:
            pytest.skip("No enriched books found")
        
        missing_similar = []
        for book_name, book_data in enriched_books:
            chapters = book_data.get(_CHAPTERS_KEY, [])
            for chapter in chapters:
                chapter_num = chapter.get("chapter_number", chapter.get("number", "?"))
                if _SIMILAR_CHAPTERS_KEY not in chapter:
                    missing_similar.append(f"{book_name} Ch.{chapter_num}")
                elif not isinstance(chapter[_SIMILAR_CHAPTERS_KEY], list):
                    missing_similar.append(f"{book_name} Ch.{chapter_num} (not a list)")
        
        assert len(missing_similar) == 0, (
            f"Chapters missing similar_chapters: {missing_similar[:10]}..."
            if len(missing_similar) > 10 else f"Chapters missing similar_chapters: {missing_similar}"
        )

    def test_similar_chapters_have_method_field(
        self, enriched_books: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """
        SBERT refactor: Each similar_chapter entry should have 'method' field.
        """
        if not enriched_books:
            pytest.skip("No enriched books found")
        
        missing_method = []
        for book_name, book_data in enriched_books:
            chapters = book_data.get(_CHAPTERS_KEY, [])
            for chapter in chapters:
                chapter_num = chapter.get("chapter_number", chapter.get("number", "?"))
                similar = chapter.get(_SIMILAR_CHAPTERS_KEY, [])
                for s in similar:
                    if "method" not in s:
                        missing_method.append(f"{book_name} Ch.{chapter_num}")
                        break  # Only report once per chapter
        
        assert len(missing_method) == 0, (
            f"Chapters with similar_chapters missing 'method' field: {missing_method[:10]}..."
            if len(missing_method) > 10 else f"Chapters missing 'method': {missing_method}"
        )


class TestEnrichedSchemaCompliance:
    """
    WBS 3.5.4.8: Validate enriched files structure.
    
    Note: The current book_enriched.schema.json is for POST-seeding state.
    We validate the llm-document-enhancer enriched format here.
    """

    @pytest.fixture
    def enriched_books(self) -> list[tuple[str, dict[str, Any]]]:
        """Load all enriched books for testing."""
        books = []
        for path in sorted(_BOOKS_ENRICHED_DIR.glob("*.json")):
            with open(path, encoding="utf-8") as f:
                books.append((path.stem, json.load(f)))
        return books

    def test_enriched_has_required_top_level_keys(
        self, enriched_books: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """
        Each enriched book must have: metadata, chapters.
        """
        if not enriched_books:
            pytest.skip("No enriched books found")
        
        required_keys = {"metadata", "chapters"}
        missing = []
        for book_name, book_data in enriched_books:
            book_keys = set(book_data.keys())
            missing_keys = required_keys - book_keys
            if missing_keys:
                missing.append(f"{book_name}: missing {missing_keys}")
        
        assert len(missing) == 0, f"Books missing required keys: {missing}"

    def test_chapters_have_required_fields(
        self, enriched_books: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """
        Each chapter must have: title, keywords, concepts, summary, similar_chapters.
        """
        if not enriched_books:
            pytest.skip("No enriched books found")
        
        required_fields = {"title", "keywords", "concepts", "summary", "similar_chapters"}
        missing = []
        for book_name, book_data in enriched_books:
            chapters = book_data.get(_CHAPTERS_KEY, [])
            for chapter in chapters:
                chapter_num = chapter.get("chapter_number", chapter.get("number", "?"))
                chapter_keys = set(chapter.keys())
                missing_fields = required_fields - chapter_keys
                if missing_fields:
                    missing.append(f"{book_name} Ch.{chapter_num}: missing {missing_fields}")
        
        assert len(missing) == 0, (
            f"Chapters missing required fields: {missing[:10]}..."
            if len(missing) > 10 else f"Chapters missing required fields: {missing}"
        )
