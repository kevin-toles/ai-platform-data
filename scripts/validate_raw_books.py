"""Validate raw book data integrity.

Phase 3.5.2: Data Transfer & Validation - REFACTOR phase.
WBS Tasks: 3.5.2.6 (validate_raw_books.py)

This script validates:
1. All books have non-empty chapters arrays
2. Chapter structure meets schema requirements (number/chapter_number, title, pages)
3. Page ranges are valid (start_page <= end_page)
4. Chapter coverage (detect significant gaps)

Anti-Pattern Audit:
- Per CODING_PATTERNS #1.3: No magic values (constants extracted)
- Per CODING_PATTERNS #2: Cognitive complexity < 15 (functions decomposed)
- Per Category 1.1: All functions have type annotations
- Per S1192: String literals extracted to constants

Cross-References:
- AI_CODING_PLATFORM_ARCHITECTURE: book_raw.schema.json chapter definition
- GUIDELINES_AI_Engineering: Segment 2 (data pipelines)
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
DEFAULT_BOOKS_PATH = Path(__file__).parent.parent / "books" / "raw"
REQUIRED_BASE_FIELDS = {"title", "start_page", "end_page"}
CHAPTER_NUMBER_FIELDS = {"number", "chapter_number"}
SIGNIFICANT_GAP_THRESHOLD = 10  # Pages


@dataclass
class ChapterIssue:
    """An issue found with a chapter."""
    
    book_name: str
    chapter_num: int
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
    def total_chapters(self) -> int:
        return sum(r.chapter_count for r in self.results)
    
    @property
    def all_passed(self) -> bool:
        return self.failed_count == 0


def validate_chapter_fields(
    chapter: dict[str, Any], 
    chapter_idx: int, 
    book_name: str
) -> list[ChapterIssue]:
    """Validate a single chapter's required fields."""
    issues: list[ChapterIssue] = []
    chapter_keys = set(chapter.keys())
    
    # Check base required fields
    missing_base = REQUIRED_BASE_FIELDS - chapter_keys
    if missing_base:
        issues.append(ChapterIssue(
            book_name=book_name,
            chapter_num=chapter_idx + 1,
            issue_type="missing_fields",
            details=f"Missing: {', '.join(sorted(missing_base))}"
        ))
    
    # Check anyOf: number OR chapter_number
    has_identifier = bool(chapter_keys & CHAPTER_NUMBER_FIELDS)
    if not has_identifier:
        issues.append(ChapterIssue(
            book_name=book_name,
            chapter_num=chapter_idx + 1,
            issue_type="missing_identifier",
            details="Missing: number or chapter_number"
        ))
    
    return issues


def validate_page_ranges(
    chapter: dict[str, Any], 
    chapter_idx: int, 
    book_name: str
) -> list[ChapterIssue]:
    """Validate chapter page ranges."""
    issues: list[ChapterIssue] = []
    
    start = chapter.get("start_page", 0)
    end = chapter.get("end_page", 0)
    
    if start <= 0 or end <= 0:
        issues.append(ChapterIssue(
            book_name=book_name,
            chapter_num=chapter_idx + 1,
            issue_type="invalid_pages",
            details=f"Invalid page numbers: start={start}, end={end}"
        ))
    elif start > end:
        issues.append(ChapterIssue(
            book_name=book_name,
            chapter_num=chapter_idx + 1,
            issue_type="invalid_range",
            details=f"start_page ({start}) > end_page ({end})"
        ))
    
    return issues


def find_chapter_gaps(
    chapters: list[dict[str, Any]], 
    book_name: str
) -> list[ChapterIssue]:
    """Find significant gaps between chapters."""
    issues: list[ChapterIssue] = []
    
    if len(chapters) < 2:
        return issues
    
    # Sort by start_page
    sorted_chapters = sorted(chapters, key=lambda c: c.get("start_page", 0))
    
    for i in range(len(sorted_chapters) - 1):
        current_end = sorted_chapters[i].get("end_page", 0)
        next_start = sorted_chapters[i + 1].get("start_page", 0)
        gap = next_start - current_end - 1
        
        if gap > SIGNIFICANT_GAP_THRESHOLD:
            issues.append(ChapterIssue(
                book_name=book_name,
                chapter_num=i + 1,
                issue_type="gap",
                details=f"{gap} page gap between chapters {i + 1} and {i + 2}"
            ))
    
    return issues


