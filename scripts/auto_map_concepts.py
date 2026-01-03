"""Automated concept-to-code mapping for enriched books.

Phase 4B: Concept Mapping Pipeline
WBS Tasks: Automated book concept → repo code mapping

This script:
1. Extracts concepts/keywords from enriched book chapters
2. Matches against pre-indexed repo concepts via Qdrant semantic search
3. Creates Neo4j relationships for high-confidence matches
4. Queues low-confidence matches for human review

Pipeline Integration:
    1. validate_enriched_books.py    # Validates schema
    2. seed_qdrant.py                # Seeds chapter embeddings
    3. seed_neo4j.py                 # Seeds book/chapter nodes
    4. auto_map_concepts.py          # THIS - maps concepts to repos

Anti-Pattern Audit:
- Per Issue #12: Connection pooling (single client instances)
- Per Category 1.1: All functions have type annotations
- Per S1192: String literals extracted to constants
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress
from rich.table import Table

if TYPE_CHECKING:
    from neo4j import Driver
    from qdrant_client import QdrantClient
    from sentence_transformers import SentenceTransformer

console = Console()
logger = logging.getLogger(__name__)

# Constants per CODING_PATTERNS_ANALYSIS.md S1192
DEFAULT_BOOKS_PATH = Path(__file__).parent.parent / "books" / "enriched"
DEFAULT_REPOS_PATH = Path(__file__).parent.parent / "repos" / "metadata"
DEFAULT_MAPPINGS_PATH = Path(__file__).parent.parent / "mappings"
REPO_CONCEPTS_COLLECTION = "repo_concepts"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
JSON_GLOB_PATTERN = "*.json"

# Confidence thresholds
CONFIDENCE_AUTO = 0.85       # Auto-create relationship
CONFIDENCE_REVIEW = 0.70     # Queue for human review
TOP_K_MATCHES = 5            # Max matches per concept


@dataclass
class ConceptMatch:
    """A matched concept between book and repo."""
    
    book_id: str
    chapter_number: int
    chapter_title: str
    concept: str
    repo_id: str
    repo_pattern: str
    score: float
    auto_approved: bool
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "book_id": self.book_id,
            "chapter_number": self.chapter_number,
            "chapter_title": self.chapter_title,
            "concept": self.concept,
            "repo_id": self.repo_id,
            "repo_pattern": self.repo_pattern,
            "score": round(self.score, 4),
            "auto_approved": self.auto_approved,
        }


@dataclass
class MappingConfig:
    """Configuration for concept mapping.
    
    Per Issue #2.2: Use dataclass instead of long parameter lists.
    """
    
    books_path: Path = field(default_factory=lambda: DEFAULT_BOOKS_PATH)
    repos_path: Path = field(default_factory=lambda: DEFAULT_REPOS_PATH)
    mappings_path: Path = field(default_factory=lambda: DEFAULT_MAPPINGS_PATH)
    confidence_auto: float = CONFIDENCE_AUTO
    confidence_review: float = CONFIDENCE_REVIEW
    top_k: int = TOP_K_MATCHES
    dry_run: bool = False
    verbose: bool = False


@dataclass
class MappingStats:
    """Statistics from concept mapping operations."""
    
    books_processed: int = 0
    chapters_processed: int = 0
    concepts_extracted: int = 0
    matches_found: int = 0
    auto_approved: int = 0
    pending_review: int = 0
    relationships_created: int = 0
    errors: int = 0


def get_qdrant_client() -> QdrantClient:
    """Create Qdrant client from environment configuration."""
    from qdrant_client import QdrantClient
    
    load_dotenv()
    
    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    
    return QdrantClient(host=host, port=port)


def get_neo4j_driver() -> Driver:
    """Create Neo4j driver from environment configuration."""
    from neo4j import GraphDatabase
    
    load_dotenv()
    
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "password")
    
    return GraphDatabase.driver(uri, auth=(user, password))


def get_embedding_model() -> SentenceTransformer:
    """Load sentence transformer model for embeddings."""
    from sentence_transformers import SentenceTransformer
    
    return SentenceTransformer(EMBEDDING_MODEL)


def extract_book_concepts(book_path: Path) -> list[dict[str, Any]]:
    """Extract concepts and keywords from enriched book chapters.
    
    Args:
        book_path: Path to enriched book JSON
        
    Returns:
        List of dicts with book_id, chapter info, and concepts
    """
    with open(book_path) as f:
        book = json.load(f)
    
    # Get book ID from metadata or filename
    book_id = book.get("metadata", {}).get("book_id")
    if not book_id:
        book_id = book_path.stem.replace("_enriched", "")
    
    results = []
    
    for chapter in book.get("chapters", []):
        chapter_number = chapter.get("chapter_number", 0)
        chapter_title = chapter.get("title", f"Chapter {chapter_number}")
        
        # Collect all concepts and keywords
        concepts = set(chapter.get("concepts", []))
        concepts.update(chapter.get("keywords", []))
        
        # Also check enriched_keywords if present
        enriched = chapter.get("enriched_keywords", {})
        if isinstance(enriched, dict):
            concepts.update(enriched.get("expanded", []))
        
        for concept in concepts:
            if concept and len(concept) > 2:  # Skip very short terms
                results.append({
                    "book_id": book_id,
                    "chapter_number": chapter_number,
                    "chapter_title": chapter_title,
                    "concept": concept.lower().strip(),
                })
    
    return results


def match_concepts_to_repos(
    concepts: list[dict[str, Any]],
    qdrant: QdrantClient,
    embedder: SentenceTransformer,
    config: MappingConfig,
) -> list[ConceptMatch]:
    """Match book concepts to repo concepts via semantic search.
    
    Args:
        concepts: List of concept dicts from extract_book_concepts
        qdrant: Qdrant client
        embedder: Sentence transformer model
        config: Mapping configuration
        
    Returns:
        List of ConceptMatch results
    """
    matches = []
    seen = set()  # Avoid duplicate matches
    
    for item in concepts:
        concept = item["concept"]
        
        # Generate embedding for concept
        embedding = embedder.encode(concept).tolist()
        
        # Search repo_concepts collection
        try:
            results = qdrant.search(
                collection_name=REPO_CONCEPTS_COLLECTION,
                query_vector=embedding,
                limit=config.top_k,
            )
        except Exception as e:
            logger.warning(f"Qdrant search failed for '{concept}': {e}")
            continue
        
        for result in results:
            if result.score < config.confidence_review:
                continue
            
            # Create unique key to avoid duplicates
            key = (
                item["book_id"],
                item["chapter_number"],
                concept,
                result.payload["repo_id"],
            )
            if key in seen:
                continue
            seen.add(key)
            
            matches.append(ConceptMatch(
                book_id=item["book_id"],
                chapter_number=item["chapter_number"],
                chapter_title=item["chapter_title"],
                concept=concept,
                repo_id=result.payload["repo_id"],
                repo_pattern=result.payload["pattern"],
                score=result.score,
                auto_approved=result.score >= config.confidence_auto,
            ))
    
    return matches


def create_neo4j_relationships(
    matches: list[ConceptMatch],
    driver: Driver,
    dry_run: bool = False,
) -> int:
    """Create Neo4j relationships for auto-approved matches.
    
    Creates: (Chapter)-[:EXEMPLIFIED_BY {concept, score}]->(Repo)
    
    Args:
        matches: List of ConceptMatch objects
        driver: Neo4j driver
        dry_run: If True, don't actually create relationships
        
    Returns:
        Number of relationships created
    """
    auto_approved = [m for m in matches if m.auto_approved]
    
    if not auto_approved:
        return 0
    
    if dry_run:
        return len(auto_approved)
    
    cypher = """
    MATCH (c:Chapter {book_id: $book_id, chapter_number: $chapter_number})
    MATCH (r:Repo {id: $repo_id})
    MERGE (c)-[rel:EXEMPLIFIED_BY {concept: $concept}]->(r)
    SET rel.score = $score,
        rel.auto_mapped = true,
        rel.created_at = datetime()
    RETURN rel
    """
    
    created = 0
    with driver.session() as session:
        for match in auto_approved:
            try:
                result = session.run(
                    cypher,
                    book_id=match.book_id,
                    chapter_number=match.chapter_number,
                    repo_id=match.repo_id,
                    concept=match.concept,
                    score=match.score,
                )
                if result.single():
                    created += 1
            except Exception as e:
                logger.warning(f"Failed to create relationship: {e}")
    
    return created


def save_pending_review(\n    matches: list[ConceptMatch],\n    config: MappingConfig,\n) -> Path | None:\n    \"\"\"Save low-confidence matches for human review.\n    \n    Args:\n        matches: All matches (will filter for review-only)
        config: Mapping configuration
        
    Returns:
        Path to saved review file, or None if no pending reviews
    """
    pending = [m for m in matches if not m.auto_approved]
    
    if not pending:
        return None
    
    # Ensure mappings directory exists
    config.mappings_path.mkdir(parents=True, exist_ok=True)
    
    # Group by book
    by_book: dict[str, list[dict]] = {}
    for match in pending:
        if match.book_id not in by_book:
            by_book[match.book_id] = []
        by_book[match.book_id].append(match.to_dict())
    
    # Save with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = config.mappings_path / f"pending_review_{timestamp}.json"
    
    with open(output_path, "w") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "confidence_range": {
                "min": config.confidence_review,
                "max": config.confidence_auto,
            },
            "total_pending": len(pending),
            "by_book": by_book,
        }, f, indent=2)
    
    return output_path


