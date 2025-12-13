"""Validate database seed integrity."""

from __future__ import annotations

import os
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

console = Console()


def count_neo4j_nodes() -> dict[str, int]:
    """Count nodes in Neo4j by label."""
    from neo4j import GraphDatabase

    load_dotenv()

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    auth = os.getenv("NEO4J_AUTH", "neo4j/password").split("/")

    driver = GraphDatabase.driver(uri, auth=(auth[0], auth[1]))
    counts = {}

    try:
        with driver.session() as session:
            # Count Books
            result = session.run("MATCH (b:Book) RETURN count(b) as count")
            counts["Books"] = result.single()["count"]

            # Count Chapters
            result = session.run("MATCH (c:Chapter) RETURN count(c) as count")
            counts["Chapters"] = result.single()["count"]

            # Count relationships
            result = session.run("MATCH ()-[r:PARALLEL]->() RETURN count(r) as count")
            counts["PARALLEL edges"] = result.single()["count"]

            result = session.run("MATCH ()-[r:PERPENDICULAR]->() RETURN count(r) as count")
            counts["PERPENDICULAR edges"] = result.single()["count"]

            result = session.run("MATCH ()-[r:SKIP_TIER]->() RETURN count(r) as count")
            counts["SKIP_TIER edges"] = result.single()["count"]

    finally:
        driver.close()

    return counts


def count_qdrant_points(collection_name: str = "chapters") -> int:
    """Count points in Qdrant collection."""
    from qdrant_client import QdrantClient

    load_dotenv()

    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))

    client = QdrantClient(host=host, port=port)

    try:
        info = client.get_collection(collection_name)
        return info.points_count
    except Exception:
        return 0


def count_local_files(books_path: Path) -> dict[str, int]:
    """Count local data files."""
    counts = {}

    raw_path = books_path / "raw"
    if raw_path.exists():
        counts["Raw books"] = len(list(raw_path.glob("*.json")))
    else:
        counts["Raw books"] = 0

    metadata_path = books_path / "metadata"
    if metadata_path.exists():
        counts["Metadata files"] = len(list(metadata_path.glob("*.json")))
    else:
        counts["Metadata files"] = 0

    enriched_path = books_path / "enriched"
    if enriched_path.exists():
        counts["Enriched files"] = len(list(enriched_path.glob("*.json")))
    else:
        counts["Enriched files"] = 0

    return counts


@click.command()
@click.option(
    "--books-path",
    type=click.Path(path_type=Path),
    default=Path("books"),
    help="Path to books directory",
)
@click.option("--expected-books", type=int, default=47, help="Expected number of books")
def main(books_path: Path, expected_books: int) -> None:
    """Validate database seed integrity."""
    console.print("[bold blue]Validating seed integrity...[/bold blue]")
    console.print()

    # Local files
    table = Table(title="Local Files")
    table.add_column("Type", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Status", justify="center")

    local_counts = count_local_files(books_path)
    for name, count in local_counts.items():
        status = "✓" if count > 0 else "✗"
        color = "green" if count > 0 else "red"
        table.add_row(name, str(count), f"[{color}]{status}[/{color}]")

    console.print(table)
    console.print()

    # Neo4j
    table = Table(title="Neo4j Database")
    table.add_column("Type", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Status", justify="center")

    try:
        neo4j_counts = count_neo4j_nodes()
        for name, count in neo4j_counts.items():
            expected = expected_books if "Books" in name else None
            if expected:
                status = "✓" if count == expected else f"✗ (expected {expected})"
                color = "green" if count == expected else "yellow"
            else:
                status = "✓" if count > 0 else "-"
                color = "green" if count > 0 else "dim"
            table.add_row(name, str(count), f"[{color}]{status}[/{color}]")
    except Exception as e:
        table.add_row("Connection", "FAILED", f"[red]{e}[/red]")

    console.print(table)
    console.print()

    # Qdrant
    table = Table(title="Qdrant Database")
    table.add_column("Collection", style="cyan")
    table.add_column("Points", justify="right")
    table.add_column("Status", justify="center")

    try:
        qdrant_count = count_qdrant_points()
        status = "✓" if qdrant_count > 0 else "✗ (empty)"
        color = "green" if qdrant_count > 0 else "yellow"
        table.add_row("chapters", str(qdrant_count), f"[{color}]{status}[/{color}]")
    except Exception as e:
        table.add_row("chapters", "FAILED", f"[red]{e}[/red]")

    console.print(table)
    console.print()

    console.print("[bold green]Validation complete![/bold green]")


if __name__ == "__main__":
    main()
