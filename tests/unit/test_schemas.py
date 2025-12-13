"""Unit tests for JSON schema validation.

This module tests all JSON schemas in the schemas/ directory:
- book_raw.schema.json: Raw book content structure
- book_metadata.schema.json: Book metadata with enriched fields
- book_enriched.schema.json: Fully enriched book with embeddings
- taxonomy.schema.json: Domain taxonomy structure

TDD RED Phase: These tests are written BEFORE the schemas exist.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft7Validator, ValidationError

# ============================================================================
# Schema Loading Fixtures
# ============================================================================


@pytest.fixture
def load_schema(schemas_dir: Path) -> Any:
    """Factory fixture to load a schema by name.

    Args:
        schemas_dir: Path to schemas directory (from conftest).

    Returns:
        Function that loads a schema given its filename.
    """
    def _load(schema_name: str) -> dict[str, Any]:
        schema_path = schemas_dir / schema_name
        if not schema_path.exists():
            pytest.fail(f"Schema file does not exist: {schema_path}")
        with open(schema_path, encoding="utf-8") as f:
            return json.load(f)
    return _load


def validate_data(schema: dict[str, Any], data: dict[str, Any]) -> bool:
    """Validate data against a JSON schema.

    Args:
        schema: JSON schema dictionary.
        data: Data to validate.

    Returns:
        True if validation passes.

    Raises:
        ValidationError: If validation fails.
    """
    Draft7Validator.check_schema(schema)  # Ensure schema itself is valid
    validator = Draft7Validator(schema)
    validator.validate(data)
    return True


# ============================================================================
# Task 1.3.1 - book_raw.schema.json Tests (RED)
# ============================================================================


class TestBookRawSchema:
    """Tests for book_raw.schema.json - raw book content from textbooks."""

    def test_schema_exists(self, schemas_dir: Path) -> None:
        """Schema file must exist."""
        schema_path = schemas_dir / "book_raw.schema.json"
        assert schema_path.exists(), f"book_raw.schema.json not found at {schema_path}"

    def test_schema_is_valid_json_schema(self, load_schema: Any) -> None:
        """Schema must be a valid JSON Schema draft-07."""
        schema = load_schema("book_raw.schema.json")
        # This will raise if schema is invalid
        Draft7Validator.check_schema(schema)

    def test_valid_raw_book_minimal(self, load_schema: Any) -> None:
        """Minimal valid raw book should pass validation."""
        schema = load_schema("book_raw.schema.json")
        valid_data = {
            "title": "Test Book",
            "author": "Test Author",
            "chapters": []
        }
        assert validate_data(schema, valid_data)

    def test_valid_raw_book_with_chapters(self, load_schema: Any) -> None:
        """Raw book with chapters should pass validation."""
        schema = load_schema("book_raw.schema.json")
        valid_data = {
            "title": "AI Engineering",
            "author": "Chip Huyen",
            "chapters": [
                {
                    "chapter_number": 1,
                    "title": "Introduction",
                    "content": "Foundation models are models trained..."
                },
                {
                    "chapter_number": 2,
                    "title": "Building Blocks",
                    "content": "This chapter covers the building blocks..."
                }
            ]
        }
        assert validate_data(schema, valid_data)

    def test_invalid_missing_title(self, load_schema: Any) -> None:
        """Book without title should fail validation."""
        schema = load_schema("book_raw.schema.json")
        invalid_data = {
            "author": "Test Author",
            "chapters": []
        }
        with pytest.raises(ValidationError) as exc_info:
            validate_data(schema, invalid_data)
        assert "title" in str(exc_info.value)

    def test_invalid_missing_author(self, load_schema: Any) -> None:
        """Book without author should fail validation."""
        schema = load_schema("book_raw.schema.json")
        invalid_data = {
            "title": "Test Book",
            "chapters": []
        }
        with pytest.raises(ValidationError) as exc_info:
            validate_data(schema, invalid_data)
        assert "author" in str(exc_info.value)

    def test_invalid_chapter_missing_number(self, load_schema: Any) -> None:
        """Chapter without chapter_number should fail validation."""
        schema = load_schema("book_raw.schema.json")
        invalid_data = {
            "title": "Test Book",
            "author": "Test Author",
            "chapters": [
                {
                    "title": "Introduction",
                    "content": "Content here"
                }
            ]
        }
        with pytest.raises(ValidationError) as exc_info:
            validate_data(schema, invalid_data)
        assert "chapter_number" in str(exc_info.value)

    def test_invalid_chapter_number_type(self, load_schema: Any) -> None:
        """Chapter with non-integer chapter_number should fail validation."""
        schema = load_schema("book_raw.schema.json")
        invalid_data = {
            "title": "Test Book",
            "author": "Test Author",
            "chapters": [
                {
                    "chapter_number": "one",  # Should be integer
                    "title": "Introduction",
                    "content": "Content here"
                }
            ]
        }
        with pytest.raises(ValidationError):
            validate_data(schema, invalid_data)


# ============================================================================
# Task 1.3.3 - book_metadata.schema.json Tests (RED)
# ============================================================================


class TestBookMetadataSchema:
    """Tests for book_metadata.schema.json - book metadata with tier info."""

    def test_schema_exists(self, schemas_dir: Path) -> None:
        """Schema file must exist."""
        schema_path = schemas_dir / "book_metadata.schema.json"
        assert schema_path.exists(), f"book_metadata.schema.json not found at {schema_path}"

    def test_schema_is_valid_json_schema(self, load_schema: Any) -> None:
        """Schema must be a valid JSON Schema draft-07."""
        schema = load_schema("book_metadata.schema.json")
        Draft7Validator.check_schema(schema)

    def test_valid_metadata_minimal(self, load_schema: Any) -> None:
        """Minimal valid metadata should pass validation."""
        schema = load_schema("book_metadata.schema.json")
        valid_data = {
            "id": "ai-engineering-001",
            "title": "AI Engineering",
            "author": "Chip Huyen",
            "tier": "architecture"
        }
        assert validate_data(schema, valid_data)

    def test_valid_metadata_full(self, load_schema: Any) -> None:
        """Full metadata with all fields should pass validation."""
        schema = load_schema("book_metadata.schema.json")
        valid_data = {
            "id": "ai-engineering-001",
            "title": "AI Engineering",
            "author": "Chip Huyen",
            "publisher": "O'Reilly Media",
            "year": 2025,
            "isbn": "978-1-098-16664-5",
            "tier": "architecture",
            "priority": 1,
            "domains": ["ai-ml", "software-engineering"],
            "concepts": ["foundation-models", "llm", "mlops"],
            "chapters": [
                {
                    "number": 1,
                    "title": "Introduction",
                    "summary": "Introduction to AI engineering"
                }
            ]
        }
        assert validate_data(schema, valid_data)

    def test_invalid_missing_id(self, load_schema: Any) -> None:
        """Metadata without id should fail validation."""
        schema = load_schema("book_metadata.schema.json")
        invalid_data = {
            "title": "AI Engineering",
            "author": "Chip Huyen",
            "tier": "architecture"
        }
        with pytest.raises(ValidationError) as exc_info:
            validate_data(schema, invalid_data)
        assert "id" in str(exc_info.value)

    def test_invalid_missing_tier(self, load_schema: Any) -> None:
        """Metadata without tier should fail validation."""
        schema = load_schema("book_metadata.schema.json")
        invalid_data = {
            "id": "ai-engineering-001",
            "title": "AI Engineering",
            "author": "Chip Huyen"
        }
        with pytest.raises(ValidationError) as exc_info:
            validate_data(schema, invalid_data)
        assert "tier" in str(exc_info.value)

    def test_invalid_year_not_integer(self, load_schema: Any) -> None:
        """Year as string should fail validation."""
        schema = load_schema("book_metadata.schema.json")
        invalid_data = {
            "id": "ai-engineering-001",
            "title": "AI Engineering",
            "author": "Chip Huyen",
            "tier": "architecture",
            "year": "2025"  # Should be integer
        }
        with pytest.raises(ValidationError):
            validate_data(schema, invalid_data)

    def test_invalid_priority_out_of_range(self, load_schema: Any) -> None:
        """Priority outside 1-10 range should fail validation."""
        schema = load_schema("book_metadata.schema.json")
        invalid_data = {
            "id": "ai-engineering-001",
            "title": "AI Engineering",
            "author": "Chip Huyen",
            "tier": "architecture",
            "priority": 0  # Should be 1-10
        }
        with pytest.raises(ValidationError):
            validate_data(schema, invalid_data)


# ============================================================================
# Task 1.3.5 - book_enriched.schema.json Tests (RED)
# ============================================================================


class TestBookEnrichedSchema:
    """Tests for book_enriched.schema.json - fully enriched book with embeddings."""

    def test_schema_exists(self, schemas_dir: Path) -> None:
        """Schema file must exist."""
        schema_path = schemas_dir / "book_enriched.schema.json"
        assert schema_path.exists(), f"book_enriched.schema.json not found at {schema_path}"

    def test_schema_is_valid_json_schema(self, load_schema: Any) -> None:
        """Schema must be a valid JSON Schema draft-07."""
        schema = load_schema("book_enriched.schema.json")
        Draft7Validator.check_schema(schema)

    def test_valid_enriched_minimal(self, load_schema: Any) -> None:
        """Minimal valid enriched book should pass validation."""
        schema = load_schema("book_enriched.schema.json")
        valid_data = {
            "id": "ai-engineering-001",
            "metadata": {
                "title": "AI Engineering",
                "author": "Chip Huyen",
                "tier": "architecture"
            },
            "embeddings": {
                "model": "sentence-transformers/all-MiniLM-L6-v2",
                "dimensions": 384
            }
        }
        assert validate_data(schema, valid_data)

    def test_valid_enriched_full(self, load_schema: Any) -> None:
        """Full enriched book with all fields should pass validation."""
        schema = load_schema("book_enriched.schema.json")
        valid_data = {
            "id": "ai-engineering-001",
            "metadata": {
                "title": "AI Engineering",
                "author": "Chip Huyen",
                "tier": "architecture",
                "domains": ["ai-ml"],
                "concepts": ["foundation-models"]
            },
            "embeddings": {
                "model": "sentence-transformers/all-MiniLM-L6-v2",
                "dimensions": 384,
                "created_at": "2024-12-01T00:00:00Z"
            },
            "graph": {
                "neo4j_node_id": "book_001",
                "relationships": ["BELONGS_TO_TIER", "HAS_CONCEPT"]
            },
            "vector_store": {
                "qdrant_collection": "books",
                "point_ids": ["point_001", "point_002"]
            }
        }
        assert validate_data(schema, valid_data)

    def test_invalid_missing_embeddings(self, load_schema: Any) -> None:
        """Enriched book without embeddings should fail validation."""
        schema = load_schema("book_enriched.schema.json")
        invalid_data = {
            "id": "ai-engineering-001",
            "metadata": {
                "title": "AI Engineering",
                "author": "Chip Huyen",
                "tier": "architecture"
            }
        }
        with pytest.raises(ValidationError) as exc_info:
            validate_data(schema, invalid_data)
        assert "embeddings" in str(exc_info.value)

    def test_invalid_embeddings_missing_model(self, load_schema: Any) -> None:
        """Embeddings without model should fail validation."""
        schema = load_schema("book_enriched.schema.json")
        invalid_data = {
            "id": "ai-engineering-001",
            "metadata": {
                "title": "AI Engineering",
                "author": "Chip Huyen",
                "tier": "architecture"
            },
            "embeddings": {
                "dimensions": 384
            }
        }
        with pytest.raises(ValidationError) as exc_info:
            validate_data(schema, invalid_data)
        assert "model" in str(exc_info.value)

    def test_invalid_dimensions_not_positive(self, load_schema: Any) -> None:
        """Dimensions <= 0 should fail validation."""
        schema = load_schema("book_enriched.schema.json")
        invalid_data = {
            "id": "ai-engineering-001",
            "metadata": {
                "title": "AI Engineering",
                "author": "Chip Huyen",
                "tier": "architecture"
            },
            "embeddings": {
                "model": "sentence-transformers/all-MiniLM-L6-v2",
                "dimensions": 0  # Should be > 0
            }
        }
        with pytest.raises(ValidationError):
            validate_data(schema, invalid_data)


# ============================================================================
# Task 1.3.7 - taxonomy.schema.json Tests (RED)
# ============================================================================


class TestTaxonomySchema:
    """Tests for taxonomy.schema.json - domain taxonomy structure."""

    def test_schema_exists(self, schemas_dir: Path) -> None:
        """Schema file must exist."""
        schema_path = schemas_dir / "taxonomy.schema.json"
        assert schema_path.exists(), f"taxonomy.schema.json not found at {schema_path}"

    def test_schema_is_valid_json_schema(self, load_schema: Any) -> None:
        """Schema must be a valid JSON Schema draft-07."""
        schema = load_schema("taxonomy.schema.json")
        Draft7Validator.check_schema(schema)

    def test_valid_taxonomy_minimal(self, load_schema: Any) -> None:
        """Minimal valid taxonomy should pass validation."""
        schema = load_schema("taxonomy.schema.json")
        valid_data = {
            "name": "AI-ML Taxonomy",
            "version": "1.0.0",
            "tiers": []
        }
        assert validate_data(schema, valid_data)

    def test_valid_taxonomy_full(self, load_schema: Any) -> None:
        """Full taxonomy with tiers and books should pass validation."""
        schema = load_schema("taxonomy.schema.json")
        valid_data = {
            "name": "AI-ML Taxonomy",
            "version": "1.0.0",
            "description": "Taxonomy for AI and ML domain",
            "tiers": [
                {
                    "name": "architecture",
                    "priority": 1,
                    "description": "System design and architecture patterns",
                    "concepts": ["design-patterns", "microservices", "event-driven"],
                    "books": [
                        {
                            "id": "ai-engineering-001",
                            "title": "AI Engineering"
                        }
                    ]
                },
                {
                    "name": "implementation",
                    "priority": 2,
                    "description": "Implementation patterns",
                    "concepts": ["python", "fastapi", "pytest"],
                    "books": []
                }
            ],
            "relationships": [
                {
                    "type": "PARALLEL",
                    "source": "architecture",
                    "target": "implementation"
                }
            ]
        }
        assert validate_data(schema, valid_data)

    def test_invalid_missing_name(self, load_schema: Any) -> None:
        """Taxonomy without name should fail validation."""
        schema = load_schema("taxonomy.schema.json")
        invalid_data = {
            "version": "1.0.0",
            "tiers": []
        }
        with pytest.raises(ValidationError) as exc_info:
            validate_data(schema, invalid_data)
        assert "name" in str(exc_info.value)

    def test_invalid_missing_version(self, load_schema: Any) -> None:
        """Taxonomy without version should fail validation."""
        schema = load_schema("taxonomy.schema.json")
        invalid_data = {
            "name": "AI-ML Taxonomy",
            "tiers": []
        }
        with pytest.raises(ValidationError) as exc_info:
            validate_data(schema, invalid_data)
        assert "version" in str(exc_info.value)

    def test_invalid_tier_missing_name(self, load_schema: Any) -> None:
        """Tier without name should fail validation."""
        schema = load_schema("taxonomy.schema.json")
        invalid_data = {
            "name": "AI-ML Taxonomy",
            "version": "1.0.0",
            "tiers": [
                {
                    "priority": 1,
                    "concepts": []
                }
            ]
        }
        with pytest.raises(ValidationError) as exc_info:
            validate_data(schema, invalid_data)
        assert "name" in str(exc_info.value)

    def test_invalid_tier_priority_not_positive(self, load_schema: Any) -> None:
        """Tier priority <= 0 should fail validation."""
        schema = load_schema("taxonomy.schema.json")
        invalid_data = {
            "name": "AI-ML Taxonomy",
            "version": "1.0.0",
            "tiers": [
                {
                    "name": "architecture",
                    "priority": 0,  # Should be > 0
                    "concepts": []
                }
            ]
        }
        with pytest.raises(ValidationError):
            validate_data(schema, invalid_data)

    def test_invalid_relationship_missing_type(self, load_schema: Any) -> None:
        """Relationship without type should fail validation."""
        schema = load_schema("taxonomy.schema.json")
        invalid_data = {
            "name": "AI-ML Taxonomy",
            "version": "1.0.0",
            "tiers": [],
            "relationships": [
                {
                    "source": "architecture",
                    "target": "implementation"
                }
            ]
        }
        with pytest.raises(ValidationError) as exc_info:
            validate_data(schema, invalid_data)
        assert "type" in str(exc_info.value)
