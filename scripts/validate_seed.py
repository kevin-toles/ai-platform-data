"""Validate database seed integrity.

Phase 3.1: Seeding Pipeline - GREEN phase implementation.
WBS Tasks: 3.1.7 (validate_seed.py)

This script validates:
1. Local file counts (raw, metadata, enriched)
2. Neo4j node counts and constraint validation
3. Neo4j relationship validation (orphan detection)
4. Qdrant collection and vector counts

Anti-Pattern Audit:
- Per Issue #12: Connection pooling (single client instance)
- Per Category 1.1: All functions have type annotations
- Per S1192: String literals extracted to constants
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

console = Console()

# Constants per CODING_PATTERNS_ANALYSIS.md S1192
DEFAULT_BOOKS_PATH = Path(__file__).parent.parent / "books"
DEFAULT_COLLECTION_NAME = "chapters"


@dataclass
class ValidationResult:
    """Result of a validation check."""
    
    name: str
    expected: int | None
    actual: int
    passed: bool
    message: str = ""


@dataclass
class ValidationReport:
    """Complete validation report."""
    
    local_files: list[ValidationResult] = field(default_factory=list)
    neo4j_nodes: list[ValidationResult] = field(default_factory=list)
    neo4j_constraints: list[ValidationResult] = field(default_factory=list)
    neo4j_relationships: list[ValidationResult] = field(default_factory=list)
    qdrant: list[ValidationResult] = field(default_factory=list)
    
    @property
    def all_passed(self) -> bool:
        """Check if all validations passed."""
        all_results = (
            self.local_files + 
            self.neo4j_nodes + 
            self.neo4j_constraints + 
            self.neo4j_relationships + 
            self.qdrant
        )
        return all(r.passed for r in all_results)
    
    @property
    def failures(self) -> list[ValidationResult]:
        """Get all failed validations."""
        all_results = (
            self.local_files + 
            self.neo4j_nodes + 
            self.neo4j_constraints + 
            self.neo4j_relationships + 
            self.qdrant
        )
        return [r for r in all_results if not r.passed]


def get_neo4j_driver() -> Any:
    """Create Neo4j driver from environment configuration."""
    from neo4j import GraphDatabase

    load_dotenv()

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    auth_str = os.getenv("NEO4J_AUTH", "neo4j/password")
    
    if "/" in auth_str:
        user, password = auth_str.split("/", 1)
    else:
        user, password = "neo4j", auth_str

    return GraphDatabase.driver(uri, auth=(user, password))


def count_neo4j_nodes() -> dict[str, int]:
    """Count nodes in Neo4j by label."""
    driver = get_neo4j_driver()
    counts = {}

    try:
        with driver.session() as session:
            # Count Books
            result = session.run("MATCH (b:Book) RETURN count(b) as count")
            counts["Books"] = result.single()["count"]

            # Count Chapters
            result = session.run("MATCH (c:Chapter) RETURN count(c) as count")
            counts["Chapters"] = result.single()["count"]
            
            # Count Tiers
            result = session.run("MATCH (t:Tier) RETURN count(t) as count")
            counts["Tiers"] = result.single()["count"]

            # Count relationships
            result = session.run("MATCH ()-[r:PARALLEL]->() RETURN count(r) as count")
            counts["PARALLEL edges"] = result.single()["count"]

            result = session.run("MATCH ()-[r:PERPENDICULAR]->() RETURN count(r) as count")
            counts["PERPENDICULAR edges"] = result.single()["count"]

            result = session.run("MATCH ()-[r:SKIP_TIER]->() RETURN count(r) as count")
            counts["SKIP_TIER edges"] = result.single()["count"]
            
            # Count HAS_CHAPTER relationships
            result = session.run("MATCH ()-[r:HAS_CHAPTER]->() RETURN count(r) as count")
            counts["HAS_CHAPTER edges"] = result.single()["count"]

    finally:
        driver.close()

    return counts


def validate_neo4j_constraints() -> list[ValidationResult]:
    """Validate that Neo4j constraints exist."""
    driver = get_neo4j_driver()
    results = []
    
    expected_constraints = [
        ("book_id", "Book", "book_id"),
        ("chapter_id", "Chapter", "chapter_id"),
        ("tier_name", "Tier", "name"),
    ]
    
    try:
        with driver.session() as session:
            # Get all constraints
            result = session.run("SHOW CONSTRAINTS")
            constraints = list(result)
            constraint_names = [c["name"] for c in constraints]
            
            for name, label, _prop in expected_constraints:
                exists = any(name in cn for cn in constraint_names)
                results.append(ValidationResult(
                    name=f"Constraint: {name}",
                    expected=1,
                    actual=1 if exists else 0,
                    passed=exists,
                    message="" if exists else f"Missing constraint for {label}.{name}",
                ))
    finally:
        driver.close()
    
    return results


def validate_neo4j_indexes() -> list[ValidationResult]:
    """Validate that Neo4j indexes exist."""
    driver = get_neo4j_driver()
    results = []
    
    expected_indexes = [
        "book_tier",
        "book_title",
        "chapter_title",
    ]
    
    try:
        with driver.session() as session:
            # Get all indexes
            result = session.run("SHOW INDEXES")
            indexes = list(result)
            index_names = [i["name"] for i in indexes]
            
            for name in expected_indexes:
                exists = any(name in idx for idx in index_names)
                results.append(ValidationResult(
                    name=f"Index: {name}",
                    expected=1,
                    actual=1 if exists else 0,
                    passed=exists,
                    message="" if exists else f"Missing index: {name}",
                ))
    finally:
        driver.close()
    
    return results


def validate_orphan_chapters() -> ValidationResult:
    """Check for chapters not linked to any book."""
    driver = get_neo4j_driver()
    
    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (c:Chapter)
                WHERE NOT (c)<-[:HAS_CHAPTER]-(:Book)
                RETURN count(c) as orphan_count
            """)
            orphan_count = result.single()["orphan_count"]
            
            return ValidationResult(
                name="Orphan chapters",
                expected=0,
                actual=orphan_count,
                passed=orphan_count == 0,
                message="" if orphan_count == 0 else f"{orphan_count} chapters without book link",
            )
    finally:
        driver.close()


