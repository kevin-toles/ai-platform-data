# Code Reference Engine - Architecture & Setup Guide

## Overview

The **Code Reference Engine** is a strategic code retrieval system that provides AI agents with access to 82+ curated repositories for pattern extraction, architecture reasoning, and code generation context. It's designed for the constraint of **no local storage** - all code lives on GitHub and is fetched on-demand.

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CODE REFERENCE ENGINE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    ai-platform-data (This Repo)                      │   │
│  │                                                                       │   │
│  │  repos/                                                               │   │
│  │  ├── repo_registry.json      ← Master index of all 82 repos         │   │
│  │  └── metadata/               ← Per-repo metadata (concepts, patterns)│   │
│  │      ├── backend/                                                     │   │
│  │      ├── game-dev/                                                    │   │
│  │      ├── infrastructure/                                              │   │
│  │      └── ...                                                          │   │
│  │                                                                       │   │
│  │  src/code_reference/                                                  │   │
│  │  ├── engine.py               ← CodeReferenceEngine class             │   │
│  │  ├── github_client.py        ← Async GitHub API client               │   │
│  │  └── models.py               ← Data models                           │   │
│  │                                                                       │   │
│  │  schemas/                                                             │   │
│  │  ├── repo_metadata.schema.json                                        │   │
│  │  └── repo_registry.schema.json                                        │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    │ Points to                               │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              code-reference-engine (GitHub Repo)                     │   │
│  │              github.com/kevin-toles/code-reference-engine            │   │
│  │                                                                       │   │
│  │  82 mirrored repositories organized by domain:                       │   │
│  │  ├── backend/frameworks/     (FastAPI, Django, Spring Boot, ...)    │   │
│  │  ├── backend/microservices/  (eShop, Online Boutique, FTGO, ...)    │   │
│  │  ├── game-dev/engines/       (Godot, Urho3D, OGRE, ...)             │   │
│  │  ├── game-dev/rendering/     (bgfx, Filament, Vulkan-Samples, ...)  │   │
│  │  ├── infrastructure/         (Kubernetes, Terraform, Helm, ...)     │   │
│  │  ├── ml/frameworks/          (PyTorch, TensorFlow, Transformers)    │   │
│  │  └── ...                                                             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3-Layer Retrieval Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          RETRIEVAL LAYERS                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  LAYER 1: QDRANT SEMANTIC SEARCH (Fastest)                                  │
│  ─────────────────────────────────────────                                  │
│  • Pre-indexed code chunks with CodeBERT embeddings                         │
│  • Single query → matches across ALL 82 repos                               │
│  • Status: ⏳ Pending (Phase 4b)                                            │
│                                                                              │
│  LAYER 2: GITHUB API (On-Demand)                                            │
│  ────────────────────────────────                                           │
│  • Fetch specific files via Contents API                                    │
│  • Search code via Code Search API                                          │
│  • No local storage - content returned directly                             │
│  • Status: ✅ Available now                                                 │
│                                                                              │
│  LAYER 3: NEO4J GRAPH (Cross-Reference)                                     │
│  ───────────────────────────────────────                                    │
│  • Traverse repo relationships and dependencies                             │
│  • "You pulled X, you might also need Y"                                    │
│  • Status: ⏳ Pending (Phase 4c)                                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Kitchen Brigade Integration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         KITCHEN BRIGADE FLOW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  👤 CUSTOMER (User/Claude/GPT)                                              │
│     │                                                                        │
│     │ "Build a distributed game server with ECS, event-driven sagas,       │
│     │  K8s deployment, and ML-based matchmaking"                            │
│     │                                                                        │
│     ▼                                                                        │
│  👨‍🍳 SOUS CHEF (Code-Orchestrator-Service)                                   │
│     │                                                                        │
│     │ 1. Parse query → extract concepts                                     │
│     │ 2. Call CodeReferenceEngine.search()                                  │
│     │ 3. Assemble context from multiple repos                               │
│     │                                                                        │
│     ▼                                                                        │
│  📦 CODE REFERENCE ENGINE                                                    │
│     │                                                                        │
│     ├──→ Qdrant: Semantic search for "ECS patterns"                        │
│     ├──→ GitHub API: Fetch EnTT, Godot ECS, Kafka saga examples            │
│     └──→ Neo4j: Cross-reference related repos                              │
│     │                                                                        │
│     ▼                                                                        │
│  📋 CONTEXT PACKET                                                           │
│     │                                                                        │
│     │ {                                                                      │
│     │   "ecs_patterns": [...],      // From game-dev/ecs                   │
│     │   "saga_examples": [...],     // From backend/event-driven           │
│     │   "k8s_configs": [...],       // From infrastructure                 │
│     │   "citations": [...]          // GitHub URLs for Auditor             │
│     │ }                                                                      │
│     │                                                                        │
│     ▼                                                                        │
│  👨‍🍳 CHEF DE PARTIE (Code Generation)                                        │
│     │                                                                        │
│     │ Generate implementation using retrieved context                       │
│     │                                                                        │
│     ▼                                                                        │
│  🔍 AUDITOR                                                                  │
│     │                                                                        │
│     │ Validate code matches plan + verify citations                         │
│     │                                                                        │
│     ▼                                                                        │
│  👤 CUSTOMER receives working code with source references                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Setup

