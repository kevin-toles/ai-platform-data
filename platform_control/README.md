# AI Platform Control Panel

Desktop application to manage the AI platform services and models.

## Features

- **Service Management**: Start/Stop/Restart Docker containers and native services
- **Health Monitoring**: Real-time status indicators (auto-refreshes every 5 seconds)
- **Model Management**: Load/Unload LLM models via inference-service API
- **Quick Actions**: Start All / Stop All buttons

## Services Managed

| Service | Type | Port | Description |
|---------|------|------|-------------|
| inference-service | Native | 8085 | LLM inference (runs native for Metal acceleration) |
| code-orchestrator | Docker | 8083 | Metadata extraction, NLP pipelines |
| llm-gateway | Docker | 8080 | API Gateway, rate limiting, routing |
| semantic-search | Docker | 8081 | Vector search, embeddings |
| ai-agents | Docker | 8082 | AI agent orchestration |

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

## Requirements

```bash
pip3 install customtkinter httpx
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              AI Platform Control Panel                   │
├─────────────────────────────────────────────────────────┤
│  ● inference-service    [Start] [Stop]   Native/Metal   │
│  ● code-orchestrator    [Start] [Stop]   Docker         │
│  ● llm-gateway          [Start] [Stop]   Docker         │
│  ● semantic-search      [Start] [Stop]   Docker         │
│  ● ai-agents            [Start] [Stop]   Docker         │
├─────────────────────────────────────────────────────────┤
│  [▶ Start All]  [■ Stop All]  [↻ Refresh]               │
├─────────────────────────────────────────────────────────┤
│  LLM Models (inference-service)                         │
│  ● qwen2.5-7b      [Unload]   4500MB • coder, primary   │
│  ○ deepseek-r1-7b  [Load]     4700MB • thinker          │
│  ○ phi-4           [Load]     8400MB • primary, coder   │
└─────────────────────────────────────────────────────────┘
```

## Notes

- **inference-service** runs natively (not Docker) to leverage Apple Metal GPU acceleration
- Docker services are managed via docker-compose in their respective directories
- Health checks run every 5 seconds automatically
- Model loading can take 30-60 seconds depending on model size