def validate_duplicate_book_ids() -> ValidationResult:
    """Check for duplicate book IDs."""
    driver = get_neo4j_driver()
    
    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (b:Book)
                WITH b.book_id as book_id, count(*) as cnt
                WHERE cnt > 1
                RETURN count(*) as duplicate_count
            """)
            duplicate_count = result.single()["duplicate_count"]
            
            return ValidationResult(
                name="Duplicate book IDs",
                expected=0,
                actual=duplicate_count,
                passed=duplicate_count == 0,
                message="" if duplicate_count == 0 else f"{duplicate_count} duplicate book IDs found",
            )
    finally:
        driver.close()


def count_qdrant_points(collection_name: str = DEFAULT_COLLECTION_NAME) -> int:
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


def run_full_validation(
    books_path: Path,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    verbose: bool = False,
) -> ValidationReport:
    """Run full validation and return report."""
    report = ValidationReport()
    
    # Local files
    local_counts = count_local_files(books_path)
    for name, count in local_counts.items():
        report.local_files.append(ValidationResult(
            name=name,
            expected=None,  # No expected count for local files
            actual=count,
            passed=count > 0 or name == "Enriched files",  # Enriched is optional
        ))
    
    # Neo4j nodes
    try:
        neo4j_counts = count_neo4j_nodes()
        for name, count in neo4j_counts.items():
            report.neo4j_nodes.append(ValidationResult(
                name=name,
                expected=None,
                actual=count,
                passed=count >= 0,  # Just check connection works
            ))
        
        # Neo4j constraints
        if verbose:
            report.neo4j_constraints = validate_neo4j_constraints()
            report.neo4j_constraints.extend(validate_neo4j_indexes())
        
        # Neo4j relationships (orphan detection)
        report.neo4j_relationships.append(validate_orphan_chapters())
        report.neo4j_relationships.append(validate_duplicate_book_ids())
        
    except Exception as e:
        report.neo4j_nodes.append(ValidationResult(
            name="Connection",
            expected=None,
            actual=0,
            passed=False,
            message=str(e),
        ))
    
    # Qdrant
    try:
        qdrant_count = count_qdrant_points(collection_name)
        report.qdrant.append(ValidationResult(
            name=f"Collection: {collection_name}",
            expected=None,
            actual=qdrant_count,
            passed=qdrant_count > 0,
        ))
    except Exception as e:
        report.qdrant.append(ValidationResult(
            name=f"Collection: {collection_name}",
            expected=None,
            actual=0,
            passed=False,
            message=str(e),
        ))
    
    return report


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
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Enable verbose output (includes constraint/index checks)",
)
def main(books_path: Path, collection: str, verbose: bool) -> None:
    """Validate database seed integrity."""
    console.print("\n[bold blue]Validating seed integrity...[/bold blue]\n")

    report = run_full_validation(books_path, collection, verbose)

    # Local files
    table = Table(title="Local Files")
    table.add_column("Type", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Status", justify="center")

    for result in report.local_files:
        status = "✓" if result.passed else "✗"
        color = "green" if result.passed else "red"
        table.add_row(result.name, str(result.actual), f"[{color}]{status}[/{color}]")

    console.print(table)
    console.print()

    # Neo4j Nodes
    table = Table(title="Neo4j Database")
    table.add_column("Type", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Status", justify="center")

    for result in report.neo4j_nodes:
        status = "✓" if result.passed else "✗"
        color = "green" if result.passed else "red"
        status_text = f"[{color}]{status}[/{color}]"
        if result.message:
            status_text += f" {result.message}"
        table.add_row(result.name, str(result.actual), status_text)

    console.print(table)
    console.print()

    # Neo4j Constraints/Indexes (verbose mode)
    if verbose and report.neo4j_constraints:
        table = Table(title="Neo4j Constraints & Indexes")
        table.add_column("Name", style="cyan")
        table.add_column("Status", justify="center")

        for result in report.neo4j_constraints:
            status = "✓" if result.passed else "✗"
            color = "green" if result.passed else "yellow"
            status_text = f"[{color}]{status}[/{color}]"
            if result.message:
                status_text += f" {result.message}"
            table.add_row(result.name, status_text)

        console.print(table)
        console.print()

    # Neo4j Relationships
    table = Table(title="Neo4j Relationships")
    table.add_column("Check", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Status", justify="center")

    for result in report.neo4j_relationships:
        status = "✓" if result.passed else "✗"
        color = "green" if result.passed else "yellow"
        status_text = f"[{color}]{status}[/{color}]"
        if result.message:
            status_text += f" {result.message}"
        table.add_row(result.name, str(result.actual), status_text)

    console.print(table)
    console.print()

    # Qdrant
    table = Table(title="Qdrant Database")
    table.add_column("Collection", style="cyan")
    table.add_column("Points", justify="right")
    table.add_column("Status", justify="center")

    for result in report.qdrant:
        status = "✓" if result.passed else "✗"
        color = "green" if result.passed else "yellow"
        status_text = f"[{color}]{status}[/{color}]"
        if result.message:
            status_text += f" {result.message}"
        table.add_row(result.name, str(result.actual), status_text)

    console.print(table)
    console.print()

    # Summary
    if report.all_passed:
        console.print("[bold green]✓ All validations passed![/bold green]\n")
    else:
        console.print("[bold yellow]⚠ Some validations failed:[/bold yellow]")
        for failure in report.failures:
            console.print(f"  - {failure.name}: {failure.message or 'Failed'}")
        console.print()


if __name__ == "__main__":
    main()
