# Code Reference Engine - Design Document

## Overview

The **Code Reference Engine** is a curated library of cloned repositories organized for semantic search, pattern extraction, and architecture reasoning. It serves as the "reference brain" for the AI platform's code understanding capabilities.

### Core Concept (from source document)

> Your **Sous Chef** service uses your code-understanding models to turn a request ("UE5 replication + ability system," "event-driven saga," "RAG chunking") into the right **concept keywords + pattern candidates**, sends those into your **Semantic Search**, pulls back the most relevant snippets/diagrams/configs from the repo library, and then hands curated context to your **coding model** to generate an implementation—while your **Auditor** verifies the final code matches the plan and includes the receipts/citations you care about.

---

## Architecture

### Two-Repo Strategy

```
ai-platform-data/                      ← Catalog & Index
├── repos/
│   ├── repo_registry.json            ← Master registry
│   └── metadata/                     ← Metadata pointers
│       ├── game-dev/
│       │   └── godot.json           → points to code-reference-engine/game-dev/engines/godot/
│       └── backend/
│           └── spring-boot.json     → points to code-reference-engine/backend/frameworks/spring-boot/
├── schemas/
│   ├── repo_metadata.schema.json
│   └── repo_registry.schema.json
└── taxonomies/

code-reference-engine/                 ← Actual Code Library (GitHub)
├── cpp/
│   ├── core/
│   ├── memory/
│   └── ecs/
├── game-dev/
│   ├── unreal/
│   │   ├── engine/
│   │   ├── gameplay/
│   │   └── networking/
│   ├── engines/
│   ├── systems/
│   ├── rendering/
│   ├── physics/
│   └── ai/
├── backend/
│   ├── frameworks/
│   ├── microservices/
│   ├── event-driven/
│   ├── serverless/
│   └── ddd/
├── frontend/
│   ├── frameworks/
│   └── micro-frontends/
├── infrastructure/
├── databases/
├── security/
├── monitoring/
├── testing/
├── ml/
│   ├── frameworks/
│   └── ops/
└── build-systems/
```

### Why This Structure?

| Concern | Location | Rationale |
|---------|----------|-----------|
| **Metadata & Search Index** | `ai-platform-data` | Keeps catalog with books, taxonomies |
| **Actual Source Code** | `code-reference-engine` | Dedicated repo for code, organized by domain |
| **Schemas** | `ai-platform-data/schemas/` | Consistent with existing schema patterns |

---

## Storage Strategy

### Problem
- ~100-150 GB of repos if cloned locally with full history
- ~30-50 GB even with shallow clones
- User has limited local storage

### Solution: GitHub as Storage Backend

| What | Where | Cost |
|------|-------|------|
| Metadata JSON files | `ai-platform-data` repo | ~500 KB |
| Actual code (mirrored) | `code-reference-engine` repo | **GitHub's servers (free)** |
| Your local machine | Only metadata repo | ~1 MB |

### Import Strategy (Not Fork)

**Forks are linked to originals** - if original is deleted, fork may lose data.

**Mirrors are independent copies** - you keep everything.

```yaml
# GitHub Action to mirror repos (runs on GitHub's servers)
name: Mirror Repository
on: workflow_dispatch
jobs:
  mirror:
    runs-on: ubuntu-latest
    steps:
      - name: Mirror repo
        run: |
          git clone --mirror ${{ inputs.source_url }}
          cd *.git
          git push --mirror https://github.com/kevin-toles/code-reference-engine.git
```

### Submodule vs Subtree vs Monorepo

| Approach | Pros | Cons | Recommendation |
|----------|------|------|----------------|
| **Submodules** | Each repo independent, easy updates | Complex management, extra commands | ❌ |
| **Subtrees** | Single repo, simpler | Harder to update from upstream | ⚠️ |
| **Monorepo (sparse)** | Single repo, organized folders | Large, but can sparse checkout | ✅ |

**Recommendation: Monorepo with sparse checkout capability**

---

## Kitchen Brigade Integration

