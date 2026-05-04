# UDIP — Unified Document Intelligence Pipeline

Local-first AI application merging **DeepTutor**, **PageIndex**, and **TurboQuant** into a unified document intelligence pipeline.

![UDIP Logo](docs/diagrams/architecture.svg) *(to be added)*

## Features

| Feature | Description |
|---------|-------------|
| **Smart Solver** | Multi-agent Q&A with dual-loop reasoning (Analysis → Solve) |
| **PageIndex** | Vectorless, reasoning-based hierarchical document indexing |
| **TurboQuant** | KV cache quantization (3–4 bit) for memory-efficient inference |
| **Deep Research** | 3-phase research pipeline with dynamic topic queue |
| **Guided Learning** | Interactive learning sessions with chat and summaries |
| **Question Generator** | Custom + exam-mimicry practice questions |
| **Content Creation** | Co-writer and idea generation tools |

## Performance Targets

| Metric | Target |
|--------|--------|
| PageIndex tree generation | < 60s (100-page document) |
| TTFT (Smart Solver) | < 3s |
| Token throughput (TurboQuant) | ≥ 15 tok/s (RTX 3090/4090) |
| RAGAS Faithfulness | ≥ 0.85 |
| Retrieval Precision@5 | ≥ 90% |

## Quick Start

### Option 1: Docker Compose (Recommended)

```bash
git clone https://github.com/shinshekai/Deep.git
cd Deep
cp .env.example .env  # Edit with your settings
docker-compose up --build
```

Access:
- **Frontend**: http://localhost:3782
- **Backend API**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs

### Option 2: Manual Setup

**Prerequisites:**
- Python 3.10+
- Node.js 18+
- LM Studio with GGUF models
- NVIDIA GPU with 6GB+ VRAM (12GB+ recommended)

**Backend:**
```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate  # Windows
# or: source .venv/bin/activate  # Linux/Mac
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8001
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev -- -p 3782
```

**LM Studio:**
1. Download a GGUF model (e.g., Qwen3-4B-Q4_K_M)
2. Start LM Studio server on port 1234
3. Update `.env` with your model name

## Environment Variables

See `.env.example` for all options. Key variables:

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `LLM_MODEL` | Yes | — | Primary LLM model |
| `LLM_HOST` | Yes | — | LM Studio API endpoint |
| `EMBEDDING_MODEL` | Yes | — | Embedding model name |
| `BACKEND_PORT` | No | 8001 | FastAPI backend port |
| `FRONTEND_PORT` | No | 3782 | Next.js frontend port |
| `TURBOQUANT_ENABLED` | No | true | Enable KV cache quantization |
| `PAGEINDEX_MODEL` | No | (LLM_MODEL) | Model for tree generation |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js :3782)                │
├─────────────────────────────────────────────────────────────┤
│  Dashboard │ Solve │ Knowledge │ Research │ Guide │ Settings │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Backend (FastAPI :8001)                    │
├─────────────────────────────────────────────────────────────┤
│ API Layer: REST + WebSocket (/api/v1/*)                       │
│ Orchestration: PriorityQueue + ModelManager + VRAMMonitor    │
│ Retrieval: Tree Search │ Hybrid RAG │ Naive RAG │ Router    │
│ Agents: Smart Solver │ Deep Research │ Guided Learning       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              LM Studio (OpenAI-compatible :1234)               │
│  T1: Qwen3-0.6B/1.7B  T2: Qwen3-4B/8B            │
│  T3: Qwen3-14B/30B-A3B  Embed: Snowflake Arctic     │
└─────────────────────────────────────────────────────────────┘
```

## Documentation

| Document | Purpose |
|-----------|---------|
| [Architecture](docs/02-system-architecture.md) | Technical design, OpenAPI spec |
| [Product Requirements](docs/01-product-requirements.md) | Functional/non-functional requirements |
| [Inference Strategy](docs/03-inference-strategy.md) | Multi-model inference, KV cache |
| [API Reference](docs/api-reference.md) | Endpoint documentation |
| [Deployment Guide](docs/deployment.md) | Docker + manual setup |
| [User Guide](docs/user-guide.md) | How to use features |

## Project Structure

```
Deep/
├── backend/           # FastAPI backend (:8001)
│   ├── app/
│   │   ├── main.py          # FastAPI app + lifespan
│   │   ├── config.py        # Settings from env vars
│   │   ├── routers/        # API route handlers
│   │   └── services/       # Business logic
│   └── tests/           # pytest test suite (104+ tests)
├── frontend/          # Next.js frontend (:3782)
│   ├── app/              # App router + pages
│   ├── components/       # Reusable UI components
│   └── lib/              # Utilities + config
├── data/              # Local filesystem storage
│   └── knowledge_bases/ # Document indexes + vectors
├── docs/              # Architecture + PRD + guides
└── .env               # Your local configuration
```

## Hardware Requirements

| Component | Minimum | Recommended |
|-----------|--------|-------------|
| GPU | 6GB VRAM (Qwen3-1.7B) | 12GB VRAM (Qwen3-14B) |
| RAM | 16GB | 32GB |
| Storage | 10GB free | 50GB free |
| CPU | 4 cores | 8 cores |

## Test Suite

```bash
cd backend
python -m pytest tests/ -v
```

Current test suite: **104+ tests**, all passing.

Coverage includes:
- Unit tests for all services
- Integration tests for API endpoints
- End-to-end pipeline verification
- Load testing for concurrent users

## Known Limitations (v1.0)

- Single GPU only (multi-GPU deferred to v2.0)
- English documents only (PageIndex tree generation)
- No cloud deployment / multi-user auth
- External vector DBs not supported (uses built-in embeddings)
- Mobile/tablet UI deferred to v2.0

## License

MIT

## Source Repositories

- DeepTutor: [github.com/shinshekai/DeepTutor](https://github.com/shinshekai/DeepTutor)
- PageIndex: [github.com/shinshekai/PageIndex](https://github.com/shinshekai/PageIndex)
- TurboQuant paper: [arxiv.org/abs/2504.19874](https://arxiv.org/abs/2504.19874) (ICLR 2026)