def print_mapping_summary(
    matches: list[ConceptMatch],
    stats: MappingStats,
) -> None:
    """Print a summary table of mapping results."""
    
    console.print("\n[bold green]📚 Concept Mapping Summary[/bold green]\n")
    
    # Stats table
    stats_table = Table(title="Statistics")
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", justify="right")
    
    stats_table.add_row("Books Processed", str(stats.books_processed))
    stats_table.add_row("Chapters Processed", str(stats.chapters_processed))
    stats_table.add_row("Concepts Extracted", str(stats.concepts_extracted))
    stats_table.add_row("Matches Found", str(stats.matches_found))
    stats_table.add_row("✅ Auto-Approved", str(stats.auto_approved))
    stats_table.add_row("⚠️ Pending Review", str(stats.pending_review))
    stats_table.add_row("Relationships Created", str(stats.relationships_created))
    
    console.print(stats_table)
    
    # Sample matches table
    if matches:
        sample_table = Table(title="\nSample Matches (first 10)")
        sample_table.add_column("Book", style="cyan", max_width=25)
        sample_table.add_column("Ch", justify="center")
        sample_table.add_column("Concept", style="yellow")
        sample_table.add_column("→ Repo", style="green")
        sample_table.add_column("Score", justify="right")
        sample_table.add_column("Status")
        
        for match in sorted(matches, key=lambda m: m.score, reverse=True)[:10]:
            status = "✅ AUTO" if match.auto_approved else "⚠️ REVIEW"
            sample_table.add_row(
                match.book_id[:25],
                str(match.chapter_number),
                match.concept[:20],
                match.repo_id[:20],
                f"{match.score:.2f}",
                status,
            )
        
        console.print(sample_table)


