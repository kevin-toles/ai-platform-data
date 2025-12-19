"""Validate enriched book data integrity.

Phase 3.5.4: Enriched Data Transfer & Validation - REFACTOR phase.
WBS Tasks: 3.5.4.8-9 (validate_enriched_books.py CLI)

This script validates:
1. Enriched directory contains 47 books
2. All chapters have keywords, concepts, summary fields
3. All chapters have similar_chapters with method field (sentence_transformers)
4. Required top-level keys present: metadata, chapters, pages, enrichment

Anti-Pattern Audit:
- Per CODING_PATTERNS #1.3: No magic values (constants extracted)
- Per CODING_PATTERNS #2: Cognitive complexity < 15 (functions decomposed)
- Per Category 1.1: All functions have type annotations
- Per S1192: String literals extracted to constants

Cross-References:
- AI_CODING_PLATFORM_ARCHITECTURE: book_enriched.schema.json definition
- GUIDELINES_AI_Engineering: Segment 2 (data pipelines)
- WBS 3.5.3.7: similar_chapters SBERT implementation
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

console = Console()

# Constants per CODING_PATTERNS_ANALYSIS.md S1192
DEFAULT_BOOKS_PATH = Path(__file__).parent.parent / "books" / "enriched"
EXPECTED_BOOK_COUNT = 47
REQUIRED_TOP_LEVEL_KEYS = {"metadata", "chapters", "pages", "enrichment", "enrichment_metadata"}
REQUIRED_CHAPTER_KEYS = {"title", "keywords", "concepts", "summary", "similar_chapters"}
# Valid methods per book_enriched_chapters.schema.json similar_chapters[].method enum
VALID_SIMILAR_CHAPTER_METHODS = {
    "sbert",
    "tfidf",
    "bertopic",
    "hybrid",
    "cosine_similarity",
    "api",
    "multi-signal",
    "sentence_transformers",  # Legacy support
}

# D2.2 - Enrichment Provenance Fields per DATA_PIPELINE_FIX_WBS.md
REQUIRED_PROVENANCE_FIELDS = {
    "taxonomy_id",
    "taxonomy_version",
    "taxonomy_path",
    "taxonomy_checksum",
    "source_metadata_file",
    "enrichment_date",
    "enrichment_method",
    "model_version",
}
NAMING_CONVENTION_SUFFIX = "_metadata_enriched.json"
TAXONOMY_CHECKSUM_PREFIX = "sha256:"
VALID_ENRICHMENT_METHODS = {"llm_enrichment", "cross_book_similarity", "hybrid"}


@dataclass
class ChapterIssue:
    """An issue found with a chapter."""
    
    book_name: str
    chapter_idx: int
    issue_type: str
    details: str


@dataclass
class BookValidationResult:
    """Validation result for a single book."""
    
    book_name: str
    chapter_count: int
    issues: list[ChapterIssue] = field(default_factory=list)
    
    @property
    def passed(self) -> bool:
        """Book passes if no issues and has chapters."""
        return len(self.issues) == 0 and self.chapter_count > 0


@dataclass
class ValidationReport:
    """Complete validation report for all books."""
    
    results: list[BookValidationResult] = field(default_factory=list)
    
    @property
    def total_books(self) -> int:
        return len(self.results)
    
    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed)
    
    @property
    def failed_count(self) -> int:
        return self.total_books - self.passed_count
    
    @property
    def total_issues(self) -> int:
        return sum(len(r.issues) for r in self.results)


def _validate_top_level_keys(data: dict[str, Any], book_name: str) -> list[ChapterIssue]:
    """Validate required top-level keys exist."""
    issues: list[ChapterIssue] = []
    keys = set(data.keys())
    missing = REQUIRED_TOP_LEVEL_KEYS - keys
    
    if missing:
        issues.append(ChapterIssue(
            book_name=book_name,
            chapter_idx=-1,
            issue_type="missing_top_level_key",
            details=f"Missing keys: {sorted(missing)}"
        ))
    
    return issues


def _validate_chapter_fields(
    chapter: dict[str, Any],
    chapter_idx: int,
    book_name: str
) -> list[ChapterIssue]:
    """Validate a single chapter has required fields."""
    issues: list[ChapterIssue] = []
    keys = set(chapter.keys())
    
    # Check required keys
    missing = REQUIRED_CHAPTER_KEYS - keys
    if missing:
        issues.append(ChapterIssue(
            book_name=book_name,
            chapter_idx=chapter_idx,
            issue_type="missing_chapter_field",
            details=f"Missing: {sorted(missing)}"
        ))
        return issues  # Can't validate further without fields
    
    # Validate keywords is a list
    if not isinstance(chapter.get("keywords"), list):
        issues.append(ChapterIssue(
            book_name=book_name,
            chapter_idx=chapter_idx,
            issue_type="invalid_keywords",
            details="keywords must be a list"
        ))
    
    # Validate concepts is a list
    if not isinstance(chapter.get("concepts"), list):
        issues.append(ChapterIssue(
            book_name=book_name,
            chapter_idx=chapter_idx,
            issue_type="invalid_concepts",
            details="concepts must be a list"
        ))
    
    # Validate summary is a string
    if not isinstance(chapter.get("summary"), str):
        issues.append(ChapterIssue(
            book_name=book_name,
            chapter_idx=chapter_idx,
            issue_type="invalid_summary",
            details="summary must be a string"
        ))
    
    # Validate similar_chapters
    similar = chapter.get("similar_chapters")
    if not isinstance(similar, list):
        issues.append(ChapterIssue(
            book_name=book_name,
            chapter_idx=chapter_idx,
            issue_type="invalid_similar_chapters",
            details="similar_chapters must be a list"
        ))
    elif similar:  # Non-empty list - check method field
        for i, item in enumerate(similar):
            method = item.get("method")
            if method not in VALID_SIMILAR_CHAPTER_METHODS:
                issues.append(ChapterIssue(
                    book_name=book_name,
                    chapter_idx=chapter_idx,
                    issue_type="wrong_method",
                    details=f"similar_chapters[{i}].method={method}, expected one of {VALID_SIMILAR_CHAPTER_METHODS}"
                ))
                break  # Report once per chapter
    
    return issues


def _validate_enrichment_metadata(
    data: dict[str, Any],
    book_name: str
) -> list[ChapterIssue]:
    """Validate enrichment_metadata provenance fields.
    
    D2.2 - DATA_PIPELINE_FIX_WBS.md Phase D2.2
    Validates presence and format of enrichment provenance fields.
    """
    issues: list[ChapterIssue] = []
    
    enrichment_metadata = data.get("enrichment_metadata")
    if enrichment_metadata is None:
        issues.append(ChapterIssue(
            book_name=book_name,
            chapter_idx=-1,
            issue_type="missing_enrichment_metadata",
            details="Missing enrichment_metadata section"
        ))
        return issues
    
    if not isinstance(enrichment_metadata, dict):
        issues.append(ChapterIssue(
            book_name=book_name,
            chapter_idx=-1,
            issue_type="invalid_enrichment_metadata",
            details="enrichment_metadata must be a dict"
        ))
        return issues
    
    # Check all required provenance fields
    keys = set(enrichment_metadata.keys())
    missing = REQUIRED_PROVENANCE_FIELDS - keys
    if missing:
        issues.append(ChapterIssue(
            book_name=book_name,
            chapter_idx=-1,
            issue_type="missing_provenance_fields",
            details=f"Missing fields: {sorted(missing)}"
        ))
    
    # Validate taxonomy_checksum format (must start with sha256:)
    checksum = enrichment_metadata.get("taxonomy_checksum", "")
    if checksum and not checksum.startswith(TAXONOMY_CHECKSUM_PREFIX):
        issues.append(ChapterIssue(
            book_name=book_name,
            chapter_idx=-1,
            issue_type="invalid_checksum_format",
            details=f"taxonomy_checksum must start with '{TAXONOMY_CHECKSUM_PREFIX}'"
        ))
    
    # Validate enrichment_method is one of valid values
    method = enrichment_metadata.get("enrichment_method", "")
    if method and method not in VALID_ENRICHMENT_METHODS:
        issues.append(ChapterIssue(
            book_name=book_name,
            chapter_idx=-1,
            issue_type="invalid_enrichment_method",
            details=f"enrichment_method must be one of: {sorted(VALID_ENRICHMENT_METHODS)}"
        ))
    
    # Validate source_metadata_file is non-empty string
    source_file = enrichment_metadata.get("source_metadata_file", "")
    if not source_file or not isinstance(source_file, str):
        issues.append(ChapterIssue(
            book_name=book_name,
            chapter_idx=-1,
            issue_type="invalid_source_metadata_file",
            details="source_metadata_file must be a non-empty string"
        ))
    
    return issues


def _validate_naming_convention(file_path: Path) -> list[ChapterIssue]:
    """Validate file follows naming convention.
    
    D2.2 - DATA_PIPELINE_FIX_WBS.md Phase D2.2
    Files should be named {Book Title}_metadata_enriched.json
    """
    issues: list[ChapterIssue] = []
    book_name = file_path.stem
    
    if not file_path.name.endswith(NAMING_CONVENTION_SUFFIX):
        issues.append(ChapterIssue(
            book_name=book_name,
            chapter_idx=-1,
            issue_type="invalid_naming_convention",
            details=f"File must end with '{NAMING_CONVENTION_SUFFIX}', got '{file_path.name}'"
        ))
    
    return issues


def validate_book(file_path: Path) -> BookValidationResult:
    """Validate a single enriched book file."""
    book_name = file_path.stem
    issues: list[ChapterIssue] = []
    
    # D2.2 - Validate naming convention first
    issues.extend(_validate_naming_convention(file_path))
    
    try:
        with open(file_path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return BookValidationResult(
            book_name=book_name,
            chapter_count=0,
            issues=[ChapterIssue(
                book_name=book_name,
                chapter_idx=-1,
                issue_type="json_error",
                details=str(e)
            )]
        )
    
    # Validate top-level structure
    issues.extend(_validate_top_level_keys(data, book_name))
    
    # D2.2 - Validate enrichment_metadata provenance fields
    issues.extend(_validate_enrichment_metadata(data, book_name))
    
    # Get chapters
    chapters = data.get("chapters", [])
    if not isinstance(chapters, list):
        issues.append(ChapterIssue(
            book_name=book_name,
            chapter_idx=-1,
            issue_type="invalid_chapters",
            details="chapters must be a list"
        ))
        return BookValidationResult(
            book_name=book_name,
            chapter_count=0,
            issues=issues
        )
    
    # Validate each chapter
    for idx, chapter in enumerate(chapters):
        issues.extend(_validate_chapter_fields(chapter, idx, book_name))
    
    return BookValidationResult(
        book_name=book_name,
        chapter_count=len(chapters),
        issues=issues
    )


def validate_enriched_directory(books_path: Path) -> ValidationReport:
    """Validate all enriched books in directory."""
    report = ValidationReport()
    
    json_files = sorted(books_path.glob("*.json"))
    
    for file_path in json_files:
        result = validate_book(file_path)
        report.results.append(result)
    
    return report


def display_report(report: ValidationReport, verbose: bool = False) -> None:
    """Display validation report using rich formatting."""
    console.print()
    console.print("[bold]WBS 3.5.4 Enriched Book Validation Report[/bold]")
    console.print("=" * 50)
    
    # Summary table
    summary_table = Table(title="Summary")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="green")
    
    summary_table.add_row("Total Books", str(report.total_books))
    summary_table.add_row("Expected Books", str(EXPECTED_BOOK_COUNT))
    summary_table.add_row("Passed", str(report.passed_count))
    summary_table.add_row("Failed", str(report.failed_count))
    summary_table.add_row("Total Issues", str(report.total_issues))
    
    console.print(summary_table)
    
    # Count check
    if report.total_books == EXPECTED_BOOK_COUNT:
        console.print(f"\n[green]✓ Book count matches expected: {EXPECTED_BOOK_COUNT}[/green]")
    else:
        console.print(f"\n[red]✗ Book count mismatch: {report.total_books} vs {EXPECTED_BOOK_COUNT}[/red]")
    
    # Failed books detail
    failed = [r for r in report.results if not r.passed]
    if failed:
        console.print("\n[bold red]Failed Books:[/bold red]")
        for result in failed:
            console.print(f"  [red]✗[/red] {result.book_name}")
            for issue in result.issues:
                console.print(f"      [{issue.issue_type}] {issue.details}")
    
    # Verbose: show all books
    if verbose:
        console.print("\n[bold]All Books:[/bold]")
        for result in report.results:
            status = "[green]✓[/green]" if result.passed else "[red]✗[/red]"
            console.print(f"  {status} {result.book_name} ({result.chapter_count} chapters)")
    
    # Final verdict
    console.print()
    if report.passed_count == report.total_books and report.total_books == EXPECTED_BOOK_COUNT:
        console.print("[bold green]✓ All validations passed![/bold green]")
    else:
        console.print("[bold red]✗ Validation failed. See issues above.[/bold red]")


@click.command()
@click.option(
    "--books-path",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_BOOKS_PATH,
    help="Path to enriched books directory"
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show all books, not just failures"
)
@click.option(
    "--json-output",
    is_flag=True,
    help="Output report as JSON"
)
def main(books_path: Path, verbose: bool, json_output: bool) -> None:
    """Validate enriched book data for WBS 3.5.4."""
    report = validate_enriched_directory(books_path)
    
    if json_output:
        # JSON output for CI/CD integration
        output = {
            "total_books": report.total_books,
            "expected_books": EXPECTED_BOOK_COUNT,
            "passed": report.passed_count,
            "failed": report.failed_count,
            "issues": report.total_issues,
            "all_passed": report.passed_count == report.total_books and report.total_books == EXPECTED_BOOK_COUNT,
            "failures": [
                {
                    "book": r.book_name,
                    "issues": [
                        {"type": i.issue_type, "chapter": i.chapter_idx, "details": i.details}
                        for i in r.issues
                    ]
                }
                for r in report.results if not r.passed
            ]
        }
        console.print_json(data=output)
    else:
        display_report(report, verbose=verbose)
    
    # Exit code for CI/CD
    if report.passed_count != report.total_books or report.total_books != EXPECTED_BOOK_COUNT:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
