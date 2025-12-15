"""Unit tests for WBS D2.2: Naming Convention Validation.

Phase D2.2: Update ai-platform-data Validation
WBS Tasks: D2.2.1-5

These tests validate:
1. Enriched files use `{Book Title}_metadata_enriched.json` naming
2. All enriched files have enrichment_metadata provenance section
3. Scripts correctly read the new naming convention
4. All required provenance fields are present

TDD Methodology:
- RED: Tests written first, expected to fail initially (files not yet renamed)
- GREEN: Implement script updates + run D3 migration
- REFACTOR: Clean code and align with CODING_PATTERNS_ANALYSIS

Anti-Pattern Audit:
- Per S1192: String literals extracted to constants
- Per Category 1.1: All functions have type annotations
- Per S3776: Functions under 15 complexity

Reference: DATA_PIPELINE_FIX_WBS.md in textbooks/pending/platform/
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest


# =============================================================================
# Constants per CODING_PATTERNS_ANALYSIS.md (S1192)
# =============================================================================

BOOKS_ENRICHED_DIR = Path(__file__).parent.parent.parent / "books" / "enriched"
EXPECTED_OUTPUT_SUFFIX = "_metadata_enriched.json"
ENRICHMENT_METADATA_KEY = "enrichment_metadata"
EXPECTED_PROVENANCE_FIELDS = {
    "taxonomy_id",
    "taxonomy_version",
    "taxonomy_path",
    "taxonomy_checksum",
    "source_metadata_file",
    "enrichment_date",
    "enrichment_method",
    "model_version",
}
EXPECTED_BOOK_COUNT = 47
MINIMUM_CHECKSUM_LENGTH = 64  # sha256 hex length
VALID_ENRICHMENT_METHODS = {"sentence_transformers", "tfidf", "statistical", "semantic_search"}


# =============================================================================
# Helper Functions
# =============================================================================

def _get_enriched_files() -> list[Path]:
    """Get all enriched JSON files in the directory."""
    if not BOOKS_ENRICHED_DIR.exists():
        return []
    return sorted(BOOKS_ENRICHED_DIR.glob("*.json"))


def _get_metadata_enriched_files() -> list[Path]:
    """Get files following new naming convention (_metadata_enriched.json)."""
    if not BOOKS_ENRICHED_DIR.exists():
        return []
    return sorted(BOOKS_ENRICHED_DIR.glob("*_metadata_enriched.json"))


def _load_enriched_book(path: Path) -> dict[str, Any]:
    """Load an enriched book JSON file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# =============================================================================
# Test Class: Naming Convention
# =============================================================================

class TestNamingConvention:
    """WBS D2.2: Test that enriched files use _metadata_enriched.json suffix."""

    def test_enriched_directory_exists(self) -> None:
        """Enriched directory must exist."""
        assert BOOKS_ENRICHED_DIR.exists(), (
            f"Directory {BOOKS_ENRICHED_DIR} does not exist"
        )

    def test_all_files_use_metadata_enriched_suffix(self) -> None:
        """All enriched files should use _metadata_enriched.json suffix.
        
        NOTE: This test will fail in RED phase until D3 migration renames files.
        Current files: {Book Title}.json
        Expected files: {Book Title}_metadata_enriched.json
        """
        all_files = _get_enriched_files()
        metadata_enriched_files = _get_metadata_enriched_files()
        
        # Skip if no files at all
        if not all_files:
            pytest.skip("No enriched files found")
        
        # Count files not matching new convention
        non_compliant = [f for f in all_files if not f.name.endswith(EXPECTED_OUTPUT_SUFFIX)]
        
        assert len(non_compliant) == 0, (
            f"Found {len(non_compliant)} files not using {EXPECTED_OUTPUT_SUFFIX} suffix:\n"
            f"  First 5: {[f.name for f in non_compliant[:5]]}"
        )

    def test_expected_book_count_with_new_naming(self) -> None:
        """Should have 47 books with _metadata_enriched.json naming."""
        metadata_enriched_files = _get_metadata_enriched_files()
        
        assert len(metadata_enriched_files) == EXPECTED_BOOK_COUNT, (
            f"Expected {EXPECTED_BOOK_COUNT} files with {EXPECTED_OUTPUT_SUFFIX} suffix, "
            f"found {len(metadata_enriched_files)}"
        )


# =============================================================================
# Test Class: Enrichment Provenance Fields
# =============================================================================