### How Agents Access Code

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         KITCHEN BRIGADE                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────────┐ │
│  │   SOMMELIER  │     │  SOUS CHEF   │     │      CHEF DE PARTIE      │ │
│  │              │     │              │     │                          │ │
│  │ "I need UE5  │────▶│ Query:       │────▶│ Generate implementation  │ │
│  │  replication │     │ - concepts   │     │ using retrieved context  │ │
│  │  patterns"   │     │ - patterns   │     │                          │ │
│  └──────────────┘     │ - repos      │     └──────────────────────────┘ │
│                       └──────┬───────┘                                   │
│                              │                                           │
│         ┌────────────────────┼────────────────────┐                     │
│         ▼                    ▼                    ▼                     │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────────┐           │
│  │  Metadata   │     │   Qdrant    │     │  GitHub/Source  │           │
│  │  Registry   │     │  Embeddings │     │     graph API   │           │
│  │             │     │             │     │                 │           │
│  │ repo_registry│    │ Code chunks │     │ On-demand file  │           │
│  │ .json       │     │ embedded    │     │ retrieval       │           │
│  └─────────────┘     └─────────────┘     └─────────────────┘           │
│         │                    │                    │                     │
│         └────────────────────┼────────────────────┘                     │
│                              ▼                                           │
│                   ┌─────────────────┐                                   │
│                   │    AUDITOR      │                                   │
│                   │                 │                                   │
│                   │ Verify code     │                                   │
│                   │ matches plan +  │                                   │
│                   │ cite sources    │                                   │
│                   └─────────────────┘                                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Query Flow

1. **User Request** → Sommelier interprets intent
2. **Sous Chef** receives structured query
   - Looks up `repo_registry.json` for relevant domains
   - Queries Qdrant for semantically similar code chunks
   - Optionally fetches specific files via GitHub API
3. **Context Assembly** → Relevant snippets + architecture patterns
4. **Chef de Partie** → Generates implementation with context
5. **Auditor** → Validates output, adds citations

### API Options for Retrieval

| Method | Use Case | Latency | Depth |
|--------|----------|---------|-------|
| **Qdrant (local embeddings)** | Semantic search on indexed code | Fast | Deep |
| **GitHub Code Search API** | Broad discovery, keyword search | Medium | Shallow |
| **GitHub Contents API** | Fetch specific files | Fast | Single file |
| **Sourcegraph API** | Semantic code intelligence | Fast | Deep |
| **Local sparse checkout** | Heavy analysis, AST parsing | Slow (initial) | Full |

### Recommended Hybrid Approach

```python
class CodeReferenceEngine:
    """Unified interface for code retrieval"""
    
    def __init__(self):
        self.registry = load_registry("ai-platform-data/repos/repo_registry.json")
        self.qdrant = QdrantClient(...)
        self.github = GitHubClient(...)
    
    def search(self, query: str, domain: str = None) -> list[CodeSnippet]:
        """
        1. Check Qdrant for embedded chunks (fast, semantic)
        2. Fall back to GitHub API for non-indexed repos
        3. Return ranked results with source citations
        """
        results = []
        
        # Semantic search in indexed repos
        embedded_results = self.qdrant.search(
            collection="code_chunks",
            query_vector=embed(query),
            filter={"domain": domain} if domain else None
        )
        results.extend(embedded_results)
        
        # GitHub API for broader search
        if len(results) < 10:
            repos = self.registry.get_repos_for_domain(domain)
            github_results = self.github.search_code(query, repos)
            results.extend(github_results)
        
        return results
    
    def get_file(self, repo: str, path: str) -> str:
        """Fetch specific file content"""
        return self.github.get_contents(repo, path)
    
    def get_pattern_examples(self, pattern: str) -> list[CodeSnippet]:
        """Find implementations of a specific pattern"""
        repos = self.registry.get_repos_for_pattern(pattern)
        return self.search(pattern, repos=repos)
```

---

## Complete Repository Manifest

### Game Development

#### Engines (game-dev/engines/)
| Repo | Source | License | Priority | Key Concepts |
|------|--------|---------|----------|--------------|
| Godot | `godotengine/godot` | MIT | 1 | Scene graph, GDScript, editor architecture |
| Urho3D | `urho3d/Urho3D` | MIT | 2 | Component system, lightweight engine |
| OGRE 3D | `OGRECave/ogre` | MIT | 3 | Rendering, scene graph, materials |
| OpenMW | `OpenMW/openmw` | GPL-3.0 | 4 | Open-world, modding, save systems |

#### Unreal Engine (game-dev/unreal/)
| Repo | Source | License | Priority | Key Concepts |
|------|--------|---------|----------|--------------|
| Unreal Engine | `EpicGames/UnrealEngine` | Epic EULA | 1 | Full engine, GAS, replication, UBT |
| Lyra Starter Game | Epic Launcher | Epic EULA | 1 | Modern UE5 architecture, GAS, modular |
| ActionRPG | Epic Samples | Epic EULA | 2 | Gameplay Ability System reference |
| ShooterGame | Epic Samples | Epic EULA | 3 | Networking, replication |
| StrategyGame | Epic Samples | Epic EULA | 4 | AI, pathfinding, RTS patterns |

