"""Seed Qdrant database with chapter embeddings."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress

if TYPE_CHECKING:
    from qdrant_client import QdrantClient

console = Console()
logger = logging.getLogger(__name__)

# Default embedding model
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


def get_qdrant_client() -> "QdrantClient":
    """Create Qdrant client from environment configuration."""
    from qdrant_client import QdrantClient

    load_dotenv()

    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))

    return QdrantClient(host=host, port=port)


def get_embedding_model():
    """Load sentence transformer model for embeddings."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL)


def ensure_collection(client: "QdrantClient", collection_name: str) -> None:
    """Create collection if it doesn't exist."""
    from qdrant_client.models import Distance, VectorParams

    collections = client.get_collections().collections
    collection_names = [c.name for c in collections]

    if collection_name not in collection_names:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )
        console.print(f"  ✓ Created collection: {collection_name}")


def seed_chapters(
    client: "QdrantClient",
    books_path: Path,
    collection_name: str = "chapters",
) -> int:
    """Seed chapter embeddings from enriched books."""
    from qdrant_client.models import PointStruct

    enriched_path = books_path / "enriched"
    count = 0

    if not enriched_path.exists():
        logger.warning(f"Enriched path does not exist: {enriched_path}")
        return count

    model = get_embedding_model()
    ensure_collection(client, collection_name)

    points = []
    point_id = 0

    for file_path in enriched_path.glob("*.json"):
        with open(file_path) as f:
            book = json.load(f)

        book_id = book.get("book_id")
        chapters = book.get("chapters", [])

        for chapter in chapters:
            # Generate embedding from chapter content
            content = chapter.get("content", chapter.get("title", ""))
            embedding = model.encode(content).tolist()

            points.append(
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "chapter_id": chapter.get("chapter_id"),
                        "book_id": book_id,
                        "title": chapter.get("title"),
                        "tier": book.get("tier"),
                        "keywords": chapter.get("keywords", []),
                    },
                )
            )
            point_id += 1
            count += 1

    # Batch upsert
    if points:
        client.upsert(collection_name=collection_name, points=points)

    return count


@click.command()
@click.option(
    "--books-path",
    type=click.Path(exists=True, path_type=Path),
    default=Path("books"),
    help="Path to books directory",
)
@click.option(
    "--collection",
    type=str,
    default="chapters",
    help="Qdrant collection name",
)
def main(books_path: Path, collection: str) -> None:
    """Seed Qdrant database with chapter embeddings."""
    console.print("[bold blue]Seeding Qdrant database...[/bold blue]")

    client = get_qdrant_client()

    try:
        with Progress() as progress:
            task = progress.add_task("Seeding...", total=1)

            chapter_count = seed_chapters(client, books_path, collection)
            console.print(f"  ✓ Seeded {chapter_count} chapter embeddings")
            progress.advance(task)

        console.print("[bold green]Qdrant seeding complete![/bold green]")

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise


if __name__ == "__main__":
    main()
