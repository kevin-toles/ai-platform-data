# AI Platform Network Architecture

> **Kitchen Brigade Pattern + Tiered Docker Networks**
>
> Last Updated: December 31, 2025

## Overview

This document describes the production-ready network architecture for the AI Platform, combining the **Kitchen Brigade** service pattern with **tiered Docker networks** for security isolation.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    COMPLETE KITCHEN BRIGADE                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  FRONT OF HOUSE (gateway-network)                                       │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │   👨‍🍳 MAÎTRE D' / ROUTER                                          │  │
│  │   ┌─────────────────┐     ┌─────────────────┐                     │  │
│  │   │   llm-gateway   │     │     redis       │                     │  │
│  │   │     :8080       │     │     :6379       │                     │  │
│  │   │                 │     │    (cache)      │                     │  │
│  │   └────────┬────────┘     └─────────────────┘                     │  │
│  │            │ (also on ai-platform-network)                        │  │
│  └────────────┼──────────────────────────────────────────────────────┘  │
│               │                                                         │
│               ▼                                                         │
│  KITCHEN (ai-platform-network)                                          │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                                                                   │  │
│  │   👨‍🍳 EXPEDITOR                                                    │  │
│  │   ┌─────────────────┐                                             │  │
│  │   │    ai-agents    │ • Orchestrates MSEP Pipeline                │  │
│  │   │      :8082      │ • Coordinates all kitchen staff             │  │
│  │   └───┬───────┬───┬─┘                                             │  │
│  │       │       │   │                                               │  │
│  │       ▼       │   ▼                                               │  │
│  │   👨‍🍳 SOUS      │  🔍 AUDITOR                                       │  │
│  │   CHEF        │  ┌──────────────┐                                 │  │
│  │   ┌──────────┐│  │ audit-       │                                 │  │
│  │   │code-orch ││  │ service:8084 │                                 │  │
│  │   │  :8083   ││  │              │                                 │  │
│  │   │          ││  │•Anti-Pattern │                                 │  │
│  │   │•Metadata ││  │•Compliance   │                                 │  │
│  │   │•Keywords ││  │•Checkpoints  │                                 │  │
│  │   └────┬─────┘│  └──────────────┘                                 │  │
│  │        │      │                                                   │  │
│  │        │      ▼                                                   │  │
│  │        │  👨‍🍳 COOKBOOK                                             │  │
│  │        │  ┌───────────────────┐                                   │  │
│  │        │  │  semantic-search  │                                   │  │
│  │        │  │      :8081        │                                   │  │
│  │        │  │                   │                                   │  │
│  │        │  │• Vector Search    │                                   │  │
│  │        │  │• Graph Queries    │                                   │  │
│  │        │  └─────────┬─────────┘                                   │  │
│  │        │            │ (also on data-network)                      │  │
│  │        │            │                                             │  │
│  │   ┌────┴────────────┴─────┐                                       │  │
│  │   │  👨‍🍳 LINE COOK         │                                       │  │
│  │   │  ┌─────────────────┐  │                                       │  │
│  │   │  │inference-service│  │ ◄── Toggle: Docker or Native (Metal)  │  │
│  │   │  │     :8085       │  │     via Platform Control Panel        │  │
│  │   │  │  • LLM Inference│  │                                       │  │
│  │   │  └─────────────────┘  │                                       │  │
│  │   └───────────────────────┘                                       │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  PANTRY / STORAGE (data-network)                                        │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │                                                                   │  │
│  │   ┌────────────┐   ┌────────────┐   ┌────────────┐               │  │
│  │   │   redis    │   │   neo4j    │   │   qdrant   │               │  │
│  │   │   :6379    │   │   :7687    │   │   :6333    │               │  │
│  │   │  (cache)   │   │  (graph)   │   │  (vectors) │               │  │
│  │   └────────────┘   └────────────┘   └────────────┘               │  │
│  │                                                                   │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

