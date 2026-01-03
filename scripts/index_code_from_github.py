#!/usr/bin/env python3
"""Index code chunks from GitHub into Qdrant.

This script fetches code from the code-reference-engine GitHub repository
and indexes it into the Qdrant `code_chunks` collection for semantic search.

IMPORTANT: This uses the GitHub API - NOT local files.
The code-reference-engine repo contains mirrored code from 82 repos.

Usage:
    # Index all priority 1 repos
    python scripts/index_code_from_github.py
    
    # Index specific domain
    python scripts/index_code_from_github.py --domain backend-frameworks
    
    # Index specific repo
    python scripts/index_code_from_github.py --repo fastapi
    
    # Dry run (no writes)
    python scripts/index_code_from_github.py --dry-run

Environment Variables:
    GITHUB_TOKEN: GitHub personal access token (required)
    QDRANT_URL: Qdrant server URL (default: http://localhost:6333)
    QDRANT_COLLECTION: Collection name (default: code_chunks)

Reference: AGENT_FUNCTIONS_ARCHITECTURE.md → Code Reference Engine
"""

import argparse
import base64
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from sentence_transformers import SentenceTransformer

# =============================================================================
# Configuration
# =============================================================================

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "code_chunks")

# GitHub repo containing mirrored code
CODE_REFERENCE_REPO = "kevin-toles/code-reference-engine"
GITHUB_API_BASE = "https://api.github.com"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com"

# Chunking configuration
MAX_CHUNK_LINES = 100
OVERLAP_LINES = 10
MIN_CHUNK_LINES = 10

# File extensions to index
CODE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".rb": "ruby",
    ".php": "php",
    ".cs": "csharp",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".ex": "elixir",
    ".exs": "elixir",
}

# Paths to skip
SKIP_PATTERNS = [
    "test",
    "tests",
    "spec",
    "specs",
    "__pycache__",
    "node_modules",
    "vendor",
    ".git",
    "dist",
    "build",
    "target",
]


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class CodeChunk:
    """A chunk of code for indexing."""
    
    chunk_id: str
    repo_id: str
    file_path: str
    start_line: int
    end_line: int
    content: str
    language: str
    repo_url: str
    domain: str
    concepts: list[str]
    patterns: list[str]


@dataclass
class RepoMetadata:
    """Metadata for a repository."""
    
    id: str
    name: str
    source_url: str
    target_path: str
    domain: str
    languages: list[str]
    concepts: list[str]
    patterns: list[str]
    priority: int


# =============================================================================
# GitHub API Client
# =============================================================================


