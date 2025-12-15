"""Sync enriched files from llm-document-enhancer to ai-platform-data.

Phase D3: Create Migration Script
WBS Tasks: D3.1.2-6

This script syncs enriched metadata files with proper naming convention:
  {Book}_enriched.json → {Book}_metadata_enriched.json

Features:
- Source path validation (directory exists, contains enriched files)
- File renaming with _metadata_enriched.json suffix
- Checksum verification post-copy
- Dry-run mode for preview

Anti-Pattern Audit:
- Per S1192: String literals extracted to constants
- Per S3776: Cognitive complexity <15 (functions decomposed)
- Per S1172: Unused parameters prefixed with underscore
- Per Category 1.1: All functions have type annotations
- Per S6903: Uses datetime.now(timezone.utc) not datetime.utcnow()

Cross-References:
- DATA_PIPELINE_FIX_WBS.md: Phase D3.1 requirements
- AI_CODING_PLATFORM_ARCHITECTURE.md: Data flow from Enhancer to Platform
- CODING_PATTERNS_ANALYSIS.md: Anti-pattern reference

Usage:
    python scripts/sync_from_enhancer.py --dry-run
    python scripts/sync_from_enhancer.py --source /path/to/source --target /path/to/target
    python scripts/sync_from_enhancer.py --verbose
"""

from __future__ import annotations

import hashlib
import json
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

console = Console()

# =============================================================================
# Constants per CODING_PATTERNS_ANALYSIS.md (S1192)
# =============================================================================

# File naming patterns
SOURCE_SUFFIX = "_enriched.json"
TARGET_SUFFIX = "_metadata_enriched.json"
GITKEEP_FILE = ".gitkeep"

# Default paths (relative to typical workspace structure)
# These assume the script is run from ai-platform-data directory
DEFAULT_SOURCE_DIR = Path(__file__).parent.parent.parent / "llm-document-enhancer" / "workflows" / "metadata_enrichment" / "output"
DEFAULT_TARGET_DIR = Path(__file__).parent.parent / "books" / "enriched"

# Validation constants
ENRICHMENT_METADATA_KEY = "enrichment_metadata"
REQUIRED_TOP_LEVEL_KEYS = {"book", "chapters"}

# Error messages (extracted per S1192)
ERROR_SOURCE_NOT_EXIST = "Source directory does not exist: {}"
ERROR_SOURCE_NOT_DIR = "Source path is not a directory: {}"
ERROR_NO_ENRICHED_FILES = "No enriched files found in source directory: {}"
ERROR_CHECKSUM_MISMATCH = "Checksum mismatch for {}: source={} target={}"
ERROR_INVALID_JSON = "Invalid JSON in file: {}"
ERROR_COPY_FAILED = "Failed to copy {}: {}"


# =============================================================================
# Custom Exceptions per CODING_PATTERNS_ANALYSIS.md (Anti-Pattern #7)
# =============================================================================

class SyncError(Exception):
    """Base exception for sync operations."""


class SourceValidationError(SyncError):
    """Error validating source directory."""


class ChecksumMismatchError(SyncError):
    """Error when file checksums don't match after copy."""


# =============================================================================
# Data Classes for Report Structure
# =============================================================================

@dataclass
class SyncedFile:
    """Details of a successfully synced file."""
    
    source_path: Path
    target_path: Path
    source_checksum: str
    target_checksum: str
    bytes_copied: int
    
    @property
    def source_name(self) -> str:
        return self.source_path.name
    
    @property
    def target_name(self) -> str:
        return self.target_path.name
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "source_name": self.source_name,
            "target_name": self.target_name,
            "source_checksum": self.source_checksum,
            "target_checksum": self.target_checksum,
            "bytes_copied": self.bytes_copied,
        }


@dataclass
class PlannedFile:
    """Details of a file planned for sync (dry-run)."""
    
    source_path: Path
    target_name: str
    bytes_to_copy: int
    skip_reason: str | None = None
    
    @property
    def source_name(self) -> str:
        return self.source_path.name
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "source_name": self.source_name,
            "target_name": self.target_name,
            "bytes_to_copy": self.bytes_to_copy,
            "skip_reason": self.skip_reason,
        }


@dataclass
class SyncWarning:
    """Warning about a synced file."""
    
    file_name: str
    message: str
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {"file_name": self.file_name, "message": self.message}


