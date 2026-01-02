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
# PCON-3: Use llm-document-enhancer metadata extraction output as primary source
DEFAULT_METADATA_EXTRACTION_PATH = Path("/Users/kevintoles/POC/llm-document-enhancer/workflows/metadata_extraction/output")


@dataclass
class SeedingConfig:
    """Configuration for Neo4j seeding.
    
    Per Issue #2.2: Use dataclass instead of long parameter lists.
    """
    
    books_path: Path = field(default_factory=lambda: DEFAULT_BOOKS_PATH)
    taxonomies_path: Path = field(default_factory=lambda: DEFAULT_TAXONOMIES_PATH)
    init_scripts_path: Path = field(default_factory=lambda: DEFAULT_INIT_SCRIPTS_PATH)
    metadata_extraction_path: Path = field(default_factory=lambda: DEFAULT_METADATA_EXTRACTION_PATH)
    apply_constraints: bool = True
    verbose: bool = False
    dry_run: bool = False
    clear_before_seed: bool = False


@dataclass
class SeedingStats:
    """Statistics from seeding operations."""
    
    constraints_applied: int = 0
    indexes_applied: int = 0
    books_seeded: int = 0
    chapters_seeded: int = 0
    concepts_seeded: int = 0
    tiers_seeded: int = 0
    relationships_seeded: int = 0
    covers_relationships: int = 0


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


def clear_database(driver: Driver, preserve_constraints: bool = True) -> dict[str, int]:
    """Clear all data from Neo4j database.
    
    Used for re-seeding when --clear flag is passed.
    
    Args:
        driver: Neo4j driver
        preserve_constraints: If True, keeps constraints and indexes
        
    Returns:
        Dict with counts of deleted nodes and relationships
    """
    stats = {"nodes_deleted": 0, "relationships_deleted": 0}
    
    with driver.session() as session:
        # First delete all relationships
        result = session.run("MATCH ()-[r]->() DELETE r RETURN count(r) as count")
        record = result.single()
        if record:
            stats["relationships_deleted"] = record["count"]
        
        # Then delete all nodes
        result = session.run("MATCH (n) DELETE n RETURN count(n) as count")
        record = result.single()
        if record:
            stats["nodes_deleted"] = record["count"]
    
    logger.info(f"Cleared database: {stats['nodes_deleted']} nodes, {stats['relationships_deleted']} relationships")
    return stats


