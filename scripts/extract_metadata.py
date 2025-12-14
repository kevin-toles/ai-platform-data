"""Extract metadata from raw books for Neo4j seeding.

Phase 3.1: Seeding Pipeline - GREEN phase implementation.
WBS Tasks: 3.1.2 (seed_neo4j.py prerequisites)

This script extracts metadata from raw JSON books in books/raw/ and creates
standardized metadata files in books/metadata/ for Neo4j seeding.

Anti-Pattern Audit:
- Per Issue #2.2 (Long parameter lists): Use dataclass for config
- Per Category 1.1 (Type annotations): All functions annotated
- Per Category 2 (Cognitive complexity): Functions under 15 complexity
- Per S1192: String literals extracted to constants
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

import click
from rich.console import Console
from rich.progress import Progress

console = Console()
logger = logging.getLogger(__name__)

# Constants per CODING_PATTERNS_ANALYSIS.md S1192
DEFAULT_RAW_PATH = Path(__file__).parent.parent / "books" / "raw"
DEFAULT_METADATA_PATH = Path(__file__).parent.parent / "books" / "metadata"
TAXONOMY_PATH = Path(__file__).parent.parent / "taxonomies" / "AI-ML_taxonomy_20251128.json"


@dataclass
class ExtractionConfig:
    """Configuration for metadata extraction.
    
    Per Issue #2.2: Use dataclass instead of long parameter lists.
    """
    
    raw_path: Path = field(default_factory=lambda: DEFAULT_RAW_PATH)
    metadata_path: Path = field(default_factory=lambda: DEFAULT_METADATA_PATH)
    taxonomy_path: Path = field(default_factory=lambda: TAXONOMY_PATH)
    overwrite: bool = False
    verbose: bool = False


@dataclass
class BookMetadata:
    """Extracted book metadata for Neo4j seeding.
    
    Per CODING_PATTERNS_ANALYSIS: Use dataclass for structured data.
    """
    
    book_id: str
    title: str
    author: str
    tier: int | None = None
    priority: float | None = None
    chapters: list[dict[str, Any]] = field(default_factory=list)
    source_file: str = ""
    extraction_date: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def generate_book_id(title: str) -> str:
    """Generate a unique book ID from title.
    
    Uses SHA-256 hash prefix for uniqueness.
    """
    # Clean title for ID generation
    clean_title = re.sub(r"[^a-zA-Z0-9\s]", "", title.lower())
    clean_title = re.sub(r"\s+", "_", clean_title.strip())
    
    # Add hash prefix for uniqueness
    hash_prefix = hashlib.sha256(title.encode()).hexdigest()[:8]
    
    return f"{clean_title[:50]}_{hash_prefix}"


def generate_chapter_id(book_id: str, chapter_number: int, chapter_title: str) -> str:
    """Generate a unique chapter ID.
    
    Format: {book_id}_ch{number}_{hash}
    """
    content = f"{book_id}_{chapter_number}_{chapter_title}"
    hash_suffix = hashlib.sha256(content.encode()).hexdigest()[:6]
    
    return f"{book_id}_ch{chapter_number:03d}_{hash_suffix}"


def extract_book_metadata(raw_book: dict[str, Any], source_file: str) -> BookMetadata:
    """Extract metadata from a raw book JSON structure.
    
    Per Category 2: Keep complexity under 15 by extracting helper functions.
    """
    # Extract basic metadata
    metadata_section = raw_book.get("metadata", {})
    
    title = metadata_section.get("title", "Unknown Title")
    author = metadata_section.get("author", "Unknown Author")
    
    book_id = generate_book_id(title)
    
    # Extract chapters with IDs
    chapters = []
    raw_chapters = raw_book.get("chapters", [])
    
    for i, chapter in enumerate(raw_chapters, start=1):
        chapter_number = chapter.get("number", i)
        chapter_title = chapter.get("title", f"Chapter {chapter_number}")
        
        chapter_id = generate_chapter_id(book_id, chapter_number, chapter_title)
        
        chapters.append({
            "chapter_id": chapter_id,
            "number": chapter_number,
            "title": chapter_title,
            "start_page": chapter.get("start_page"),
            "end_page": chapter.get("end_page"),
        })
    
    return BookMetadata(
        book_id=book_id,
        title=title,
        author=author,
        chapters=chapters,
        source_file=source_file,
    )


def load_taxonomy(taxonomy_path: Path) -> dict[str, dict[str, Any]]:
    """Load taxonomy and create title-to-tier mapping.
    
    Returns dict mapping book titles to tier info.
    """
    if not taxonomy_path.exists():
        logger.warning(f"Taxonomy file not found: {taxonomy_path}")
        return {}
    
    with open(taxonomy_path) as f:
        taxonomy = json.load(f)
    
    # Build title -> tier mapping
    title_mapping: dict[str, dict[str, Any]] = {}
    
    # Navigate taxonomy structure to find books
    for domain in taxonomy.get("domains", []):
        for subdomain in domain.get("subdomains", []):
            for book in subdomain.get("books", []):
                book_title = book.get("title", "")
                tier = book.get("tier", None)
                priority = book.get("priority", None)
                
                if book_title:
                    title_mapping[book_title.lower()] = {
                        "tier": tier,
                        "priority": priority,
                    }
    
    return title_mapping


def apply_taxonomy_tiers(
    metadata: BookMetadata,
    taxonomy_mapping: dict[str, dict[str, Any]],
) -> BookMetadata:
    """Apply tier information from taxonomy to book metadata."""
    title_lower = metadata.title.lower()
    
    # Try exact match first
    if title_lower in taxonomy_mapping:
        tier_info = taxonomy_mapping[title_lower]
        metadata.tier = tier_info.get("tier")
        metadata.priority = tier_info.get("priority")
        return metadata
    
    # Try partial match
    for taxonomy_title, tier_info in taxonomy_mapping.items():
        if taxonomy_title in title_lower or title_lower in taxonomy_title:
            metadata.tier = tier_info.get("tier")
            metadata.priority = tier_info.get("priority")
            return metadata
    
    # Default tier for unmatched books
    metadata.tier = 3  # Default to implementation tier
    metadata.priority = 0.5
    
    return metadata


def extract_all_metadata(
    config: ExtractionConfig,
) -> Generator[tuple[BookMetadata, Path], None, None]:
    """Extract metadata from all raw books.
    
    Per AsyncIterator pattern: Use generator for streaming results.
    """
    if not config.raw_path.exists():
        logger.error(f"Raw books path does not exist: {config.raw_path}")
        return
    
    # Load taxonomy for tier mapping
    taxonomy_mapping = load_taxonomy(config.taxonomy_path)
    
    for raw_file in config.raw_path.glob("*.json"):
        if raw_file.name.startswith("."):
            continue
        
        try:
            with open(raw_file) as f:
                raw_book = json.load(f)
            
            metadata = extract_book_metadata(raw_book, raw_file.name)
            metadata = apply_taxonomy_tiers(metadata, taxonomy_mapping)
            
            # Determine output path
            output_file = config.metadata_path / f"{metadata.book_id}.json"
            
            yield metadata, output_file
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse {raw_file.name}: {e}")
        except Exception as e:
            logger.error(f"Error processing {raw_file.name}: {e}")


def save_metadata(metadata: BookMetadata, output_path: Path) -> None:
    """Save metadata to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    data = {
        "book_id": metadata.book_id,
        "title": metadata.title,
        "author": metadata.author,
        "tier": metadata.tier,
        "priority": metadata.priority,
        "chapters": metadata.chapters,
        "source_file": metadata.source_file,
        "extraction_date": metadata.extraction_date,
    }
    
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)