### Prerequisites

```bash
# Required
- Python 3.11+
- Poetry (for dependency management)
- GitHub Personal Access Token (for API access)

# Optional (for full functionality)
- Docker (for Qdrant/Neo4j)
- Qdrant running on localhost:6333
- Neo4j running on localhost:7687
```

### Installation

#### 1. Clone the Repository

```bash
git clone https://github.com/kevin-toles/ai-platform-data.git
cd ai-platform-data
```

#### 2. Install Dependencies

```bash
poetry install
```

#### 3. Configure Environment

Create a `.env` file or export environment variables:

```bash
# Required for GitHub API (higher rate limits)
export GITHUB_TOKEN="ghp_your_personal_access_token"

# Optional: Qdrant configuration
export QDRANT_HOST="localhost"
export QDRANT_PORT="6333"

# Optional: Neo4j configuration
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_AUTH="neo4j/password"
```

#### 4. Verify Installation

```bash
python3 -c "
from src.code_reference import CodeReferenceEngine

engine = CodeReferenceEngine()
stats = engine.get_statistics()
print(f'✅ Engine loaded: {stats[\"total_repos\"]} repos across {stats[\"domains\"]} domains')
print(f'✅ Mirrored: {stats[\"mirrored_repos\"]} repos')
"
```

Expected output:
```
✅ Engine loaded: 82 repos across 22 domains
✅ Mirrored: 82 repos
```

---

## Usage

### Basic Usage

```python
import asyncio
from src.code_reference import CodeReferenceEngine

async def main():
    async with CodeReferenceEngine() as engine:
        # Search for code patterns
        context = await engine.search(
            query="event-driven saga with compensation",
            domains=["backend-event-driven", "backend-microservices"],
            top_k=10,
        )
        
        # Get formatted context for LLM prompt
        prompt_context = context.to_prompt_context()
        print(prompt_context)
        
        # Get citations for Auditor
        citations = context.get_citations()
        print(f"Sources: {citations}")

asyncio.run(main())
```

### API Reference

#### CodeReferenceEngine

```python
class CodeReferenceEngine:
    """Strategic code retrieval across all mirrored repositories."""
    
    async def search(
        self,
        query: str,                      # Natural language query
        domains: list[str] = None,       # Limit to specific domains
        concepts: list[str] = None,      # Limit to repos with concepts
        top_k: int = 10,                 # Maximum results
        expand_context: bool = True,     # Fetch full file content
        context_lines: int = 20,         # Lines of context around matches
    ) -> CodeContext:
        """Multi-layer retrieval across all repos."""
    
    def get_metadata(self, repo_id: str) -> RepoMetadata | None:
        """Load metadata for a specific repository."""
    
    def get_repos_for_domain(self, domain_id: str) -> list[RepoMetadata]:
        """Get all repos in a domain."""
    
    def get_repos_by_concept(self, concept: str) -> list[RepoMetadata]:
        """Find repos that demonstrate a specific concept."""
    
    def get_repos_by_pattern(self, pattern: str) -> list[RepoMetadata]:
        """Find repos that implement a specific design pattern."""
    
    async def get_file(self, path: str) -> str | None:
        """Fetch a specific file from code-reference-engine."""
    
    async def get_file_with_citation(self, path: str) -> tuple[str | None, str]:
        """Fetch file content and citation URL."""
    
    def get_statistics(self) -> dict[str, Any]:
        """Get engine statistics."""
```

#### GitHubClient

