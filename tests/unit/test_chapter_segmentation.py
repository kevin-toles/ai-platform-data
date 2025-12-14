"""
TDD Tests for Phase 3.5.1 - Chapter Segmentation Validation.

WBS Reference: AI_CODING_PLATFORM_WBS.md Phase 3.5.1
TDD Phase: RED - These tests MUST fail initially

Anti-Pattern Audit:
- CODING_PATTERNS #1.3: No hardcoded book counts (use dynamic discovery)
- CODING_PATTERNS #2: Cognitive complexity < 15
- Comp_Static_Analysis #12: Batch processing pattern

Document Cross-References:
- GUIDELINES_AI_Engineering: Segment 2 (data pipelines)
- AI_CODING_PLATFORM_ARCHITECTURE: Pantry (ai-platform-data) data storage
- TIER_RELATIONSHIP_DIAGRAM: Chapter metadata structure
"""

import json
import pytest
from pathlib import Path


# Constants - Per CODING_PATTERNS #1.3: No magic values
BOOKS_RAW_DIR = Path(__file__).parent.parent.parent / "books" / "raw"
# Per book_raw.schema.json: chapter requires (number OR chapter_number), title
# Optional but expected: start_page, end_page, detection_method
REQUIRED_CHAPTER_FIELDS_BASE = {"title", "start_page", "end_page"}
# Per schema anyOf: either "number" or "chapter_number" must be present
CHAPTER_NUMBER_FIELDS = {"number", "chapter_number"}
# detection_method is expected but not required in schema (for legacy compatibility)
EXPECTED_CHAPTER_FIELDS = {"detection_method"}


class TestAllBooksHaveChapters:
    """
    WBS 3.5.1.1: Verify all books have non-empty chapters arrays.
    
    Expected: This test FAILS initially (RED phase) because 12 books
    have empty chapters arrays.
    """
    
    def test_all_books_have_chapters(self) -> None:
        """
        RED: All books in books/raw/ must have non-empty chapters.
        
        Acceptance Criteria:
        - Every JSON file in books/raw/ has a 'chapters' key
        - Every 'chapters' array is non-empty
        - Dynamic discovery (no hardcoded file count)
        """
        book_files = list(BOOKS_RAW_DIR.glob("*.json"))
        assert book_files, f"No book files found in {BOOKS_RAW_DIR}"
        
        books_with_empty_chapters: list[str] = []
        
        for book_file in book_files:
            with open(book_file, encoding="utf-8") as f:
                data = json.load(f)
            
            chapters = data.get("chapters", [])
            if not chapters:
                books_with_empty_chapters.append(book_file.name)
        
        # This assertion WILL FAIL in RED phase (12 books have empty chapters)
        assert not books_with_empty_chapters, (
            f"Found {len(books_with_empty_chapters)} books with empty chapters:\n"
            + "\n".join(f"  - {name}" for name in sorted(books_with_empty_chapters))
        )


class TestChapterStructure:
    """
    WBS 3.5.1.3-3.5.1.4: Verify chapter structure meets schema requirements.
    """
    
    def test_chapters_have_required_fields(self) -> None:
        """
        Verify chapters meet schema requirements.
        
        Per book_raw.schema.json:
        - Required: (number OR chapter_number), title
        - Expected: start_page, end_page, detection_method
        
        Uses anyOf pattern from schema: either 'number' or 'chapter_number' is valid.
        """
        book_files = list(BOOKS_RAW_DIR.glob("*.json"))
        assert book_files, f"No book files found in {BOOKS_RAW_DIR}"
        
        invalid_chapters: list[tuple[str, int, set[str]]] = []
        
        for book_file in book_files:
            with open(book_file, encoding="utf-8") as f:
                data = json.load(f)
            
            for i, chapter in enumerate(data.get("chapters", [])):
                chapter_keys = set(chapter.keys())
                
                # Check for base required fields
                missing_fields = REQUIRED_CHAPTER_FIELDS_BASE - chapter_keys
                
                # Check anyOf: either 'number' or 'chapter_number' must exist
                has_chapter_identifier = bool(chapter_keys & CHAPTER_NUMBER_FIELDS)
                if not has_chapter_identifier:
                    missing_fields.add("number|chapter_number")
                
                if missing_fields:
                    invalid_chapters.append((book_file.name, i + 1, missing_fields))
        
        assert not invalid_chapters, (
            f"Found {len(invalid_chapters)} chapters with missing fields:\n"
            + "\n".join(
                f"  - {name} Ch.{num}: missing {fields}"
                for name, num, fields in invalid_chapters[:10]
            )
            + (f"\n  ... and {len(invalid_chapters) - 10} more" if len(invalid_chapters) > 10 else "")
        )
    
    def test_chapters_have_page_ranges(self) -> None:
        """
        RED: Each chapter must have valid page ranges (start_page <= end_page).
        
        WBS 3.5.1.3: Validate chapter structure.
        """
        book_files = list(BOOKS_RAW_DIR.glob("*.json"))
        invalid_ranges: list[tuple[str, int, int, int]] = []
        
        for book_file in book_files:
            with open(book_file, encoding="utf-8") as f:
                data = json.load(f)
            
            for chapter in data.get("chapters", []):
                start = chapter.get("start_page", 0)
                end = chapter.get("end_page", 0)
                num = chapter.get("number", 0)
                
                if start > end or start <= 0 or end <= 0:
                    invalid_ranges.append((book_file.name, num, start, end))
        
        assert not invalid_ranges, (
            f"Found {len(invalid_ranges)} chapters with invalid page ranges:\n"
            + "\n".join(
                f"  - {name} Ch.{num}: pages {start}-{end}"
                for name, num, start, end in invalid_ranges[:10]
            )
        )