@dataclass
class SyncFileError:
    """Error processing a file."""
    
    file_name: str
    message: str
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {"file_name": self.file_name, "message": self.message}


@dataclass
class SyncReport:
    """Complete report of sync operation."""
    
    dry_run: bool = False
    synced_files: list[SyncedFile] = field(default_factory=list)
    planned_files: list[PlannedFile] = field(default_factory=list)
    would_skip_files: list[PlannedFile] = field(default_factory=list)
    warnings: list[SyncWarning] = field(default_factory=list)
    errors: list[SyncFileError] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    
    @property
    def synced_count(self) -> int:
        """Number of files successfully synced."""
        return len(self.synced_files)
    
    @property
    def skipped_count(self) -> int:
        """Number of files skipped."""
        return len([f for f in self.planned_files if f.skip_reason])
    
    @property
    def error_count(self) -> int:
        """Number of files with errors."""
        return len(self.errors)
    
    @property
    def total_bytes_copied(self) -> int:
        """Total bytes copied."""
        return sum(f.bytes_copied for f in self.synced_files)
    
    @property
    def would_sync_count(self) -> int:
        """Number of files that would be synced (dry-run)."""
        return len([f for f in self.planned_files if not f.skip_reason])
    
    @property
    def would_skip_count(self) -> int:
        """Number of files that would be skipped (dry-run)."""
        return len(self.would_skip_files)
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "dry_run": self.dry_run,
            "synced_count": self.synced_count,
            "skipped_count": self.skipped_count,
            "error_count": self.error_count,
            "total_bytes_copied": self.total_bytes_copied,
            "elapsed_seconds": self.elapsed_seconds,
            "synced_files": [f.to_dict() for f in self.synced_files],
            "planned_files": [f.to_dict() for f in self.planned_files],
            "warnings": [w.to_dict() for w in self.warnings],
            "errors": [e.to_dict() for e in self.errors],
        }


# =============================================================================
# Helper Functions (decomposed for cognitive complexity)
# =============================================================================