```python
class GitHubClient:
    """Async client for GitHub Contents API."""
    
    async def get_file(self, path: str, ref: str = "main") -> GitHubFile | None:
        """Fetch a single file."""
    
    async def get_file_lines(
        self,
        path: str,
        start_line: int,
        end_line: int,
        context_lines: int = 0,
    ) -> str | None:
        """Fetch specific lines from a file."""
    
    async def list_directory(self, path: str) -> list[dict]:
        """List directory contents."""
    
    async def search_code(
        self,
        query: str,
        path: str = None,
        extension: str = None,
    ) -> list[dict]:
        """Search code in the repository."""
    
    def get_html_url(self, path: str, start_line: int = None, end_line: int = None) -> str:
        """Get GitHub URL for citations."""
```

#### Data Models

```python
@dataclass
class RepoMetadata:
    id: str                    # e.g., "fastapi"
    name: str                  # e.g., "FastAPI"
    source_url: str            # Original GitHub URL
    target_path: str           # Path in code-reference-engine
    domain: str                # e.g., "backend-frameworks"
    tier: str                  # e.g., "T1-architecture"
    priority: int              # 1-10 (1 = highest)
    languages: list[str]       # e.g., ["python"]
    concepts: list[str]        # e.g., ["async", "pydantic", "openapi"]
    patterns: list[str]        # e.g., ["dependency-injection", "middleware"]
    mirrored: bool             # Is code mirrored to code-reference-engine?
    indexed: bool              # Is code indexed in Qdrant?

@dataclass
class CodeContext:
    query: str                           # Original search query
    primary_references: list[CodeReference]  # Retrieved code snippets
    related_repos: list[dict]            # Cross-referenced repos
    domains_searched: list[str]          # Domains that were searched
    total_chunks_found: int              # Total matches found
    
    def to_prompt_context(self) -> str:
        """Format for LLM prompt inclusion."""
    
    def get_citations(self) -> list[str]:
        """Get all citation URLs."""
```

---

## Domain Reference

### Available Domains

| Domain ID | Description | Repo Count |
|-----------|-------------|------------|
| `game-dev-engines` | Game engines (Godot, Urho3D, OGRE) | 4 |
| `game-dev-systems` | ECS, input, UI (EnTT, SDL, ImGui) | 4 |
| `game-dev-rendering` | Graphics (bgfx, Filament, Vulkan) | 4 |
| `game-dev-physics` | Physics (Bullet, Box2D) | 2 |
| `game-dev-ai` | Navigation, behavior trees | 2 |
| `cpp-core` | C++ libraries (Abseil, folly, glm) | 4 |
| `backend-frameworks` | Web frameworks (FastAPI, Django, Spring) | 10 |
| `backend-microservices` | Reference architectures (eShop, FTGO) | 4 |
| `backend-event-driven` | Event streaming (Kafka) | 2 |
| `backend-serverless` | Serverless patterns | 2 |
| `backend-ddd` | Domain-driven design samples | 1 |
| `frontend-frameworks` | UI frameworks (React, Vue, Angular) | 4 |
| `frontend-micro-frontends` | Micro-frontend patterns | 1 |
| `infrastructure` | IaC (Terraform, K8s, Helm) | 6 |
| `databases` | Database internals (PostgreSQL, Redis) | 5 |
| `security` | Auth, secrets (Keycloak, Vault) | 3 |
| `monitoring` | Observability (Prometheus, Grafana) | 4 |
| `testing` | Test frameworks (pytest, Selenium) | 6 |
| `ml-frameworks` | ML (PyTorch, TensorFlow, Transformers) | 6 |
| `ml-ops` | MLOps (MLflow, Kubeflow, Airflow) | 3 |
| `build-systems` | Build tools (CMake, Bazel) | 3 |
| `networking` | Game networking (ENet, Steam) | 2 |

### Common Concepts

```python
# Find repos by concept
engine.get_repos_by_concept("saga")           # → ftgo
engine.get_repos_by_concept("ecs")            # → entt, godot
engine.get_repos_by_concept("event-driven")   # → kafka, ftgo, eshop
engine.get_repos_by_concept("grpc")           # → online-boutique
engine.get_repos_by_concept("behavior-tree")  # → behaviortree-cpp
```

### Common Patterns

```python
# Find repos by design pattern
engine.get_repos_by_pattern("saga")           # → ftgo
engine.get_repos_by_pattern("cqrs")           # → eshop
engine.get_repos_by_pattern("component")      # → godot, entt
engine.get_repos_by_pattern("observer")       # → godot, react
```

---

## Integration Examples

### 1. Sous Chef Integration (Code-Orchestrator-Service)