def validate_book(book_path: Path) -> BookValidationResult:
    """Validate a single book file."""
    with open(book_path, encoding="utf-8") as f:
        data = json.load(f)
    
    chapters = data.get("chapters", [])
    result = BookValidationResult(
        book_name=book_path.name,
        chapter_count=len(chapters)
    )
    
    # Empty chapters is an issue
    if not chapters:
        result.issues.append(ChapterIssue(
            book_name=book_path.name,
            chapter_num=0,
            issue_type="empty_chapters",
            details="No chapters found"
        ))
        return result
    
    # Validate each chapter
    for i, chapter in enumerate(chapters):
        result.issues.extend(validate_chapter_fields(chapter, i, book_path.name))
        result.issues.extend(validate_page_ranges(chapter, i, book_path.name))
    
    # Check for gaps
    result.issues.extend(find_chapter_gaps(chapters, book_path.name))
    
    return result


def validate_all_books(books_dir: Path) -> ValidationReport:
    """Validate all books in directory."""
    report = ValidationReport()
    
    book_files = sorted(books_dir.glob("*.json"))
    if not book_files:
        console.print(f"[yellow]Warning: No JSON files found in {books_dir}[/yellow]")
        return report
    
    for book_path in book_files:
        result = validate_book(book_path)
        report.results.append(result)
    
    return report


def print_report(report: ValidationReport, verbose: bool = False) -> None:
    """Print validation report using rich tables."""
    # Summary table
    summary_table = Table(title="📚 Raw Books Validation Summary")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="green")
    
    summary_table.add_row("Total Books", str(report.total_books))
    summary_table.add_row("Total Chapters", str(report.total_chapters))
    summary_table.add_row("Passed", str(report.passed_count))
    summary_table.add_row("Failed", str(report.failed_count))
    
    console.print(summary_table)
    console.print()
    
    # Failed books detail
    if report.failed_count > 0:
        issues_table = Table(title="❌ Validation Issues")
        issues_table.add_column("Book", style="red")
        issues_table.add_column("Chapter", style="yellow")
        issues_table.add_column("Issue Type", style="magenta")
        issues_table.add_column("Details", style="white")
        
        for result in report.results:
            if not result.passed:
                for issue in result.issues:
                    issues_table.add_row(
                        issue.book_name,
                        str(issue.chapter_num) if issue.chapter_num > 0 else "-",
                        issue.issue_type,
                        issue.details
                    )
        
        console.print(issues_table)
    else:
        console.print("[green]✅ All books validated successfully![/green]")
    
    # Verbose output: show all books
    if verbose:
        console.print()
        details_table = Table(title="📖 Book Details")
        details_table.add_column("Book", style="cyan")
        details_table.add_column("Chapters", style="green")
        details_table.add_column("Status", style="white")
        
        for result in sorted(report.results, key=lambda r: r.book_name):
            status = "✅" if result.passed else f"❌ ({len(result.issues)} issues)"
            details_table.add_row(
                result.book_name,
                str(result.chapter_count),
                status
            )
        
        console.print(details_table)


@click.command()
@click.option(
    "--books-dir",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_BOOKS_PATH,
    help="Path to books/raw directory"
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show detailed output for all books"
)
@click.option(
    "--fail-on-issues",
    is_flag=True,
    help="Exit with code 1 if any issues found"
)
def main(books_dir: Path, verbose: bool, fail_on_issues: bool) -> None:
    """Validate raw book JSON files in ai-platform-data.
    
    Checks:
    - All books have non-empty chapters
    - Chapter structure meets schema (number/chapter_number, title, pages)
    - Page ranges are valid
    - No significant gaps between chapters
    """
    console.print(f"[cyan]Validating books in: {books_dir}[/cyan]")
    console.print()
    
    report = validate_all_books(books_dir)
    print_report(report, verbose=verbose)
    
    if fail_on_issues and not report.all_passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
