"""Unit tests for WBS D3.1: Migration Script (sync_from_enhancer.py).

Phase D3: Create Migration Script
WBS Tasks: D3.1.1-6

These tests validate:
1. Source path validation (directory exists, contains enriched files)
2. File renaming logic: `{Book}_enriched.json` → `{Book}_metadata_enriched.json`
3. JSON structure validation (valid JSON, has required fields)
4. Checksum verification post-copy
5. Dry-run flag previews changes without writing

TDD Methodology:
- RED: Tests written first, expected to fail (sync_from_enhancer.py doesn't exist yet)
- GREEN: Implement sync_from_enhancer.py to pass tests
- REFACTOR: Clean code and align with CODING_PATTERNS_ANALYSIS

Anti-Pattern Audit:
- Per S1192: String literals extracted to constants
- Per S3776: Functions under 15 complexity
- Per S1172: Unused parameters prefixed with underscore
- Per Category 1.1: All functions have type annotations

Reference: DATA_PIPELINE_FIX_WBS.md in textbooks/pending/platform/
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest


# =============================================================================
# Constants per CODING_PATTERNS_ANALYSIS.md (S1192)
# =============================================================================

SOURCE_SUFFIX = "_enriched.json"
TARGET_SUFFIX = "_metadata_enriched.json"
ENRICHMENT_METADATA_KEY = "enrichment_metadata"
REQUIRED_PROVENANCE_FIELDS = {
    "taxonomy_id",
    "taxonomy_version",
    "taxonomy_path",
    "taxonomy_checksum",
    "source_metadata_file",
    "enrichment_date",
    "enrichment_method",
    "model_version",
}
TAXONOMY_CHECKSUM_PREFIX = "sha256:"
GITKEEP_FILE = ".gitkeep"


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_source_dir(tmp_path: Path) -> Path:
    """Create a temporary source directory with sample enriched files."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    return source_dir


@pytest.fixture
def temp_target_dir(tmp_path: Path) -> Path:
    """Create a temporary target directory."""
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    return target_dir


@pytest.fixture
def sample_enriched_data() -> dict[str, Any]:
    """Sample enriched data with OLD format (no provenance)."""
    return {
        "book": {
            "title": "Test Book",
            "author": "Test Author"
        },
        "enrichment_metadata": {
            "generated": "2025-11-29T18:21:28.517610",
            "method": "statistical",
            "libraries": {
                "yake": "0.4.8",
                "sentence_transformers": "available"
            }
        },
        "chapters": [
            {
                "chapter_number": 1,
                "title": "Introduction",
                "keywords": ["test", "intro"],
                "concepts": ["testing"],
                "summary": "A test chapter"
            }
        ]
    }


@pytest.fixture
def sample_enriched_data_with_provenance() -> dict[str, Any]:
    """Sample enriched data with NEW provenance format."""
    return {
        "book": {
            "title": "Test Book",
            "author": "Test Author"
        },
        "enrichment_metadata": {
            "taxonomy_id": "ai-ml-2024",
            "taxonomy_version": "1.0.0",
            "taxonomy_path": "AI-ML_taxonomy_20251128.json",
            "taxonomy_checksum": "sha256:abc123def456",
            "source_metadata_file": "Test Book_metadata.json",
            "enrichment_date": "2025-12-15T12:00:00Z",
            "enrichment_method": "sentence_transformers",
            "model_version": "all-MiniLM-L6-v2"
        },
        "chapters": [
            {
                "chapter_number": 1,
                "title": "Introduction",
                "keywords": ["test", "intro"],
                "concepts": ["testing"],
                "summary": "A test chapter"
            }
        ]
    }


@pytest.fixture
def create_source_files(
    temp_source_dir: Path,
    sample_enriched_data: dict[str, Any]
) -> list[Path]:
    """Create sample source files with enriched data."""
    files = []
    book_titles = ["Test Book A", "Test Book B", "Test Book C"]
    
    for title in book_titles:
        data = sample_enriched_data.copy()
        data["book"] = {"title": title, "author": "Author"}
        
        file_path = temp_source_dir / f"{title}_enriched.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        files.append(file_path)
    
    return files