```python
# In Code-Orchestrator-Service

from ai_platform_data.src.code_reference import CodeReferenceEngine

class SousChef:
    def __init__(self):
        self.code_engine = CodeReferenceEngine()
    
    async def prepare_context(self, user_query: str) -> dict:
        """Extract concepts and retrieve relevant code."""
        
        # Step 1: Extract concepts (using CodeT5+ or similar)
        concepts = await self.extract_concepts(user_query)
        # → ["event-driven", "saga", "compensation", "microservices"]
        
        # Step 2: Determine relevant domains
        domains = self.map_concepts_to_domains(concepts)
        # → ["backend-event-driven", "backend-microservices"]
        
        # Step 3: Retrieve code
        async with self.code_engine as engine:
            context = await engine.search(
                query=user_query,
                domains=domains,
                concepts=concepts,
                top_k=15,
            )
        
        # Step 4: Format for Line Cook
        return {
            "user_query": user_query,
            "code_context": context.to_prompt_context(),
            "citations": context.get_citations(),
            "domains_searched": context.domains_searched,
        }
```

### 2. Direct File Retrieval

```python
async with CodeReferenceEngine() as engine:
    # Get a specific file
    content = await engine.get_file("backend/frameworks/fastapi/fastapi/main.py")
    
    # Get file with citation for Auditor
    content, citation = await engine.get_file_with_citation(
        "game-dev/engines/godot/core/object/object.cpp"
    )
    print(f"Source: {citation}")
    # → https://github.com/kevin-toles/code-reference-engine/blob/main/game-dev/engines/godot/core/object/object.cpp
```

### 3. Domain-Specific Search

```python
async with CodeReferenceEngine() as engine:
    # Search only game development repos
    context = await engine.search(
        query="component entity system update loop",
        domains=["game-dev-systems", "game-dev-engines"],
        top_k=5,
    )
    
    # Search only ML repos
    ml_context = await engine.search(
        query="transformer attention mechanism",
        domains=["ml-frameworks"],
        top_k=10,
    )
```

### 4. Pattern Discovery

```python
engine = CodeReferenceEngine()

# Find all repos implementing saga pattern
saga_repos = engine.get_repos_by_pattern("saga")
for repo in saga_repos:
    print(f"{repo.name}: {repo.target_path}")
    print(f"  Concepts: {repo.concepts}")
    print(f"  Why: {repo.why_include}")
```

---

## Rate Limits & Best Practices

### GitHub API Limits

| Auth Status | Rate Limit |
|-------------|------------|
| No token | 60 requests/hour |
| With token | 5,000 requests/hour |

**Always use a GitHub token in production.**

### Best Practices

1. **Use domain filters** - Narrow searches to relevant domains
2. **Cache metadata** - RepoMetadata is cached automatically
3. **Batch requests** - Use `search()` instead of multiple `get_file()` calls
4. **Set reasonable top_k** - Start with 10, increase if needed
5. **Use concepts/patterns** - More specific than broad queries

### Error Handling

```python
async with CodeReferenceEngine() as engine:
    try:
        context = await engine.search(query="...")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            print("Rate limited - wait or use token")
        elif e.response.status_code == 404:
            print("File not found")
```

---

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 3** | ✅ Complete | Metadata system (82 repos) |
| **Phase 4a** | ✅ Complete | Mark repos as mirrored |
| **Phase 4b** | ⏳ Pending | Index code chunks in Qdrant |
| **Phase 4c** | ⏳ Pending | Neo4j repo relationships |
| **Phase 5** | ⏳ Pending | Wire into Code-Orchestrator-Service |

### Upcoming Features

- **Qdrant indexing**: Pre-indexed semantic search across all code
- **Neo4j graph**: Cross-reference relationships between repos
- **Incremental sync**: Auto-update when upstream repos change
- **AST parsing**: Language-aware code chunking

---

## Troubleshooting

### Common Issues

**"Rate limited" errors**
```bash
export GITHUB_TOKEN="ghp_your_token"
```

**"Module not found"**
```bash
cd ai-platform-data
poetry install
```

**"Repo not mirrored"**
Check if the repo exists in code-reference-engine:
```bash
gh api repos/kevin-toles/code-reference-engine/contents/game-dev/engines
```

**Empty search results**
1. Check domain spelling
2. Try broader concepts
3. Verify repo is mirrored (`metadata.mirrored == True`)

---

## Contributing

1. Add new repos to `repos/repo_registry.json`
2. Create metadata file in `repos/metadata/{domain}/{repo}.json`
3. Trigger mirroring via GitHub Actions
4. Update documentation

See [CODE_REFERENCE_ENGINE_DESIGN.md](CODE_REFERENCE_ENGINE_DESIGN.md) for detailed design decisions.