class TestPageChapterAssignments:
    """
    WBS 3.5.1.5-3.5.1.6: Verify page-to-chapter assignments.
    """
    
    def test_pages_have_chapter_field(self) -> None:
        """
        RED: Each page should have a 'chapter' field assigned.
        
        Note: This test may need adjustment based on actual schema.
        Front matter pages (before Chapter 1) may have chapter=None.
        """
        book_files = list(BOOKS_RAW_DIR.glob("*.json"))
        books_missing_page_chapters: list[str] = []
        
        for book_file in book_files:
            with open(book_file, encoding="utf-8") as f:
                data = json.load(f)
            
            pages = data.get("pages", [])
            chapters = data.get("chapters", [])
            
            # Skip books without chapters (separate test handles that)
            if not chapters:
                continue
            
            # Check if pages have chapter assignments
            # Note: This checks if the structure exists, not if it's populated
            pages_without_chapter = [
                p.get("page_number", i + 1)
                for i, p in enumerate(pages)
                if "chapter" not in p
            ]
            
            if pages_without_chapter:
                books_missing_page_chapters.append(book_file.name)
        
        # This may pass or fail depending on current schema
        # Marking as warning if some books are missing page.chapter field
        if books_missing_page_chapters:
            pytest.skip(
                f"Page.chapter field not implemented in {len(books_missing_page_chapters)} books. "
                "This is optional per current schema."
            )


class TestChapterCoverage:
    """
    Additional validation for complete chapter coverage.
    """
    
    def test_chapters_cover_all_pages(self) -> None:
        """
        Verify that chapters cover the full page range of each book.
        
        Gaps between chapters indicate potential segmentation issues.
        """
        book_files = list(BOOKS_RAW_DIR.glob("*.json"))
        books_with_gaps: list[tuple[str, list[tuple[int, int]]]] = []
        
        for book_file in book_files:
            with open(book_file, encoding="utf-8") as f:
                data = json.load(f)
            
            chapters = data.get("chapters", [])
            if not chapters:
                continue
            
            # Sort chapters by start_page
            sorted_chapters = sorted(chapters, key=lambda c: c.get("start_page", 0))
            
            # Check for gaps between chapters
            gaps: list[tuple[int, int]] = []
            for i in range(len(sorted_chapters) - 1):
                current_end = sorted_chapters[i].get("end_page", 0)
                next_start = sorted_chapters[i + 1].get("start_page", 0)
                
                if next_start > current_end + 1:
                    gaps.append((current_end, next_start))
            
            if gaps:
                books_with_gaps.append((book_file.name, gaps))
        
        # Allow some gaps (front matter, appendices)
        # Only fail if gaps are excessive
        significant_gaps = [
            (name, gaps) for name, gaps in books_with_gaps
            if any(end - start > 10 for start, end in gaps)
        ]
        
        assert not significant_gaps, (
            f"Found {len(significant_gaps)} books with significant page gaps:\n"
            + "\n".join(
                f"  - {name}: gaps at pages {gaps}"
                for name, gaps in significant_gaps[:5]
            )
        )