class GitHubClient:
    """Client for GitHub API with rate limiting."""
    
    def __init__(self, token: str):
        self.token = token
        self.client = httpx.Client(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        self.rate_limit_remaining = 5000
        self.rate_limit_reset = 0
        self._tree_cache: dict[str, list[dict]] = {}  # Cache full tree per repo
    
    def _check_rate_limit(self, response: httpx.Response) -> None:
        """Update rate limit tracking from response headers."""
        self.rate_limit_remaining = int(
            response.headers.get("X-RateLimit-Remaining", 5000)
        )
        self.rate_limit_reset = int(
            response.headers.get("X-RateLimit-Reset", 0)
        )
        
        if self.rate_limit_remaining < 100:
            wait_time = self.rate_limit_reset - time.time()
            if wait_time > 0:
                print(f"⚠️  Rate limit low ({self.rate_limit_remaining}), waiting {wait_time:.0f}s...")
                time.sleep(min(wait_time, 60))
    
    def get_tree(self, repo: str, path: str = "", recursive: bool = True) -> list[dict]:
        """Get repository tree (file listing) for a specific path.
        
        Uses per-path tree caching since the full repo tree is truncated.
        GitHub limits recursive tree responses to ~50K items.
        
        Args:
            repo: Repository in format "owner/repo"
            path: Subdirectory path (required for large repos)
            recursive: Whether to get tree recursively
            
        Returns:
            List of tree entries (files and directories)
        """
        path = path.strip("/") if path else ""
        cache_key = f"{repo}:{path}"
        
        # Check cache first
        if cache_key not in self._tree_cache:
            # First get the SHA of the subdirectory
            if path:
                # Get the tree for the subdirectory specifically
                # First, get the SHA of the path by walking down
                parts = path.split("/")
                current_sha = "main"
                
                for part in parts:
                    url = f"{GITHUB_API_BASE}/repos/{repo}/git/trees/{current_sha}"
                    response = self.client.get(url)
                    self._check_rate_limit(response)
                    
                    if response.status_code != 200:
                        print(f"   ❌ Failed to get tree for {part}: {response.status_code}")
                        return []
                    
                    data = response.json()
                    # Find the entry for this part
                    found = False
                    for entry in data.get("tree", []):
                        if entry.get("path") == part and entry.get("type") == "tree":
                            current_sha = entry.get("sha")
                            found = True
                            break
                    
                    if not found:
                        print(f"   ❌ Path not found: {part} in {path}")
                        return []
                
                # Now get the recursive tree for this subdirectory
                url = f"{GITHUB_API_BASE}/repos/{repo}/git/trees/{current_sha}?recursive=1"
            else:
                url = f"{GITHUB_API_BASE}/repos/{repo}/git/trees/main?recursive=1"
            
            response = self.client.get(url)
            self._check_rate_limit(response)
            
            if response.status_code != 200:
                print(f"   ❌ Failed to get tree: {response.status_code}")
                return []
            
            data = response.json()
            tree_items = data.get("tree", [])
            truncated = data.get("truncated", False)
            
            # Prepend the base path to all entries
            if path:
                for item in tree_items:
                    item["path"] = f"{path}/{item['path']}"
            
            self._tree_cache[cache_key] = tree_items
            
            status = "⚠️ TRUNCATED" if truncated else "✅"
            print(f"   📥 Tree for {path or 'root'}: {len(tree_items)} items {status}")
        
        return self._tree_cache[cache_key]
    
    def _get_contents_recursive(self, repo: str, path: str) -> list[dict]:
        """Recursively get contents using Contents API.
        
        Args:
            repo: Repository in format "owner/repo"
            path: Directory path
            
        Returns:
            List of file entries with path and type
        """
        url = f"{GITHUB_API_BASE}/repos/{repo}/contents/{path}"
        response = self.client.get(url)
        self._check_rate_limit(response)
        
        if response.status_code != 200:
            return []
        
        data = response.json()
        if not isinstance(data, list):
            # Single file
            return [{"path": path, "type": "blob"}]
        
        results = []
        for item in data:
            item_path = item.get("path", "")
            item_type = item.get("type", "")
            
            if item_type == "file":
                results.append({"path": item_path, "type": "blob"})
            elif item_type == "dir":
                # Recursively get directory contents
                results.extend(self._get_contents_recursive(repo, item_path))
        
        return results
    
    def get_file_content(self, repo: str, file_path: str) -> str | None:
        """Fetch file content from GitHub.
        
        Args:
            repo: Repository in format "owner/repo"
            file_path: Path to file within repository
            
        Returns:
            File content as string, or None if not found
        """
        # Use raw content URL for efficiency
        url = f"{GITHUB_RAW_BASE}/{repo}/main/{file_path}"
        
        response = self.client.get(url)
        
        if response.status_code != 200:
            return None
        
        return response.text
    
    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()


# =============================================================================
# Code Chunking
# =============================================================================


def chunk_code(
    content: str,
    file_path: str,
    max_lines: int = MAX_CHUNK_LINES,
    overlap: int = OVERLAP_LINES,
    min_lines: int = MIN_CHUNK_LINES,
) -> list[tuple[int, int, str]]:
    """Split code into overlapping chunks.
    
    Args:
        content: Full file content
        file_path: Path for context
        max_lines: Maximum lines per chunk
        overlap: Lines to overlap between chunks
        min_lines: Minimum lines for a chunk
        
    Returns:
        List of (start_line, end_line, chunk_content) tuples
    """
    lines = content.split("\n")
    total_lines = len(lines)
    
    if total_lines <= max_lines:
        # Small file - return as single chunk
        return [(1, total_lines, content)]
    
    chunks = []
    start = 0
    
    while start < total_lines:
        end = min(start + max_lines, total_lines)
        chunk_lines = lines[start:end]
        
        # Only create chunk if it meets minimum size
        if len(chunk_lines) >= min_lines:
            chunk_content = "\n".join(chunk_lines)
            chunks.append((start + 1, end, chunk_content))  # 1-indexed
        
        # Move start forward with overlap
        start = end - overlap
        
        # Prevent infinite loop on small files
        if start >= total_lines - min_lines:
            break
    
    return chunks


def should_index_file(file_path: str) -> bool:
    """Check if a file should be indexed.
    
    Args:
        file_path: Path to check
        
    Returns:
        True if file should be indexed
    """
    # Check extension
    ext = Path(file_path).suffix.lower()
    if ext not in CODE_EXTENSIONS:
        return False
    
    # Check skip patterns
    path_lower = file_path.lower()
    for pattern in SKIP_PATTERNS:
        if f"/{pattern}/" in path_lower or path_lower.startswith(f"{pattern}/"):
            return False
    
    return True


def get_language(file_path: str) -> str:
    """Get language from file extension."""
    ext = Path(file_path).suffix.lower()
    return CODE_EXTENSIONS.get(ext, "text")


# =============================================================================
# Registry Loading
# =============================================================================


def load_registry(registry_path: str) -> dict[str, RepoMetadata]:
    """Load repository registry.
    
    Args:
        registry_path: Path to repo_registry.json
        
    Returns:
        Dict mapping repo_id to RepoMetadata
    """
    with open(registry_path) as f:
        data = json.load(f)
    
    repos = {}
    
    for domain in data.get("domains", []):
        domain_id = domain.get("id", "")
        
        for repo_entry in domain.get("repos", []):
            repo_id = repo_entry.get("id", "")
            metadata_path = repo_entry.get("metadata_path", "")
            priority = repo_entry.get("priority", 99)
            
            # Load detailed metadata if available
            full_metadata_path = Path(registry_path).parent.parent / metadata_path
            if full_metadata_path.exists():
                with open(full_metadata_path) as f:
                    meta = json.load(f)
                
                repos[repo_id] = RepoMetadata(
                    id=repo_id,
                    name=meta.get("name", repo_id),
                    source_url=meta.get("source_url", ""),
                    target_path=meta.get("target_path", ""),
                    domain=domain_id,
                    languages=meta.get("languages", []),
                    concepts=meta.get("concepts", []),
                    patterns=meta.get("patterns", []),
                    priority=priority,
                )
    
    return repos


# =============================================================================
# Qdrant Indexing
# =============================================================================


class QdrantIndexer:
    """Index code chunks into Qdrant."""
    
    def __init__(self, url: str, collection: str, dry_run: bool = False):
        self.url = url
        self.collection = collection
        self.dry_run = dry_run
        self.client = httpx.Client(timeout=30.0)
        
        # Load embedding model
        print("📦 Loading embedding model...")
        self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        print("✅ Model loaded")
    
    def index_chunks(self, chunks: list[CodeChunk]) -> int:
        """Index chunks into Qdrant.
        
        Args:
            chunks: List of CodeChunk objects
            
        Returns:
            Number of chunks indexed
        """
        if not chunks:
            return 0
        
        if self.dry_run:
            print(f"  [DRY RUN] Would index {len(chunks)} chunks")
            return len(chunks)
        
        # Generate embeddings
        texts = [
            f"{c.file_path}\n{c.content[:500]}"  # Truncate for embedding
            for c in chunks
        ]
        embeddings = self.model.encode(texts, show_progress_bar=False)
        
        # Build Qdrant points
        points = []
        for i, chunk in enumerate(chunks):
            point_id = hashlib.md5(
                f"{chunk.repo_id}:{chunk.file_path}:{chunk.start_line}".encode()
            ).hexdigest()
            
            points.append({
                "id": point_id,
                "vector": embeddings[i].tolist(),
                "payload": {
                    "chunk_id": chunk.chunk_id,
                    "repo_id": chunk.repo_id,
                    "file_path": chunk.file_path,
                    "start_line": chunk.start_line,
                    "end_line": chunk.end_line,
                    "content": chunk.content,
                    "language": chunk.language,
                    "repo_url": chunk.repo_url,
                    "domain": chunk.domain,
                    "concepts": chunk.concepts,
                    "patterns": chunk.patterns,
                },
            })
        
        # Upsert to Qdrant
        response = self.client.put(
            f"{self.url}/collections/{self.collection}/points",
            json={"points": points},
        )
        
        if response.status_code not in (200, 201):
            print(f"  ❌ Failed to index: {response.text}")
            return 0
        
        return len(points)
    
    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()


# =============================================================================
# Main Indexing Logic
# =============================================================================


def index_repository(
    github: GitHubClient,
    indexer: QdrantIndexer,
    repo_meta: RepoMetadata,
) -> int:
    """Index a single repository.
    
    Args:
        github: GitHub API client
        indexer: Qdrant indexer
        repo_meta: Repository metadata
        
    Returns:
        Number of chunks indexed
    """
    print(f"\n📂 Indexing {repo_meta.name} ({repo_meta.id})")
    print(f"   Path: {repo_meta.target_path}")
    print(f"   Domain: {repo_meta.domain}")
    
    # Get file tree for this repo's path in code-reference-engine
    tree = github.get_tree(CODE_REFERENCE_REPO, repo_meta.target_path)
    
    if not tree:
        print(f"   ⚠️  No files found")
        return 0
    
    # Filter to indexable files
    files = [
        entry for entry in tree
        if entry.get("type") == "blob" and should_index_file(entry.get("path", ""))
    ]
    
    print(f"   Found {len(files)} indexable files")
    
    all_chunks = []
    
    for i, file_entry in enumerate(files):
        file_path = file_entry.get("path", "")
        
        # Fetch file content
        content = github.get_file_content(CODE_REFERENCE_REPO, file_path)
        
        if content is None:
            continue
        
        # Handle large files with larger chunks to keep total count reasonable
        file_size = len(content)
        if file_size > 500_000:  # 500KB+ - use larger chunks
            language = get_language(file_path)
            chunks = chunk_code(content, file_path, max_lines=500, overlap=20, min_lines=50)
            for start_line, end_line, chunk_content in chunks:
                chunk_id = hashlib.md5(
                    f"{repo_meta.id}:{file_path}:{start_line}:{end_line}".encode()
                ).hexdigest()[:16]
                all_chunks.append(CodeChunk(
                    chunk_id=chunk_id,
                    repo_id=repo_meta.id,
                    file_path=file_path,
                    start_line=start_line,
                    end_line=end_line,
                    content=chunk_content,
                    language=language,
                    repo_url=repo_meta.source_url,
                    domain=repo_meta.domain,
                    concepts=repo_meta.concepts,
                    patterns=repo_meta.patterns,
                ))
            continue
        
        # Normal files - standard chunking
        language = get_language(file_path)
        chunks = chunk_code(content, file_path)
        
        for start_line, end_line, chunk_content in chunks:
            chunk_id = hashlib.md5(
                f"{repo_meta.id}:{file_path}:{start_line}:{end_line}".encode()
            ).hexdigest()[:16]
            
            all_chunks.append(CodeChunk(
                chunk_id=chunk_id,
                repo_id=repo_meta.id,
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                content=chunk_content,
                language=language,
                repo_url=repo_meta.source_url,
                domain=repo_meta.domain,
                concepts=repo_meta.concepts,
                patterns=repo_meta.patterns,
            ))
        
        # Progress indicator
        if (i + 1) % 10 == 0:
            print(f"   Processed {i + 1}/{len(files)} files...")
    
    # Index in batches
    batch_size = 100
    total_indexed = 0
    
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i + batch_size]
        indexed = indexer.index_chunks(batch)
        total_indexed += indexed
    
    print(f"   ✅ Indexed {total_indexed} chunks")
    return total_indexed


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Index code from GitHub into Qdrant"
    )
    parser.add_argument(
        "--registry",
        default="/Users/kevintoles/POC/ai-platform-data/repos/repo_registry.json",
        help="Path to repo_registry.json",
    )
    parser.add_argument(
        "--domain",
        help="Only index repos from this domain",
    )
    parser.add_argument(
        "--repo",
        help="Only index this specific repo",
    )
    parser.add_argument(
        "--priority",
        type=int,
        default=1,
        help="Only index repos with this priority or higher (lower number = higher priority)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of repos to process per batch",
    )
    parser.add_argument(
        "--batch-num",
        type=int,
        default=None,
        help="Which batch to process (1-indexed). If not set, processes all.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't actually index, just show what would be done",
    )
    args = parser.parse_args()
    
    # Check for GitHub token
    if not GITHUB_TOKEN:
        print("❌ GITHUB_TOKEN environment variable not set")
        print("   Set it with: export GITHUB_TOKEN=ghp_...")
        sys.exit(1)
    
    print("=" * 60)
    print("Code Reference Engine Indexer (GitHub API)")
    print("=" * 60)
    print(f"Qdrant URL: {QDRANT_URL}")
    print(f"Collection: {QDRANT_COLLECTION}")
    print(f"Source Repo: {CODE_REFERENCE_REPO}")
    if args.dry_run:
        print("MODE: DRY RUN (no writes)")
    print("=" * 60)
    
    # Load registry
    print("\n📖 Loading repository registry...")
    repos = load_registry(args.registry)
    print(f"   Found {len(repos)} repositories")
    
    # Filter repos
    if args.repo:
        repos = {k: v for k, v in repos.items() if k == args.repo}
    elif args.domain:
        repos = {k: v for k, v in repos.items() if v.domain == args.domain}
    else:
        repos = {k: v for k, v in repos.items() if v.priority <= args.priority}
    
    # Convert to list for batch processing
    repo_list = list(repos.items())
    total_repos = len(repo_list)
    
    # Calculate batches
    batch_size = args.batch_size
    total_batches = (total_repos + batch_size - 1) // batch_size
    
    if args.batch_num is not None:
        # Process specific batch
        batch_start = (args.batch_num - 1) * batch_size
        batch_end = min(batch_start + batch_size, total_repos)
        repo_list = repo_list[batch_start:batch_end]
        print(f"   Processing batch {args.batch_num}/{total_batches} (repos {batch_start+1}-{batch_end} of {total_repos})")
    else:
        print(f"   Indexing {total_repos} repositories (priority <= {args.priority})")
        print(f"   Total batches: {total_batches} (batch size: {batch_size})")
    
    # Initialize clients
    github = GitHubClient(GITHUB_TOKEN)
    indexer = QdrantIndexer(QDRANT_URL, QDRANT_COLLECTION, dry_run=args.dry_run)
    
    try:
        total_chunks = 0
        
        for i, (repo_id, repo_meta) in enumerate(repo_list, 1):
            print(f"\n[{i}/{len(repo_list)}] ", end="")
            try:
                chunks = index_repository(github, indexer, repo_meta)
                total_chunks += chunks
            except Exception as e:
                print(f"   ❌ Error indexing {repo_id}: {e}")
                continue
        
        print("\n" + "=" * 60)
        if args.batch_num is not None:
            print(f"✅ BATCH {args.batch_num} COMPLETE: Indexed {total_chunks} chunks")
        else:
            print(f"✅ COMPLETE: Indexed {total_chunks} total chunks")
        print("=" * 60)
        
    finally:
        github.close()
        indexer.close()


if __name__ == "__main__":
    main()
