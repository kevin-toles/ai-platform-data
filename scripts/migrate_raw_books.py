"""Migrate raw book JSON files to ai-platform-data repository.

This script provides scalable migration with:
- MigrationConfig dataclass for parameterized migration
- Generator pattern (migrate_books_batch) for streaming progress
- Streaming validation (validate_books_streaming) for memory efficiency
- Support for 10,000+ files via configurable batch processing

Patterns Applied (per CODING_PATTERNS_ANALYSIS.md):
- Anti-Pattern #2.2: Dataclass instead of long parameter lists
- Anti-Pattern #2.1: Cognitive complexity < 15 via Extract Method
- Comp_Static_Analysis #12: Connection pooling pattern (lazy resource init)

Usage:
    python -m scripts.migrate_raw_books --source /path/to/textbooks --target /path/to/books/raw
"""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generator, Optional

from jsonschema import Draft7Validator, ValidationError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes (per Anti-Pattern #2.2 - avoid long parameter lists)
# ============================================================================


@dataclass
class MigrationConfig:
    """Configuration for scalable book migration.

    Groups migration parameters into a single context object,
    avoiding functions with >4 parameters (per Anti-Pattern #2.2).

    Attributes:
        source_dir: Source directory containing JSON text files.
        target_dir: Target directory for migrated files.
        batch_size: Number of files to process per batch (for 10K+ scaling).
        validate_schema: Whether to validate files during migration.
        continue_on_error: Continue migration if individual files fail.
        schema_path: Optional path to JSON schema for validation.
    """

    source_dir: Path
    target_dir: Path
    batch_size: int = 100
    validate_schema: bool = True
    continue_on_error: bool = False
    schema_path: Optional[Path] = None

    def __post_init__(self) -> None:
        """Convert string paths to Path objects."""
        if isinstance(self.source_dir, str):
            self.source_dir = Path(self.source_dir)
        if isinstance(self.target_dir, str):
            self.target_dir = Path(self.target_dir)
        if isinstance(self.schema_path, str):
            self.schema_path = Path(self.schema_path)


@dataclass
class MigrationResult:
    """Result of migrating a single file.

    Provides streaming feedback for progress tracking on large migrations.

    Attributes:
        source_path: Original file path.
        target_path: Destination file path.
        success: Whether migration succeeded.
        error: Error message if failed (None if success).
    """

    source_path: Path
    target_path: Path
    success: bool
    error: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of validating a single file against schema.

    Supports streaming validation for memory-efficient processing
    of 10,000+ files.

    Attributes:
        file_path: Path to validated file.
        valid: Whether validation passed.
        errors: List of validation error messages.
    """

    file_path: Path
    valid: bool
    errors: list[str] = field(default_factory=list)


# ============================================================================
# Generator Functions (for streaming/batch processing)
# ============================================================================


def migrate_books_batch(
    config: MigrationConfig,
) -> Generator[MigrationResult, None, None]:
    """Migrate JSON book files using generator pattern for streaming.

    Yields MigrationResult for each file, enabling:
    - Progress tracking on large migrations
    - Memory efficiency (no full list in memory)
    - Interruptible processing

    Args:
        config: Migration configuration with source/target paths.

    Yields:
        MigrationResult for each processed file.

    Raises:
        FileNotFoundError: If source directory doesn't exist.
        MigrationError: If continue_on_error=False and a file fails.
    """
    if not config.source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {config.source_dir}")

    # Ensure target directory exists
    config.target_dir.mkdir(parents=True, exist_ok=True)

    # Load schema if validation requested
    schema: Optional[dict[str, Any]] = None
    if config.validate_schema and config.schema_path:
        schema = _load_schema(config.schema_path)

    # Get all JSON files
    json_files = list(config.source_dir.glob("*.json"))
    total_files = len(json_files)
    logger.info(f"Found {total_files} JSON files to migrate")

    # Process in batches for logging/progress
    for batch_start in range(0, total_files, config.batch_size):
        batch_end = min(batch_start + config.batch_size, total_files)
        batch = json_files[batch_start:batch_end]
        logger.info(f"Processing batch {batch_start//config.batch_size + 1}: files {batch_start + 1}-{batch_end}")

        for source_file in batch:
            result = _migrate_single_file(source_file, config.target_dir, schema)
            yield result

            if not result.success and not config.continue_on_error:
                raise MigrationError(f"Migration failed: {result.error}")


def validate_books_streaming(
    books_dir: Path,
    schema: dict[str, Any],
    batch_size: int = 100,
) -> Generator[ValidationResult, None, None]:
    """Validate book files using streaming/generator pattern.

    Memory-efficient validation for 10,000+ files - yields results
    one at a time without loading all files into memory.

    Args:
        books_dir: Directory containing JSON book files.
        schema: JSON schema dictionary to validate against.
        batch_size: Number of files per batch (for logging progress).

    Yields:
        ValidationResult for each validated file.
    """
    if not books_dir.exists():
        logger.warning(f"Books directory does not exist: {books_dir}")
        return

    json_files = list(books_dir.glob("*.json"))
    total_files = len(json_files)

    if total_files == 0:
        logger.warning(f"No JSON files found in {books_dir}")
        return

    logger.info(f"Validating {total_files} files against schema")

    # Create validator once (connection pooling pattern)
    validator = Draft7Validator(schema)

    for batch_start in range(0, total_files, batch_size):
        batch_end = min(batch_start + batch_size, total_files)
        batch = json_files[batch_start:batch_end]

        for file_path in batch:
            result = _validate_single_file(file_path, validator)
            yield result


# ============================================================================
# Taxonomy Migration
# ============================================================================


def copy_taxonomies(
    source_dir: Path,
    target_dir: Path,
    registry_path: Optional[Path] = None,
) -> list[Path]:
    """Copy taxonomy files and update registry.

    Args:
        source_dir: Source directory containing taxonomy files.
        target_dir: Target taxonomies directory.
        registry_path: Path to taxonomy_registry.json to update.

    Returns:
        List of copied taxonomy file paths.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    copied_files: list[Path] = []

    # Copy taxonomy files
    for source_file in source_dir.glob("*.json"):
        if source_file.name == "taxonomy_registry.json":
            continue  # Don't overwrite registry
        target_file = target_dir / source_file.name
        shutil.copy2(source_file, target_file)
        copied_files.append(target_file)
        logger.info(f"Copied taxonomy: {source_file.name}")

    # Update registry if exists
    if registry_path and registry_path.exists():
        _update_taxonomy_registry(registry_path, copied_files)

    return copied_files


# ============================================================================
# Private Helper Functions (Extract Method pattern)
# ============================================================================


def _load_schema(schema_path: Path) -> dict[str, Any]:
    """Load JSON schema from file.

    Args:
        schema_path: Path to schema file.

    Returns:
        Schema dictionary.
    """
    with open(schema_path, encoding="utf-8") as f:
        return json.load(f)


def _migrate_single_file(
    source_file: Path,
    target_dir: Path,
    schema: Optional[dict[str, Any]] = None,
) -> MigrationResult:
    """Migrate a single JSON file.

    Extracted method to keep cognitive complexity low (<15).

    Args:
        source_file: Source file path.
        target_dir: Target directory path.
        schema: Optional schema for validation.

    Returns:
        MigrationResult indicating success/failure.
    """
    target_file = target_dir / source_file.name

    try:
        # Read and parse JSON (validates JSON syntax)
        with open(source_file, encoding="utf-8") as f:
            data = json.load(f)

        # Optional schema validation
        if schema:
            validator = Draft7Validator(schema)
            errors = list(validator.iter_errors(data))
            if errors:
                error_msg = "; ".join(str(e.message) for e in errors[:3])
                return MigrationResult(
                    source_path=source_file,
                    target_path=target_file,
                    success=False,
                    error=f"Schema validation failed: {error_msg}",
                )

        # Copy file
        shutil.copy2(source_file, target_file)
        return MigrationResult(
            source_path=source_file,
            target_path=target_file,
            success=True,
        )

    except json.JSONDecodeError as e:
        return MigrationResult(
            source_path=source_file,
            target_path=target_file,
            success=False,
            error=f"Invalid JSON: {e}",
        )
    except OSError as e:
        return MigrationResult(
            source_path=source_file,
            target_path=target_file,
            success=False,
            error=f"File error: {e}",
        )


def _validate_single_file(
    file_path: Path,
    validator: Draft7Validator,
) -> ValidationResult:
    """Validate a single file against schema.

    Extracted method for cognitive complexity management.

    Args:
        file_path: Path to JSON file.
        validator: JSON schema validator instance.

    Returns:
        ValidationResult with validation status.
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)

        errors = [str(e.message) for e in validator.iter_errors(data)]
        return ValidationResult(
            file_path=file_path,
            valid=len(errors) == 0,
            errors=errors,
        )

    except json.JSONDecodeError as e:
        return ValidationResult(
            file_path=file_path,
            valid=False,
            errors=[f"Invalid JSON: {e}"],
        )
    except OSError as e:
        return ValidationResult(
            file_path=file_path,
            valid=False,
            errors=[f"File error: {e}"],
        )


def _update_taxonomy_registry(
    registry_path: Path,
    taxonomy_files: list[Path],
) -> None:
    """Update taxonomy registry with new files.

    Args:
        registry_path: Path to taxonomy_registry.json.
        taxonomy_files: List of taxonomy files to add.
    """
    with open(registry_path, encoding="utf-8") as f:
        registry = json.load(f)

    # Add any new taxonomies not already in registry
    existing_ids = {t["id"] for t in registry.get("taxonomies", [])}

    for tax_file in taxonomy_files:
        try:
            with open(tax_file, encoding="utf-8") as f:
                tax_data = json.load(f)

            tax_id = tax_data.get("id") or tax_file.stem
            if tax_id not in existing_ids:
                registry.setdefault("taxonomies", []).append({
                    "id": tax_id,
                    "name": tax_data.get("name", tax_file.stem),
                    "file": tax_file.name,
                    "version": tax_data.get("version", "1.0.0"),
                })
                logger.info(f"Added taxonomy to registry: {tax_id}")
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Could not read taxonomy {tax_file}: {e}")

    # Save updated registry
    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)


# ============================================================================
# Custom Exceptions (per Comp_Static_Analysis #6-7)
# ============================================================================


class MigrationError(Exception):
    """Error during book migration.

    Named with prefix to avoid shadowing builtins (per Issue #7).
    """

    pass


# ============================================================================
# CLI Entry Point
# ============================================================================


def main() -> int:
    """Command-line entry point for migration script.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate raw book JSON files to ai-platform-data"
    )
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Source directory containing JSON text files",
    )
    parser.add_argument(
        "--target",
        type=Path,
        required=True,
        help="Target directory for migrated files",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of files per batch (default: 100)",
    )
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip schema validation during migration",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue migration if individual files fail",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        help="Path to JSON schema for validation",
    )

    args = parser.parse_args()

    config = MigrationConfig(
        source_dir=args.source,
        target_dir=args.target,
        batch_size=args.batch_size,
        validate_schema=not args.no_validate,
        continue_on_error=args.continue_on_error,
        schema_path=args.schema,
    )

    try:
        success_count = 0
        error_count = 0

        for result in migrate_books_batch(config):
            if result.success:
                success_count += 1
            else:
                error_count += 1
                logger.error(f"Failed: {result.source_path} - {result.error}")

        logger.info(f"Migration complete: {success_count} succeeded, {error_count} failed")
        return 0 if error_count == 0 else 1

    except MigrationError as e:
        logger.error(f"Migration aborted: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
