"""Data models for Code Reference Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RepoMetadata:
    """Metadata for a mirrored repository."""
    
    id: str
    name: str
    source_url: str
    target_path: str
    domain: str
    tier: str
    priority: int = 5
    owner: str = ""
    license: str = "Unknown"
    languages: list[str] = field(default_factory=list)
    concepts: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    description: str = ""
    why_include: str = ""
    mirrored: bool = False
    indexed: bool = False
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RepoMetadata:
        """Create RepoMetadata from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            source_url=data["source_url"],
            target_path=data["target_path"],
            domain=data["domain"],
            tier=data["tier"],
            priority=data.get("priority", 5),
            owner=data.get("owner", ""),
            license=data.get("license", "Unknown"),
            languages=data.get("languages", []),
            concepts=data.get("concepts", []),
            patterns=data.get("patterns", []),
            tags=data.get("tags", []),
            description=data.get("description", ""),
            why_include=data.get("why_include", ""),
            mirrored=data.get("mirrored", False),
            indexed=data.get("indexed", False),
        )


@dataclass
class CodeChunk:
    """A chunk of code from a repository."""
    
    chunk_id: str
    repo_id: str
    file_path: str
    start_line: int
    end_line: int
    content: str
    language: str = ""
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CodeReference:
    """A code reference with full context."""
    
    chunk: CodeChunk
    full_content: str | None = None
    source_url: str = ""
    repo_metadata: RepoMetadata | None = None
    
    @property
    def citation(self) -> str:
        """Generate citation string for this reference."""
        if self.source_url:
            return self.source_url
        base = "https://github.com/kevin-toles/code-reference-engine/blob/main"
        return f"{base}/{self.chunk.file_path}#L{self.chunk.start_line}-L{self.chunk.end_line}"


@dataclass
class CodeContext:
    """Assembled context from code retrieval."""
    
    query: str
    primary_references: list[CodeReference] = field(default_factory=list)
    related_repos: list[dict[str, str]] = field(default_factory=list)
    domains_searched: list[str] = field(default_factory=list)
    total_chunks_found: int = 0
    
    def to_prompt_context(self) -> str:
        """Format context for inclusion in LLM prompt."""
        sections = []
        
        for ref in self.primary_references:
            section = f"### {ref.chunk.file_path} (lines {ref.chunk.start_line}-{ref.chunk.end_line})\n"
            section += f"Source: {ref.citation}\n"
            section += f"```{ref.chunk.language}\n"
            section += ref.full_content or ref.chunk.content
            section += "\n```\n"
            sections.append(section)
        
        return "\n".join(sections)
    
    def get_citations(self) -> list[str]:
        """Get all citation URLs."""
        return [ref.citation for ref in self.primary_references]
