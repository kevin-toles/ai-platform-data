"""Pytest configuration and fixtures for ai-platform-data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Generator

import pytest


# ============================================================================
# Path Fixtures
# ============================================================================


@pytest.fixture
def project_root() -> Path:
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def books_raw_dir(project_root: Path) -> Path:
    """Return the books/raw directory."""
    return project_root / "books" / "raw"


@pytest.fixture
def books_metadata_dir(project_root: Path) -> Path:
    """Return the books/metadata directory."""
    return project_root / "books" / "metadata"


@pytest.fixture
def taxonomies_dir(project_root: Path) -> Path:
    """Return the taxonomies directory."""
    return project_root / "taxonomies"


@pytest.fixture
def schemas_dir(project_root: Path) -> Path:
    """Return the schemas directory."""
    return project_root / "schemas"


# ============================================================================
# Sample Data Fixtures
# ============================================================================


@pytest.fixture
def sample_book_metadata() -> dict[str, Any]:
    """Return sample book metadata for testing."""
    return {
        "id": "test-book-001",
        "title": "Test Book",
        "author": "Test Author",
        "publisher": "Test Publisher",
        "year": 2024,
        "isbn": "978-0-000-00000-0",
        "tier": "Tier_1_Foundational",
        "domain": "software-engineering",
        "chapters": [
            {
                "number": 1,
                "title": "Introduction",
                "summary": "Introduction to testing",
            },
        ],
    }


@pytest.fixture
def sample_taxonomy() -> dict[str, Any]:
    """Return sample taxonomy for testing."""
    return {
        "name": "Test Taxonomy",
        "version": "1.0.0",
        "domains": [
            {
                "id": "test-domain",
                "name": "Test Domain",
                "description": "A domain for testing",
                "subdomains": [],
            },
        ],
    }


# ============================================================================
# Temp File Fixtures
# ============================================================================


@pytest.fixture
def temp_json_file(tmp_path: Path) -> Generator[tuple[Path, Any], None, None]:
    """Create a temporary JSON file for testing.

    Yields:
        Tuple of (file_path, data_dict)
    """
    data = {"test": "data", "nested": {"key": "value"}}
    file_path = tmp_path / "test.json"

    with open(file_path, "w") as f:
        json.dump(data, f)

    yield file_path, data


# ============================================================================
# Database Fixtures (for integration tests)
# ============================================================================


@pytest.fixture
def neo4j_connection_params() -> dict[str, str]:
    """Return Neo4j connection parameters for testing."""
    return {
        "uri": "bolt://localhost:7687",
        "user": "neo4j",
        "password": "pantry_test",
    }


@pytest.fixture
def qdrant_connection_params() -> dict[str, Any]:
    """Return Qdrant connection parameters for testing."""
    return {
        "host": "localhost",
        "port": 6333,
    }


# ============================================================================
# Markers
# ============================================================================


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (deselect with '-m \"not integration\"')",
    )
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    )
    config.addinivalue_line(
        "markers",
        "requires_neo4j: marks tests requiring Neo4j connection",
    )
    config.addinivalue_line(
        "markers",
        "requires_qdrant: marks tests requiring Qdrant connection",
    )