NATIVE MODE (macOS with Metal GPU):
┌───────────────────────────────────────────────────────────────────┐
│  When inference-service is toggled to Native mode:                │
│  - Runs on host with Metal GPU acceleration                       │
│  - Docker services access via host.docker.internal:8085           │
│  - Performance: 30-100 tokens/sec (vs 0.04 in Docker CPU mode)    │
└───────────────────────────────────────────────────────────────────┘
```

---

## Kitchen Brigade Roles

| Role | Service | Port | Responsibility |
|------|---------|------|----------------|
| **Maître d' / Router** | llm-gateway | 8080 | External API entry point, authentication, rate limiting, request routing |
| **Expeditor** | ai-agents | 8082 | Orchestrates MSEP pipeline, coordinates all services |
| **Sous Chef** | code-orchestrator | 8083 | Metadata extraction, keyword analysis, code understanding |
| **Cookbook** | semantic-search | 8081 | Vector similarity search, graph traversal, knowledge retrieval |
| **Auditor** | audit-service | 8084 | Anti-pattern detection, compliance validation, checkpoint verification |
| **Line Cook** | inference-service | 8085 | LLM inference - toggleable between Docker (CUDA) and Native (Metal) |

---

## Network Tiers

### 1. Gateway Network (`gateway-network`)
**Purpose**: External-facing DMZ tier

- Only `llm-gateway` and `redis` are on this network
- This is the only network exposed to external traffic
- Provides security isolation for internal services

### 2. Platform Network (`ai-platform-network`)
**Purpose**: Internal service mesh for application logic

- All application services communicate here
- `llm-gateway` bridges from gateway-network to here
- Services can discover each other by container name

### 3. Data Network (`data-network`)
**Purpose**: Database and storage tier

- Contains: redis, neo4j, qdrant
- Only services that need data access are connected
- Gateway cannot directly access databases (must go through service layer)

### 4. Host Network (Native)
**Purpose**: GPU-accelerated inference

- `inference-service` runs natively on macOS for Metal GPU access
- Docker services access via `host.docker.internal:8085`
- Performance: 30-100 tokens/sec (vs 0.04 tokens/sec in Docker)

---

## Network Membership Matrix

| Service | gateway-network | ai-platform-network | data-network | Notes |
|---------|:---------------:|:-------------------:|:------------:|-------|
| **llm-gateway** | ✅ | ✅ | ❌ | Entry point, bridges gateway→platform |
| **ai-agents** | ❌ | ✅ | ✅ | Expeditor, needs data access |
| **code-orchestrator** | ❌ | ✅ | ❌ | Sous Chef |
| **semantic-search** | ❌ | ✅ | ✅ | Cookbook, queries neo4j/qdrant |
| **audit-service** | ❌ | ✅ | ❌ | Auditor |
| **inference-service** | ❌ | ✅ | ❌ | Line Cook - Docker or Native (toggle) |
| **redis** | ✅ | ❌ | ✅ | Cache for gateway sessions |
| **neo4j** | ❌ | ❌ | ✅ | Graph database |
| **qdrant** | ❌ | ❌ | ✅ | Vector database |

---

## Request Flow Examples

### Example 1: Document Enrichment (MSEP Pipeline)

```
1. Client Request
   └─► llm-gateway:8080          [gateway-network]
       │
2. Route to Expeditor
   └─► ai-agents:8082            [ai-platform-network]
       │
3. Extract Metadata
   └─► code-orchestrator:8083    [ai-platform-network]
       │
4. Generate Summary (LLM)
   └─► inference-service:8085    [host.docker.internal]
       │
5. Semantic Search
   └─► semantic-search:8081      [ai-platform-network]
       │
6. Query Knowledge Graph
   └─► neo4j:7687                [data-network]
       │
7. Response flows back up the chain
```

### Example 2: Direct LLM Query

```
1. Client Request
   └─► llm-gateway:8080          [gateway-network]
       │