@click.command()
@click.option(
    "--raw-path",
    type=click.Path(path_type=Path),
    default=DEFAULT_RAW_PATH,
    help="Path to raw books directory",
)
@click.option(
    "--metadata-path",
    type=click.Path(path_type=Path),
    default=DEFAULT_METADATA_PATH,
    help="Path to output metadata directory",
)
@click.option(
    "--taxonomy-path",
    type=click.Path(path_type=Path),
    default=TAXONOMY_PATH,
    help="Path to taxonomy JSON file",
)
@click.option(
    "--overwrite",
    is_flag=True,
    default=False,
    help="Overwrite existing metadata files",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Enable verbose output",
)
def main(
    raw_path: Path,
    metadata_path: Path,
    taxonomy_path: Path,
    overwrite: bool,
    verbose: bool,
) -> None:
    """Extract metadata from raw books for Neo4j seeding."""
    config = ExtractionConfig(
        raw_path=raw_path,
        metadata_path=metadata_path,
        taxonomy_path=taxonomy_path,
        overwrite=overwrite,
        verbose=verbose,
    )
    
    console.print(f"\n[bold blue]Extracting metadata from {config.raw_path}[/bold blue]\n")
    
    extracted_count = 0
    skipped_count = 0
    
    with Progress() as progress:
        # Count total files first
        total_files = len(list(config.raw_path.glob("*.json")))
        task = progress.add_task("[green]Extracting...", total=total_files)
        
        for metadata, output_path in extract_all_metadata(config):
            if output_path.exists() and not config.overwrite:
                if verbose:
                    console.print(f"  [yellow]Skipped[/yellow]: {metadata.title}")
                skipped_count += 1
            else:
                save_metadata(metadata, output_path)
                if verbose:
                    console.print(f"  [green]✓[/green] {metadata.title}")
                extracted_count += 1
            
            progress.update(task, advance=1)
    
    console.print(f"\n[bold green]Extraction complete![/bold green]")
    console.print(f"  Extracted: {extracted_count}")
    console.print(f"  Skipped:   {skipped_count}")
    console.print(f"  Output:    {config.metadata_path}")


if __name__ == "__main__":
    main()
