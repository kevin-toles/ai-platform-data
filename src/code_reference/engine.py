"""Code Reference Engine - Strategic code retrieval across mirrored repos.

This module provides the main interface for retrieving code from the
code-reference-engine repository. It supports:

1. Registry-based lookups (by domain, concept, pattern)
2. Qdrant semantic search (when indexed)
3. GitHub API on-demand retrieval
4. Neo4j graph traversal for cross-references

Kitchen Brigade Role: Used by Sous Chef (Code-Orchestrator-Service) to
assemble context for code generation tasks.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .github_client import GitHubClient
from .models import CodeChunk, CodeContext, CodeReference, RepoMetadata

if TYPE_CHECKING:
    from qdrant_client import QdrantClient

logger = logging.getLogger(__name__)

# Paths relative to ai-platform-data root
DEFAULT_REGISTRY_PATH = Path(__file__).parent.parent.parent / "repos" / "repo_registry.json"
DEFAULT_METADATA_PATH = Path(__file__).parent.parent.parent / "repos" / "metadata"


class CodeReferenceEngine:
    """Strategic code retrieval across all mirrored repositories.
    
    This class provides a unified interface for code retrieval that works
    whether searching 1 repo or 87 repos. It implements a 3-layer strategy:
    
    1. Qdrant semantic search (pre-indexed, fast)
    2. GitHub API on-demand retrieval (fetch full files)
    3. Neo4j graph traversal (cross-reference related repos)
    
    Example:
        async with CodeReferenceEngine() as engine:
            context = await engine.search(
                query="event-driven saga with compensation",
                domains=["backend-event-driven", "backend-microservices"],
                top_k=10,
            )
            print(context.to_prompt_context())
    """
    
    def __init__(
        self,
        registry_path: Path | str | None = None,
        metadata_path: Path | str | None = None,
        github_token: str | None = None,
        qdrant_client: QdrantClient | None = None,
        qdrant_collection: str = "code_chunks",
    ):
        """Initialize the Code Reference Engine.
        
        Args:
            registry_path: Path to repo_registry.json
            metadata_path: Path to metadata directory
            github_token: GitHub API token (or from GITHUB_TOKEN env var)
            qdrant_client: Pre-configured Qdrant client (optional)
            qdrant_collection: Qdrant collection name for code chunks
        """
        self.registry_path = Path(registry_path or DEFAULT_REGISTRY_PATH)
        self.metadata_path = Path(metadata_path or DEFAULT_METADATA_PATH)
        self.qdrant_client = qdrant_client
        self.qdrant_collection = qdrant_collection
        
        # Lazy-loaded
        self._registry: dict[str, Any] | None = None
        self._metadata_cache: dict[str, RepoMetadata] = {}
        self._github: GitHubClient | None = None
        self._github_token = github_token
    
    async def __aenter__(self) -> CodeReferenceEngine:
        """Async context manager entry."""
        self._github = GitHubClient(token=self._github_token)
        await self._github.__aenter__()
        return self
    
    async def __aexit__(self, *args) -> None:
        """Async context manager exit."""
        if self._github:
            await self._github.__aexit__(*args)
    
    @property
    def registry(self) -> dict[str, Any]:
        """Load and cache the repository registry."""
        if self._registry is None:
            with open(self.registry_path) as f:
                self._registry = json.load(f)
        return self._registry
    
    @property
    def github(self) -> GitHubClient:
        """Get GitHub client."""
        if self._github is None:
            self._github = GitHubClient(token=self._github_token)
        return self._github
    
    def get_metadata(self, repo_id: str) -> RepoMetadata | None:
        """Load metadata for a repository.
        
        Args:
            repo_id: Repository identifier
            
        Returns:
            RepoMetadata or None if not found
        """
        if repo_id in self._metadata_cache:
            return self._metadata_cache[repo_id]
        
        # Search through domains
        for domain in self.registry.get("domains", []):
            for repo in domain.get("repos", []):
                if repo.get("id") == repo_id:
                    metadata_path = self.registry_path.parent.parent / repo["metadata_path"]
                    if metadata_path.exists():
                        with open(metadata_path) as f:
                            data = json.load(f)
                        metadata = RepoMetadata.from_dict(data)
                        self._metadata_cache[repo_id] = metadata
                        return metadata
        
        return None
    
    def get_repos_for_domain(self, domain_id: str) -> list[RepoMetadata]:
        """Get all repos in a domain.
        
        Args:
            domain_id: Domain identifier (e.g., "backend-frameworks")
            
        Returns:
            List of RepoMetadata for repos in the domain
        """
        repos = []
        for domain in self.registry.get("domains", []):
            if domain.get("id") == domain_id:
                for repo in domain.get("repos", []):
                    metadata = self.get_metadata(repo["id"])
                    if metadata:
                        repos.append(metadata)
        return repos
    
    def get_repos_by_concept(self, concept: str) -> list[RepoMetadata]:
        """Find repos that demonstrate a specific concept.
        
        Args:
            concept: Concept to search for (e.g., "event-driven", "saga")
            
        Returns:
            List of RepoMetadata matching the concept
        """
        matching = []
        concept_lower = concept.lower()
        
        for domain in self.registry.get("domains", []):
            for repo in domain.get("repos", []):
                metadata = self.get_metadata(repo["id"])
                if metadata:
                    concepts = [c.lower() for c in metadata.concepts]
                    if any(concept_lower in c for c in concepts):
                        matching.append(metadata)
        
        return matching
    
    def get_repos_by_pattern(self, pattern: str) -> list[RepoMetadata]:
        """Find repos that implement a specific design pattern.
        
        Args:
            pattern: Pattern to search for (e.g., "saga", "cqrs")
            
        Returns:
            List of RepoMetadata implementing the pattern
        """
        matching = []
        pattern_lower = pattern.lower()
        
        for domain in self.registry.get("domains", []):
            for repo in domain.get("repos", []):
                metadata = self.get_metadata(repo["id"])
                if metadata:
                    patterns = [p.lower() for p in metadata.patterns]
                    if any(pattern_lower in p for p in patterns):
                        matching.append(metadata)
        
        return matching
    
    async def search(
        self,
        query: str,
        domains: list[str] | None = None,
        concepts: list[str] | None = None,
        top_k: int = 10,
        expand_context: bool = True,
        context_lines: int = 20,
    ) -> CodeContext:
        """Strategic search across all mirrored repositories.
        
        Implements 3-layer retrieval:
        1. Qdrant semantic search (if available)
        2. GitHub API keyword search
        3. Registry-based filtering
        
        Args:
            query: Natural language query
            domains: Limit to specific domains
            concepts: Limit to repos with specific concepts
            top_k: Maximum results to return
            expand_context: Fetch full file content for matches
            context_lines: Lines of context around matches
            
        Returns:
            CodeContext with assembled references
        """
        references: list[CodeReference] = []
        domains_searched: list[str] = []
        
        # Determine which repos to search
        target_repos: list[RepoMetadata] = []
        
        if domains:
            for domain_id in domains:
                target_repos.extend(self.get_repos_for_domain(domain_id))
                domains_searched.append(domain_id)
        elif concepts:
            for concept in concepts:
                target_repos.extend(self.get_repos_by_concept(concept))
        else:
            # Search all repos
            for domain in self.registry.get("domains", []):
                for repo in domain.get("repos", []):
                    metadata = self.get_metadata(repo["id"])
                    if metadata and metadata.mirrored:
                        target_repos.append(metadata)
        
        # Remove duplicates
        seen_ids = set()
        unique_repos = []
        for repo in target_repos:
            if repo.id not in seen_ids:
                seen_ids.add(repo.id)
                unique_repos.append(repo)
        target_repos = unique_repos
        
        # Layer 1: Try Qdrant semantic search if available
        if self.qdrant_client:
            try:
                qdrant_refs = await self._search_qdrant(
                    query=query,
                    domains=domains,
                    top_k=top_k,
                )
                references.extend(qdrant_refs)
            except Exception as e:
                logger.warning(f"Qdrant search failed: {e}")
        
        # Layer 2: GitHub Code Search API
        if len(references) < top_k:
            remaining = top_k - len(references)
            for repo in target_repos[:10]:  # Limit to first 10 repos
                if len(references) >= top_k:
                    break
                try:
                    github_refs = await self._search_github(
                        query=query,
                        path_prefix=repo.target_path,
                        limit=min(remaining, 5),
                    )
                    references.extend(github_refs)
                except Exception as e:
                    logger.warning(f"GitHub search failed for {repo.id}: {e}")
        
        # Expand context (fetch full files)
        if expand_context:
            for ref in references:
                if ref.full_content is None:
                    try:
                        content = await self.github.get_file_lines(
                            path=ref.chunk.file_path,
                            start_line=max(1, ref.chunk.start_line - context_lines),
                            end_line=ref.chunk.end_line + context_lines,
                        )
                        if content:
                            ref.full_content = content
                    except Exception as e:
                        logger.warning(f"Failed to expand context for {ref.chunk.file_path}: {e}")
        
        # Attach repo metadata
        for ref in references:
            if ref.repo_metadata is None:
                ref.repo_metadata = self.get_metadata(ref.chunk.repo_id)
        
        return CodeContext(
            query=query,
            primary_references=references[:top_k],
            domains_searched=domains_searched,
            total_chunks_found=len(references),
        )
    
    async def _search_qdrant(\n        self,\n        query: str,\n        domains: list[str] | None = None,\n        top_k: int = 10,  # noqa: ARG002 - reserved for future Qdrant implementation\n    ) -> list[CodeReference]:\n        \"\"\"Search Qdrant for semantically similar code chunks.\n        \n        Args:\n            query: Natural language query\n            domains: Limit to specific domains\n            top_k: Maximum results (reserved for future use)\n            \n        Returns:\n            List of CodeReference from Qdrant matches\n        \"\"\"\n        if not self.qdrant_client:\n            return []\n        \n        # Yield control to event loop (placeholder for async Qdrant operations)\n        await asyncio.sleep(0)\n        \n        # This requires an embedding model - placeholder for now\n        # In production, use CodeBERT or SBERT to encode query\n        _ = domains  # Reserved for filtering\n        logger.info(f\"Qdrant search not yet implemented - query: {query}\")\n        return []
    
    async def _search_github(
        self,
        query: str,
        path_prefix: str | None = None,
        limit: int = 5,
    ) -> list[CodeReference]:
        """Search GitHub for code matching query.
        
        Args:
            query: Search query
            path_prefix: Limit to path prefix
            limit: Maximum results
            
        Returns:
            List of CodeReference from GitHub search
        """
        results = await self.github.search_code(
            query=query,
            path=path_prefix,
            per_page=limit,
        )
        
        references = []
        for result in results:
            chunk = CodeChunk(
                chunk_id=f"github:{result['sha'][:8]}",
                repo_id=result["path"].split("/")[0] if "/" in result["path"] else "",
                file_path=result["path"],
                start_line=1,
                end_line=100,  # Will be refined when expanding context
                content="",  # Will be fetched when expanding
                score=result.get("score", 0),
            )
            references.append(CodeReference(
                chunk=chunk,
                source_url=result.get("html_url", ""),
            ))
        
        return references
    
    async def get_file(self, path: str) -> str | None:
        """Fetch a specific file from code-reference-engine.
        
        Args:
            path: File path relative to repo root
            
        Returns:
            File content or None if not found
        """
        file = await self.github.get_file(path)
        return file.content if file else None
    
    async def get_file_with_citation(self, path: str) -> tuple[str | None, str]:
        """Fetch a file and return with citation URL.
        
        Args:
            path: File path relative to repo root
            
        Returns:
            Tuple of (content, citation_url)
        """
        file = await self.github.get_file(path)
        if file:
            return file.content, file.html_url
        return None, ""
    
    def get_all_domains(self) -> list[dict[str, Any]]:
        """Get list of all domains in the registry.
        
        Returns:
            List of domain dictionaries
        """
        return self.registry.get("domains", [])
    
    def get_statistics(self) -> dict[str, Any]:
        """Get statistics about the code reference engine.
        
        Returns:
            Dictionary with stats
        """
        total_repos = 0
        mirrored_repos = 0
        indexed_repos = 0
        
        for domain in self.registry.get("domains", []):
            for repo in domain.get("repos", []):
                total_repos += 1
                metadata = self.get_metadata(repo["id"])
                if metadata:
                    if metadata.mirrored:
                        mirrored_repos += 1
                    if metadata.indexed:
                        indexed_repos += 1
        
        return {
            "total_repos": total_repos,
            "mirrored_repos": mirrored_repos,
            "indexed_repos": indexed_repos,
            "domains": len(self.registry.get("domains", [])),
            "qdrant_available": self.qdrant_client is not None,
        }