2. Route to Inference
   └─► inference-service:8085    [host.docker.internal]
       │
3. Response
```

---

## Service URLs (Internal)

When services communicate within Docker, use **container names** (not localhost):

| From | To | URL |
|------|----|-----|
| llm-gateway | ai-agents | `http://ai-agents:8082` |
| llm-gateway | inference | `http://inference-service:8085` or `http://host.docker.internal:8085` |
| ai-agents | code-orchestrator | `http://code-orchestrator-service:8083` |
| ai-agents | semantic-search | `http://semantic-search-service:8081` |
| ai-agents | audit-service | `http://audit-service:8084` |
| ai-agents | inference | `http://inference-service:8085` or `http://host.docker.internal:8085` |
| ai-agents | neo4j | `bolt://neo4j:7687` |
| code-orchestrator | inference | `http://inference-service:8085` or `http://host.docker.internal:8085` |
| semantic-search | neo4j | `bolt://neo4j:7687` |
| semantic-search | qdrant | `http://qdrant:6333` |
| audit-service | inference | `http://inference-service:8085` or `http://host.docker.internal:8085` |

> **Note**: When inference-service is in Native mode (Metal GPU), use `host.docker.internal:8085`.
> When in Docker mode, use `inference-service:8085`.

---

## Security Benefits

1. **Network Isolation**: External traffic can only reach `llm-gateway`
2. **Defense in Depth**: Gateway cannot directly query databases
3. **Least Privilege**: Services only have access to networks they need
4. **Native GPU Access**: inference-service runs on host for Metal acceleration

---

## Network Setup Commands

### Create Networks (One-time setup)

```bash
# Create all three networks
docker network create gateway-network
docker network create ai-platform-network
docker network create data-network
```

### Verify Networks

```bash
# List networks
docker network ls | grep -E "gateway|ai-platform|data"

# Inspect network membership
docker network inspect ai-platform-network --format '{{range .Containers}}{{.Name}} {{end}}'
```

### Restart All Services

```bash
# Stop all services
docker-compose -f /path/to/llm-gateway/docker-compose.yml down
docker-compose -f /path/to/ai-agents/docker-compose.yml down
docker-compose -f /path/to/Code-Orchestrator-Service/docker-compose.yml down
docker-compose -f /path/to/semantic-search-service/docker-compose.yml down

# Start all services (networks must exist first)
docker-compose -f /path/to/llm-gateway/docker-compose.yml up -d
docker-compose -f /path/to/ai-agents/docker-compose.yml up -d
docker-compose -f /path/to/Code-Orchestrator-Service/docker-compose.yml up -d
docker-compose -f /path/to/semantic-search-service/docker-compose.yml up -d
```

---

## Platform Control Panel

Use the Platform Control Panel UI for service management:

```bash
cd /Users/kevintoles/POC/ai-platform-data/platform_control
python3 main.py
```

Features:
- Start/Stop individual services
- Toggle Docker/Native mode for inference-service
- Health status monitoring
- Model management

---

## Migration to Kubernetes

This tiered network design maps directly to Kubernetes:

| Docker Network | Kubernetes Equivalent |
|----------------|----------------------|
| gateway-network | Ingress + Gateway namespace |
| ai-platform-network | Application namespace with NetworkPolicy |
| data-network | Data namespace with restricted NetworkPolicy |
| Host (native) | Node with GPU, accessed via NodePort or hostNetwork |

---

## References

- [Kitchen Brigade Pattern](../textbooks/Guidelines/KITCHEN_BRIGADE_ARCHITECTURE.md)
- [MSEP Pipeline Architecture](../ai-agents/docs/MULTI_STAGE_ENRICHMENT_PIPELINE_ARCHITECTURE.md)
- [LLM Gateway Architecture](../llm-gateway/docs/ARCHITECTURE.md)
