# AI Platform Control Panel

Desktop application to manage the AI platform services and models.

## Features

- **🚀 Platform Start/Restart**: One-click startup of entire platform (infrastructure + all services)
- **Infrastructure Management**: Automatic startup of Neo4j, Qdrant, Redis with health monitoring
- **Service Management**: Start/Stop/Restart Docker containers and native services
- **Health Monitoring**: Real-time status indicators (auto-refreshes every 5 seconds)
- **Model Management**: Load/Unload LLM models via inference-service API
- **Quick Actions**: Start All / Stop All buttons

## Platform Startup Sequence

When you click **"⚡ Start Platform"**, the following sequence executes:

1. **Infrastructure** (Neo4j, Qdrant, Redis) starts via docker-compose
2. **Wait for Health** - Monitors until all infrastructure is healthy (90s timeout)
3. **Services Start** in dependency order:
   - inference-service (Line Cook - LLM inference)
   - semantic-search (Cookbook - vector search)
   - code-orchestrator (Sous Chef - HuggingFace models)
   - audit-service (Auditor - citation tracking)
   - ai-agents (Expeditor - orchestration)
   - llm-gateway (Maître d' - external entry point)
4. **Wait for Services** - 10s delay for services to fully initialize
5. **Wait for Inference** - Polls inference-service health (60s timeout)
6. **Load Default Model** - Automatically loads `qwen2.5-7b` (configurable)

**Total startup time:** ~2-3 minutes (model loading adds ~30-60s)

## Services Managed (Kitchen Brigade Architecture)

| Service | Role | Port | Description |
|---------|------|------|-------------|
| inference-service | Line Cook | 8085 | LLM inference (runs native for Metal acceleration) |
| semantic-search | Cookbook | 8081 | Vector search, embeddings |
| code-orchestrator | Sous Chef | 8083 | Metadata extraction, NLP pipelines |
| audit-service | Auditor | 8084 | Citation tracking, footnotes |
| ai-agents | Expeditor | 8082 | AI agent orchestration |
| llm-gateway | Maître d' | 8080 | API Gateway, rate limiting, routing |

## Infrastructure Services

| Service | Port (Internal) | Purpose |
|---------|-----------------|---------|
| Neo4j | 7687 (Bolt), 7474 (HTTP) | Knowledge graph |
| Qdrant | 6333 (HTTP), 6334 (gRPC) | Vector database |
| Redis | 6379 | Caching, session state |

## Usage

### Option 1: Double-click launcher
```bash
# Make executable (one time)
chmod +x Platform_Control.command

# Then double-click Platform_Control.command in Finder
```

### Option 2: Command line
```bash
cd /Users/kevintoles/POC/ai-platform-data/platform_control
python3 main.py
```

## Quick Start: Launch Entire Platform

1. Open Platform Control Panel
2. Click **"⚡ Start Platform"** button
3. Watch the status panel as:
   - Infrastructure containers start (Neo4j, Qdrant, Redis)
   - Services start in dependency order
   - All indicators turn green ✅
4. Load your LLM model of choice

## Requirements

```bash
pip3 install customtkinter httpx
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              AI Platform Control Panel                       │
├─────────────────────────────────────────────────────────────┤
│  INFRASTRUCTURE          PLATFORM CONTROL                    │
│  ● Neo4j                 [⚡ Start Platform]                 │
│  ● Qdrant                [🔄 Restart Platform]               │
│  ● Redis                 [⏹  Stop All]                       │
├─────────────────────────────────────────────────────────────┤
│  SERVICES (Kitchen Brigade)                                  │
│  ● inference-service    [Start] [Stop]   Native/Metal        │
│  ● semantic-search      [Start] [Stop]   Docker              │
│  ● code-orchestrator    [Start] [Stop]   Docker              │
│  ● audit-service        [Start] [Stop]   Docker              │
│  ● ai-agents            [Start] [Stop]   Docker              │
│  ● llm-gateway          [Start] [Stop]   Docker              │
├─────────────────────────────────────────────────────────────┤
│  [▶ Start All]  [■ Stop All]  [↻ Refresh]                    │
├─────────────────────────────────────────────────────────────┤
│  LLM Models (inference-service)                              │
│  ● qwen2.5-7b      [Unload]   4500MB • coder, primary        │
│  ○ deepseek-r1-7b  [Load]     4700MB • thinker               │
│  ○ phi-4           [Load]     8400MB • primary, coder        │
└─────────────────────────────────────────────────────────────┘
```

## Notes

- **inference-service** runs natively (not Docker) to leverage Apple Metal GPU acceleration
- Docker services are managed via docker-compose in their respective directories
- Health checks run every 5 seconds automatically
- Model loading can take 30-60 seconds depending on model size
- **Start Platform** starts infrastructure first, waits for health, then starts services in order
- **Restart Platform** stops everything, then performs a fresh start
- **Stop All** gracefully stops services first, then infrastructure
