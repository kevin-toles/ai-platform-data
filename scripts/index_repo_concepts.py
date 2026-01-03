"""Index repository concepts for semantic matching.

Phase 4B: Concept Mapping Pipeline - Pre-indexing
WBS Tasks: Build repo_concepts Qdrant collection

This script:
1. Loads all repo metadata from repos/metadata/**/*.json
2. Extracts concepts, patterns, and tags from each repo
3. Generates embeddings using sentence-transformers
4. Creates/updates Qdrant "repo_concepts" collection

Run this:
- Once initially to set up the collection
- When repos/metadata changes (new repos, updated concepts)
- Before running auto_map_concepts.py

Anti-Pattern Audit:
- Per Issue #12: Connection pooling (single client instance)
- Per Category 1.1: All functions have type annotations
- Per S1192: String literals extracted to constants
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress

if TYPE_CHECKING:
    from qdrant_client import QdrantClient
    from sentence_transformers import SentenceTransformer

console = Console()
logger = logging.getLogger(__name__)

# Constants
DEFAULT_REPOS_PATH = Path(__file__).parent.parent / "repos" / "metadata"
REPO_CONCEPTS_COLLECTION = "repo_concepts"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384
JSON_GLOB_PATTERN = "*.json"


@dataclass
class IndexingStats:
    """Statistics from repo concept indexing."""
    
    repos_processed: int = 0
    concepts_indexed: int = 0
    patterns_indexed: int = 0
    tags_indexed: int = 0
    total_points: int = 0
    collection_created: bool = False
    errors: int = 0


def get_qdrant_client() -> QdrantClient:
    """Create Qdrant client from environment configuration."""
    from qdrant_client import QdrantClient
    
    load_dotenv()
    
    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    
    return QdrantClient(host=host, port=port)


def get_embedding_model() -> SentenceTransformer:
    """Load sentence transformer model for embeddings."""
    from sentence_transformers import SentenceTransformer
    
    return SentenceTransformer(EMBEDDING_MODEL)


def ensure_collection(
    qdrant: QdrantClient,
    recreate: bool = False,
) -> bool:
    """Create or verify the repo_concepts collection exists.
    
    Args:
        qdrant: Qdrant client
        recreate: If True, delete and recreate the collection
        
    Returns:
        True if collection was created, False if already existed
    """
    from qdrant_client.models import Distance, VectorParams
    
    collections = [c.name for c in qdrant.get_collections().collections]
    
    if REPO_CONCEPTS_COLLECTION in collections:
        if recreate:
            console.print(f"Deleting existing collection: {REPO_CONCEPTS_COLLECTION}")
            qdrant.delete_collection(REPO_CONCEPTS_COLLECTION)
        else:
            console.print(f"✓ Collection '{REPO_CONCEPTS_COLLECTION}' exists")
            return False
    
    console.print(f"Creating collection: {REPO_CONCEPTS_COLLECTION}")
    qdrant.create_collection(
        collection_name=REPO_CONCEPTS_COLLECTION,
        vectors_config=VectorParams(
            size=EMBEDDING_DIM,
            distance=Distance.COSINE,
        ),
    )
    
    return True


def load_repo_metadata(repos_path: Path) -> list[dict[str, Any]]:
    """Load all repo metadata files.
    
    Args:
        repos_path: Path to repos/metadata directory
        
    Returns:
        List of repo metadata dictionaries
    """
    repos = []
    
    for json_file in repos_path.rglob(JSON_GLOB_PATTERN):
        try:
            with open(json_file) as f:
                repo = json.load(f)
            
            # Skip if no concepts or patterns
            if not (repo.get("concepts") or repo.get("patterns") or repo.get("tags")):
                logger.debug(f"Skipping {json_file.name}: no concepts/patterns/tags")
                continue
            
            repo["_source_file"] = str(json_file)
            repos.append(repo)
            
        except Exception as e:
            logger.warning(f"Failed to load {json_file}: {e}")
    
    return repos


def extract_indexable_terms(repo: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract all indexable terms from a repo.
    
    Args:
        repo: Repo metadata dict
        
    Returns:
        List of term dicts with type, term, and repo info
    """
    terms = []
    repo_id = repo.get("id", "unknown")
    
    # Extract concepts
    for concept in repo.get("concepts", []):
        if concept and len(concept) > 2:
            terms.append({
                "type": "concept",
                "term": concept.lower().strip(),
                "repo_id": repo_id,
                "repo_name": repo.get("name", repo_id),
                "domain": repo.get("domain", "unknown"),
                "target_path": repo.get("target_path", ""),
                "tier": repo.get("tier", ""),
            })
    
    # Extract patterns
    for pattern in repo.get("patterns", []):
        if pattern and len(pattern) > 2:
            terms.append({
                "type": "pattern",
                "term": pattern.lower().strip(),
                "repo_id": repo_id,
                "repo_name": repo.get("name", repo_id),
                "domain": repo.get("domain", "unknown"),
                "target_path": repo.get("target_path", ""),
                "tier": repo.get("tier", ""),
            })
    
    # Extract relevant tags (skip generic ones)
    skip_tags = {"java", "python", "go", "rust", "typescript", "javascript", "cpp", "c"}
    for tag in repo.get("tags", []):
        if tag and len(tag) > 2 and tag.lower() not in skip_tags:
            terms.append({
                "type": "tag",
                "term": tag.lower().strip(),
                "repo_id": repo_id,
                "repo_name": repo.get("name", repo_id),
                "domain": repo.get("domain", "unknown"),
                "target_path": repo.get("target_path", ""),
                "tier": repo.get("tier", ""),
            })
    
    return terms


