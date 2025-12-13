"""Unit tests for data migration scripts.

This module tests the migration functionality:
- migrate_raw_books.py: Migrate JSON texts to books/raw/
- MigrationConfig: Configuration dataclass for scalable migration
- Streaming validation for 10K+ file scalability

TDD RED Phase: Tests written BEFORE implementation.

Scalability Patterns Applied (per CODING_PATTERNS_ANALYSIS.md):
- Dataclass for Config: MigrationConfig groups migration parameters
- Generator Pattern: migrate_books_batch() yields MigrationResult
- Streaming Validation: validate_books_streaming() yields ValidationResult
- Dynamic Counts: Tests use glob patterns instead of hardcoded values
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generator

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator


# ============================================================================
# Task 1.4.1 - Migration Script Existence Tests (RED)
# ============================================================================


class TestMigrationScriptExists:
    """Tests for migration script existence (Task 1.4.1 RED)."""

    def test_migrate_raw_books_script_exists(self, scripts_dir: Path) -> None:
        """Migration script must exist at scripts/migrate_raw_books.py."""
        script_path = scripts_dir / "migrate_raw_books.py"
        assert script_path.exists(), f"migrate_raw_books.py not found at {script_path}"

    def test_migration_script_is_importable(self) -> None:
        """Migration script must be importable as a module."""
        try:
            from scripts import migrate_raw_books  # noqa: F401
        except ImportError as e:
            pytest.fail(f"Failed to import migrate_raw_books: {e}")

    def test_migration_config_dataclass_exists(self) -> None:
        """MigrationConfig dataclass must exist (per Anti-Pattern #2.2)."""
        try:
            from scripts.migrate_raw_books import MigrationConfig
            assert hasattr(MigrationConfig, "__dataclass_fields__"), \
                "MigrationConfig must be a dataclass"
        except ImportError as e:
            pytest.fail(f"MigrationConfig not found: {e}")

    def test_migration_config_has_required_fields(self) -> None:
        """MigrationConfig must have scalability fields."""
        from scripts.migrate_raw_books import MigrationConfig

        required_fields = {
            "source_dir",      # Source directory for JSON texts
            "target_dir",      # Target directory (books/raw/)
            "batch_size",      # Configurable batch size for 10K+ scaling
            "validate_schema", # Whether to validate during migration
            "continue_on_error",  # Continue on individual file errors
        }
        actual_fields = set(MigrationConfig.__dataclass_fields__.keys())
        missing = required_fields - actual_fields
        assert not missing, f"MigrationConfig missing fields: {missing}"


# ============================================================================
# Task 1.4.2 - Migration Script Functionality Tests (GREEN target)
# ============================================================================


class TestMigrationScriptFunctionality:
    """Tests for migration script functionality (Task 1.4.2 GREEN)."""

    def test_migrate_books_batch_function_exists(self) -> None:
        """migrate_books_batch() generator function must exist."""
        from scripts.migrate_raw_books import migrate_books_batch
        import inspect
        assert inspect.isgeneratorfunction(migrate_books_batch), \
            "migrate_books_batch must be a generator function for streaming"

    def test_migration_result_dataclass_exists(self) -> None:
        """MigrationResult dataclass must exist for streaming results."""
        try:
            from scripts.migrate_raw_books import MigrationResult
            assert hasattr(MigrationResult, "__dataclass_fields__"), \
                "MigrationResult must be a dataclass"
        except ImportError as e:
            pytest.fail(f"MigrationResult not found: {e}")

    def test_migration_result_has_required_fields(self) -> None:
        """MigrationResult must have tracking fields."""
        from scripts.migrate_raw_books import MigrationResult

        required_fields = {
            "source_path",  # Original file path
            "target_path",  # Destination file path
            "success",      # Whether migration succeeded
            "error",        # Error message if failed (Optional)
        }
        actual_fields = set(MigrationResult.__dataclass_fields__.keys())
        missing = required_fields - actual_fields
        assert not missing, f"MigrationResult missing fields: {missing}"

    def test_migrate_single_file(
        self,
        tmp_path: Path,
        sample_raw_book: dict[str, Any],
    ) -> None:
        """Single file migration should work correctly."""
        import json
        from scripts.migrate_raw_books import MigrationConfig, migrate_books_batch

        # Setup source
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        source_file = source_dir / "test_book.json"
        source_file.write_text(json.dumps(sample_raw_book))

        # Setup target
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        config = MigrationConfig(
            source_dir=source_dir,
            target_dir=target_dir,
            batch_size=10,
            validate_schema=False,
            continue_on_error=False,
        )

        results = list(migrate_books_batch(config))
        assert len(results) == 1
        assert results[0].success is True
        assert (target_dir / "test_book.json").exists()

    def test_migrate_batch_processing(
        self,
        tmp_path: Path,
        sample_raw_book: dict[str, Any],
    ) -> None:
        """Batch processing should handle multiple files efficiently."""
        import json
        from scripts.migrate_raw_books import MigrationConfig, migrate_books_batch

        # Setup source with multiple files
        source_dir = tmp_path / "source"
        source_dir.mkdir()
        for i in range(25):  # Create 25 test files
            file_path = source_dir / f"book_{i:03d}.json"
            file_path.write_text(json.dumps({**sample_raw_book, "title": f"Book {i}"}))

        # Setup target
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        config = MigrationConfig(
            source_dir=source_dir,
            target_dir=target_dir,
            batch_size=10,  # Process in batches of 10
            validate_schema=False,
            continue_on_error=False,
        )

        results = list(migrate_books_batch(config))
        assert len(results) == 25
        assert all(r.success for r in results)
        assert len(list(target_dir.glob("*.json"))) == 25

    def test_migrate_continues_on_error_when_configured(
        self,
        tmp_path: Path,
        sample_raw_book: dict[str, Any],
    ) -> None:
        """Migration should continue on error when configured."""
        import json
        from scripts.migrate_raw_books import MigrationConfig, migrate_books_batch

        # Setup source
        source_dir = tmp_path / "source"
        source_dir.mkdir()

        # Create valid file
        valid_file = source_dir / "valid_book.json"
        valid_file.write_text(json.dumps(sample_raw_book))

        # Create invalid file (not JSON)
        invalid_file = source_dir / "invalid_book.json"
        invalid_file.write_text("not valid json {{{")

        # Setup target
        target_dir = tmp_path / "target"
        target_dir.mkdir()

        config = MigrationConfig(
            source_dir=source_dir,
            target_dir=target_dir,
            batch_size=10,
            validate_schema=False,
            continue_on_error=True,  # Continue despite errors
        )

        results = list(migrate_books_batch(config))
        assert len(results) == 2
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        assert len(successful) == 1
        assert len(failed) == 1
        assert failed[0].error is not None


# ============================================================================
# Task 1.4.3 - Dynamic Book Count Tests (RED)
# ============================================================================


class TestExpectedBooksMigrated:
    """Tests for dynamic book count validation (Task 1.4.3 RED).

    Note: Tests use dynamic counts from source directory, not hardcoded "47".
    This supports scaling from 47 to 10,000+ books.
    """

    def test_source_directory_has_books(self, textbooks_json_dir: Path) -> None:
        """Source directory must contain JSON book files."""
        json_files = list(textbooks_json_dir.glob("*.json"))
        assert len(json_files) > 0, f"No JSON files found in {textbooks_json_dir}"

    def test_migrated_count_matches_source(
        self,
        books_raw_dir: Path,
        textbooks_json_dir: Path,
    ) -> None:
        """Target directory count must match source directory count."""
        source_count = len(list(textbooks_json_dir.glob("*.json")))
        target_count = len(list(books_raw_dir.glob("*.json")))

        assert target_count == source_count, (
            f"Migration incomplete: {target_count}/{source_count} books migrated"
        )

    def test_all_source_files_have_corresponding_target(
        self,
        books_raw_dir: Path,
        textbooks_json_dir: Path,
    ) -> None:
        """Every source file must have a corresponding target file."""
        source_files = {f.name for f in textbooks_json_dir.glob("*.json")}
        target_files = {f.name for f in books_raw_dir.glob("*.json")}

        missing = source_files - target_files
        assert not missing, f"Missing migrated files: {missing}"


# ============================================================================
# Task 1.4.5/1.4.6 - Streaming Validation Tests (RED)
# ============================================================================


class TestStreamingValidation:
    """Tests for streaming/chunked validation (Task 1.4.5/1.4.6).

    Scalability: Uses generator pattern for memory-efficient validation
    of 10,000+ files without loading all into memory.
    """

    def test_validation_result_dataclass_exists(self) -> None:
        """ValidationResult dataclass must exist for streaming."""
        try:
            from scripts.migrate_raw_books import ValidationResult
            assert hasattr(ValidationResult, "__dataclass_fields__"), \
                "ValidationResult must be a dataclass"
        except ImportError as e:
            pytest.fail(f"ValidationResult not found: {e}")

    def test_validation_result_has_required_fields(self) -> None:
        """ValidationResult must have validation tracking fields."""
        from scripts.migrate_raw_books import ValidationResult

        required_fields = {
            "file_path",  # Path to validated file
            "valid",      # Whether validation passed
            "errors",     # List of validation errors (empty if valid)
        }
        actual_fields = set(ValidationResult.__dataclass_fields__.keys())
        missing = required_fields - actual_fields
        assert not missing, f"ValidationResult missing fields: {missing}"

    def test_validate_books_streaming_function_exists(self) -> None:
        """validate_books_streaming() generator must exist."""
        from scripts.migrate_raw_books import validate_books_streaming
        import inspect
        assert inspect.isgeneratorfunction(validate_books_streaming), \
            "validate_books_streaming must be a generator function"

    def test_validate_books_streaming_yields_results(
        self,
        tmp_path: Path,
        sample_raw_book: dict[str, Any],
        load_schema: Any,
    ) -> None:
        """Streaming validation should yield ValidationResult for each file."""
        import json
        from scripts.migrate_raw_books import validate_books_streaming, ValidationResult

        # Setup test files
        test_dir = tmp_path / "books"
        test_dir.mkdir()
        for i in range(5):
            (test_dir / f"book_{i}.json").write_text(json.dumps(sample_raw_book))

        schema = load_schema("book_raw.schema.json")
        results = list(validate_books_streaming(test_dir, schema, batch_size=2))

        assert len(results) == 5
        assert all(isinstance(r, ValidationResult) for r in results)
        assert all(r.valid for r in results)

    def test_validate_books_streaming_catches_invalid(
        self,
        tmp_path: Path,
        sample_raw_book: dict[str, Any],
        load_schema: Any,
    ) -> None:
        """Streaming validation should catch invalid files."""
        import json
        from scripts.migrate_raw_books import validate_books_streaming

        # Setup test files - one valid, one invalid
        test_dir = tmp_path / "books"
        test_dir.mkdir()
        (test_dir / "valid.json").write_text(json.dumps(sample_raw_book))
        (test_dir / "invalid.json").write_text(json.dumps({"invalid": "data"}))

        schema = load_schema("book_raw.schema.json")
        results = list(validate_books_streaming(test_dir, schema, batch_size=10))

        valid_results = [r for r in results if r.valid]
        invalid_results = [r for r in results if not r.valid]

        assert len(valid_results) == 1
        assert len(invalid_results) == 1
        assert len(invalid_results[0].errors) > 0

    def test_all_migrated_files_valid_against_schema(
        self,
        books_raw_dir: Path,
        load_schema: Any,
    ) -> None:
        """All migrated files must pass schema validation (Task 1.4.6 GREEN)."""
        from scripts.migrate_raw_books import validate_books_streaming

        if not books_raw_dir.exists() or not list(books_raw_dir.glob("*.json")):
            pytest.skip("No migrated files to validate yet")

        schema = load_schema("book_raw.schema.json")
        results = list(validate_books_streaming(books_raw_dir, schema, batch_size=100))

        invalid = [r for r in results if not r.valid]
        assert len(invalid) == 0, (
            f"{len(invalid)} files failed validation: "
            f"{[str(r.file_path) for r in invalid[:5]]}..."
        )


# ============================================================================
# Task 1.4.7 - Taxonomy Migration Tests
# ============================================================================


class TestTaxonomyMigration:
    """Tests for taxonomy file migration (Task 1.4.7)."""

    def test_copy_taxonomies_function_exists(self) -> None:
        """copy_taxonomies() function must exist."""
        try:
            from scripts.migrate_raw_books import copy_taxonomies
        except ImportError as e:
            pytest.fail(f"copy_taxonomies function not found: {e}")

    def test_taxonomy_files_exist_in_target(self, taxonomies_dir: Path) -> None:
        """Taxonomy files must exist in target taxonomies/ directory."""
        assert taxonomies_dir.exists(), f"Taxonomies directory not found: {taxonomies_dir}"

        # Check for AI-ML taxonomy (primary)
        aiml_taxonomy = taxonomies_dir / "AI-ML_taxonomy_20251128.json"
        assert aiml_taxonomy.exists() or len(list(taxonomies_dir.glob("*.json"))) > 0, \
            "No taxonomy files found in taxonomies/"

    def test_taxonomy_registry_updated(self, taxonomies_dir: Path) -> None:
        """Taxonomy registry must be updated after migration."""
        registry_path = taxonomies_dir / "taxonomy_registry.json"
        assert registry_path.exists(), "taxonomy_registry.json not found"

        import json
        with open(registry_path) as f:
            registry = json.load(f)

        assert "taxonomies" in registry, "Registry missing 'taxonomies' key"
        assert len(registry["taxonomies"]) > 0, "Registry has no taxonomies listed"


# ============================================================================
# Fixtures (will be added to conftest.py)
# ============================================================================


@pytest.fixture
def sample_raw_book() -> dict[str, Any]:
    """Sample valid raw book for testing (matches llm-document-enhancer output format).
    
    This fixture matches the actual output from llm-document-enhancer's pdf_to_json
    workflow, with flexible additionalProperties support for evolving formats.
    """
    return {
        "metadata": {
            "title": "Test Book",
            "author": "Test Author",
            "publisher": "Test Publisher",
            "edition": "1st Edition",
            "isbn": "978-0-000-00000-0",
            "total_pages": 100,
            "conversion_date": "2025-01-15T12:00:00",
            "conversion_method": "PyMuPDF + OCR fallback",
            "source_pdf": "test_book.pdf",
            "extraction_method": "PyMuPDF (Direct: 100, OCR: 0)",
        },
        "chapters": [
            {
                "number": 1,
                "title": "Introduction",
                "start_page": 1,
                "end_page": 10,
                "detection_method": "topic_boundary",
                "content": "This is the introduction chapter content.",
                "page_number": 1,
            },
            {
                "number": 2,
                "title": "Getting Started",
                "start_page": 11,
                "end_page": 25,
                "detection_method": "topic_boundary",
                "content": "This is the getting started chapter content.",
                "page_number": 11,
            },
        ],
        "pages": [
            {
                "page_number": 1,
                "chapter": None,
                "content": "Introduction chapter content...",
                "content_length": 100,
                "extraction_method": "Direct",
            },
            {
                "page_number": 2,
                "chapter": None,
                "content": "More introduction content...",
                "content_length": 150,
                "extraction_method": "Direct",
            },
        ],
    }