def _compute_sha256(file_path: Path) -> str:
    """Compute SHA256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def _validate_source_directory(source_dir: Path) -> None:
    """Validate source directory exists and is a directory.
    
    Raises:
        SyncError: If source directory is invalid
    """
    if not source_dir.exists():
        raise SyncError(ERROR_SOURCE_NOT_EXIST.format(source_dir))
    
    if not source_dir.is_dir():
        raise SyncError(ERROR_SOURCE_NOT_DIR.format(source_dir))


def _get_enriched_files(source_dir: Path) -> list[Path]:
    """Get all files matching *_enriched.json pattern.
    
    Returns:
        List of Path objects for enriched files (excludes _metadata_enriched.json)
    """
    all_files = list(source_dir.glob(f"*{SOURCE_SUFFIX}"))
    # Exclude files that already have the target naming
    return [f for f in all_files if not f.name.endswith(TARGET_SUFFIX)]


def _validate_has_enriched_files(source_dir: Path, enriched_files: list[Path]) -> None:
    """Validate that source directory contains enriched files.
    
    Raises:
        SyncError: If no enriched files found
    """
    if not enriched_files:
        raise SyncError(ERROR_NO_ENRICHED_FILES.format(source_dir))


def _generate_target_name(source_name: str) -> str:
    """Generate target filename with new naming convention.
    
    Transforms: {Book}_enriched.json → {Book}_metadata_enriched.json
    """
    # Remove _enriched.json suffix and add _metadata_enriched.json
    book_title = source_name.removesuffix(SOURCE_SUFFIX)
    return f"{book_title}{TARGET_SUFFIX}"


def _validate_json_file(file_path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Validate that file contains valid JSON.
    
    Returns:
        Tuple of (parsed_data, error_message). If valid, error_message is None.
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
            if not content.strip():
                return None, "File is empty"
            return json.loads(content), None
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON: {e}"


def _check_enrichment_metadata(
    data: dict[str, Any],
    file_name: str
) -> SyncWarning | None:
    """Check if file has enrichment_metadata field.
    
    Returns:
        SyncWarning if field is missing, None otherwise.
    """
    if ENRICHMENT_METADATA_KEY not in data:
        return SyncWarning(
            file_name=file_name,
            message=f"Missing {ENRICHMENT_METADATA_KEY} field"
        )
    return None


def _copy_with_checksum_verification(
    source_path: Path,
    target_path: Path
) -> tuple[str, str, int]:
    """Copy file and verify checksum matches.
    
    Returns:
        Tuple of (source_checksum, target_checksum, bytes_copied)
        
    Raises:
        SyncError: If checksum mismatch detected
    """
    # Compute source checksum
    source_checksum = _compute_sha256(source_path)
    
    # Copy file
    shutil.copy2(source_path, target_path)
    
    # Compute target checksum
    target_checksum = _compute_sha256(target_path)
    
    # Verify checksums match
    if source_checksum != target_checksum:
        raise SyncError(ERROR_CHECKSUM_MISMATCH.format(
            source_path.name,
            source_checksum,
            target_checksum
        ))
    
    bytes_copied = target_path.stat().st_size
    return source_checksum, target_checksum, bytes_copied


def _should_skip_file(source_path: Path) -> str | None:
    """Determine if file should be skipped and return reason.
    
    Returns:
        Skip reason string if file should be skipped, None otherwise.
    """
    file_name = source_path.name
    
    # Skip .gitkeep and other hidden files
    if file_name.startswith("."):
        return "Hidden file"
    
    # Skip files that don't end with _enriched.json
    if not file_name.endswith(SOURCE_SUFFIX):
        return "Not an enriched file"
    
    # Skip files that already have target naming (shouldn't happen but be safe)
    if file_name.endswith(TARGET_SUFFIX):
        return "Already has target naming"
    
    return None


# =============================================================================
# Main Sync Function
# =============================================================================

def sync_from_enhancer(
    source_dir: Path,
    target_dir: Path,
    dry_run: bool = False
) -> SyncReport:
    """Sync enriched files from llm-document-enhancer to ai-platform-data.
    
    Performs:
    1. Source directory validation
    2. File enumeration (files matching *_enriched.json)
    3. For each file:
       - Rename from _enriched.json to _metadata_enriched.json
       - Copy to target directory
       - Verify checksum
    4. Generate sync report
    
    Args:
        source_dir: Path to llm-document-enhancer output directory
        target_dir: Path to ai-platform-data/books/enriched directory
        dry_run: If True, preview changes without writing files
        
    Returns:
        SyncReport with details of operation
        
    Raises:
        SyncError: If source directory is invalid or checksum mismatch detected
    """
    start_time = time.time()
    report = SyncReport(dry_run=dry_run)
    
    # Validate source directory
    _validate_source_directory(source_dir)
    
    # Get enriched files
    enriched_files = _get_enriched_files(source_dir)
    _validate_has_enriched_files(source_dir, enriched_files)
    
    # Ensure target directory exists (unless dry-run)
    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)
    
    # Process each enriched file
    for source_path in enriched_files:
        _process_single_file(source_path, target_dir, dry_run, report)
    
    report.elapsed_seconds = time.time() - start_time
    return report


def _process_single_file(
    source_path: Path,
    target_dir: Path,
    dry_run: bool,
    report: SyncReport
) -> None:
    """Process a single enriched file.
    
    Decomposed from sync_from_enhancer for cognitive complexity.
    """
    file_name = source_path.name
    target_name = _generate_target_name(file_name)
    target_path = target_dir / target_name
    
    # Check if should skip
    skip_reason = _should_skip_file(source_path)
    if skip_reason:
        report.planned_files.append(PlannedFile(
            source_path=source_path,
            target_name=target_name,
            bytes_to_copy=0,
            skip_reason=skip_reason
        ))
        return
    
    # Validate JSON
    data, json_error = _validate_json_file(source_path)
    if json_error:
        report.errors.append(SyncFileError(file_name=file_name, message=json_error))
        return
    
    # Check for enrichment_metadata (warning only)
    if data:
        warning = _check_enrichment_metadata(data, file_name)
        if warning:
            report.warnings.append(warning)
    
    # Handle dry-run mode
    if dry_run:
        _handle_dry_run(source_path, target_path, target_name, report)
        return
    
    # Perform actual sync
    _perform_sync(source_path, target_path, target_name, report)


def _handle_dry_run(
    source_path: Path,
    target_path: Path,
    target_name: str,
    report: SyncReport
) -> None:
    """Handle dry-run mode - record what would happen."""
    bytes_to_copy = source_path.stat().st_size
    
    if target_path.exists():
        report.would_skip_files.append(PlannedFile(
            source_path=source_path,
            target_name=target_name,
            bytes_to_copy=bytes_to_copy,
            skip_reason="Target file already exists"
        ))
    else:
        report.planned_files.append(PlannedFile(
            source_path=source_path,
            target_name=target_name,
            bytes_to_copy=bytes_to_copy
        ))


def _perform_sync(
    source_path: Path,
    target_path: Path,
    _target_name: str,
    report: SyncReport
) -> None:
    """Perform actual file sync with checksum verification."""
    try:
        source_checksum, target_checksum, bytes_copied = _copy_with_checksum_verification(
            source_path, target_path
        )
        report.synced_files.append(SyncedFile(
            source_path=source_path,
            target_path=target_path,
            source_checksum=source_checksum,
            target_checksum=target_checksum,
            bytes_copied=bytes_copied
        ))
    except PermissionError as e:
        report.errors.append(SyncFileError(
            file_name=source_path.name,
            message=f"Permission denied: {e}"
        ))
    except OSError as e:
        report.errors.append(SyncFileError(
            file_name=source_path.name,
            message=str(e)
        ))


# =============================================================================
# CLI Interface
# =============================================================================

def _display_report(report: SyncReport, verbose: bool = False) -> None:
    """Display sync report to console.
    
    Decomposed for cognitive complexity per S3776.
    """
    if report.dry_run:
        _display_dry_run_report(report, verbose)
    else:
        _display_actual_report(report, verbose)


def _display_dry_run_report(report: SyncReport, verbose: bool) -> None:
    """Display dry-run specific report."""
    console.print("\n[bold cyan]DRY RUN - No files were modified[/bold cyan]\n")
    
    if verbose and report.planned_files:
        table = Table(title="Files to Sync")
        table.add_column("Source", style="dim")
        table.add_column("Target", style="green")
        table.add_column("Size", justify="right")
        
        for pf in report.planned_files:
            if not pf.skip_reason:
                table.add_row(pf.source_name, pf.target_name, f"{pf.bytes_to_copy:,}")
        
        console.print(table)
    
    console.print(f"\n[green]Would sync:[/green] {report.would_sync_count} files")
    console.print(f"[yellow]Would skip:[/yellow] {report.would_skip_count} files")


def _display_actual_report(report: SyncReport, verbose: bool) -> None:
    """Display actual sync report."""
    if verbose and report.synced_files:
        table = Table(title="Synced Files")
        table.add_column("Source", style="dim")
        table.add_column("Target", style="green")
        table.add_column("Checksum", style="cyan")
        
        for sf in report.synced_files:
            table.add_row(sf.source_name, sf.target_name, sf.source_checksum[:12] + "...")
        
        console.print(table)
    
    console.print(f"\n[green]Synced:[/green] {report.synced_count} files")
    console.print(f"[yellow]Skipped:[/yellow] {report.skipped_count} files")
    console.print(f"[red]Errors:[/red] {report.error_count}")
    console.print(f"[cyan]Total bytes:[/cyan] {report.total_bytes_copied:,}")
    console.print(f"[dim]Elapsed:[/dim] {report.elapsed_seconds:.2f}s")
    
    # Display warnings
    for warning in report.warnings:
        console.print(f"[yellow]⚠ {warning.file_name}:[/yellow] {warning.message}")
    
    # Display errors
    for error in report.errors:
        console.print(f"[red]✗ {error.file_name}:[/red] {error.message}")


@click.command()
@click.option(
    "--source",
    type=click.Path(exists=False, path_type=Path),
    default=DEFAULT_SOURCE_DIR,
    help="Source directory containing enriched files"
)
@click.option(
    "--target",
    type=click.Path(exists=False, path_type=Path),
    default=DEFAULT_TARGET_DIR,
    help="Target directory for migrated files"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Preview changes without writing files"
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show detailed output"
)
def cli(
    source: Path,
    target: Path,
    dry_run: bool,
    verbose: bool
) -> None:
    """Sync enriched files from llm-document-enhancer to ai-platform-data.
    
    Renames files from {Book}_enriched.json to {Book}_metadata_enriched.json
    and copies them to the target directory with checksum verification.
    """
    try:
        console.print(f"[bold]Source:[/bold] {source}")
        console.print(f"[bold]Target:[/bold] {target}")
        
        report = sync_from_enhancer(source, target, dry_run=dry_run)
        _display_report(report, verbose=verbose)
        
        if report.error_count > 0:
            raise SystemExit(1)
            
    except SyncError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1) from e


if __name__ == "__main__":
    cli()
