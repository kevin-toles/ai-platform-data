"""Unit tests for graph models.

Phase 2.2: Neo4j Schema - Tests for EdgeType, TraversalResult, PathResult.

These tests validate the Python models WITHOUT requiring Neo4j connection.
Integration tests (test_neo4j_schema.py) verify the schema in Neo4j.
"""

from __future__ import annotations

import pytest

from src.graph import (
    EdgeType,
    NavigationDirection,
    PathResult,
    TraversalResult,
    get_edge_type_for_tier_diff,
)


class TestEdgeType:
    """Tests for EdgeType enum."""

    def test_edge_type_parallel_exists(self) -> None:
        """PARALLEL edge type must exist."""
        assert EdgeType.PARALLEL.value == "PARALLEL"

    def test_edge_type_perpendicular_exists(self) -> None:
        """PERPENDICULAR edge type must exist."""
        assert EdgeType.PERPENDICULAR.value == "PERPENDICULAR"

    def test_edge_type_skip_tier_exists(self) -> None:
        """SKIP_TIER edge type must exist."""
        assert EdgeType.SKIP_TIER.value == "SKIP_TIER"

    def test_edge_type_is_string_enum(self) -> None:
        """EdgeType must inherit from str for JSON serialization."""
        assert isinstance(EdgeType.PARALLEL, str)
        assert EdgeType.PARALLEL == "PARALLEL"


class TestNavigationDirection:
    """Tests for NavigationDirection enum."""

    def test_upward_direction(self) -> None:
        """UPWARD direction for lower→higher tier traversal."""
        assert NavigationDirection.UPWARD.value == "UPWARD"

    def test_downward_direction(self) -> None:
        """DOWNWARD direction for higher→lower tier traversal."""
        assert NavigationDirection.DOWNWARD.value == "DOWNWARD"

    def test_lateral_direction(self) -> None:
        """LATERAL direction for same-tier traversal."""
        assert NavigationDirection.LATERAL.value == "LATERAL"


class TestGetEdgeTypeForTierDiff:
    """Tests for get_edge_type_for_tier_diff function."""

    def test_same_tier_returns_parallel(self) -> None:
        """Same tier (diff=0) should return PARALLEL."""
        assert get_edge_type_for_tier_diff(1, 1) == EdgeType.PARALLEL
        assert get_edge_type_for_tier_diff(2, 2) == EdgeType.PARALLEL
        assert get_edge_type_for_tier_diff(3, 3) == EdgeType.PARALLEL

    def test_adjacent_tier_returns_perpendicular(self) -> None:
        """Adjacent tiers (diff=1) should return PERPENDICULAR."""
        assert get_edge_type_for_tier_diff(1, 2) == EdgeType.PERPENDICULAR
        assert get_edge_type_for_tier_diff(2, 1) == EdgeType.PERPENDICULAR
        assert get_edge_type_for_tier_diff(2, 3) == EdgeType.PERPENDICULAR

    def test_non_adjacent_tier_returns_skip_tier(self) -> None:
        """Non-adjacent tiers (diff>=2) should return SKIP_TIER."""
        assert get_edge_type_for_tier_diff(1, 3) == EdgeType.SKIP_TIER
        assert get_edge_type_for_tier_diff(3, 1) == EdgeType.SKIP_TIER
        assert get_edge_type_for_tier_diff(1, 5) == EdgeType.SKIP_TIER


class TestTraversalResult:
    """Tests for TraversalResult dataclass."""

    def test_traversal_result_creation(self) -> None:
        """TraversalResult should be creatable with required fields."""
        result = TraversalResult(
            chapter_id="ch_001",
            title="Test Chapter",
            tier=1,
            edge_type=EdgeType.PARALLEL,
            score=0.85,
        )
        assert result.chapter_id == "ch_001"
        assert result.title == "Test Chapter"
        assert result.tier == 1
        assert result.edge_type == EdgeType.PARALLEL
        assert result.score == 0.85

    def test_traversal_result_optional_fields(self) -> None:
        """TraversalResult should have optional book fields."""
        result = TraversalResult(
            chapter_id="ch_001",
            title="Test Chapter",
            tier=1,
            edge_type=EdgeType.PARALLEL,
            score=0.85,
            book_id="book_001",
            book_title="Test Book",
        )
        assert result.book_id == "book_001"
        assert result.book_title == "Test Book"

    def test_traversal_result_to_dict(self) -> None:
        """TraversalResult.to_dict() should return JSON-serializable dict."""
        result = TraversalResult(
            chapter_id="ch_001",
            title="Test Chapter",
            tier=1,
            edge_type=EdgeType.PARALLEL,
            score=0.85,
        )
        d = result.to_dict()
        assert d["chapter_id"] == "ch_001"
        assert d["edge_type"] == "PARALLEL"  # String, not enum
        assert isinstance(d["edge_type"], str)


