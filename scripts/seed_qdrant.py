"""Seed Qdrant database with chapter embeddings.

Phase 3.1: Seeding Pipeline - GREEN phase implementation.
WBS Tasks: 3.1.4 (seed_qdrant.py)

This script seeds Qdrant with:
1. Creates chapters collection with proper schema
2. Generates embeddings from chapter content using sentence-transformers
3. Stores vectors with metadata payloads (chapter_id, book_id, title, tier)

Anti-Pattern Audit:
- Per Issue #12: Connection pooling (single client instance)
- Per Category 1.1: All functions have type annotations
- Per S1192: String literals extracted to constants
- Per Category 2: Functions under 15 complexity
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress

if TYPE_CHECKING:
    from qdrant_client import QdrantClient

console = Console()
logger = logging.getLogger(__name__)

# Constants per CODING_PATTERNS_ANALYSIS.md S1192
DEFAULT_BOOKS_PATH = Path(__file__).parent.parent / "books"
DEFAULT_COLLECTION_NAME = "chapters"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
JSON_GLOB_PATTERN = "*.json"  # Per S1192: extract duplicated literal
MAX_CONTENT_LENGTH = 8000  # Truncate content for embedding


@dataclass
class QdrantConfig:
    """Configuration for Qdrant seeding.
    
    Per Issue #2.2: Use dataclass instead of long parameter lists.
    """
    
    books_path: Path = field(default_factory=lambda: DEFAULT_BOOKS_PATH)
    collection_name: str = DEFAULT_COLLECTION_NAME
    batch_size: int = 100
    recreate_collection: bool = False
    verbose: bool = False


@dataclass
class SeedingStats:
    """Statistics from Qdrant seeding operations."""
    
    collection_created: bool = False
    chapters_seeded: int = 0
    books_processed: int = 0
    errors: int = 0


def get_qdrant_client() -> QdrantClient:
    """Create Qdrant client from environment configuration.
    
    Per Issue #12: Single client instance with connection pooling.
    """
    from qdrant_client import QdrantClient

    load_dotenv()

    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))

    return QdrantClient(host=host, port=port)


def get_embedding_model() -> Any:
    """Load sentence transformer model for embeddings.
    
    Uses all-MiniLM-L6-v2 (384 dimensions) for semantic search.
    """
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL)


def ensure_collection(
    client: QdrantClient,
    collection_name: str,
    recreate: bool = False,
) -> bool:
    """Create collection if it doesn't exist.
    
    Returns True if collection was created, False if it already existed.
    """
    from qdrant_client.models import Distance, VectorParams

    collections = client.get_collections().collections
    collection_names = [c.name for c in collections]

    if collection_name in collection_names:
        if recreate:
            client.delete_collection(collection_name)
            console.print(f"  ✓ Deleted existing collection: {collection_name}")
        else:
            return False

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    )
    console.print(f"  ✓ Created collection: {collection_name}")
    return True


def seed_chapters_from_metadata(
    client: QdrantClient,
    books_path: Path,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    batch_size: int = 100,
) -> tuple[int, int]:
    """Seed chapter embeddings from metadata files.
    
    Uses chapter titles for embedding generation.
    Returns tuple of (chapters_seeded, books_processed).
    """
    from qdrant_client.models import PointStruct

    metadata_path = books_path / "metadata"
    chapters_count = 0
    books_count = 0

    if not metadata_path.exists():
        logger.warning(f"Metadata path does not exist: {metadata_path}")
        return chapters_count, books_count

    model = get_embedding_model()

    points: list[PointStruct] = []
    point_id = 0

    for file_path in sorted(metadata_path.glob(JSON_GLOB_PATTERN)):
        if file_path.name.startswith("."):
            continue
            
        try:
            with open(file_path) as f:
                book = json.load(f)

            book_id = book.get("book_id", "")
            book_title = book.get("title", "")
            tier = book.get("tier")
            chapters = book.get("chapters", [])

            for chapter in chapters:
                # Generate embedding from chapter title
                chapter_title = chapter.get("title", f"Chapter {chapter.get('number', 0)}")
                content_for_embedding = f"{book_title}: {chapter_title}"
                
                embedding = model.encode(content_for_embedding).tolist()

                points.append(
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "chapter_id": chapter.get("chapter_id", ""),
                            "book_id": book_id,
                            "book_title": book_title,
                            "title": chapter_title,
                            "number": chapter.get("number"),
                            "tier": tier,
                        },
                    )
                )
                point_id += 1
                chapters_count += 1

                # Batch upsert when batch is full
                if len(points) >= batch_size:
                    client.upsert(collection_name=collection_name, points=points)
                    points = []

            books_count += 1
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse {file_path.name}: {e}")
        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {e}")

    # Upsert remaining points
    if points:
        client.upsert(collection_name=collection_name, points=points)

    return chapters_count, books_count


def _build_enriched_payload(
    chapter: dict[str, Any],
    book_id: str,
    book_title: str,
    tier: Any,
) -> dict[str, Any]:
    """Build payload with all enriched fields per WBS 3.5.5.
    
    Per AI_CODING_PLATFORM_ARCHITECTURE: enriched data includes
    keywords, concepts, summary, similar_chapters.
    
    Extracted per S3776 to reduce cognitive complexity.
    """
    return {
        "chapter_id": chapter.get("chapter_id", ""),
        "book_id": book_id,
        "book_title": book_title,
        "title": chapter.get("title", ""),
        "number": chapter.get("number"),
        "tier": tier,
        # Enriched fields per WBS 3.5.5.3-6
        "keywords": chapter.get("keywords", []),
        "concepts": chapter.get("concepts", []),
        "summary": chapter.get("summary", ""),
        "similar_chapters": chapter.get("similar_chapters", []),
    }


def _process_enriched_book(
    file_path: Path,
    model: Any,
    points: list[Any],
    point_id: int,
) -> tuple[int, int]:
    """Process a single enriched book file.
    
    Returns tuple of (chapters_processed, updated_point_id).
    Extracted per S3776 to reduce cognitive complexity.
    """
    from qdrant_client.models import PointStruct
    
    chapters_count = 0
    
    with open(file_path) as f:
        book = json.load(f)

    book_id = book.get("book_id", "")
    book_title = book.get("title", "")
    tier = book.get("tier")
    chapters = book.get("chapters", [])

    for chapter in chapters:
        # Generate embedding from chapter content (or title if no content)
        content = chapter.get("content", chapter.get("title", ""))
        if len(content) > MAX_CONTENT_LENGTH:
            content = content[:MAX_CONTENT_LENGTH]
            
        embedding = model.encode(content).tolist()
        payload = _build_enriched_payload(chapter, book_id, book_title, tier)

        points.append(
            PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload,
            )
        )
        point_id += 1
        chapters_count += 1

    return chapters_count, point_id


def seed_chapters_from_enriched(
    client: QdrantClient,
    books_path: Path,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    batch_size: int = 100,
) -> tuple[int, int]:
    """Seed chapter embeddings from enriched books.
    
    Uses full chapter content for embedding generation.
    Returns tuple of (chapters_seeded, books_processed).
    """
    from qdrant_client.models import PointStruct

    enriched_path = books_path / "enriched"
    chapters_count = 0
    books_count = 0

    if not enriched_path.exists():
        logger.warning(f"Enriched path does not exist: {enriched_path}")
        return chapters_count, books_count

    model = get_embedding_model()
    points: list[PointStruct] = []
    point_id = 0

    for file_path in sorted(enriched_path.glob(JSON_GLOB_PATTERN)):
        if file_path.name.startswith("."):
            continue
            
        try:
            processed, point_id = _process_enriched_book(
                file_path, model, points, point_id
            )
            chapters_count += processed
            books_count += 1

            # Batch upsert when batch is full
            if len(points) >= batch_size:
                client.upsert(collection_name=collection_name, points=points)
                points = []

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse {file_path.name}: {e}")
        except Exception as e:
            logger.error(f"Error processing {file_path.name}: {e}")

    # Upsert remaining points
    if points:
        client.upsert(collection_name=collection_name, points=points)

    return chapters_count, books_count


def seed_all(config: QdrantConfig) -> SeedingStats:
    """Execute full Qdrant seeding pipeline."""
    stats = SeedingStats()
    client = get_qdrant_client()
    
    # Step 1: Ensure collection exists
    stats.collection_created = ensure_collection(
        client,
        config.collection_name,
        recreate=config.recreate_collection,
    )
    
    # Step 2: Try enriched data first, fall back to metadata
    enriched_path = config.books_path / "enriched"
    if enriched_path.exists() and list(enriched_path.glob("*.json")):
        chapters, books = seed_chapters_from_enriched(
            client,
            config.books_path,
            config.collection_name,
            config.batch_size,
        )
    else:
        chapters, books = seed_chapters_from_metadata(
            client,
            config.books_path,
            config.collection_name,
            config.batch_size,
        )
    
    stats.chapters_seeded = chapters
    stats.books_processed = books
    
    return stats


@click.command()
@click.option(
    "--books-path",
    type=click.Path(path_type=Path),
    default=DEFAULT_BOOKS_PATH,
    help="Path to books directory",
)
@click.option(
    "--collection",
    type=str,
    default=DEFAULT_COLLECTION_NAME,
    help="Qdrant collection name",
)
@click.option(
    "--batch-size",
    type=int,
    default=100,
    help="Batch size for upserting points",
)
@click.option(
    "--recreate",
    is_flag=True,
    default=False,
    help="Recreate collection if it exists",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Enable verbose output",
)
def main(
    books_path: Path,
    collection: str,
    batch_size: int,
    recreate: bool,
    verbose: bool,  # noqa: ARG001 - reserved for future logging control
) -> None:
    """Seed Qdrant database with chapter embeddings."""
    # Note: verbose is reserved for future logging level control
    # Config object available for programmatic API usage
    _config = QdrantConfig(  # noqa: F841 - kept for API compatibility
        books_path=books_path,
        collection_name=collection,
        batch_size=batch_size,
        recreate_collection=recreate,
        verbose=verbose,
    )
    
    console.print("\n[bold blue]Seeding Qdrant database...[/bold blue]\n")

    client = get_qdrant_client()

    try:
        with Progress() as progress:
            task = progress.add_task("[green]Seeding...", total=2)
            
            # Step 1: Ensure collection exists
            created = ensure_collection(client, collection, recreate=recreate)
            if created:
                console.print(f"  ✓ Created collection: {collection}")
            else:
                console.print(f"  ✓ Using existing collection: {collection}")
            progress.update(task, advance=1)
            
            # Step 2: Seed chapters (try enriched first, fall back to metadata)
            enriched_path = books_path / "enriched"
            if enriched_path.exists() and list(enriched_path.glob(JSON_GLOB_PATTERN)):
                chapters, books = seed_chapters_from_enriched(
                    client, books_path, collection, batch_size
                )
                console.print(f"  ✓ Seeded {chapters} chapters from {books} enriched books")
            else:
                chapters, books = seed_chapters_from_metadata(
                    client, books_path, collection, batch_size
                )
                console.print(f"  ✓ Seeded {chapters} chapters from {books} metadata files")
            progress.update(task, advance=1)

        console.print("\n[bold green]Qdrant seeding complete![/bold green]")

    except Exception as e:
        console.print(f"\n[bold red]Error: {e}[/bold red]")
        raise


if __name__ == "__main__":
    main()