class TestEnrichmentProvenanceFields:
    """WBS D2.2: Test that enrichment_metadata contains provenance fields."""

    @pytest.fixture
    def sample_enriched_book(self) -> dict[str, Any] | None:
        """Load a sample enriched book for testing."""
        files = _get_enriched_files()
        if not files:
            return None
        return _load_enriched_book(files[0])

    def test_enriched_books_have_enrichment_metadata(
        self, sample_enriched_book: dict[str, Any] | None
    ) -> None:
        """All enriched books must have enrichment_metadata section."""
        if sample_enriched_book is None:
            pytest.skip("No enriched books found")
        
        assert ENRICHMENT_METADATA_KEY in sample_enriched_book, (
            f"Missing '{ENRICHMENT_METADATA_KEY}' section in enriched book"
        )

    def test_all_provenance_fields_present(
        self, sample_enriched_book: dict[str, Any] | None
    ) -> None:
        """All required provenance fields must be present."""
        if sample_enriched_book is None:
            pytest.skip("No enriched books found")
        
        enrichment_metadata = sample_enriched_book.get(ENRICHMENT_METADATA_KEY, {})
        actual_fields = set(enrichment_metadata.keys())
        missing_fields = EXPECTED_PROVENANCE_FIELDS - actual_fields
        
        assert not missing_fields, (
            f"Missing provenance fields: {missing_fields}\n"
            f"Present fields: {actual_fields}"
        )

    def test_taxonomy_checksum_format(
        self, sample_enriched_book: dict[str, Any] | None
    ) -> None:
        """Taxonomy checksum should be sha256 format."""
        if sample_enriched_book is None:
            pytest.skip("No enriched books found")
        
        enrichment_metadata = sample_enriched_book.get(ENRICHMENT_METADATA_KEY, {})
        checksum = enrichment_metadata.get("taxonomy_checksum", "")
        
        # Should start with "sha256:" prefix
        assert checksum.startswith("sha256:"), (
            f"Checksum should start with 'sha256:', got: {checksum[:20]}..."
        )
        
        # Extract hex part and validate length
        if ":" in checksum:
            hex_part = checksum.split(":")[1]
            # Allow "none" for local mode without taxonomy
            if hex_part != "none":
                assert len(hex_part) == MINIMUM_CHECKSUM_LENGTH, (
                    f"Checksum hex should be {MINIMUM_CHECKSUM_LENGTH} chars, "
                    f"got {len(hex_part)}"
                )

    def test_enrichment_method_valid(
        self, sample_enriched_book: dict[str, Any] | None
    ) -> None:
        """Enrichment method should be one of valid methods."""
        if sample_enriched_book is None:
            pytest.skip("No enriched books found")
        
        enrichment_metadata = sample_enriched_book.get(ENRICHMENT_METADATA_KEY, {})
        method = enrichment_metadata.get("enrichment_method", "")
        
        assert method in VALID_ENRICHMENT_METHODS, (
            f"Invalid enrichment method: {method}\n"
            f"Valid methods: {VALID_ENRICHMENT_METHODS}"
        )


# =============================================================================
# Test Class: All Books Validation
# =============================================================================

class TestAllBooksValidation:
    """Validate all enriched books have required structure."""

    @pytest.fixture
    def all_enriched_books(self) -> list[tuple[str, dict[str, Any]]]:
        """Load all enriched books for validation."""
        books = []
        for path in _get_enriched_files():
            try:
                book_data = _load_enriched_book(path)
                books.append((path.name, book_data))
            except json.JSONDecodeError:
                continue
        return books

    def test_all_books_have_enrichment_metadata(
        self, all_enriched_books: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """Every book must have enrichment_metadata section."""
        if not all_enriched_books:
            pytest.skip("No enriched books found")
        
        missing_metadata = []
        for book_name, book_data in all_enriched_books:
            if ENRICHMENT_METADATA_KEY not in book_data:
                missing_metadata.append(book_name)
        
        assert not missing_metadata, (
            f"{len(missing_metadata)} books missing enrichment_metadata:\n"
            f"  {missing_metadata[:5]}..."
        )

    def test_all_books_have_source_metadata_file(
        self, all_enriched_books: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """Every book must track its source metadata file."""
        if not all_enriched_books:
            pytest.skip("No enriched books found")
        
        missing_source = []
        for book_name, book_data in all_enriched_books:
            enrichment_metadata = book_data.get(ENRICHMENT_METADATA_KEY, {})
            if "source_metadata_file" not in enrichment_metadata:
                missing_source.append(book_name)
        
        assert not missing_source, (
            f"{len(missing_source)} books missing source_metadata_file:\n"
            f"  {missing_source[:5]}..."
        )


# =============================================================================
# Test Class: Script Compatibility
# =============================================================================

class TestScriptCompatibility:
    """Test that scripts can read the new naming convention."""

    def test_validate_enriched_books_glob_pattern(self) -> None:
        """validate_enriched_books.py uses *.json glob - should work with new names."""
        # The glob pattern "*.json" will match both:
        # - Old: "A Philosophy of Software Design.json"
        # - New: "A Philosophy of Software Design_metadata_enriched.json"
        # So no code change needed, just verify the pattern works
        files = list(BOOKS_ENRICHED_DIR.glob("*.json"))
        assert len(files) > 0, "No JSON files found with *.json glob"

    def test_seed_qdrant_enriched_path(self) -> None:
        """seed_qdrant.py reads from books/enriched/ - should work with new names."""
        enriched_path = BOOKS_ENRICHED_DIR
        assert enriched_path.exists(), f"Enriched path does not exist: {enriched_path}"
        
        # Verify files can be discovered
        json_files = list(enriched_path.glob("*.json"))
        assert len(json_files) > 0, "No JSON files in enriched path"