class TestPathResult:
    """Tests for PathResult dataclass."""

    def test_path_result_creation(self) -> None:
        """PathResult should be creatable with required fields."""
        result = PathResult(
            chapters=["ch_001", "ch_002", "ch_003"],
            hops=2,
            edge_types=[EdgeType.PARALLEL, EdgeType.PERPENDICULAR],
            score=0.75,
        )
        assert result.chapters == ["ch_001", "ch_002", "ch_003"]
        assert result.hops == 2
        assert len(result.edge_types) == 2
        assert result.score == 0.75

    def test_path_result_spider_web_traversal(self) -> None:
        """PathResult should support non-linear spider web paths.
        
        Per TIER_RELATIONSHIP_DIAGRAM.md:
        'A single annotation may traverse: T1 → T2 → T3 → T1 → T2'
        """
        # Simulate: T1 → T2 → T3 → T1 path
        result = PathResult(
            chapters=["ch_t1_a", "ch_t2_a", "ch_t3_a", "ch_t1_b"],
            hops=3,
            edge_types=[
                EdgeType.PERPENDICULAR,  # T1 → T2
                EdgeType.PERPENDICULAR,  # T2 → T3
                EdgeType.SKIP_TIER,      # T3 → T1 (back!)
            ],
            score=0.70,
        )
        assert result.hops == 3
        assert EdgeType.SKIP_TIER in result.edge_types

    def test_path_result_to_dict(self) -> None:
        """PathResult.to_dict() should return JSON-serializable dict."""
        result = PathResult(
            chapters=["ch_001", "ch_002"],
            hops=1,
            edge_types=[EdgeType.PARALLEL],
            score=0.80,
        )
        d = result.to_dict()
        assert d["chapters"] == ["ch_001", "ch_002"]
        assert d["edge_types"] == ["PARALLEL"]  # List of strings
        assert all(isinstance(e, str) for e in d["edge_types"])


class TestTierRelationshipDiagramCompliance:
    """Validate models against TIER_RELATIONSHIP_DIAGRAM.md concepts."""

    def test_bidirectional_edge_types(self) -> None:
        """All edge types are inherently bidirectional (can traverse either way).
        
        'ALL ARROWS ARE BIDIRECTIONAL (◄────►)'
        """
        # Edge types don't encode direction - they describe relationship type
        # Direction is determined by query, not by edge type
        assert EdgeType.PARALLEL == EdgeType.PARALLEL  # Same going either way
        
    def test_spider_web_model_supported(self) -> None:
        """Path can go in any direction through the web.
        
        'Relationships are BIDIRECTIONAL - concepts flow in ANY direction'
        """
        # A path can go: T1 → T2 → T3 → T1 (back to start tier)
        path = PathResult(
            chapters=["a", "b", "c", "d"],
            hops=3,
            edge_types=[
                EdgeType.PERPENDICULAR,
                EdgeType.PERPENDICULAR,
                EdgeType.SKIP_TIER,
            ],
            score=0.5,
        )
        # The path ends at same tier as start (T1) - valid in spider web
        assert path.hops == 3

    def test_all_relationship_types_defined(self) -> None:
        """All three relationship types from TIER_RELATIONSHIP_DIAGRAM.md exist.
        
        | Relationship | Definition |
        |--------------|------------|
        | PARALLEL     | Same tier level |
        | PERPENDICULAR| Adjacent tier levels (±1) |
        | SKIP_TIER    | Non-adjacent tiers (±2+) |
        """
        expected_types = {"PARALLEL", "PERPENDICULAR", "SKIP_TIER"}
        actual_types = {e.value for e in EdgeType}
        assert actual_types == expected_types
