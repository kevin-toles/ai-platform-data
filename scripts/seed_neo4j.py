"""Seed Neo4j database with books, chapters, and tier relationships."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import click
from rich.console import Console
from rich.progress import Progress

if TYPE_CHECKING:
    from neo4j import Driver

console = Console()
logger = logging.getLogger(__name__)


def get_neo4j_driver() -> Driver:
    """Create Neo4j driver from environment configuration."""
    import os

    from dotenv import load_dotenv
    from neo4j import GraphDatabase

    load_dotenv()

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    auth = os.getenv("NEO4J_AUTH", "neo4j/password").split("/")

    return GraphDatabase.driver(uri, auth=(auth[0], auth[1]))


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


def seed_tier_relationships(driver: Driver, taxonomies_path: Path) -> int:
    """Seed tier relationships (PARALLEL, PERPENDICULAR, SKIP_TIER)."""
    count = 0
    taxonomy_file = taxonomies_path / "AI-ML_taxonomy.json"

    if not taxonomy_file.exists():
        logger.warning(f"Taxonomy file does not exist: {taxonomy_file}")
        return count

    with open(taxonomy_file) as f:
        taxonomy = json.load(f)

    with driver.session() as session:
        relationships = taxonomy.get("relationships", [])

        for rel in relationships:
            session.run(
                f"""
                MATCH (a:Book {{book_id: $source}})
                MATCH (b:Book {{book_id: $target}})
                MERGE (a)-[:{rel.get('type', 'RELATED')}]->(b)
                """,
                source=rel.get("source"),
                target=rel.get("target"),
            )
            count += 1

    return count


@click.command()
@click.option(
    "--books-path",
    type=click.Path(exists=True, path_type=Path),
    default=Path("books"),
    help="Path to books directory",
)
@click.option(
    "--taxonomies-path",
    type=click.Path(exists=True, path_type=Path),
    default=Path("taxonomies"),
    help="Path to taxonomies directory",
)
def main(books_path: Path, taxonomies_path: Path) -> None:
    """Seed Neo4j database with books and tier relationships."""
    console.print("[bold blue]Seeding Neo4j database...[/bold blue]")

    driver = get_neo4j_driver()

    try:
        with Progress() as progress:
            task = progress.add_task("Seeding...", total=3)

            book_count = seed_books(driver, books_path)
            console.print(f"  ✓ Seeded {book_count} books")
            progress.advance(task)

            chapter_count = seed_chapters(driver, books_path)
            console.print(f"  ✓ Seeded {chapter_count} chapters")
            progress.advance(task)

            rel_count = seed_tier_relationships(driver, taxonomies_path)
            console.print(f"  ✓ Seeded {rel_count} tier relationships")
            progress.advance(task)

        console.print("[bold green]Neo4j seeding complete![/bold green]")

    finally:
        driver.close()


if __name__ == "__main__":
    main()