def _compute_sha256(file_path: Path) -> str:
    """Compute SHA256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


# =============================================================================
# Test Class: Source Path Validation (D3.1.3)
# =============================================================================

class TestSourcePathValidation:
    """WBS D3.1.3: Test source path validation."""

    def test_source_directory_must_exist(self, tmp_path: Path, temp_target_dir: Path) -> None:
        """Sync should raise error if source directory doesn't exist."""
        from scripts.sync_from_enhancer import sync_from_enhancer, SyncError
        
        non_existent = tmp_path / "does_not_exist"
        
        with pytest.raises(SyncError, match="Source directory does not exist"):
            sync_from_enhancer(non_existent, temp_target_dir)

    def test_source_directory_must_be_directory(
        self,
        tmp_path: Path,
        temp_target_dir: Path
    ) -> None:
        """Sync should raise error if source path is a file, not directory."""
        from scripts.sync_from_enhancer import sync_from_enhancer, SyncError
        
        file_path = tmp_path / "file.txt"
        file_path.write_text("not a directory")
        
        with pytest.raises(SyncError, match="Source path is not a directory"):
            sync_from_enhancer(file_path, temp_target_dir)

    def test_source_directory_must_contain_enriched_files(
        self,
        temp_source_dir: Path,
        temp_target_dir: Path
    ) -> None:
        """Sync should raise error if source contains no enriched files."""
        from scripts.sync_from_enhancer import sync_from_enhancer, SyncError
        
        # Empty directory (or only .gitkeep)
        (temp_source_dir / ".gitkeep").touch()
        
        with pytest.raises(SyncError, match="No enriched files found"):
            sync_from_enhancer(temp_source_dir, temp_target_dir)

    def test_target_directory_created_if_not_exists(
        self,
        temp_source_dir: Path,
        create_source_files: list[Path],
        tmp_path: Path
    ) -> None:
        """Sync should create target directory if it doesn't exist."""
        from scripts.sync_from_enhancer import sync_from_enhancer
        
        target_dir = tmp_path / "new_target"
        assert not target_dir.exists()
        
        sync_from_enhancer(temp_source_dir, target_dir)
        
        assert target_dir.exists()


# =============================================================================
# Test Class: File Renaming Logic (D3.1.4)
# =============================================================================