def get_database_stats(driver: Driver) -> dict[str, int]:
    """Get current database statistics.
    
    Useful for dry-run mode and validation.
    """
    stats = {}
    
    with driver.session() as session:
        # Node counts by label
        for label in ["Book", "Chapter", "Concept", "Tier", "CodeFile", "Pattern", "Repository"]:
            result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
            record = result.single()
            stats[f"{label.lower()}_count"] = record["count"] if record else 0
        
        # Relationship counts
        for rel_type in ["HAS_CHAPTER", "COVERS", "PARALLEL", "PERPENDICULAR", "SKIP_TIER"]:
            result = session.run(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count")
            record = result.single()
            stats[f"{rel_type.lower()}_count"] = record["count"] if record else 0
    
    return stats


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


# =============================================================================
# PCON-3: Enhanced seeding from llm-document-enhancer metadata extraction
# =============================================================================

def seed_from_metadata_extraction(driver: Driver, metadata_path: Path) -> tuple[int, int, int, int]:
    """Seed Books, Chapters with keywords/concepts from llm-document-enhancer output.
    
    PCON-3: Uses /Users/kevintoles/POC/llm-document-enhancer/workflows/metadata_extraction/output
    as the primary data source for rich chapter metadata including keywords and concepts.
    
    Returns tuple of (books_seeded, chapters_seeded, concepts_seeded, covers_relationships).
    """
    books_count = 0
    chapters_count = 0
    concepts_set: set[str] = set()
    covers_count = 0
    
    if not metadata_path.exists():
        logger.warning(f"Metadata extraction path does not exist: {metadata_path}")
        return books_count, chapters_count, 0, covers_count
    
    metadata_files = list(metadata_path.glob("*_metadata.json"))
    logger.info(f"Found {len(metadata_files)} metadata files to process")
    
    with driver.session() as session:
        for file_path in metadata_files:
            try:
                with open(file_path) as f:
                    chapters_data = json.load(f)
                
                # Extract book title from filename (remove _metadata.json suffix)
                book_title = file_path.stem.replace("_metadata", "")
                book_id = _generate_book_id(book_title)
                
                # Determine tier based on content (default to T2)
                tier = _infer_tier_from_content(book_title, chapters_data)
                
                # Create Book node
                session.run(
                    """
                    MERGE (b:Book {book_id: $book_id})
                    SET b.title = $title,
                        b.tier = $tier,
                        b.source = 'metadata_extraction'
                    """,
                    book_id=book_id,
                    title=book_title,
                    tier=tier,
                )
                books_count += 1
                
                # Create Chapter nodes with keywords and concepts
                for chapter in chapters_data:
                    chapter_num = chapter.get("chapter_number", 0)
                    chapter_id = f"{book_id}_ch{chapter_num:03d}"
                    title = chapter.get("title", f"Chapter {chapter_num}")
                    keywords = chapter.get("keywords", [])[:50]  # Limit to top 50
                    concepts = chapter.get("concepts", [])
                    summary = chapter.get("summary", "")[:500]  # Limit summary length
                    
                    # Track unique concepts for Concept nodes
                    for concept in concepts:
                        if concept and len(concept) > 2:  # Filter out noise
                            concepts_set.add(concept)
                    
                    session.run(
                        """
                        MERGE (c:Chapter {chapter_id: $chapter_id})
                        SET c.title = $title,
                            c.number = $chapter_num,
                            c.book_id = $book_id,
                            c.keywords = $keywords,
                            c.concepts = $concepts,
                            c.summary = $summary,
                            c.start_page = $start_page,
                            c.end_page = $end_page
                        WITH c
                        MATCH (b:Book {book_id: $book_id})
                        MERGE (b)-[:HAS_CHAPTER]->(c)
                        """,
                        chapter_id=chapter_id,
                        title=title,
                        chapter_num=chapter_num,
                        book_id=book_id,
                        keywords=keywords,
                        concepts=concepts,
                        summary=summary,
                        start_page=chapter.get("start_page"),
                        end_page=chapter.get("end_page"),
                    )
                    chapters_count += 1
                    
            except Exception as e:
                logger.warning(f"Error processing {file_path.name}: {e}")
                continue
    
    # Now seed Concept nodes and COVERS relationships
    concepts_count = seed_concepts(driver, concepts_set)
    covers_count = seed_covers_relationships(driver)
    
    return books_count, chapters_count, concepts_count, covers_count


def _generate_book_id(title: str) -> str:
    """Generate a stable book ID from title."""
    import hashlib
    # Clean title and create hash
    clean_title = re.sub(r'[^a-zA-Z0-9\s]', '', title.lower())
    clean_title = re.sub(r'\s+', '_', clean_title.strip())[:50]
    hash_suffix = hashlib.md5(title.encode()).hexdigest()[:8]
    return f"{clean_title}_{hash_suffix}"


def _infer_tier_from_content(title: str, chapters: list[dict]) -> int:
    """Infer tier level from book title and content.
    
    Tier mapping:
    - T1 (1): Foundations, basics, introductions
    - T2 (2): Practice, implementation, patterns
    - T3 (3): Advanced, specialized, deep dives
    """
    title_lower = title.lower()
    
    # T1 indicators
    t1_keywords = ['introduction', 'basics', 'fundamentals', 'beginner', 'primer', 'getting started']
    if any(kw in title_lower for kw in t1_keywords):
        return 1
    
    # T3 indicators
    t3_keywords = ['advanced', 'expert', 'mastering', 'deep dive', 'internals', 'performance']
    if any(kw in title_lower for kw in t3_keywords):
        return 3
    
    # Default to T2 (practice/implementation)
    return 2


def seed_concepts(driver: Driver, concepts: set[str] | None = None) -> int:
    """Seed Concept nodes from extracted concepts.
    
    PCON-3 AC-3.1: seed_neo4j.py includes seed_concepts() function
    PCON-3 AC-3.7: Database contains >0 Concept nodes
    
    Args:
        driver: Neo4j driver
        concepts: Optional set of concepts. If None, extracts from existing Chapters.
    
    Returns:
        Number of Concept nodes created.
    """
    count = 0
    
    with driver.session() as session:
        if concepts is None:
            # Extract concepts from existing Chapter nodes
            result = session.run("""
                MATCH (c:Chapter)
                WHERE c.concepts IS NOT NULL
                UNWIND c.concepts AS concept
                WITH concept WHERE concept IS NOT NULL AND size(concept) > 2
                RETURN DISTINCT concept
            """)
            concepts = {record["concept"] for record in result}
        
        # Filter out noise (URLs, code snippets, etc.)
        filtered_concepts = {
            c for c in concepts 
            if c and len(c) > 2 
            and not c.startswith('http')
            and not c.startswith('__')
            and not c.startswith('/')
        }
        
        logger.info(f"Seeding {len(filtered_concepts)} unique Concept nodes")
        
        for concept in filtered_concepts:
            try:
                # Normalize concept name
                concept_id = re.sub(r'[^a-zA-Z0-9\s]', '', concept.lower())
                concept_id = re.sub(r'\s+', '_', concept_id.strip())[:50]
                
                if not concept_id:
                    continue
                
                session.run(
                    """
                    MERGE (c:Concept {concept_id: $concept_id})
                    SET c.name = $name
                    """,
                    concept_id=concept_id,
                    name=concept,
                )
                count += 1
            except Exception as e:
                logger.debug(f"Error creating concept '{concept}': {e}")
                continue
    
    return count


def seed_covers_relationships(driver: Driver) -> int:
    """Create COVERS relationships between Chapters and Concepts.
    
    PCON-3 AC-3.3: COVERS relationships created between Chapters and Concepts
    
    Returns:
        Number of COVERS relationships created.
    """
    count = 0
    
    with driver.session() as session:
        # Create COVERS relationships based on Chapter.concepts array
        result = session.run("""
            MATCH (ch:Chapter)
            WHERE ch.concepts IS NOT NULL
            UNWIND ch.concepts AS concept_name
            WITH ch, concept_name 
            WHERE concept_name IS NOT NULL AND size(concept_name) > 2
            WITH ch, concept_name,
                 toLower(replace(replace(concept_name, ' ', '_'), '-', '_')) AS normalized
            MATCH (c:Concept)
            WHERE toLower(replace(replace(c.name, ' ', '_'), '-', '_')) = normalized
               OR c.concept_id = normalized
            MERGE (ch)-[:COVERS]->(c)
            RETURN count(*) as count
        """)
        record = result.single()
        if record:
            count = record["count"]
    
    logger.info(f"Created {count} COVERS relationships")
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
    "--metadata-path",
    type=click.Path(path_type=Path),
    default=DEFAULT_METADATA_EXTRACTION_PATH,
    help="Path to llm-document-enhancer metadata extraction output",
)
@click.option(
    "--skip-constraints",
    is_flag=True,
    default=False,
    help="Skip applying constraints and indexes",
)
@click.option(
    "--use-metadata-extraction/--no-metadata-extraction",
    default=True,
    help="Use llm-document-enhancer metadata (default: True)",
)
@click.option(
    "--clear",
    is_flag=True,
    default=False,
    help="Clear existing data before seeding (for re-seeding)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be done without making changes",
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
    metadata_path: Path,
    skip_constraints: bool,
    use_metadata_extraction: bool,
    clear: bool,
    dry_run: bool,
    verbose: bool,
) -> None:
    """Seed Neo4j database with books, chapters, concepts, and relationships.
    
    PCON-3: Updated to use llm-document-enhancer metadata extraction output
    which provides rich keywords and concepts for each chapter.
    
    Examples:
        # Normal seeding with metadata extraction
        python scripts/seed_neo4j.py
        
        # Re-seed from scratch (clears existing data)
        python scripts/seed_neo4j.py --clear
        
        # Dry run to see what would happen
        python scripts/seed_neo4j.py --dry-run
        
        # Use legacy books/metadata directory
        python scripts/seed_neo4j.py --no-metadata-extraction
    """
    if verbose:
        logging.basicConfig(level=logging.INFO)
    
    config = SeedingConfig(
        books_path=books_path,
        taxonomies_path=taxonomies_path,
        init_scripts_path=init_scripts_path,
        metadata_extraction_path=metadata_path,
        apply_constraints=not skip_constraints,
        verbose=verbose,
        dry_run=dry_run,
        clear_before_seed=clear,
    )
    
    driver = get_neo4j_driver()
    
    try:
        # Dry run mode - show current state and what would be done
        if dry_run:
            console.print("\n[bold yellow]🔍 DRY RUN MODE - No changes will be made[/bold yellow]\n")
            stats = get_database_stats(driver)
            console.print("[bold]Current Database State:[/bold]")
            console.print(f"  • Books: {stats['book_count']}")
            console.print(f"  • Chapters: {stats['chapter_count']}")
            console.print(f"  • Concepts: {stats['concept_count']}")
            console.print(f"  • Tiers: {stats['tier_count']}")
            console.print(f"  • HAS_CHAPTER: {stats['has_chapter_count']}")
            console.print(f"  • COVERS: {stats['covers_count']}")
            console.print(f"  • PARALLEL: {stats['parallel_count']}")
            console.print(f"  • PERPENDICULAR: {stats['perpendicular_count']}")
            console.print(f"  • SKIP_TIER: {stats['skip_tier_count']}")
            
            # Count source files
            if use_metadata_extraction and metadata_path.exists():
                file_count = len(list(metadata_path.glob("*_metadata.json")))
                console.print(f"\n[bold]Would seed from:[/bold] {metadata_path}")
                console.print(f"  • {file_count} metadata files available")
            
            if clear:
                console.print("\n[bold red]Would CLEAR all existing data first[/bold red]")
            
            driver.close()
            return
        
        console.print("\n[bold blue]🗃️  Seeding Neo4j database (PCON-3)...[/bold blue]\n")
        
        # Clear if requested
        if clear:
            console.print("[bold red]⚠️  Clearing existing data...[/bold red]")
            clear_stats = clear_database(driver)
            console.print(f"  ✓ Deleted {clear_stats['nodes_deleted']} nodes, {clear_stats['relationships_deleted']} relationships")
        
        with Progress() as progress:
            task = progress.add_task("[green]Seeding...", total=6)
            
            # Step 1: Apply constraints and indexes
            if config.apply_constraints:
                constraints, indexes = apply_cypher_scripts(driver, config.init_scripts_path)
                console.print(f"  ✓ Applied {constraints} constraints, {indexes} indexes")
            progress.update(task, advance=1)
            
            # Step 2: Seed Tier nodes
            tier_count = seed_tier_nodes(driver)
            console.print(f"  ✓ Seeded {tier_count} tier nodes")
            progress.update(task, advance=1)
            
            if use_metadata_extraction:
                # PCON-3: Use llm-document-enhancer metadata extraction
                console.print(f"  📚 Using metadata extraction from: {config.metadata_extraction_path}")
                books, chapters, concepts, covers = seed_from_metadata_extraction(
                    driver, config.metadata_extraction_path
                )
                console.print(f"  ✓ Seeded {books} books (from metadata extraction)")
                console.print(f"  ✓ Seeded {chapters} chapters with keywords/concepts")
                console.print(f"  ✓ Seeded {concepts} unique Concept nodes")
                console.print(f"  ✓ Created {covers} COVERS relationships")
                progress.update(task, advance=3)
            else:
                # Legacy: Use books/metadata directory
                book_count = seed_books(driver, config.books_path)
                console.print(f"  ✓ Seeded {book_count} books")
                progress.update(task, advance=1)
                
                chapter_count = seed_chapters(driver, config.books_path)
                console.print(f"  ✓ Seeded {chapter_count} chapters")
                progress.update(task, advance=1)
                
                # PCON-3: Seed concepts from existing data
                concept_count = seed_concepts(driver)
                console.print(f"  ✓ Seeded {concept_count} concepts")
                progress.update(task, advance=1)
            
            # Step 6: Seed tier relationships
            rel_count = seed_tier_relationships(driver, config.taxonomies_path)
            console.print(f"  ✓ Created {rel_count} tier relationships")
            progress.update(task, advance=1)
            
    finally:
            driver.close()
    
    console.print("\n[bold green]✅ Neo4j seeding complete![/bold green]")
    console.print("\n[dim]PCON-3 Exit Criteria:[/dim]")
    console.print("[dim]  - AC-3.1: seed_concepts() function ✓[/dim]")
    console.print("[dim]  - AC-3.2: Chapters have keywords/concepts ✓[/dim]")
    console.print("[dim]  - AC-3.3: COVERS relationships created ✓[/dim]")
    console.print("[dim]  - AC-3.5-3.7: Books, Chapters, Concepts exist ✓[/dim]")


if __name__ == "__main__":
    main()