#### Game Systems (game-dev/systems/)
| Repo | Source | License | Priority | Key Concepts |
|------|--------|---------|----------|--------------|
| EnTT | `skypjack/entt` | MIT | 1 | ECS, modern C++, header-only |
| SDL2 | `libsdl-org/SDL` | Zlib | 2 | Windowing, input, audio |
| GLFW | `glfw/glfw` | Zlib | 3 | Window/context creation |
| ImGui | `ocornut/imgui` | MIT | 2 | Immediate-mode UI |

#### Rendering (game-dev/rendering/)
| Repo | Source | License | Priority | Key Concepts |
|------|--------|---------|----------|--------------|
| bgfx | `bkaradzic/bgfx` | BSD-2 | 1 | Cross-platform rendering abstraction |
| Filament | `google/filament` | Apache-2.0 | 1 | PBR rendering engine |
| The Forge | `ConfettiFX/The-Forge` | Apache-2.0 | 2 | High-performance rendering |
| Vulkan-Samples | `KhronosGroup/Vulkan-Samples` | Apache-2.0 | 2 | Low-level graphics patterns |
| DirectX-Graphics-Samples | `microsoft/DirectX-Graphics-Samples` | MIT | 3 | DX12 rendering |

#### Physics (game-dev/physics/)
| Repo | Source | License | Priority | Key Concepts |
|------|--------|---------|----------|--------------|
| Bullet Physics | `bulletphysics/bullet3` | Zlib | 1 | Physics simulation |
| PhysX | `NVIDIA-Omniverse/PhysX` | BSD-3 | 2 | Physics engine (UE uses this) |
| Box2D | `erincatto/box2d` | MIT | 3 | 2D physics |

#### Game AI (game-dev/ai/)
| Repo | Source | License | Priority | Key Concepts |
|------|--------|---------|----------|--------------|
| Recast & Detour | `recastnavigation/recastnavigation` | Zlib | 1 | Navigation mesh, pathfinding |
| BehaviorTree.CPP | `BehaviorTree/BehaviorTree.CPP` | MIT | 1 | Behavior trees |
| OpenSteer | `opensteer/opensteer` | MIT | 3 | Steering behaviors |

### C++ Core (cpp/)

#### Core Libraries (cpp/core/)
| Repo | Source | License | Priority | Key Concepts |
|------|--------|---------|----------|--------------|
| Boost | `boostorg/boost` | BSL-1.0 | 1 | Comprehensive C++ utilities |
| Abseil | `abseil/abseil-cpp` | Apache-2.0 | 2 | Google's C++ library |
| folly | `facebook/folly` | Apache-2.0 | 3 | Facebook's C++ library |

#### Math (cpp/math/)
| Repo | Source | License | Priority | Key Concepts |
|------|--------|---------|----------|--------------|
| Eigen | `eigenteam/eigen` | MPL-2.0 | 1 | Linear algebra |
| glm | `g-truc/glm` | MIT | 1 | Graphics math |

### Backend Architecture

#### Frameworks (backend/frameworks/)
| Repo | Source | License | Priority | Key Concepts |
|------|--------|---------|----------|--------------|
| Spring Boot | `spring-projects/spring-boot` | Apache-2.0 | 1 | Java microservices, auto-config |
| Django | `django/django` | BSD-3 | 1 | Python MVC, ORM, batteries-included |
| FastAPI | `tiangolo/fastapi` | MIT | 1 | Python async APIs, Pydantic |
| Flask | `pallets/flask` | BSD-3 | 2 | Python microframework |
| Express | `expressjs/express` | MIT | 1 | Node.js web framework |
| Koa | `koajs/koa` | MIT | 2 | Node.js async middleware |
| Rails | `rails/rails` | MIT | 1 | Ruby MVC, convention over config |
| Laravel | `laravel/laravel` | MIT | 2 | PHP web framework |
| ASP.NET Core | `dotnet/aspnetcore` | Apache-2.0 | 1 | C# web framework |
| Phoenix | `phoenixframework/phoenix` | MIT | 3 | Elixir real-time framework |

#### Microservices Examples (backend/microservices/)
| Repo | Source | License | Priority | Key Concepts |
|------|--------|---------|----------|--------------|
| eShopOnContainers | `dotnet-architecture/eShopOnContainers` | MIT | 1 | .NET microservices, DDD, Docker, K8s |
| Online Boutique | `GoogleCloudPlatform/microservices-demo` | Apache-2.0 | 1 | Polyglot, gRPC, Kubernetes, Istio |
| FTGO Application | `microservices-patterns/ftgo-application` | Apache-2.0 | 2 | Sagas, event-driven, Java |
| Spring PetClinic | `spring-projects/spring-petclinic` | Apache-2.0 | 2 | Layered monolith, Spring MVC |

