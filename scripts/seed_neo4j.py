"""Seed Neo4j database with books, chapters, and tier relationships.

Phase 3.1: Seeding Pipeline - GREEN phase implementation.
WBS Tasks: 3.1.2 (seed_neo4j.py)

This script seeds Neo4j with:
1. Constraints and indexes from init-scripts/
2. Book nodes from books/metadata/
3. Chapter nodes linked to Books
4. Tier nodes from taxonomy
5. Tier relationships (PARALLEL, PERPENDICULAR, SKIP_TIER)

Anti-Pattern Audit:
- Per Issue #12: Uses connection pooling (single driver instance)
- Per Issue #9-11: No race conditions (single-threaded seeding)
- Per Category 1.1: All functions have type annotations
- Per S1192: String literals extracted to constants
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress

if TYPE_CHECKING:
    from neo4j import Driver

console = Console()
logger = logging.getLogger(__name__)

# Constants per CODING_PATTERNS_ANALYSIS.md S1192
DEFAULT_BOOKS_PATH = Path(__file__).parent.parent / "books"
DEFAULT_TAXONOMIES_PATH = Path(__file__).parent.parent / "taxonomies"
DEFAULT_INIT_SCRIPTS_PATH = Path(__file__).parent.parent / "docker" / "neo4j" / "init-scripts"


@dataclass
class SeedingConfig:
    """Configuration for Neo4j seeding.
    
    Per Issue #2.2: Use dataclass instead of long parameter lists.
    """
    
    books_path: Path = field(default_factory=lambda: DEFAULT_BOOKS_PATH)
    taxonomies_path: Path = field(default_factory=lambda: DEFAULT_TAXONOMIES_PATH)
    init_scripts_path: Path = field(default_factory=lambda: DEFAULT_INIT_SCRIPTS_PATH)
    apply_constraints: bool = True
    verbose: bool = False


@dataclass
class SeedingStats:
    """Statistics from seeding operations."""
    
    constraints_applied: int = 0
    indexes_applied: int = 0
    books_seeded: int = 0
    chapters_seeded: int = 0
    tiers_seeded: int = 0
    relationships_seeded: int = 0


def get_neo4j_driver() -> Driver:
    """Create Neo4j driver from environment configuration.
    
    Per Issue #12: Single driver instance with connection pooling.
    """
    from neo4j import GraphDatabase

    load_dotenv()

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    auth_str = os.getenv("NEO4J_AUTH", "neo4j/password")
    
    # Handle auth string parsing safely
    if "/" in auth_str:
        user, password = auth_str.split("/", 1)
    else:
        user, password = "neo4j", auth_str

    return GraphDatabase.driver(uri, auth=(user, password))


def seed_books(driver: Driver, books_path: Path) -> int:
    """Seed Book nodes from metadata files."""
    count = 0
    metadata_path = books_path / "metadata"

    if not metadata_path.exists():
        logger.warning(f"Metadata path does not exist: {metadata_path}")
        return count

    with driver.session() as session:
        for file_path in metadata_path.glob("*.json"):
            with open(file_path) as f:
                book = json.load(f)

            session.run(
                """
                MERGE (b:Book {book_id: $book_id})
                SET b.title = $title,
                    b.author = $author,
                    b.tier = $tier
                """,
                book_id=book.get("book_id"),
                title=book.get("title"),
                author=book.get("author"),
                tier=book.get("tier"),
            )
            count += 1

    return count


def seed_chapters(driver: Driver, books_path: Path) -> int:
    """Seed Chapter nodes and connect to Books."""
    count = 0
    metadata_path = books_path / "metadata"

    if not metadata_path.exists():
        return count

    with driver.session() as session:
        for file_path in metadata_path.glob("*.json"):
            with open(file_path) as f:
                book = json.load(f)

            book_id = book.get("book_id")
            chapters = book.get("chapters", [])

            for chapter in chapters:
                session.run(
                    """
                    MERGE (c:Chapter {chapter_id: $chapter_id})
                    SET c.title = $title,
                        c.number = $number
                    WITH c
                    MATCH (b:Book {book_id: $book_id})
                    MERGE (b)-[:HAS_CHAPTER]->(c)
                    """,
                    chapter_id=chapter.get("chapter_id"),
                    title=chapter.get("title"),
                    number=chapter.get("number"),
                    book_id=book_id,
                )
                count += 1

    return count


def apply_cypher_scripts(driver: Driver, init_scripts_path: Path) -> tuple[int, int]:
    """Apply Cypher scripts for constraints and indexes.
    
    Returns tuple of (constraints_applied, indexes_applied).
    """
    constraints = 0
    indexes = 0
    
    if not init_scripts_path.exists():
        logger.warning(f"Init scripts path does not exist: {init_scripts_path}")
        return constraints, indexes
    
    # Sort files to ensure execution order (01_, 02_, etc.)
    script_files = sorted(init_scripts_path.glob("*.cypher"))
    
    with driver.session() as session:
        for script_file in script_files:
            with open(script_file) as f:
                content = f.read()
            
            # Parse and execute each statement
            # Remove comments and split by semicolon
            statements = parse_cypher_statements(content)
            
            for statement in statements:
                statement = statement.strip()
                if not statement:
                    continue
                
                try:
                    session.run(statement)
                    
                    # Track what was applied
                    if "CONSTRAINT" in statement.upper():
                        constraints += 1
                    elif "INDEX" in statement.upper():
                        indexes += 1
                        
                except Exception as e:
                    # Constraints/indexes may already exist
                    if "already exists" in str(e).lower():
                        logger.debug(f"Already exists: {statement[:50]}...")
                    else:
                        logger.warning(f"Failed to execute: {statement[:50]}... Error: {e}")
    
    return constraints, indexes


def parse_cypher_statements(content: str) -> list[str]:
    """Parse Cypher script content into individual statements.
    
    Handles comments and multi-line statements.
    """
    # Remove single-line comments
    content = re.sub(r"//.*$", "", content, flags=re.MULTILINE)
    
    # Split by semicolon
    statements = content.split(";")
    
    # Clean up whitespace
    return [s.strip() for s in statements if s.strip()]


def seed_tier_nodes(driver: Driver) -> int:
    """Seed Tier nodes (T0-T5) per TIER_RELATIONSHIP_DIAGRAM.md.
    
    Tier Structure:
    - T0: Domain (highest level)
    - T1: Theory/Foundations
    - T2: Practice/Implementation
    - T3: Application/Integration
    - T4: Advanced/Specialized
    - T5: Reference/Supplementary
    """
    tier_definitions = [
        {"name": "T0", "level": 0, "description": "Domain - Highest level concepts"},
        {"name": "T1", "level": 1, "description": "Theory and Foundations"},
        {"name": "T2", "level": 2, "description": "Practice and Implementation"},
        {"name": "T3", "level": 3, "description": "Application and Integration"},
        {"name": "T4", "level": 4, "description": "Advanced and Specialized"},
        {"name": "T5", "level": 5, "description": "Reference and Supplementary"},
    ]
    
    count = 0
    
    with driver.session() as session:
        for tier in tier_definitions:
            session.run(
                """
                MERGE (t:Tier {name: $name})
                SET t.level = $level,
                    t.description = $description
                """,
                name=tier["name"],
                level=tier["level"],
                description=tier["description"],
            )
            count += 1
    
    return count


def seed_tier_relationships(driver: Driver, taxonomies_path: Path) -> int:
    """Seed tier relationships (PARALLEL, PERPENDICULAR, SKIP_TIER).
    
    Per TIER_RELATIONSHIP_DIAGRAM.md:
    - PARALLEL: Same tier (horizontal)
    - PERPENDICULAR: Adjacent tier ±1 (vertical)
    - SKIP_TIER: Non-adjacent tier ±2+ (diagonal)
    """
    count = 0
    
    # First, create PARALLEL relationships between books at same tier
    with driver.session() as session:
        # PARALLEL: Same tier books
        result = session.run("""
            MATCH (a:Book), (b:Book)
            WHERE a.tier = b.tier 
              AND a.book_id < b.book_id  // Avoid duplicates
              AND a.tier IS NOT NULL
            MERGE (a)-[:PARALLEL]->(b)
            MERGE (b)-[:PARALLEL]->(a)
            RETURN count(*) as count
        """)
        record = result.single()
        if record:
            count += record["count"]
        
        # PERPENDICULAR: Adjacent tier books (tier diff = 1)
        result = session.run("""
            MATCH (a:Book), (b:Book)
            WHERE abs(a.tier - b.tier) = 1
              AND a.book_id < b.book_id
              AND a.tier IS NOT NULL
              AND b.tier IS NOT NULL
            MERGE (a)-[:PERPENDICULAR]->(b)
            MERGE (b)-[:PERPENDICULAR]->(a)
            RETURN count(*) as count
        """)
        record = result.single()
        if record:
            count += record["count"]
        
        # SKIP_TIER: Non-adjacent tier books (tier diff >= 2)
        result = session.run("""
            MATCH (a:Book), (b:Book)
            WHERE abs(a.tier - b.tier) >= 2
              AND a.book_id < b.book_id
              AND a.tier IS NOT NULL
              AND b.tier IS NOT NULL
            MERGE (a)-[:SKIP_TIER]->(b)
            MERGE (b)-[:SKIP_TIER]->(a)
            RETURN count(*) as count
        """)
        record = result.single()
        if record:
            count += record["count"]
    
    return count


def seed_all(config: SeedingConfig) -> SeedingStats:
    """Execute full Neo4j seeding pipeline.
    
    Per Issue #9-11: Single-threaded to avoid race conditions.
    """
    stats = SeedingStats()
    driver = get_neo4j_driver()
    
    try:
        # Step 1: Apply constraints and indexes
        if config.apply_constraints:
            constraints, indexes = apply_cypher_scripts(driver, config.init_scripts_path)
            stats.constraints_applied = constraints
            stats.indexes_applied = indexes
        
        # Step 2: Seed Tier nodes
        stats.tiers_seeded = seed_tier_nodes(driver)
        
        # Step 3: Seed Books
        stats.books_seeded = seed_books(driver, config.books_path)
        
        # Step 4: Seed Chapters
        stats.chapters_seeded = seed_chapters(driver, config.books_path)
        
        # Step 5: Seed tier relationships
        stats.relationships_seeded = seed_tier_relationships(driver, config.taxonomies_path)
        
    finally:
        driver.close()
    
    return stats


@click.command()
@click.option(
    "--books-path",
    type=click.Path(path_type=Path),
    default=DEFAULT_BOOKS_PATH,
    help="Path to books directory",
)
@click.option(
    "--taxonomies-path",
    type=click.Path(path_type=Path),
    default=DEFAULT_TAXONOMIES_PATH,
    help="Path to taxonomies directory",
)
@click.option(
    "--init-scripts-path",
    type=click.Path(path_type=Path),
    default=DEFAULT_INIT_SCRIPTS_PATH,
    help="Path to Neo4j init scripts",
)
@click.option(
    "--skip-constraints",
    is_flag=True,
    default=False,
    help="Skip applying constraints and indexes",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Enable verbose output",
)
def main(
    books_path: Path,
    taxonomies_path: Path,
    init_scripts_path: Path,
    skip_constraints: bool,
    verbose: bool,
) -> None:
    """Seed Neo4j database with books, chapters, and tier relationships."""
    config = SeedingConfig(
        books_path=books_path,
        taxonomies_path=taxonomies_path,
        init_scripts_path=init_scripts_path,
        apply_constraints=not skip_constraints,
        verbose=verbose,
    )
    
    console.print("\n[bold blue]Seeding Neo4j database...[/bold blue]\n")
    
    with Progress() as progress:
        task = progress.add_task("[green]Seeding...", total=5)
        
        driver = get_neo4j_driver()
        
        try:
            # Step 1: Apply constraints and indexes
            if config.apply_constraints:
                constraints, indexes = apply_cypher_scripts(driver, config.init_scripts_path)
                console.print(f"  ✓ Applied {constraints} constraints, {indexes} indexes")
            progress.update(task, advance=1)
            
            # Step 2: Seed Tier nodes
            tier_count = seed_tier_nodes(driver)
            console.print(f"  ✓ Seeded {tier_count} tier nodes")
            progress.update(task, advance=1)
            
            # Step 3: Seed Books
            book_count = seed_books(driver, config.books_path)
            console.print(f"  ✓ Seeded {book_count} books")
            progress.update(task, advance=1)
            
            # Step 4: Seed Chapters
            chapter_count = seed_chapters(driver, config.books_path)
            console.print(f"  ✓ Seeded {chapter_count} chapters")
            progress.update(task, advance=1)
            
            # Step 5: Seed tier relationships
            rel_count = seed_tier_relationships(driver, config.taxonomies_path)
            console.print(f"  ✓ Created {rel_count} tier relationships")
            progress.update(task, advance=1)
            
        finally:
            driver.close()
    
    console.print("\n[bold green]Neo4j seeding complete![/bold green]")


if __name__ == "__main__":
    main()