class TestFileRenamingLogic:
    """WBS D3.1.4: Test file renaming from _enriched.json to _metadata_enriched.json."""

    def test_files_renamed_with_metadata_suffix(
        self,
        temp_source_dir: Path,
        temp_target_dir: Path,
        create_source_files: list[Path]
    ) -> None:
        """Files should be renamed from _enriched.json to _metadata_enriched.json."""
        from scripts.sync_from_enhancer import sync_from_enhancer
        
        _report = sync_from_enhancer(temp_source_dir, temp_target_dir)
        
        # Verify target files have new naming convention
        target_files = list(temp_target_dir.glob("*_metadata_enriched.json"))
        assert len(target_files) == 3
        
        expected_names = {
            "Test Book A_metadata_enriched.json",
            "Test Book B_metadata_enriched.json",
            "Test Book C_metadata_enriched.json",
        }
        actual_names = {f.name for f in target_files}
        assert actual_names == expected_names

    def test_book_title_preserved_in_rename(
        self,
        temp_source_dir: Path,
        temp_target_dir: Path,
        sample_enriched_data: dict[str, Any]
    ) -> None:
        """Book title portion of filename should be preserved during rename."""
        from scripts.sync_from_enhancer import sync_from_enhancer
        
        # Create file with complex title
        title = "A Philosophy of Software Design"
        data = sample_enriched_data.copy()
        data["book"]["title"] = title
        
        source_file = temp_source_dir / f"{title}_enriched.json"
        with open(source_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
        
        sync_from_enhancer(temp_source_dir, temp_target_dir)
        
        expected_target = temp_target_dir / f"{title}_metadata_enriched.json"
        assert expected_target.exists()

    def test_source_files_not_modified(
        self,
        temp_source_dir: Path,
        temp_target_dir: Path,
        create_source_files: list[Path]
    ) -> None:
        """Sync should copy, not move - source files remain unchanged."""
        from scripts.sync_from_enhancer import sync_from_enhancer
        
        # Record original file count and names
        original_files = set(temp_source_dir.glob("*.json"))
        original_names = {f.name for f in original_files}
        
        sync_from_enhancer(temp_source_dir, temp_target_dir)
        
        # Source files should still exist with original names
        remaining_files = set(temp_source_dir.glob("*.json"))
        remaining_names = {f.name for f in remaining_files}
        
        assert remaining_names == original_names

    def test_skip_non_enriched_json_files(
        self,
        temp_source_dir: Path,
        temp_target_dir: Path,
        sample_enriched_data: dict[str, Any]
    ) -> None:
        """Sync should only process files matching *_enriched.json pattern.
        
        Files not matching the pattern (config.json, _metadata.json) are
        simply ignored - they don't appear in any count since they're not
        candidates for sync in the first place.
        """
        from scripts.sync_from_enhancer import sync_from_enhancer
        
        # Create valid enriched file
        valid_file = temp_source_dir / "Test Book_enriched.json"
        with open(valid_file, "w", encoding="utf-8") as f:
            json.dump(sample_enriched_data, f)
        
        # Create files that should be ignored (not matching *_enriched.json)
        (temp_source_dir / "config.json").write_text('{"key": "value"}')
        (temp_source_dir / "Test Book_metadata.json").write_text('{"key": "value"}')
        (temp_source_dir / ".gitkeep").touch()
        
        report = sync_from_enhancer(temp_source_dir, temp_target_dir)
        
        # Only one file should be synced - others are simply not candidates
        assert report.synced_count == 1
        # Non-matching files are not tracked at all (they're not enriched files)
        assert report.error_count == 0


# =============================================================================
# Test Class: JSON Validation (D3.1.3 extended)
# =============================================================================

class TestJsonValidation:
    """WBS D3.1.3: Test JSON validation during sync."""

    def test_invalid_json_raises_error(
        self,
        temp_source_dir: Path,
        temp_target_dir: Path
    ) -> None:
        """Sync should report error for invalid JSON files."""
        from scripts.sync_from_enhancer import sync_from_enhancer
        
        # Create invalid JSON file
        invalid_file = temp_source_dir / "Bad Book_enriched.json"
        invalid_file.write_text("{ not valid json }")
        
        report = sync_from_enhancer(temp_source_dir, temp_target_dir)
        
        assert report.error_count == 1
        assert "Bad Book" in report.errors[0].file_name
        assert "JSON" in report.errors[0].message or "json" in report.errors[0].message.lower()

    def test_missing_required_fields_logged(
        self,
        temp_source_dir: Path,
        temp_target_dir: Path
    ) -> None:
        """Sync should log warning for files missing enrichment_metadata."""
        from scripts.sync_from_enhancer import sync_from_enhancer
        
        # Create JSON without enrichment_metadata
        data = {"book": {"title": "Test"}, "chapters": []}
        file_path = temp_source_dir / "Incomplete Book_enriched.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        
        report = sync_from_enhancer(temp_source_dir, temp_target_dir)
        
        # Should sync but log warning
        assert report.synced_count == 1
        assert len(report.warnings) >= 1
        assert any("enrichment_metadata" in w.message for w in report.warnings)


# =============================================================================
# Test Class: Checksum Verification (D3.1.5)
# =============================================================================

class TestChecksumVerification:
    """WBS D3.1.5: Test checksum verification post-copy."""

    def test_checksum_matches_after_copy(
        self,
        temp_source_dir: Path,
        temp_target_dir: Path,
        sample_enriched_data: dict[str, Any]
    ) -> None:
        """Checksum of source and target files should match."""
        from scripts.sync_from_enhancer import sync_from_enhancer
        
        # Create source file
        source_file = temp_source_dir / "Test Book_enriched.json"
        with open(source_file, "w", encoding="utf-8") as f:
            json.dump(sample_enriched_data, f, indent=2)
        
        source_checksum = _compute_sha256(source_file)
        
        _report = sync_from_enhancer(temp_source_dir, temp_target_dir)
        
        # Target file checksum should match source
        target_file = temp_target_dir / "Test Book_metadata_enriched.json"
        target_checksum = _compute_sha256(target_file)
        
        assert source_checksum == target_checksum

    def test_checksum_included_in_report(
        self,
        temp_source_dir: Path,
        temp_target_dir: Path,
        create_source_files: list[Path]
    ) -> None:
        """Sync report should include checksum for each synced file."""
        from scripts.sync_from_enhancer import sync_from_enhancer
        
        report = sync_from_enhancer(temp_source_dir, temp_target_dir)
        
        assert len(report.synced_files) == 3
        for synced_file in report.synced_files:
            assert synced_file.source_checksum is not None
            assert synced_file.target_checksum is not None
            assert synced_file.source_checksum == synced_file.target_checksum
            assert len(synced_file.source_checksum) == 64  # SHA256 hex length

    def test_checksum_mismatch_raises_error(
        self,
        temp_source_dir: Path,
        temp_target_dir: Path,
        sample_enriched_data: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sync should raise error if checksum mismatch detected."""
        from scripts.sync_from_enhancer import sync_from_enhancer, SyncError
        
        # Create source file
        source_file = temp_source_dir / "Test Book_enriched.json"
        with open(source_file, "w", encoding="utf-8") as f:
            json.dump(sample_enriched_data, f)
        
        # Mock shutil.copy2 to corrupt the file during copy
        original_copy = shutil.copy2
        
        def corrupt_copy(src: Path, dst: Path) -> None:
            original_copy(src, dst)
            # Corrupt the target file
            with open(dst, "a", encoding="utf-8") as f:
                f.write("CORRUPTED")
        
        monkeypatch.setattr(shutil, "copy2", corrupt_copy)
        
        with pytest.raises(SyncError, match="[Cc]hecksum mismatch"):
            sync_from_enhancer(temp_source_dir, temp_target_dir)


# =============================================================================
# Test Class: Dry Run Mode (D3.1.6)
# =============================================================================

class TestDryRunMode:
    """WBS D3.1.6: Test --dry-run flag for preview mode."""

    def test_dry_run_does_not_create_files(
        self,
        temp_source_dir: Path,
        temp_target_dir: Path,
        create_source_files: list[Path]
    ) -> None:
        """Dry run should not create any files in target directory."""
        from scripts.sync_from_enhancer import sync_from_enhancer
        
        # Ensure target is empty
        target_files_before = list(temp_target_dir.glob("*.json"))
        assert len(target_files_before) == 0
        
        report = sync_from_enhancer(temp_source_dir, temp_target_dir, dry_run=True)
        
        # Target should still be empty
        target_files_after = list(temp_target_dir.glob("*.json"))
        assert len(target_files_after) == 0
        
        # But report should show what would be synced
        assert report.would_sync_count == 3

    def test_dry_run_returns_preview_report(
        self,
        temp_source_dir: Path,
        temp_target_dir: Path,
        create_source_files: list[Path]
    ) -> None:
        """Dry run should return report showing planned operations."""
        from scripts.sync_from_enhancer import sync_from_enhancer
        
        report = sync_from_enhancer(temp_source_dir, temp_target_dir, dry_run=True)
        
        assert report.dry_run is True
        assert report.would_sync_count == 3
        
        # Verify planned file names
        planned_names = {f.target_name for f in report.planned_files}
        expected_names = {
            "Test Book A_metadata_enriched.json",
            "Test Book B_metadata_enriched.json",
            "Test Book C_metadata_enriched.json",
        }
        assert planned_names == expected_names

    def test_dry_run_detects_existing_files(
        self,
        temp_source_dir: Path,
        temp_target_dir: Path,
        sample_enriched_data: dict[str, Any]
    ) -> None:
        """Dry run should report files that already exist in target."""
        from scripts.sync_from_enhancer import sync_from_enhancer
        
        # Create source file
        source_file = temp_source_dir / "Existing Book_enriched.json"
        with open(source_file, "w", encoding="utf-8") as f:
            json.dump(sample_enriched_data, f)
        
        # Create target file with same name (already migrated)
        target_file = temp_target_dir / "Existing Book_metadata_enriched.json"
        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(sample_enriched_data, f)
        
        report = sync_from_enhancer(temp_source_dir, temp_target_dir, dry_run=True)
        
        assert report.would_skip_count == 1
        assert any("already exists" in f.skip_reason for f in report.would_skip_files)


# =============================================================================
# Test Class: Sync Report Structure
# =============================================================================

class TestSyncReportStructure:
    """Test SyncReport dataclass structure and methods."""

    def test_sync_report_has_statistics(
        self,
        temp_source_dir: Path,
        temp_target_dir: Path,
        create_source_files: list[Path]
    ) -> None:
        """SyncReport should include summary statistics."""
        from scripts.sync_from_enhancer import sync_from_enhancer
        
        report = sync_from_enhancer(temp_source_dir, temp_target_dir)
        
        assert hasattr(report, "synced_count")
        assert hasattr(report, "skipped_count")
        assert hasattr(report, "error_count")
        assert hasattr(report, "total_bytes_copied")
        assert hasattr(report, "elapsed_seconds")
        
        assert report.synced_count == 3
        assert report.skipped_count == 0
        assert report.error_count == 0
        assert report.total_bytes_copied > 0
        assert report.elapsed_seconds >= 0

    def test_sync_report_to_dict(
        self,
        temp_source_dir: Path,
        temp_target_dir: Path,
        create_source_files: list[Path]
    ) -> None:
        """SyncReport should serialize to dictionary."""
        from scripts.sync_from_enhancer import sync_from_enhancer
        
        report = sync_from_enhancer(temp_source_dir, temp_target_dir)
        
        report_dict = report.to_dict()
        
        assert isinstance(report_dict, dict)
        assert "synced_count" in report_dict
        assert "synced_files" in report_dict
        assert isinstance(report_dict["synced_files"], list)


# =============================================================================
# Test Class: CLI Interface
# =============================================================================

class TestCliInterface:
    """Test CLI interface for sync_from_enhancer.py."""

    def test_cli_with_dry_run_flag(
        self,
        temp_source_dir: Path,
        temp_target_dir: Path,
        create_source_files: list[Path]
    ) -> None:
        """CLI should accept --dry-run flag."""
        from click.testing import CliRunner
        from scripts.sync_from_enhancer import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            "--source", str(temp_source_dir),
            "--target", str(temp_target_dir),
            "--dry-run"
        ])
        
        assert result.exit_code == 0
        assert "dry run" in result.output.lower() or "would sync" in result.output.lower()

    def test_cli_with_verbose_flag(
        self,
        temp_source_dir: Path,
        temp_target_dir: Path,
        create_source_files: list[Path]
    ) -> None:
        """CLI should accept --verbose flag for detailed output."""
        from click.testing import CliRunner
        from scripts.sync_from_enhancer import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, [
            "--source", str(temp_source_dir),
            "--target", str(temp_target_dir),
            "--verbose"
        ])
        
        assert result.exit_code == 0
        # Verbose should show individual file names
        assert "Test Book A" in result.output or "synced" in result.output.lower()

    def test_cli_missing_source_arg(self) -> None:
        """CLI should fail with clear error if source not provided."""
        from click.testing import CliRunner
        from scripts.sync_from_enhancer import cli
        
        runner = CliRunner()
        result = runner.invoke(cli, ["--target", "/some/path"])
        
        assert result.exit_code != 0

    def test_cli_default_paths(
        self,
        monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """CLI should have sensible default paths."""
        from scripts.sync_from_enhancer import DEFAULT_SOURCE_DIR, DEFAULT_TARGET_DIR
        
        # Verify defaults are defined
        assert DEFAULT_SOURCE_DIR is not None
        assert DEFAULT_TARGET_DIR is not None
        assert "llm-document-enhancer" in str(DEFAULT_SOURCE_DIR) or "output" in str(DEFAULT_SOURCE_DIR)
        assert "ai-platform-data" in str(DEFAULT_TARGET_DIR) or "enriched" in str(DEFAULT_TARGET_DIR)


# =============================================================================
# Test Class: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_enriched_file(
        self,
        temp_source_dir: Path,
        temp_target_dir: Path
    ) -> None:
        """Sync should handle empty JSON files gracefully."""
        from scripts.sync_from_enhancer import sync_from_enhancer
        
        # Create empty file
        empty_file = temp_source_dir / "Empty Book_enriched.json"
        empty_file.write_text("")
        
        report = sync_from_enhancer(temp_source_dir, temp_target_dir)
        
        assert report.error_count == 1
        assert "Empty Book" in report.errors[0].file_name

    def test_permission_error_handling(
        self,
        temp_source_dir: Path,
        temp_target_dir: Path,
        sample_enriched_data: dict[str, Any],
        monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sync should handle permission errors gracefully."""
        from scripts.sync_from_enhancer import sync_from_enhancer
        
        # Create source file
        source_file = temp_source_dir / "Test Book_enriched.json"
        with open(source_file, "w", encoding="utf-8") as f:
            json.dump(sample_enriched_data, f)
        
        # Mock copy to raise permission error
        def raise_permission_error(*_args: Any, **_kwargs: Any) -> None:
            raise PermissionError("Access denied")
        
        monkeypatch.setattr(shutil, "copy2", raise_permission_error)
        
        report = sync_from_enhancer(temp_source_dir, temp_target_dir)
        
        assert report.error_count == 1
        assert "permission" in report.errors[0].message.lower() or "access" in report.errors[0].message.lower()

    def test_unicode_in_book_title(
        self,
        temp_source_dir: Path,
        temp_target_dir: Path,
        sample_enriched_data: dict[str, Any]
    ) -> None:
        """Sync should handle Unicode characters in book titles."""
        from scripts.sync_from_enhancer import sync_from_enhancer
        
        # Create file with Unicode in title
        unicode_title = "Bücher über Programmierung"
        data = sample_enriched_data.copy()
        data["book"]["title"] = unicode_title
        
        source_file = temp_source_dir / f"{unicode_title}_enriched.json"
        with open(source_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
        
        report = sync_from_enhancer(temp_source_dir, temp_target_dir)
        
        assert report.synced_count == 1
        expected_target = temp_target_dir / f"{unicode_title}_metadata_enriched.json"
        assert expected_target.exists()

    def test_very_long_book_title(
        self,
        temp_source_dir: Path,
        temp_target_dir: Path,
        sample_enriched_data: dict[str, Any]
    ) -> None:
        """Sync should handle very long book titles (filesystem limit aware)."""
        from scripts.sync_from_enhancer import sync_from_enhancer
        
        # Create file with long title (but within reasonable filesystem limits)
        long_title = "A" * 100  # 100 chars + suffix should still be valid
        data = sample_enriched_data.copy()
        data["book"]["title"] = long_title
        
        source_file = temp_source_dir / f"{long_title}_enriched.json"
        with open(source_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
        
        report = sync_from_enhancer(temp_source_dir, temp_target_dir)
        
        assert report.synced_count == 1