@click.command()
@click.option(
    "--books-path",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_BOOKS_PATH,
    help="Path to enriched books directory",
)
@click.option(
    "--repos-path",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_REPOS_PATH,
    help="Path to repo metadata directory",
)
@click.option(
    "--book",
    "book_filter",
    type=str,
    default=None,
    help="Process only books matching this pattern",
)
@click.option(
    "--confidence-auto",
    type=float,
    default=CONFIDENCE_AUTO,
    help=f"Auto-approve threshold (default: {CONFIDENCE_AUTO})",
)
@click.option(
    "--confidence-review",
    type=float,
    default=CONFIDENCE_REVIEW,
    help=f"Review threshold (default: {CONFIDENCE_REVIEW})",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Don't create Neo4j relationships or save files",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Enable verbose output",
)
def main(
    books_path: Path,
    repos_path: Path,
    book_filter: str | None,
    confidence_auto: float,
    confidence_review: float,
    dry_run: bool,
    verbose: bool,
) -> None:
    """Map enriched book concepts to code repository implementations.
    
    This script extracts concepts from enriched books and matches them
    to relevant code repositories using semantic similarity. High-confidence
    matches are automatically linked in Neo4j, while lower-confidence
    matches are queued for human review.
    """
    config = MappingConfig(
        books_path=books_path,
        repos_path=repos_path,
        confidence_auto=confidence_auto,
        confidence_review=confidence_review,
        dry_run=dry_run,
        verbose=verbose,
    )
    stats = MappingStats()
    
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    console.print("[bold blue]🔗 Concept-to-Code Mapping Pipeline[/bold blue]\n")
    
    if dry_run:
        console.print("[yellow]⚠️ DRY RUN - No changes will be made[/yellow]\n")
    
    # Initialize clients
    console.print("Initializing clients...")
    qdrant = get_qdrant_client()
    embedder = get_embedding_model()
    driver = get_neo4j_driver() if not dry_run else None
    
    # Verify repo_concepts collection exists
    try:
        collection_info = qdrant.get_collection(REPO_CONCEPTS_COLLECTION)
        console.print(f"✓ Found {collection_info.points_count} indexed repo concepts")
    except Exception:
        console.print(
            f"[red]✗ Collection '{REPO_CONCEPTS_COLLECTION}' not found![/red]\n"
            f"Run: python scripts/index_repo_concepts.py first"
        )
        raise click.Abort()
    
    # Find enriched books
    book_files = list(books_path.glob(JSON_GLOB_PATTERN))
    if book_filter:
        book_files = [f for f in book_files if book_filter.lower() in f.name.lower()]
    
    console.print(f"Found {len(book_files)} enriched books to process\n")
    
    all_matches: list[ConceptMatch] = []
    
    with Progress() as progress:
        task = progress.add_task("Processing books...", total=len(book_files))
        
        for book_path in book_files:
            # Extract concepts from book
            concepts = extract_book_concepts(book_path)
            stats.books_processed += 1
            stats.concepts_extracted += len(concepts)
            
            # Count unique chapters
            chapters = {(c["book_id"], c["chapter_number"]) for c in concepts}
            stats.chapters_processed += len(chapters)
            
            # Match concepts to repos
            matches = match_concepts_to_repos(concepts, qdrant, embedder, config)
            all_matches.extend(matches)
            
            if verbose and matches:
                console.print(f"  {book_path.name}: {len(matches)} matches")
            
            progress.advance(task)
    
    # Tally results
    stats.matches_found = len(all_matches)
    stats.auto_approved = sum(1 for m in all_matches if m.auto_approved)
    stats.pending_review = stats.matches_found - stats.auto_approved
    
    # Create Neo4j relationships
    if driver and all_matches:
        console.print("\nCreating Neo4j relationships...")
        stats.relationships_created = create_neo4j_relationships(
            all_matches, driver, dry_run=dry_run
        )
    
    # Save pending review
    if not dry_run and stats.pending_review > 0:
        review_path = save_pending_review(all_matches, config)
        if review_path:
            console.print(f"\n⚠️ Pending review saved: {review_path}")
    
    # Print summary
    print_mapping_summary(all_matches, stats)
    
    if driver:
        driver.close()
    
    console.print("\n[bold green]✓ Concept mapping complete![/bold green]")


if __name__ == "__main__":
    main()
