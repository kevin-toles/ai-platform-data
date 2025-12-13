"""Orchestrate full database seeding."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console

console = Console()


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
@click.option("--skip-neo4j", is_flag=True, help="Skip Neo4j seeding")
@click.option("--skip-qdrant", is_flag=True, help="Skip Qdrant seeding")
def main(
    books_path: Path,
    taxonomies_path: Path,
    skip_neo4j: bool,
    skip_qdrant: bool,
) -> None:
    """Orchestrate full database seeding."""
    console.print("[bold blue]Starting full database seed...[/bold blue]")
    console.print()

    scripts_dir = Path(__file__).parent

    # Seed Neo4j
    if not skip_neo4j:
        console.print("[bold cyan]Step 1/2: Seeding Neo4j...[/bold cyan]")
        result = subprocess.run(
            [
                sys.executable,
                str(scripts_dir / "seed_neo4j.py"),
                "--books-path",
                str(books_path),
                "--taxonomies-path",
                str(taxonomies_path),
            ],
            capture_output=False,
        )
        if result.returncode != 0:
            console.print("[bold red]Neo4j seeding failed![/bold red]")
            sys.exit(1)
        console.print()

    # Seed Qdrant
    if not skip_qdrant:
        console.print("[bold cyan]Step 2/2: Seeding Qdrant...[/bold cyan]")
        result = subprocess.run(
            [
                sys.executable,
                str(scripts_dir / "seed_qdrant.py"),
                "--books-path",
                str(books_path),
            ],
            capture_output=False,
        )
        if result.returncode != 0:
            console.print("[bold red]Qdrant seeding failed![/bold red]")
            sys.exit(1)
        console.print()

    console.print("[bold green]✓ Full database seed complete![/bold green]")


if __name__ == "__main__":
    main()
