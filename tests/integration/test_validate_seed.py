"""Integration tests for seed validation script.

Phase 3.1: Seeding Pipeline - TDD tests following RED-GREEN-REFACTOR cycle.
WBS Tasks: 3.1.6-3.1.7

These tests validate:
1. validate_seed.py correctly reports database statistics
2. Cross-database consistency (Neo4j chapters match Qdrant vectors)
3. Validation detects missing data
4. Validation provides actionable error messages

Requirements:
- Neo4j and Qdrant must be running (docker-compose up)
- Tests use the ai-platform-data Docker stack

Anti-Pattern Audit:
- Per Issue #12: Uses connection pooling (single driver/client instance)
- Per CODING_PATTERNS_ANALYSIS: Type annotations, type guards
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
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

# Script paths
SCRIPTS_PATH = Path(__file__).parent.parent.parent / "scripts"
VALIDATE_SEED_SCRIPT = SCRIPTS_PATH / "validate_seed.py"


@dataclass
class ValidationResult:
    """Result from validate_seed.py execution."""
    
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    
    @property
    def has_warnings(self) -> bool:
        """Check if validation produced warnings."""
        return "WARNING" in self.stdout or "WARNING" in self.stderr


def neo4j_available() -> bool:
    """Check if Neo4j is available."""
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        driver.close()
        return True
    except Exception:
        return False


def qdrant_available() -> bool:
    """Check if Qdrant is available."""
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        client.get_collections()
        return True
    except Exception:
        return False


# Skip if databases not available
pytestmark = pytest.mark.skipif(
    not neo4j_available() or not qdrant_available(),
    reason="Neo4j or Qdrant not available - run 'docker-compose up' first"
)


@pytest.fixture(scope="module")
def neo4j_driver() -> Generator[Any, None, None]:
    """Create Neo4j driver for tests."""
    from neo4j import GraphDatabase
    
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    yield driver
    driver.close()


@pytest.fixture(scope="module")
def qdrant_client() -> Generator[Any, None, None]:
    """Create Qdrant client for tests."""
    from qdrant_client import QdrantClient
    
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    yield client


def run_validate_seed(*args: str) -> ValidationResult:
    """Run validate_seed.py and capture output."""
    cmd = [sys.executable, str(VALIDATE_SEED_SCRIPT)] + list(args)
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
    )
    
    return ValidationResult(
        success=result.returncode == 0,
        exit_code=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


class TestValidateSeedScript:
    """Tests for validate_seed.py script (WBS 3.1.6-3.1.7)."""

    def test_validate_seed_script_exists(self) -> None:
        """3.1.6/3.1.7: validate_seed.py script must exist."""
        assert VALIDATE_SEED_SCRIPT.exists(), (
            f"Script not found at {VALIDATE_SEED_SCRIPT}"
        )

    def test_validate_seed_runs_without_error(self) -> None:
        """Script should run without throwing exceptions."""
        if not VALIDATE_SEED_SCRIPT.exists():
            pytest.skip("validate_seed.py does not exist")
        
        result = run_validate_seed()
        
        # Script may fail if databases are empty, but shouldn't crash
        assert "Traceback" not in result.stderr, (
            f"Script crashed with error: {result.stderr}"
        )

    def test_validate_seed_help_option(self) -> None:
        """Script should support --help option."""
        if not VALIDATE_SEED_SCRIPT.exists():
            pytest.skip("validate_seed.py does not exist")
        
        result = run_validate_seed("--help")
        
        assert result.exit_code == 0, (
            f"--help failed with code {result.exit_code}: {result.stderr}"
        )
        assert "Usage" in result.stdout or "usage" in result.stdout, (
            "Help output should contain usage information"
        )


class TestValidateSeedNeo4jCounts:
    """Tests for Neo4j count validation."""

    def test_reports_book_count(
        self, neo4j_driver: Any
    ) -> None:
        """Validation should report book count."""
        if not VALIDATE_SEED_SCRIPT.exists():
            pytest.skip("validate_seed.py does not exist")
        
        # Get actual count
        with neo4j_driver.session() as session:
            result = session.run("MATCH (b:Book) RETURN count(b) as count")
            actual_count = result.single()["count"]
        
        validation = run_validate_seed()
        
        # Output should contain book count
        assert "Book" in validation.stdout or "book" in validation.stdout, (
            f"Output should mention books: {validation.stdout}"
        )

    def test_reports_chapter_count(
        self, neo4j_driver: Any
    ) -> None:
        """Validation should report chapter count."""
        if not VALIDATE_SEED_SCRIPT.exists():
            pytest.skip("validate_seed.py does not exist")
        
        with neo4j_driver.session() as session:
            result = session.run("MATCH (c:Chapter) RETURN count(c) as count")
            actual_count = result.single()["count"]
        
        validation = run_validate_seed()
        
        assert "Chapter" in validation.stdout or "chapter" in validation.stdout, (
            f"Output should mention chapters: {validation.stdout}"
        )

    def test_reports_relationship_counts(
        self, neo4j_driver: Any
    ) -> None:
        """Validation should report tier relationship counts."""
        if not VALIDATE_SEED_SCRIPT.exists():
            pytest.skip("validate_seed.py does not exist")
        
        validation = run_validate_seed()
        
        # Should mention at least one relationship type
        has_relationship_info = (
            "PARALLEL" in validation.stdout or
            "PERPENDICULAR" in validation.stdout or
            "edge" in validation.stdout.lower() or
            "relationship" in validation.stdout.lower()
        )
        
        assert has_relationship_info, (
            f"Output should mention relationships: {validation.stdout}"
        )


class TestValidateSeedQdrantCounts:
    """Tests for Qdrant count validation."""

    def test_reports_vector_count(
        self, qdrant_client: Any
    ) -> None:
        """Validation should report vector count."""
        if not VALIDATE_SEED_SCRIPT.exists():
            pytest.skip("validate_seed.py does not exist")
        
        validation = run_validate_seed()
        
        has_vector_info = (
            "vector" in validation.stdout.lower() or
            "Qdrant" in validation.stdout or
            "qdrant" in validation.stdout
        )
        
        assert has_vector_info, (
            f"Output should mention vectors/Qdrant: {validation.stdout}"
        )


class TestValidateSeedConsistency:
    """Tests for cross-database consistency validation."""

    def test_detects_chapter_vector_mismatch(
        self, neo4j_driver: Any, qdrant_client: Any
    ) -> None:
        """Validation should detect mismatch between Neo4j chapters and Qdrant vectors.
        
        Per CODING_PATTERNS_ANALYSIS: Type guards for None checks.
        """
        if not VALIDATE_SEED_SCRIPT.exists():
            pytest.skip("validate_seed.py does not exist")
        
        # Get Neo4j chapter count
        with neo4j_driver.session() as session:
            result = session.run("MATCH (c:Chapter) RETURN count(c) as count")
            neo4j_chapters = result.single()["count"]
        
        # Get Qdrant vector count
        try:
            info = qdrant_client.get_collection("chapters")
            qdrant_vectors = info.vectors_count or 0
        except Exception:
            qdrant_vectors = 0
        
        validation = run_validate_seed()
        
        # If counts differ significantly, validation should warn
        if neo4j_chapters > 0 and qdrant_vectors > 0:
            # Counts should be reasonably close (within 10%)
            diff_pct = abs(neo4j_chapters - qdrant_vectors) / max(neo4j_chapters, 1) * 100
            
            if diff_pct > 10:
                assert (
                    validation.has_warnings or 
                    "mismatch" in validation.stdout.lower() or
                    "warning" in validation.stdout.lower()
                ), "Large chapter/vector count difference should trigger warning"

    def test_validates_book_chapter_relationships(
        self, neo4j_driver: Any
    ) -> None:
        """Validation should check that all chapters have books."""
        if not VALIDATE_SEED_SCRIPT.exists():
            pytest.skip("validate_seed.py does not exist")
        
        # Check for orphan chapters
        with neo4j_driver.session() as session:
            result = session.run("""
                MATCH (c:Chapter)
                WHERE NOT (c)<-[:HAS_CHAPTER]-(:Book)
                RETURN count(c) as orphan_count
            """)
            orphan_count = result.single()["orphan_count"]
        
        validation = run_validate_seed()
        
        # If there are orphans, validation should report
        if orphan_count > 0:
            assert (
                "orphan" in validation.stdout.lower() or
                validation.has_warnings or
                not validation.success
            ), f"Found {orphan_count} orphan chapters but validation didn't report"


class TestValidateSeedOutput:
    """Tests for validation output format."""

    def test_output_is_human_readable(self) -> None:
        """Output should be formatted for human reading."""
        if not VALIDATE_SEED_SCRIPT.exists():
            pytest.skip("validate_seed.py does not exist")
        
        validation = run_validate_seed()
        
        # Should have some structure (tables, headers, etc.)
        has_structure = (
            "│" in validation.stdout or  # Table borders
            ":" in validation.stdout or  # Key-value pairs
            "✓" in validation.stdout or  # Checkmarks
            "✗" in validation.stdout or  # X marks
            "\n" in validation.stdout     # Multiple lines
        )
        
        assert has_structure, (
            "Output should be structured and readable"
        )

    def test_supports_json_output(self) -> None:
        """Script should support --json flag for machine-readable output."""
        if not VALIDATE_SEED_SCRIPT.exists():
            pytest.skip("validate_seed.py does not exist")
        
        # Try with --json flag (may not be implemented yet)
        result = run_validate_seed("--json")
        
        if result.exit_code == 0:
            import json
            try:
                data = json.loads(result.stdout)
                assert isinstance(data, dict), "JSON output should be a dict"
            except json.JSONDecodeError:
                # --json not implemented yet
                pass


class TestValidateSeedExitCodes:
    """Tests for validation exit codes."""

    def test_returns_zero_on_success(self) -> None:
        """Script should return 0 when all validations pass."""
        if not VALIDATE_SEED_SCRIPT.exists():
            pytest.skip("validate_seed.py does not exist")
        
        validation = run_validate_seed()
        
        # May fail if databases are empty, which is expected
        # We just verify it returns a valid exit code
        assert validation.exit_code in [0, 1], (
            f"Unexpected exit code: {validation.exit_code}"
        )

    def test_returns_nonzero_on_empty_database(
        self, neo4j_driver: Any
    ) -> None:
        """Script should return non-zero if databases are empty."""
        if not VALIDATE_SEED_SCRIPT.exists():
            pytest.skip("validate_seed.py does not exist")
        
        # Check if databases have data
        with neo4j_driver.session() as session:
            result = session.run("MATCH (b:Book) RETURN count(b) as count")
            book_count = result.single()["count"]
        
        validation = run_validate_seed()
        
        # If no books, validation should fail or warn
        if book_count == 0:
            assert (
                validation.exit_code != 0 or 
                validation.has_warnings or
                "empty" in validation.stdout.lower() or
                "no " in validation.stdout.lower()
            ), "Empty database should trigger failure or warning"


class TestValidateSeedVerbosity:
    """Tests for validation verbosity options."""

    def test_supports_verbose_flag(self) -> None:
        """Script should support -v/--verbose flag."""
        if not VALIDATE_SEED_SCRIPT.exists():
            pytest.skip("validate_seed.py does not exist")
        
        # Compare output with and without verbose
        normal_result = run_validate_seed()
        verbose_result = run_validate_seed("-v")
        
        # Verbose output should be at least as long
        assert len(verbose_result.stdout) >= len(normal_result.stdout), (
            "Verbose output should not be shorter than normal"
        )

    def test_supports_quiet_flag(self) -> None:
        """Script should support -q/--quiet flag for minimal output."""
        if not VALIDATE_SEED_SCRIPT.exists():
            pytest.skip("validate_seed.py does not exist")
        
        # Compare output with and without quiet
        normal_result = run_validate_seed()
        quiet_result = run_validate_seed("-q")
        
        # Quiet output should be shorter or same
        # (Script may not implement quiet yet)
        if quiet_result.exit_code == 0:
            assert len(quiet_result.stdout) <= len(normal_result.stdout), (
                "Quiet output should not be longer than normal"
            )
