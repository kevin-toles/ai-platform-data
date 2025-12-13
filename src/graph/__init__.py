"""Graph models for Neo4j schema.

Phase 2.2: Neo4j Schema - Domain models for graph traversal.

Per TIER_RELATIONSHIP_DIAGRAM.md:
- All relationships are BIDIRECTIONAL (spider web model)
- Traversal can go in ANY direction (T1 → T2 → T3 → T1 → T2)
- Skip-tier connections are valid (direct T1 ↔ T3)

Anti-Pattern Audit:
- Per CODING_PATTERNS_ANALYSIS: Type annotations on all functions
- Per Issue #6: No duplicate class definitions
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class EdgeType(str, Enum):
    """Tier relationship types per TIER_RELATIONSHIP_DIAGRAM.md.
    
    All relationships are BIDIRECTIONAL - the graph is a spider web, not a tree.
    
    Relationship Types:
        PARALLEL: Same tier level (horizontal traversal)
            - Use: Compare complementary approaches at same abstraction level
            - Example: Python Distilled (T1) ↔ Philosophy of SW Design (T1)
        
        PERPENDICULAR: Adjacent tier levels ±1 (vertical traversal)
            - Use: Bridge theory to implementation (or vice versa)
            - Example: Python Distilled (T1) ↔ Clean Code (T2)
        
        SKIP_TIER: Non-adjacent tiers ±2+ (diagonal traversal)
            - Use: Connect foundational concepts directly to operational patterns
            - Example: Python Distilled (T1) ↔ Microservices Patterns (T3)
    """
    PARALLEL = "PARALLEL"
    PERPENDICULAR = "PERPENDICULAR"
    SKIP_TIER = "SKIP_TIER"


class NavigationDirection(str, Enum):
    """Navigation directions for bidirectional traversal.
    
    Per TIER_RELATIONSHIP_DIAGRAM.md, all traversals work in both directions.
    """
    UPWARD = "UPWARD"      # Lower tier → Higher tier (e.g., T3 → T1)
    DOWNWARD = "DOWNWARD"  # Higher tier → Lower tier (e.g., T1 → T3)
    LATERAL = "LATERAL"    # Same tier (PARALLEL relationships)


@dataclass
class TraversalResult:
    """Result from a graph traversal operation.
    
    Fields:
        chapter_id: Unique identifier for the chapter
        title: Chapter title
        tier: Tier level (1, 2, or 3)
        edge_type: Type of relationship used to reach this node
        score: Relevance score (0.0 to 1.0)
        book_id: Parent book identifier
        book_title: Parent book title
    """
    chapter_id: str
    title: str
    tier: int
    edge_type: EdgeType
    score: float
    book_id: str | None = None
    book_title: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "chapter_id": self.chapter_id,
            "title": self.title,
            "tier": self.tier,
            "edge_type": self.edge_type.value,
            "score": self.score,
            "book_id": self.book_id,
            "book_title": self.book_title,
        }


@dataclass
class PathResult:
    """Result from a multi-hop path finding operation.
    
    Per TIER_RELATIONSHIP_DIAGRAM.md, paths can traverse:
    'T1 → T2 → T3 → T1 → T2' (non-linear, web-like)
    
    Fields:
        chapters: List of chapter IDs in path order
        hops: Number of relationship traversals
        edge_types: List of edge types used in order
        score: Combined relevance score
    """
    chapters: list[str]
    hops: int
    edge_types: list[EdgeType]
    score: float
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "chapters": self.chapters,
            "hops": self.hops,
            "edge_types": [e.value for e in self.edge_types],
            "score": self.score,
        }


def get_edge_type_for_tier_diff(tier1: int, tier2: int) -> EdgeType:
    """Determine the appropriate edge type based on tier difference.
    
    Args:
        tier1: Source tier level
        tier2: Target tier level
    
    Returns:
        EdgeType appropriate for the tier difference:
        - PARALLEL if same tier
        - PERPENDICULAR if adjacent (diff = 1)
        - SKIP_TIER if non-adjacent (diff >= 2)
    
    Examples:
        >>> get_edge_type_for_tier_diff(1, 1)
        <EdgeType.PARALLEL: 'PARALLEL'>
        >>> get_edge_type_for_tier_diff(1, 2)
        <EdgeType.PERPENDICULAR: 'PERPENDICULAR'>
        >>> get_edge_type_for_tier_diff(1, 3)
        <EdgeType.SKIP_TIER: 'SKIP_TIER'>
    """
    diff = abs(tier1 - tier2)
    if diff == 0:
        return EdgeType.PARALLEL
    elif diff == 1:
        return EdgeType.PERPENDICULAR
    else:
        return EdgeType.SKIP_TIER