#### Event-Driven (backend/event-driven/)
| Repo | Source | License | Priority | Key Concepts |
|------|--------|---------|----------|--------------|
| Event-Driven Microservices Demo | `gschmutz/event-driven-microservices-demo` | Apache-2.0 | 1 | Kafka, event coordination |
| Apache Kafka | `apache/kafka` | Apache-2.0 | 1 | Event streaming platform |

#### Serverless (backend/serverless/)
| Repo | Source | License | Priority | Key Concepts |
|------|--------|---------|----------|--------------|
| AWS Serverless Airline | `aws-samples/aws-serverless-airline-booking` | MIT-0 | 1 | Lambda, DynamoDB, Step Functions |
| OpenFaaS | `openfaas/faas` | MIT | 2 | Serverless on Kubernetes |

#### DDD (backend/ddd/)
| Repo | Source | License | Priority | Key Concepts |
|------|--------|---------|----------|--------------|
| DDD Cargo Sample | `citerus/dddsample-core` | Apache-2.0 | 1 | Aggregates, bounded contexts, domain events |

### Frontend

#### Frameworks (frontend/frameworks/)
| Repo | Source | License | Priority | Key Concepts |
|------|--------|---------|----------|--------------|
| React | `facebook/react` | MIT | 1 | Component model, virtual DOM |
| Angular | `angular/angular` | MIT | 1 | Full MVC framework |
| Vue | `vuejs/vue` | MIT | 1 | Progressive framework |
| Svelte | `sveltejs/svelte` | MIT | 2 | Compiler-based components |

#### Micro-Frontends (frontend/micro-frontends/)
| Repo | Source | License | Priority | Key Concepts |
|------|--------|---------|----------|--------------|
| single-spa | `single-spa/single-spa` | MIT | 1 | Micro-frontend orchestration |

### Infrastructure

#### Containers & Orchestration (infrastructure/)
| Repo | Source | License | Priority | Key Concepts |
|------|--------|---------|----------|--------------|
| Kubernetes | `kubernetes/kubernetes` | Apache-2.0 | 1 | Container orchestration |
| Kubernetes The Hard Way | `kelseyhightower/kubernetes-the-hard-way` | Apache-2.0 | 1 | K8s internals tutorial |
| Docker (Moby) | `moby/moby` | Apache-2.0 | 1 | Containerization |
| Terraform | `hashicorp/terraform` | MPL-2.0 | 1 | Infrastructure as Code |
| Ansible | `ansible/ansible` | GPL-3.0 | 2 | Configuration management |
| Helm | `helm/helm` | Apache-2.0 | 2 | K8s package manager |

### Databases

| Repo | Source | License | Priority | Key Concepts |
|------|--------|---------|----------|--------------|
| PostgreSQL | `postgres/postgres` | PostgreSQL | 1 | Advanced RDBMS |
| Redis | `redis/redis` | BSD-3 | 1 | In-memory data store |
| Apache Cassandra | `apache/cassandra` | Apache-2.0 | 2 | Distributed NoSQL |
| CockroachDB | `cockroachdb/cockroach` | BSL/Apache-2.0 | 3 | Distributed SQL |
| OpenSearch | `opensearch-project/OpenSearch` | Apache-2.0 | 2 | Search and analytics |

### Security

| Repo | Source | License | Priority | Key Concepts |
|------|--------|---------|----------|--------------|
| Keycloak | `keycloak/keycloak` | Apache-2.0 | 1 | Identity, OAuth2, SSO |
| Vault | `hashicorp/vault` | MPL-2.0 | 1 | Secrets management |
| OWASP ZAP | `zaproxy/zaproxy` | Apache-2.0 | 2 | Security testing |

### Monitoring & Observability

| Repo | Source | License | Priority | Key Concepts |
|------|--------|---------|----------|--------------|
| Prometheus | `prometheus/prometheus` | Apache-2.0 | 1 | Metrics monitoring |
| Grafana | `grafana/grafana` | AGPL-3.0 | 1 | Dashboards, visualization |
| Jaeger | `jaegertracing/jaeger` | Apache-2.0 | 2 | Distributed tracing |
| Loki | `grafana/loki` | AGPL-3.0 | 2 | Log aggregation |

### Testing

