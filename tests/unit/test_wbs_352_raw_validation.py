#!/usr/bin/env python3
"""
TDD Tests for WBS 3.5.2 - Data Transfer & Validation.

WBS Reference: AI_CODING_PLATFORM_WBS.md Phase 3.5.2
Repo: ai-platform-data
TDD Phase: RED → GREEN

Tasks Covered:
- 3.5.2.1: RED - Write test_all_books_have_chapters
- 3.5.2.3: GREEN - Validate all 47 books have chapters
- 3.5.2.4: RED - Write test_chapters_have_required_fields
- 3.5.2.5: GREEN - Validate chapter structure

Anti-Pattern Audit:
- CODING_PATTERNS #1.1: All functions have type annotations
- CODING_PATTERNS #1.3: No hardcoded book counts (use constant)
- CODING_PATTERNS #2: Cognitive complexity < 15
- CODING_PATTERNS S1192: No duplicated literals (module constants)
- Comp_Static_Analysis_Report: Custom exceptions not shadowing builtins

Document Cross-References:
- AI_CODING_PLATFORM_ARCHITECTURE: ai-platform-data = Pantry (storage)
- book_raw.schema.json: Chapter field requirements (number/chapter_number, title, pages)
- TECHNICAL_CHANGE_LOG: Data flow from llm-document-enhancer → ai-platform-data
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

# =============================================================================
# Module Constants (CODING_PATTERNS S1192: No duplicated literals)
# =============================================================================
_BOOKS_RAW_DIR = Path(__file__).parent.parent.parent / "books" / "raw"
_EXPECTED_BOOK_COUNT = 47
_CHAPTERS_KEY = "chapters"
_TITLE_KEY = "title"
_START_PAGE_KEY = "start_page"
_END_PAGE_KEY = "end_page"
_NUMBER_KEY = "number"
_CHAPTER_NUMBER_KEY = "chapter_number"


# =============================================================================
# WBS 3.5.2.1: test_all_books_have_chapters
# =============================================================================


class TestAllBooksHaveChapters:
    """
    WBS 3.5.2.1: RED - Write test_all_books_have_chapters.

    Acceptance Criteria: Test fails if any book has empty chapters.
    TDD Phase: RED - This test defines expected behavior.
    """

    def test_raw_directory_exists(self, books_raw_dir: Path) -> None:
        """
        Precondition: books/raw/ directory must exist.
        """
        assert books_raw_dir.exists(), (
            f"Directory {books_raw_dir} does not exist. "
            "Transfer books from llm-document-enhancer first."
        )

    def test_raw_directory_has_books(self, books_raw_dir: Path) -> None:
        """
        Precondition: books/raw/ must contain JSON files.
        """
        raw_files = list(books_raw_dir.glob("*.json"))
        assert len(raw_files) > 0, (
            f"No JSON files found in {books_raw_dir}. "
            "Run WBS 3.5.2.2 to transfer books."
        )

    def test_all_books_have_chapters(self, books_raw_dir: Path) -> None:
        """
        WBS 3.5.2.1: Every book must have a non-empty chapters array.

        RED Phase Test: Defines the expected behavior.
        This test will FAIL if any book in books/raw/ has an empty chapters array.

        Acceptance Criteria:
        - Every JSON file in books/raw/ must have a "chapters" key
        - The chapters array must not be empty
        """
        raw_files = sorted(books_raw_dir.glob("*.json"))
        if not raw_files:
            pytest.skip("No raw books found - run WBS 3.5.2.2 first")

        books_without_chapters: list[str] = []

        for book_path in raw_files:
            with open(book_path, encoding="utf-8") as f:
                book_data = json.load(f)

            chapters = book_data.get(_CHAPTERS_KEY, [])
            if not chapters:
                books_without_chapters.append(book_path.stem)

        assert not books_without_chapters, (
            f"Found {len(books_without_chapters)} book(s) with empty chapters: "
            f"{books_without_chapters[:5]}{'...' if len(books_without_chapters) > 5 else ''}"
        )

    def test_47_books_transferred(self, books_raw_dir: Path) -> None:
        """
        WBS 3.5.2.3: Validate all 47 books have chapters.

        GREEN Phase Verification: Confirms expected book count.
        """
        raw_files = list(books_raw_dir.glob("*.json"))
        assert len(raw_files) == _EXPECTED_BOOK_COUNT, (
            f"Expected {_EXPECTED_BOOK_COUNT} books in {books_raw_dir}, "
            f"found {len(raw_files)}"
        )


# =============================================================================
# WBS 3.5.2.4: test_chapters_have_required_fields
# =============================================================================


class TestChaptersHaveRequiredFields:
    """
    WBS 3.5.2.4: RED - Write test_chapters_have_required_fields.

    Acceptance Criteria: Each chapter has number, title, start_page, end_page.
    TDD Phase: RED - This test defines expected chapter structure.

    Schema Reference: book_raw.schema.json chapter definition supports:
    - number OR chapter_number (legacy format support)
    - title (required)
    - start_page, end_page (for page range validation)
    """

    @pytest.fixture
    def all_raw_books(self, books_raw_dir: Path) -> list[tuple[str, dict[str, Any]]]:
        """
        Load all raw books for testing.

        Returns:
            List of (book_name, book_data) tuples.
        """
        books: list[tuple[str, dict[str, Any]]] = []
        for path in sorted(books_raw_dir.glob("*.json")):
            with open(path, encoding="utf-8") as f:
                books.append((path.stem, json.load(f)))
        return books

    def test_all_chapters_have_number_field(
        self, all_raw_books: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """
        Each chapter must have a number field (number OR chapter_number).

        Per book_raw.schema.json: anyOf [number, chapter_number] is required.
        """
        if not all_raw_books:
            pytest.skip("No raw books found")

        chapters_missing_number: list[str] = []

        for book_name, book_data in all_raw_books:
            chapters = book_data.get(_CHAPTERS_KEY, [])
            for idx, chapter in enumerate(chapters):
                has_number = (
                    _NUMBER_KEY in chapter or _CHAPTER_NUMBER_KEY in chapter
                )
                if not has_number:
                    chapters_missing_number.append(f"{book_name}[{idx}]")

        assert not chapters_missing_number, (
            f"Found {len(chapters_missing_number)} chapter(s) without number field: "
            f"{chapters_missing_number[:5]}{'...' if len(chapters_missing_number) > 5 else ''}"
        )

    def test_all_chapters_have_title(
        self, all_raw_books: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """
        Each chapter must have a title field.

        Per book_raw.schema.json: title is required.
        """
        if not all_raw_books:
            pytest.skip("No raw books found")

        chapters_missing_title: list[str] = []

        for book_name, book_data in all_raw_books:
            chapters = book_data.get(_CHAPTERS_KEY, [])
            for idx, chapter in enumerate(chapters):
                title = chapter.get(_TITLE_KEY, "")
                if not title or not str(title).strip():
                    chapters_missing_title.append(f"{book_name}[{idx}]")

        assert not chapters_missing_title, (
            f"Found {len(chapters_missing_title)} chapter(s) without title: "
            f"{chapters_missing_title[:5]}{'...' if len(chapters_missing_title) > 5 else ''}"
        )

    def test_all_chapters_have_start_page(
        self, all_raw_books: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """
        Each chapter must have a start_page field.

        Per WBS 3.5.2.4: Each chapter has number, title, start_page, end_page.
        """
        if not all_raw_books:
            pytest.skip("No raw books found")

        chapters_missing_start_page: list[str] = []

        for book_name, book_data in all_raw_books:
            chapters = book_data.get(_CHAPTERS_KEY, [])
            for idx, chapter in enumerate(chapters):
                if _START_PAGE_KEY not in chapter:
                    chapters_missing_start_page.append(f"{book_name}[{idx}]")

        assert not chapters_missing_start_page, (
            f"Found {len(chapters_missing_start_page)} chapter(s) without start_page: "
            f"{chapters_missing_start_page[:5]}{'...' if len(chapters_missing_start_page) > 5 else ''}"
        )

    def test_all_chapters_have_end_page(
        self, all_raw_books: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """
        Each chapter must have an end_page field.

        Per WBS 3.5.2.4: Each chapter has number, title, start_page, end_page.
        """
        if not all_raw_books:
            pytest.skip("No raw books found")

        chapters_missing_end_page: list[str] = []

        for book_name, book_data in all_raw_books:
            chapters = book_data.get(_CHAPTERS_KEY, [])
            for idx, chapter in enumerate(chapters):
                if _END_PAGE_KEY not in chapter:
                    chapters_missing_end_page.append(f"{book_name}[{idx}]")

        assert not chapters_missing_end_page, (
            f"Found {len(chapters_missing_end_page)} chapter(s) without end_page: "
            f"{chapters_missing_end_page[:5]}{'...' if len(chapters_missing_end_page) > 5 else ''}"
        )

    def test_page_ranges_valid(
        self, all_raw_books: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """
        Page ranges must be valid: start_page <= end_page.

        Per book_raw.schema.json: Both must be integers >= 1.
        """
        if not all_raw_books:
            pytest.skip("No raw books found")

        invalid_page_ranges: list[str] = []

        for book_name, book_data in all_raw_books:
            chapters = book_data.get(_CHAPTERS_KEY, [])
            for idx, chapter in enumerate(chapters):
                start = chapter.get(_START_PAGE_KEY)
                end = chapter.get(_END_PAGE_KEY)

                # Skip if pages not present (covered by other tests)
                if start is None or end is None:
                    continue

                if start > end:
                    invalid_page_ranges.append(
                        f"{book_name}[{idx}]: start={start} > end={end}"
                    )

        assert not invalid_page_ranges, (
            f"Found {len(invalid_page_ranges)} chapter(s) with invalid page ranges: "
            f"{invalid_page_ranges[:5]}{'...' if len(invalid_page_ranges) > 5 else ''}"
        )


# =============================================================================
# WBS 3.5.2.5: Schema Compliance Tests
# =============================================================================


class TestChapterSchemaCompliance:
    """
    WBS 3.5.2.5: GREEN - Validate chapter structure.

    Acceptance Criteria: All chapters conform to book_raw.schema.json.
    """

    def test_chapters_conform_to_schema(
        self, books_raw_dir: Path, load_schema: Any
    ) -> None:
        """
        All chapters must conform to book_raw.schema.json chapter definition.

        This is a comprehensive validation test that uses the actual schema.
        """
        from jsonschema import Draft7Validator

        schema = load_schema("book_raw.schema.json")
        validator = Draft7Validator(schema)

        validation_errors: list[str] = []
        raw_files = sorted(books_raw_dir.glob("*.json"))

        for book_path in raw_files:
            with open(book_path, encoding="utf-8") as f:
                book_data = json.load(f)

            errors = list(validator.iter_errors(book_data))
            if errors:
                for error in errors[:2]:  # Limit to first 2 errors per book
                    validation_errors.append(
                        f"{book_path.stem}: {error.message}"
                    )

        assert not validation_errors, (
            "Schema validation errors found:\n"
            + "\n".join(validation_errors[:10])
            + (f"\n... and {len(validation_errors) - 10} more" if len(validation_errors) > 10 else "")
        )


# =============================================================================
# Summary Statistics Test
# =============================================================================


class TestRawBooksStatistics:
    """
    Summary statistics to verify data integrity.

    These tests provide visibility into the data state.
    """

    def test_total_chapter_count(self, books_raw_dir: Path) -> None:
        """
        Report total chapter count across all books.

        This is not a strict assertion but provides useful metrics.
        """
        raw_files = sorted(books_raw_dir.glob("*.json"))
        total_chapters = 0
        books_by_chapter_count: dict[str, int] = {}

        for book_path in raw_files:
            with open(book_path, encoding="utf-8") as f:
                book_data = json.load(f)
            chapter_count = len(book_data.get(_CHAPTERS_KEY, []))
            total_chapters += chapter_count
            books_by_chapter_count[book_path.stem] = chapter_count

        # Sanity check - should have reasonable number of chapters
        assert total_chapters > 0, "No chapters found in any book"

        # Log statistics (visible in pytest -v output)
        min_chapters = min(books_by_chapter_count.values()) if books_by_chapter_count else 0
        max_chapters = max(books_by_chapter_count.values()) if books_by_chapter_count else 0
        avg_chapters = total_chapters / len(raw_files) if raw_files else 0

        # These are soft assertions - just ensure reasonable data
        assert min_chapters >= 1, f"Found book with {min_chapters} chapters"
        assert max_chapters < 200, f"Found book with {max_chapters} chapters (unusually high)"

        # Output for visibility (captured in pytest output)
        print("\n📊 Raw Books Statistics:")
        print(f"   Total books: {len(raw_files)}")
        print(f"   Total chapters: {total_chapters}")
        print(f"   Min chapters: {min_chapters}")
        print(f"   Max chapters: {max_chapters}")
        print(f"   Avg chapters: {avg_chapters:.1f}")