def index_terms(
    terms: list[dict[str, Any]],
    qdrant: QdrantClient,
    embedder: SentenceTransformer,
    batch_size: int = 100,
) -> int:
    """Generate embeddings and upsert terms to Qdrant.
    
    Args:
        terms: List of term dicts to index
        qdrant: Qdrant client
        embedder: Sentence transformer model
        batch_size: Batch size for upserts
        
    Returns:
        Number of points indexed
    """
    from qdrant_client.models import PointStruct
    
    # Deduplicate by term + repo_id
    seen = set()
    unique_terms = []
    for term in terms:
        key = (term["term"], term["repo_id"])
        if key not in seen:
            seen.add(key)
            unique_terms.append(term)
    
    console.print(f"Generating embeddings for {len(unique_terms)} unique terms...")
    
    # Batch embed all terms
    term_texts = [t["term"] for t in unique_terms]
    embeddings = embedder.encode(term_texts, show_progress_bar=True)
    
    # Create points
    points = []
    for i, (term, embedding) in enumerate(zip(unique_terms, embeddings)):
        point_id = str(uuid.uuid5(
            uuid.NAMESPACE_DNS,
            f"{term['repo_id']}:{term['term']}"
        ))
        
        points.append(PointStruct(
            id=point_id,
            vector=embedding.tolist(),
            payload={
                "pattern": term["term"],
                "type": term["type"],
                "repo_id": term["repo_id"],
                "repo_name": term["repo_name"],
                "domain": term["domain"],
                "target_path": term["target_path"],
                "tier": term["tier"],
            },
        ))
    
    # Upsert in batches
    console.print(f"Upserting {len(points)} points to Qdrant...")
    
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        qdrant.upsert(
            collection_name=REPO_CONCEPTS_COLLECTION,
            points=batch,
        )
    
    return len(points)


@click.command()
@click.option(
    "--repos-path",
    type=click.Path(exists=True, path_type=Path),
    default=DEFAULT_REPOS_PATH,
    help="Path to repo metadata directory",
)
@click.option(
    "--recreate",
    is_flag=True,
    help="Delete and recreate the collection",
)
@click.option(
    "--batch-size",
    type=int,
    default=100,
    help="Batch size for Qdrant upserts",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Enable verbose output",
)
def main(
    repos_path: Path,
    recreate: bool,
    batch_size: int,
    verbose: bool,
) -> None:
    """Index repository concepts/patterns for semantic matching.
    
    This script extracts concepts, patterns, and tags from all repo
    metadata files and indexes them in Qdrant for semantic search.
    Run this before using auto_map_concepts.py.
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    stats = IndexingStats()
    
    console.print("[bold blue]🔍 Repo Concepts Indexer[/bold blue]\n")
    
    # Initialize clients
    console.print("Initializing clients...")
    qdrant = get_qdrant_client()
    embedder = get_embedding_model()
    
    # Ensure collection exists
    stats.collection_created = ensure_collection(qdrant, recreate=recreate)
    
    # Load repo metadata
    console.print(f"\nLoading repo metadata from: {repos_path}")
    repos = load_repo_metadata(repos_path)
    stats.repos_processed = len(repos)
    console.print(f"Found {len(repos)} repos with indexable terms")
    
    # Extract all terms
    all_terms = []
    with Progress() as progress:
        task = progress.add_task("Extracting terms...", total=len(repos))
        
        for repo in repos:
            terms = extract_indexable_terms(repo)
            all_terms.extend(terms)
            
            # Update stats
            stats.concepts_indexed += sum(1 for t in terms if t["type"] == "concept")
            stats.patterns_indexed += sum(1 for t in terms if t["type"] == "pattern")
            stats.tags_indexed += sum(1 for t in terms if t["type"] == "tag")
            
            progress.advance(task)
    
    console.print("\nExtracted terms:")
    console.print(f"  • Concepts: {stats.concepts_indexed}")
    console.print(f"  • Patterns: {stats.patterns_indexed}")
    console.print(f"  • Tags: {stats.tags_indexed}")
    
    # Index terms
    stats.total_points = index_terms(all_terms, qdrant, embedder, batch_size)
    
    # Verify
    collection_info = qdrant.get_collection(REPO_CONCEPTS_COLLECTION)
    console.print(f"\n✓ Collection now has {collection_info.points_count} points")
    
    console.print("\n[bold green]✓ Indexing complete![/bold green]")
    console.print("\nNext step: python scripts/auto_map_concepts.py")


if __name__ == "__main__":
    main()