| Repo | Source | License | Priority | Key Concepts |
|------|--------|---------|----------|--------------|
| Selenium | `SeleniumHQ/selenium` | Apache-2.0 | 1 | Browser automation |
| Cypress | `cypress-io/cypress` | MIT | 1 | E2E testing |
| JMeter | `apache/jmeter` | Apache-2.0 | 2 | Load testing |
| Locust | `locustio/locust` | MIT | 2 | Python load testing |
| JUnit 5 | `junit-team/junit5` | EPL-2.0 | 1 | Java unit testing |
| pytest | `pytest-dev/pytest` | MIT | 1 | Python testing |

### Machine Learning

#### Frameworks (ml/frameworks/)
| Repo | Source | License | Priority | Key Concepts |
|------|--------|---------|----------|--------------|
| TensorFlow | `tensorflow/tensorflow` | Apache-2.0 | 1 | Deep learning platform |
| PyTorch | `pytorch/pytorch` | BSD-3 | 1 | Dynamic deep learning |
| scikit-learn | `scikit-learn/scikit-learn` | BSD-3 | 1 | Classical ML algorithms |
| Hugging Face Transformers | `huggingface/transformers` | Apache-2.0 | 1 | NLP models |
| XGBoost | `dmlc/xgboost` | Apache-2.0 | 2 | Gradient boosting |
| Ray | `ray-project/ray` | Apache-2.0 | 2 | Distributed ML |

#### MLOps (ml/ops/)
| Repo | Source | License | Priority | Key Concepts |
|------|--------|---------|----------|--------------|
| MLflow | `mlflow/mlflow` | Apache-2.0 | 1 | ML lifecycle management |
| Kubeflow | `kubeflow/kubeflow` | Apache-2.0 | 2 | ML on Kubernetes |
| Airflow | `apache/airflow` | Apache-2.0 | 1 | Workflow orchestration |

### Build Systems

| Repo | Source | License | Priority | Key Concepts |
|------|--------|---------|----------|--------------|
| CMake | `Kitware/CMake` | BSD-3 | 1 | Cross-platform builds |
| Premake | `premake/premake-core` | BSD-3 | 2 | Game-friendly builds |
| Bazel | `bazelbuild/bazel` | Apache-2.0 | 2 | Scalable builds |
| FastBuild | `fastbuild/fastbuild` | MIT | 3 | Distributed C++ builds |

### Networking

| Repo | Source | License | Priority | Key Concepts |
|------|--------|---------|----------|--------------|
| ENet | `lsalzman/enet` | MIT | 1 | Reliable UDP |
| SteamNetworkingSockets | `ValveSoftware/GameNetworkingSockets` | BSD-3 | 1 | Game networking |

---

## Total Repository Count

| Domain | Count |
|--------|-------|
| Game Dev - Engines | 4 |
| Game Dev - Unreal | 5 |
| Game Dev - Systems | 4 |
| Game Dev - Rendering | 5 |
| Game Dev - Physics | 3 |
| Game Dev - AI | 3 |
| C++ Core | 5 |
| Backend - Frameworks | 10 |
| Backend - Microservices | 4 |
| Backend - Event-Driven | 2 |
| Backend - Serverless | 2 |
| Backend - DDD | 1 |
| Frontend | 5 |
| Infrastructure | 6 |
| Databases | 5 |
| Security | 3 |
| Monitoring | 4 |
| Testing | 6 |
| ML - Frameworks | 6 |
| ML - Ops | 3 |
| Build Systems | 4 |
| Networking | 2 |
| **TOTAL** | **~92 repos** |

---

## Implementation Plan

### Phase 1: Setup (This Session)
1. ✅ Design document (this file)
2. Create schemas in `ai-platform-data`
3. Create folder structure in `code-reference-engine`
4. Create GitHub Action for mirroring

### Phase 2: Batch Mirroring
- Run GitHub Action to mirror repos in batches
- Each batch: ~10-15 repos to avoid rate limits
- Estimated: 6-8 batches over several hours

### Phase 3: Metadata Generation
- Generate metadata JSON for each repo
- Link to `code-reference-engine` paths
- Populate `repo_registry.json`

### Phase 4: Indexing
- Index key repos into Qdrant
- Generate embeddings for code chunks
- Build search index

### Phase 5: Integration
- Connect to Sous Chef service
- Implement query routing
- Test end-to-end flow

---

## Estimated Sizes

| Approach | Size on GitHub |
|----------|----------------|
| Full history (all repos) | ~100-150 GB |
| Shallow clones (--depth 1) | ~40-60 GB |
| Code only (no assets) | ~30-50 GB |

**GitHub Free Tier: Unlimited public repo storage**

---

## Next Steps

1. Review this document
2. Confirm repository list is complete
3. Revert current changes in both repos
4. Begin clean implementation following this design
