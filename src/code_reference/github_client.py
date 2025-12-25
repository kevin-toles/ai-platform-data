"""GitHub API client for on-demand code retrieval."""

from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Constants
GITHUB_API_BASE = "https://api.github.com"
CODE_ENGINE_REPO = "kevin-toles/code-reference-engine"
DEFAULT_TIMEOUT = 30.0


@dataclass
class GitHubFile:
    """A file retrieved from GitHub."""
    
    path: str
    content: str
    sha: str
    size: int
    download_url: str
    html_url: str


class GitHubClient:
    """Client for GitHub Contents API.
    
    Fetches file content on-demand from code-reference-engine repo.
    No local storage - content is returned directly.
    """
    
    def __init__(
        self,
        token: str | None = None,
        repo: str = CODE_ENGINE_REPO,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        """Initialize GitHub client.
        
        Args:
            token: GitHub personal access token (or from GITHUB_TOKEN env var)
            repo: Repository in owner/repo format
            timeout: Request timeout in seconds
        """
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self.repo = repo
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
    
    @property
    def headers(self) -> dict[str, str]:
        """Build request headers."""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers
    
    async def __aenter__(self) -> GitHubClient:
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            base_url=GITHUB_API_BASE,
            headers=self.headers,
            timeout=self.timeout,
        )
        return self
    
    async def __aexit__(self, *args) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Get HTTP client, creating if needed."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=GITHUB_API_BASE,
                headers=self.headers,
                timeout=self.timeout,
            )
        return self._client
    
    async def get_file(self, path: str, ref: str = "main") -> GitHubFile | None:
        """Fetch a single file from the repository.
        
        Args:
            path: File path relative to repo root (e.g., "game-dev/engines/godot/core/main.cpp")
            ref: Branch, tag, or commit SHA
            
        Returns:
            GitHubFile with decoded content, or None if not found
        """
        url = f"/repos/{self.repo}/contents/{path}"
        params = {"ref": ref}
        
        try:
            response = await self.client.get(url, params=params)
            
            if response.status_code == 404:
                logger.warning(f"File not found: {path}")
                return None
            
            response.raise_for_status()
            data = response.json()
            
            # Decode base64 content
            content = ""
            if data.get("encoding") == "base64" and data.get("content"):
                content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            
            return GitHubFile(
                path=data["path"],
                content=content,
                sha=data["sha"],
                size=data["size"],
                download_url=data.get("download_url", ""),
                html_url=data.get("html_url", ""),
            )
            
        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub API error for {path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {path}: {e}")
            return None
    
    async def get_file_lines(
        self,
        path: str,
        start_line: int,
        end_line: int,
        ref: str = "main",
        context_lines: int = 0,
    ) -> str | None:
        """Fetch specific lines from a file.
        
        Args:
            path: File path relative to repo root
            start_line: Start line (1-indexed)
            end_line: End line (1-indexed, inclusive)
            ref: Branch, tag, or commit SHA
            context_lines: Additional lines of context before/after
            
        Returns:
            Selected lines as string, or None if not found
        """
        file = await self.get_file(path, ref)
        if file is None:
            return None
        
        lines = file.content.splitlines()
        
        # Adjust for 0-indexing and context
        start_idx = max(0, start_line - 1 - context_lines)
        end_idx = min(len(lines), end_line + context_lines)
        
        return "\n".join(lines[start_idx:end_idx])
    
    async def list_directory(self, path: str, ref: str = "main") -> list[dict]:
        """List contents of a directory.
        
        Args:
            path: Directory path relative to repo root
            ref: Branch, tag, or commit SHA
            
        Returns:
            List of file/directory entries
        """
        url = f"/repos/{self.repo}/contents/{path}"
        params = {"ref": ref}
        
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if isinstance(data, list):
                return [
                    {
                        "name": item["name"],
                        "path": item["path"],
                        "type": item["type"],  # "file" or "dir"
                        "size": item.get("size", 0),
                    }
                    for item in data
                ]
            return []
            
        except Exception as e:
            logger.error(f"Error listing {path}: {e}")
            return []
    
    async def search_code(
        self,
        query: str,
        path: str | None = None,
        extension: str | None = None,
        per_page: int = 30,
    ) -> list[dict]:
        """Search code in the repository.
        
        Note: Requires repo to be indexed by GitHub (may take time after push).
        
        Args:
            query: Search query
            path: Limit search to path prefix
            extension: Limit to file extension (e.g., "py", "cpp")
            per_page: Results per page (max 100)
            
        Returns:
            List of search results with file paths and matched content
        """
        # Build search query
        q = f"{query} repo:{self.repo}"
        if path:
            q += f" path:{path}"
        if extension:
            q += f" extension:{extension}"
        
        url = "/search/code"
        params = {"q": q, "per_page": min(per_page, 100)}
        
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            return [
                {
                    "path": item["path"],
                    "name": item["name"],
                    "sha": item["sha"],
                    "html_url": item["html_url"],
                    "score": item.get("score", 0),
                }
                for item in data.get("items", [])
            ]
            
        except Exception as e:
            logger.error(f"Error searching for '{query}': {e}")
            return []
    
    def get_raw_url(self, path: str, ref: str = "main") -> str:
        """Get raw content URL for a file.
        
        Args:
            path: File path relative to repo root
            ref: Branch, tag, or commit SHA
            
        Returns:
            Raw GitHub URL for direct download
        """
        return f"https://raw.githubusercontent.com/{self.repo}/{ref}/{path}"
    
    def get_html_url(self, path: str, start_line: int | None = None, end_line: int | None = None) -> str:
        """Get HTML URL for a file (for citations).
        
        Args:
            path: File path relative to repo root
            start_line: Optional start line to highlight
            end_line: Optional end line to highlight
            
        Returns:
            GitHub HTML URL
        """
        url = f"https://github.com/{self.repo}/blob/main/{path}"
        if start_line:
            url += f"#L{start_line}"
            if end_line and end_line != start_line:
                url += f"-L{end_line}"
        return url
