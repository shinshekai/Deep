# Product Requirements Document: Unified Document Intelligence Pipeline

**Version:** 1.0  
**Date:** March 31, 2026  
**Status:** Draft  
**Author:** Perplexity Computer  

---

## Executive Summary

This PRD defines a locally-deployed, web-based application that merges three systems — DeepTutor (AI-powered document tutoring and Q&A), PageIndex (vectorless, reasoning-based document retrieval), and Google's TurboQuant KV Cache optimization — into a unified document intelligence pipeline. The application ingests documents, builds hierarchical semantic indexes, and enables multi-modal AI interactions (Q&A, tutoring, research, exercise generation) entirely on local hardware, with no cloud dependencies.

The core thesis: combining PageIndex's reasoning-based retrieval with DeepTutor's multi-agent tutoring framework eliminates the accuracy and explainability weaknesses of conventional vector-RAG systems, while TurboQuant's KV cache compression enables these memory-intensive pipelines to operate within consumer-grade GPU constraints.

---

## Product Overview and Goals

### What the Application Does

The Unified Document Intelligence Pipeline (UDIP) is a local-first web application that transforms uploaded documents into interactive knowledge systems. Users upload PDFs, textbooks, technical manuals, or research papers. The system:

1. Builds a hierarchical tree index of each document using PageIndex — no vector database, no chunking — preserving natural document structure and enabling reasoning-based retrieval with page-level traceability ([PageIndex GitHub](https://github.com/VectifyAI/PageIndex)).
2. Optionally constructs a complementary vector-based knowledge base using DeepTutor's RAG pipeline (hybrid/naive retrieval modes with Docling support) for high-recall search across large document collections ([DeepTutor GitHub](https://github.com/shinshekai/DeepTutor)).
3. Exposes the full DeepTutor agent suite — Smart Solver, Question Generator, Guided Learning, Deep Research, Interactive IdeaGen, and Automated IdeaGen — all powered by a local LLM served through LM Studio's OpenAI-compatible API.
4. Applies TurboQuant KV cache quantization at the inference layer to compress the KV cache by 4–6x, enabling long-context operations (8K–32K+ tokens) on hardware that would otherwise run out of VRAM ([Google Research Blog](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/)).

### Who It's For

- Knowledge workers processing large technical document collections (immigration law, financial regulations, academic research, engineering manuals)
- Solo practitioners and small teams who require local data privacy and cannot use cloud-based document Q&A services
- Learners and educators who need AI-powered tutoring, practice question generation, and guided learning from their own materials
- Developers building local-first AI workflows who need a reference implementation of combined reasoning-based and vector-based retrieval with optimized inference

### Problems Solved

| Problem | How UDIP Addresses It |
|---|---|
| Vector RAG produces opaque, approximate retrieval with no traceability | PageIndex provides reasoning-based tree search with exact page/section references — no "vibe retrieval" |
| Long documents exceed LLM context limits | PageIndex hierarchical indexing + DeepTutor's dual-loop agent architecture break problems into manageable reasoning steps |
| KV cache consumes excessive VRAM during long-context inference | TurboQuant compresses KV cache to 3–4 bits per element, reducing memory by 4–6x with negligible quality loss |
| Cloud-based document AI raises privacy/sovereignty concerns | Entire pipeline runs locally: FastAPI backend, React frontend, LM Studio for inference |
| Existing tools treat Q&A, tutoring, and research as separate workflows | UDIP unifies document ingestion, retrieval, Q&A, guided learning, question generation, deep research, and idea generation under one system |

---

## Core Feature Set

All features from DeepTutor and PageIndex are treated as core, not optional. Features are grouped by functional domain.

### Document Ingestion and Indexing

| Feature | Origin | Description |
|---|---|---|
| PDF/TXT/MD Upload | DeepTutor | Upload documents through the web UI or CLI to build knowledge bases |
| PageIndex Tree Generation | PageIndex | Generate hierarchical, semantic tree indexes from PDFs and Markdown files — no chunking, no vector DB required ([PageIndex GitHub](https://github.com/VectifyAI/PageIndex)) |
| Vector Knowledge Base Creation | DeepTutor | Build embedding-based knowledge repositories using configurable embedding models via LM Studio |
| Incremental Document Addition | DeepTutor | Add new documents to existing knowledge bases without reprocessing the entire collection |
| Numbered Item Extraction | DeepTutor | Extract definitions, theorems, equations, and other numbered items from documents |
| Vision-Based Indexing | PageIndex | Process page images directly for documents where OCR is unreliable — a reasoning-native RAG pipeline over raw page images |
| Docling RAG Pipeline | DeepTutor (v0.5.2+) | Alternative RAG pipeline using Docling for document parsing |
| Knowledge Base Management Dashboard | DeepTutor | Track activity, manage knowledge bases, and monitor system status |

### Retrieval

| Feature | Origin | Description |
|---|---|---|
| Reasoning-Based Tree Search | PageIndex | LLM reasons over the hierarchical tree index to locate the most relevant document sections — simulates how human experts navigate documents. Achieved 98.7% accuracy on FinanceBench ([PageIndex GitHub](https://github.com/VectifyAI/PageIndex)) |
| Hybrid RAG Retrieval | DeepTutor | Combines vector similarity search with keyword-based retrieval for high-recall document search |
| Naive RAG Retrieval | DeepTutor | Pure vector similarity search for simpler queries |
| Agentic Retrieval | PageIndex | Self-hosted agentic retrieval using PageIndex tree search with tool-calling agents |
| RAG Pipeline Selection | DeepTutor (v0.5.0+) | User-configurable choice between retrieval pipelines (hybrid, naive, Docling, PageIndex tree) |
| Citation Tracking | DeepTutor | Centralized CitationManager with ID generation (PLAN-XX/CIT-X-XX), reference number mapping, and deduplication |

### AI-Powered Analysis and Q&A

| Feature | Origin | Description |
|---|---|---|
| Smart Solver | DeepTutor | Dual-loop architecture — Analysis Loop (InvestigateAgent → NoteAgent) and Solve Loop (PlanAgent → ManagerAgent → SolveAgent → CheckAgent → Format) — with multi-mode reasoning, dynamic knowledge retrieval, and real-time WebSocket streaming |
| Deep Research (DR-in-KG) | DeepTutor | Three-phase research pipeline (Planning → Researching → Reporting) with Dynamic Topic Queue, parallel/series execution (max 5 concurrent topics), and centralized citation management |
| Academic Paper Search | DeepTutor | Search academic paper databases as part of the research pipeline |
| Web Search Integration | DeepTutor | Configurable search providers (Perplexity, Tavily, Serper, Jina, Exa, Baidu) for supplementing document knowledge |
| Code Execution | DeepTutor | Python code execution as a reasoning tool within the agent pipelines |

### Learning and Tutoring

| Feature | Origin | Description |
|---|---|---|
| Guided Learning | DeepTutor | Generate personalized learning paths from notebook content: progressive knowledge points, interactive HTML pages, contextual Q&A, and learning summaries. Agents: LocateAgent, InteractiveAgent, ChatAgent, SummaryAgent |
| Question Generator (Custom) | DeepTutor | Generate targeted quizzes, practice problems, and assessments tailored to difficulty level and learning objectives from knowledge base content |
| Question Generator (Exam Mimicry) | DeepTutor | Upload reference exams to generate practice questions matching original style, format, and difficulty |
| Knowledge Simplification | DeepTutor | Transform complex concepts into visual aids, step-by-step breakdowns, and interactive demonstrations |
| Session-Based Knowledge Tracking | DeepTutor | Context-aware conversations that adapt to learning progress across sessions |

### Content Creation

| Feature | Origin | Description |
|---|---|---|
| Interactive IdeaGen (Co-Writer) | DeepTutor | AI-assisted Markdown editor with rewrite/shorten/expand, auto-annotation, and TTS narration |
| Automated IdeaGen | DeepTutor | Extract knowledge points from notebooks, apply multi-stage filtering to surface novel research ideas |
| Notebook System | DeepTutor | Unified learning record management across all modules |

### Inference Optimization

| Feature | Origin | Description |
|---|---|---|
| TurboQuant KV Cache Compression | TurboQuant | Two-stage quantization — PolarQuant (random rotation + scalar quantization at b-1 bits) followed by QJL residual correction (1-bit sign sketch) — compressing KV cache to 3–4 bits per element with zero accuracy loss at 3.5 bits ([Google Research](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/)) |
| Adaptive Bit Allocation | TurboQuant | Mixed-precision: allocate more bits (3–4) to outlier channels and fewer bits (2–3) to regular channels, achieving effective rates like 2.5 or 3.5 bits per element ([Tom's Hardware](https://www.tomshardware.com/tech-industry/artificial-intelligence/googles-turboquant-compresses-llm-kv-caches-to-3-bits-with-no-accuracy-loss)) |
| Residual Window | TurboQuant | Keep the most recent 128–256 tokens in full FP16 precision; compress only older KV cache entries ([DEV Community](https://dev.to/arshtechpro/turboquant-what-developers-need-to-know-about-googles-kv-cache-compression-eeg)) |
| LM Studio Integration | System | Connect to LM Studio's local OpenAI-compatible REST API for all LLM inference and embedding operations |

---

## Technical Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        React / Next.js Frontend                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │
│  │ Solver   │ │ Research │ │ Learning │ │ Question │ │ KB Mgmt│ │
│  │   UI     │ │    UI    │ │    UI    │ │  Gen UI  │ │   UI   │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └───┬────┘ │
│       │            │            │            │           │       │
│       └────────────┴────────┬───┴────────────┴───────────┘       │
│                             │ HTTP + WebSocket                    │
└─────────────────────────────┼────────────────────────────────────┘
                              │
┌─────────────────────────────┼────────────────────────────────────┐
│                    FastAPI Backend (Python)                        │
│                             │                                     │
│  ┌──────────────────────────┴──────────────────────────────────┐ │
│  │                    API Gateway / Router                      │ │
│  └──┬──────┬──────┬──────┬──────┬──────┬──────┬──────────────┘  │
│     │      │      │      │      │      │      │                  │
│  ┌──┴──┐┌──┴──┐┌──┴──┐┌──┴──┐┌──┴──┐┌──┴──┐┌──┴────────────┐  │
│  │Smart││Deep ││Guide││Quest││Idea ││Note ││  Document      │  │
│  │Solv.││Res. ││Learn││ Gen ││ Gen ││book ││  Processing    │  │
│  └──┬──┘└──┬──┘└──┬──┘└──┬──┘└──┬──┘└──┬──┘└──┬────────────┘  │
│     │      │      │      │      │      │      │                  │
│  ┌──┴──────┴──────┴──────┴──────┴──────┴──────┴──────────────┐  │
│  │                    Tool Integration Layer                   │  │
│  │  ┌────────────────┐ ┌─────────────┐ ┌──────────────────┐  │  │
│  │  │ PageIndex Tree │ │ Vector RAG  │ │ Code Execution   │  │  │
│  │  │ Search Engine  │ │ (Hybrid +   │ │ + Web Search     │  │  │
│  │  │                │ │  Naive)     │ │ + Paper Search   │  │  │
│  │  └───────┬────────┘ └──────┬──────┘ └──────────────────┘  │  │
│  └──────────┼─────────────────┼───────────────────────────────┘  │
│             │                 │                                    │
│  ┌──────────┴─────────────────┴───────────────────────────────┐  │
│  │              Knowledge & Memory Foundation                  │  │
│  │  ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐ │  │
│  │  │ PageIndex    │ │ Vector Store │ │ Memory System      │ │  │
│  │  │ Tree Store   │ │ (Embeddings) │ │ (Session state,    │ │  │
│  │  │ (JSON trees) │ │              │ │  citation tracking)│ │  │
│  │  └──────────────┘ └──────────────┘ └────────────────────┘ │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │               LLM Client (OpenAI-compatible)                │  │
│  │    ┌──────────────────────────────────────────────────┐    │  │
│  │    │       TurboQuant KV Cache Optimization Layer      │    │  │
│  │    │  (Applied at request/inference boundary)          │    │  │
│  │    └──────────────────────────────────────────────────┘    │  │
│  └──────────────────────────┬─────────────────────────────────┘  │
└─────────────────────────────┼────────────────────────────────────┘
                              │ HTTP (localhost)
┌─────────────────────────────┼────────────────────────────────────┐
│                     LM Studio (Local LLM)                         │
│                                                                    │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────────┐  │
│  │ Chat/Completion│  │ Embedding      │  │ KV Cache           │  │
│  │ Endpoints      │  │ Endpoint       │  │ (with TurboQuant   │  │
│  │                │  │                │  │  if supported)      │  │
│  └────────────────┘  └────────────────┘  └────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### How the Three Systems Integrate

#### PageIndex as Primary Retrieval Engine

PageIndex replaces or augments DeepTutor's default vector-based retrieval with a reasoning-based approach. During document ingestion, the system generates both:

1. A PageIndex hierarchical tree (JSON) using an LLM to analyze document structure, creating a semantic table-of-contents with node summaries, page ranges, and nested hierarchy.
2. A vector knowledge base (DeepTutor's existing pipeline) for high-recall fallback queries.

At query time, the retrieval layer selects the appropriate strategy:

- **PageIndex Tree Search** (default for single-document deep queries): The LLM traverses the tree structure, reasoning about which branches contain relevant content, then retrieves the specific page ranges. This provides explainable, page-cited results.
- **Vector Hybrid RAG** (for multi-document breadth queries): Standard embedding-based search across the entire knowledge base when the query spans multiple documents.
- **Combined mode**: Tree search for precision, vector search for recall, results merged and deduplicated.

#### DeepTutor as Agent Orchestration Layer

All DeepTutor modules (Smart Solver, Deep Research, Guided Learning, Question Generator, IdeaGen, Notebook) operate as the application's intelligence layer. The key architectural change: every agent that previously called DeepTutor's RAG tool now has access to both PageIndex tree search and vector RAG as retrieval tools, selected dynamically based on query characteristics.

The multi-agent architectures remain intact:
- Smart Solver's dual-loop (Analysis Loop + Solve Loop) with 6 specialized agents
- Deep Research's three-phase pipeline (Planning → Researching → Reporting) with Dynamic Topic Queue
- Guided Learning's 4-agent progression (LocateAgent → InteractiveAgent → ChatAgent → SummaryAgent)

#### TurboQuant KV Cache Optimization — Integration Strategy

TurboQuant applies at the inference/request layer between the FastAPI backend and LM Studio. The integration depends on LM Studio's backend capabilities and has three implementation tiers:

**Tier 1 — LM Studio Native (Preferred, Requires Verification)**

LM Studio uses llama.cpp as its inference backend. If LM Studio exposes llama.cpp's `--cache-type-k` and `--cache-type-v` flags (or incorporates the TurboQuant llama.cpp integration from community PRs at [ggml-org/llama.cpp#20969](https://github.com/ggml-org/llama.cpp/issues/20969)), TurboQuant operates natively within the inference engine:

```
LM Studio server launched with:
  --cache-type-k turbo3 --cache-type-v turbo3 -fa on
```

This is the optimal path. The KV cache is quantized in-engine with no application-layer overhead.

> **Verification Required:** As of March 2026, LM Studio's support for TurboQuant KV cache types (`turbo3`, `turbo4`) has not been confirmed. The llama.cpp community fork `turboquant_plus` ([TheTom/turboquant_plus](https://dev.to/arshtechpro/turboquant-what-developers-need-to-know-about-googles-kv-cache-compression-eeg)) works end-to-end, and there is active discussion on mainline llama.cpp. LM Studio's adoption timeline is unknown.

**Tier 2 — Standalone TurboQuant Server (Fallback)**

If LM Studio does not yet support TurboQuant natively, the application can run a standalone TurboQuant-enabled inference server alongside or instead of LM Studio:

```bash
pip install turboquant
turboquant-server --model <model-path> --bits 4 --port 8000
```

This community package ([back2matching/turboquant](https://dev.to/arshtechpro/turboquant-what-developers-need-to-know-about-googles-kv-cache-compression-eeg)) provides an OpenAI-compatible API with TurboQuant KV cache compression built in. The FastAPI backend connects to it identically to how it connects to LM Studio.

**Tier 3 — Application-Layer Cache Management (Advanced)**

For maximum control, the FastAPI backend manages KV cache state directly using the `turboquant` Python library:

```python
from turboquant import TurboQuantCache

cache = TurboQuantCache(bits=4)
# Pass as past_key_values to HuggingFace model.generate()
```

This tier is relevant only if the application bypasses LM Studio and loads models directly via HuggingFace Transformers. It provides the finest-grained control but requires GPU access from the Python process.

### How TurboQuant KV Cache Optimization Works

TurboQuant is a training-free, data-oblivious compression algorithm published by Google Research (ICLR 2026, [paper](https://arxiv.org/abs/2504.19874)) that quantizes transformer KV cache vectors to 3–4 bits per element. It reduces the memory bandwidth required during autoregressive decoding by compressing the stored key and value vectors that the model reads at every generation step.

#### The Memory Bottleneck

During autoregressive text generation, the transformer attention mechanism must read the entire KV cache from GPU memory (HBM) into compute units (SRAM) for every new token. At FP16 precision, an 8B parameter model at 32K context consumes approximately 4.6 GB of VRAM for the KV cache alone ([DEV Community](https://dev.to/arshtechpro/turboquant-what-developers-need-to-know-about-googles-kv-cache-compression-eeg)). The decode phase is fundamentally memory-bandwidth-bound: the bottleneck is not computation but the speed at which the GPU can load KV cache data from HBM.

#### Two-Stage Compression Pipeline

TurboQuant applies a two-stage compression that is mathematically grounded in information theory:

**Stage 1 — PolarQuant (b-1 bits):** A random orthogonal rotation matrix is applied to each KV vector. This rotation spreads the energy uniformly across all coordinates, making each coordinate follow a predictable Beta distribution in high dimensions. Because the distribution is known in advance, an optimal scalar quantizer (Lloyd-Max algorithm) can be precomputed once for any target bit-width — no calibration data or model-specific tuning required. PolarQuant converts coordinates into polar form (radius + angles), eliminating the per-block normalization constants that traditional quantizers must store alongside compressed data ([Google Research Blog](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/)).

**Stage 2 — QJL Residual Correction (1 bit):** The residual quantization error from Stage 1 is projected through a random Gaussian matrix (Johnson-Lindenstrauss transform), and only the sign bit (+1 or -1) is stored. This single-bit sketch acts as a bias correction that makes inner product estimates (attention scores) mathematically unbiased. The overhead is exactly 1 extra bit per coordinate ([MarkTechPost](https://www.marktechpost.com/2026/03/25/google-introduces-turboquant-a-new-compression-algorithm-that-reduces-llm-key-value-cache-memory-by-6x-and-delivers-up-to-8x-speedup-all-with-zero-accuracy-loss/)).

**Combined result:** b total bits per coordinate, with provably near-optimal distortion (within a factor of approximately 2.7 of the information-theoretic lower bound), zero memory overhead from normalization constants, and unbiased attention score estimation.

#### How This Reduces Memory Bandwidth

By compressing each KV cache element from 16 bits (FP16) to 3–4 bits, TurboQuant reduces the volume of data the GPU must transfer from HBM to SRAM during each decode step by 4–6x. Since the decode phase is memory-bandwidth-bound, this directly translates to faster token generation. Google benchmarks on H100 GPUs showed up to 8x speedup in computing attention logits at 4-bit compared to 32-bit keys ([Tom's Hardware](https://www.tomshardware.com/tech-industry/artificial-intelligence/googles-turboquant-compresses-llm-kv-caches-to-3-bits-with-no-accuracy-loss)).

#### Application-Level Impact

For UDIP running on consumer hardware (16–24 GB VRAM):

| Scenario | Without TurboQuant (FP16 KV) | With TurboQuant (4-bit KV) |
|---|---|---|
| Max context length (8B model, 16 GB GPU) | ~16K tokens | ~48K–64K tokens |
| KV cache memory at 16K context | ~2.3 GB | ~0.5 GB |
| Concurrent agent operations feasible | 1–2 | 3–5 |
| Token throughput under memory pressure | Collapses as cache fills VRAM | Maintains 2–3x higher throughput |

> **Important caveats:** The 8x speedup figure is for attention logit computation specifically, not end-to-end token generation ([LinkedIn](https://www.linkedin.com/pulse/turboquant-paper-moved-billions-tom-mathews-g1kgc)). TurboQuant does not accelerate the prefill phase (initial prompt processing). Short contexts below 1K tokens see negligible benefit; the optimization shines at 4K+ tokens. Models smaller than 3B parameters are more sensitive to quantization noise at 3-bit; 4-bit is the recommended sweet spot ([DEV Community](https://dev.to/arshtechpro/turboquant-what-developers-need-to-know-about-googles-kv-cache-compression-eeg)).

### Technology Stack

| Layer | Technology | Role |
|---|---|---|
| Frontend | React / Next.js 16+ | Local web UI, WebSocket client for real-time streaming |
| Backend | Python 3.10+ / FastAPI | API server, agent orchestration, document processing |
| LLM Inference | LM Studio (OpenAI-compatible API) | Local LLM serving for chat, completion, embeddings |
| KV Cache Optimization | TurboQuant (via llama.cpp backend or standalone) | 3–4 bit KV cache quantization |
| Document Indexing | PageIndex (Python) | Hierarchical tree index generation |
| Vector Store | DeepTutor's embedding pipeline | Embedding-based knowledge base |
| Real-time Communication | WebSocket | Streaming agent reasoning to frontend |
| Data Storage | Local filesystem (JSON, Markdown, session files) | Knowledge bases, indexes, user data |

---

## Functional Requirements

### FR-1: Document Ingestion

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| FR-1.1 | System accepts PDF, TXT, and Markdown file uploads via the web UI | Files up to 500 pages / 50 MB accepted; upload progress indicator shown; invalid files rejected with clear error message |
| FR-1.2 | Uploaded documents are processed into a PageIndex hierarchical tree | Tree JSON generated with title, node_id, start_index, end_index, summary for each node; tree depth reflects actual document structure |
| FR-1.3 | Uploaded documents are processed into a vector knowledge base | Embeddings generated via LM Studio embedding endpoint; stored in retrievable index |
| FR-1.4 | Users can add documents to existing knowledge bases incrementally | New documents processed and merged without reprocessing existing documents; existing data preserved |
| FR-1.5 | Numbered items (definitions, theorems, equations) are extractable | CLI or UI command extracts and catalogs numbered items from knowledge base documents |
| FR-1.6 | Vision-based indexing available for scanned/image-heavy PDFs | PageIndex processes page images directly when standard text extraction fails |
| FR-1.7 | PageIndex tree generation is configurable | User can set: model, toc-check-pages (default 20), max-pages-per-node (default 10), max-tokens-per-node (default 20000), node ID/summary/description toggles |

### FR-2: Retrieval

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| FR-2.1 | PageIndex tree search returns results with page-level citations | Query response includes node_id, start_index, end_index for each retrieved section |
| FR-2.2 | Hybrid RAG retrieval available for multi-document queries | Combines vector similarity and keyword search; returns ranked results with sources |
| FR-2.3 | User can select retrieval pipeline per query | UI provides choice: PageIndex tree, hybrid RAG, naive RAG, combined |
| FR-2.4 | Retrieval pipeline is dynamically selectable by agents | Agent tools can specify retrieval mode based on query characteristics |
| FR-2.5 | All retrievals produce traceable citations | Every retrieved passage linked to source document, page number, and section |

### FR-3: Smart Solver

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| FR-3.1 | Dual-loop architecture processes user questions | Analysis Loop (InvestigateAgent → NoteAgent) and Solve Loop (PlanAgent → ManagerAgent → SolveAgent → CheckAgent → Format) execute in sequence |
| FR-3.2 | Reasoning streams in real-time via WebSocket | Each agent's reasoning steps visible in the UI as they execute |
| FR-3.3 | Solver uses RAG, web search, code execution, and query lookup as tools | All tool types invocable by agents during problem solving |
| FR-3.4 | Final answers include step-by-step solutions with citations | Output stored in data/user/solve/solve_YYYYMMDD_HHMMSS/ with memory files, final_answer.md, artifacts |
| FR-3.5 | Multiple solving modes available | User selects: auto, detailed, quick — affecting reasoning depth |

### FR-4: Question Generator

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| FR-4.1 | Custom question generation from knowledge base | User specifies: requirement text, difficulty (easy/medium/hard), question type (choice/short answer/essay), count; system generates validated questions |
| FR-4.2 | Exam mimicry from reference upload | User uploads reference exam PDF; system generates new questions matching style, format, difficulty |
| FR-4.3 | Generated questions include answer keys and explanations | Each question accompanied by correct answer, explanation, and source citation |
| FR-4.4 | Automatic validation of generated questions | System verifies question quality, answer correctness, and difficulty alignment before presenting |

### FR-5: Guided Learning

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| FR-5.1 | Learning plan generation from selected notebooks | System produces 3–5 progressive knowledge points from notebook content |
| FR-5.2 | Interactive HTML learning pages generated | Each knowledge point produces an interactive page with visual aids |
| FR-5.3 | Contextual Q&A during learning sessions | User can ask questions within the learning flow; ChatAgent provides answers grounded in current context |
| FR-5.4 | Learning summaries generated per session | SummaryAgent produces session summary stored in data/user/guide/session_{session_id}.json |

### FR-6: Deep Research

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| FR-6.1 | Three-phase research pipeline executes end-to-end | Planning (RephraseAgent + DecomposeAgent) → Researching (ManagerAgent + ResearchAgent + NoteAgent) → Reporting |
| FR-6.2 | Dynamic Topic Queue manages research subtopics | Topics transition through PENDING → RESEARCHING → COMPLETED/FAILED states |
| FR-6.3 | Parallel and series execution modes available | Parallel mode runs up to 5 concurrent topics; series mode processes sequentially |
| FR-6.4 | Research reports include centralized citations | CitationManager produces deduplicated citations with consistent ID format |
| FR-6.5 | Research uses RAG, web search, paper search, and code execution | All tool types available during research phase |

### FR-7: Content Creation

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| FR-7.1 | Co-Writer provides AI-assisted Markdown editing | Rewrite, shorten, expand operations available; auto-annotation functional |
| FR-7.2 | TTS narration available for written content | Text-to-speech generates audio files stored in data/user/co-writer/audio/ |
| FR-7.3 | Automated IdeaGen extracts and filters knowledge points | Multi-stage filtering surfaces novel research directions from notebook content |
| FR-7.4 | Notebook system tracks all learning records | Unified record management across Solver, Research, Learning, and Question Gen modules |

### FR-8: Inference Optimization

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| FR-8.1 | TurboQuant KV cache compression active during inference | KV cache quantized to 4-bit (default) or user-configurable 3-bit; verified by reduced VRAM consumption during long-context operations |
| FR-8.2 | Residual window preserves recent token precision | Most recent 128–256 tokens stored in full FP16; only older tokens quantized |
| FR-8.3 | System detects and reports inference backend capabilities | Startup health check identifies whether LM Studio supports TurboQuant natively, or falls back to Tier 2/3 |
| FR-8.4 | Bit-width is configurable | User can set KV cache quantization to 3-bit or 4-bit via settings UI |
| FR-8.5 | System reports KV cache memory usage | Dashboard shows current KV cache size, compression ratio, and VRAM utilization |

### FR-9: System Management

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| FR-9.1 | LM Studio connection configurable | User sets LLM_HOST, LLM_MODEL, EMBEDDING_MODEL, API keys via settings UI or .env |
| FR-9.2 | Multi-model support | Different models assignable to different tasks (e.g., smaller model for tree search, larger for solver) |
| FR-9.3 | Session persistence | Frontend sessions survive page reload (implemented in DeepTutor v0.6.0) |
| FR-9.4 | Full Chinese language support | All UI elements and AI interactions function correctly in Chinese (implemented in DeepTutor v0.6.0) |
| FR-9.5 | Docker deployment available | docker-compose.yml brings up the entire stack (backend + frontend) |

---

## Non-Functional Requirements

### Performance

| ID | Requirement | Target |
|---|---|---|
| NFR-1.1 | PageIndex tree generation time | Less than 60 seconds for a 100-page document |
| NFR-1.2 | Vector knowledge base creation | Less than 120 seconds for a 300-page document |
| NFR-1.3 | Query-to-first-token latency (Smart Solver) | Less than 3 seconds from query submission to first streamed token |
| NFR-1.4 | PageIndex tree search latency | Less than 5 seconds per retrieval (includes LLM reasoning over tree) |
| NFR-1.5 | Token generation throughput with TurboQuant | At least 15 tokens/second on consumer GPU (RTX 3090/4090 class) at 8K+ context |
| NFR-1.6 | WebSocket streaming latency | Less than 100ms between agent producing a token and frontend displaying it |

### Memory Efficiency

| ID | Requirement | Target |
|---|---|---|
| NFR-2.1 | KV cache memory reduction with TurboQuant | 4x minimum reduction vs FP16 baseline at 4-bit quantization |
| NFR-2.2 | Maximum supported context length on 16 GB VRAM | 32K tokens minimum with TurboQuant enabled (8B model) |
| NFR-2.3 | Backend process memory footprint | Less than 2 GB RAM (excluding model weights) |
| NFR-2.4 | PageIndex tree storage | Less than 1 MB per 100-page document |

### Privacy and Security

| ID | Requirement | Target |
|---|---|---|
| NFR-3.1 | No external network calls for core operations | All document processing, indexing, and Q&A operate fully offline. Web search is an opt-in feature only. |
| NFR-3.2 | WebSocket security | Authenticated WebSocket connections (implemented in DeepTutor v0.2.0) |
| NFR-3.3 | Data residency | All user data stored in local data/ directory; no telemetry, no cloud sync |

### Reliability and Error Handling

| ID | Requirement | Target |
|---|---|---|
| NFR-4.1 | LM Studio connection failure handling | Graceful degradation with clear error message when LM Studio is unreachable; automatic reconnection attempts |
| NFR-4.2 | Document processing failure isolation | Failed document processing does not corrupt existing knowledge base; partial progress saved |
| NFR-4.3 | Agent execution error recovery | Individual agent failures within multi-agent pipelines trigger fallback behavior, not full pipeline crashes |
| NFR-4.4 | KV cache quantization fallback | If TurboQuant is unavailable, system operates with standard FP16/FP8 KV cache with warning displayed |
| NFR-4.5 | Input validation | All API endpoints validate inputs; malformed requests return structured error responses |

### Testing

| ID | Requirement | Target |
|---|---|---|
| NFR-5.1 | Unit test coverage | Minimum 80% line coverage on backend Python code |
| NFR-5.2 | Integration tests | End-to-end tests for each agent pipeline (Solver, Research, Learning, Question Gen) |
| NFR-5.3 | Retrieval accuracy tests | PageIndex tree search accuracy benchmarked against known document Q&A pairs; target: 95%+ on structured documents |
| NFR-5.4 | KV cache compression verification | Automated tests verify compression ratio and output quality at 3-bit and 4-bit |
| NFR-5.5 | Frontend component tests | React component tests for all major UI flows |
| NFR-5.6 | CI/CD pipeline | Automated test execution on commit; Docker image builds (implemented in DeepTutor v0.3.0+) |

### Documentation

| ID | Requirement | Target |
|---|---|---|
| NFR-6.1 | API documentation | OpenAPI/Swagger docs auto-generated at /docs endpoint |
| NFR-6.2 | Setup guide | Step-by-step installation for manual and Docker deployment |
| NFR-6.3 | Architecture documentation | System design document covering integration of all three systems |
| NFR-6.4 | Configuration reference | Complete reference for all environment variables and configuration options |
| NFR-6.5 | User guide | End-user documentation for each module (Solver, Research, Learning, etc.) |

---

## Data Flows

### Document Ingestion Flow

```
User uploads PDF/TXT/MD via React UI
         │
         ▼
FastAPI /api/v1/knowledge/upload endpoint
         │
         ├──► Document Parser (PDF → text + structure)
         │         │
         │         ├──► PageIndex Tree Generator
         │         │         │
         │         │         ▼
         │         │    LM Studio API call:
         │         │    - Analyze document structure
         │         │    - Identify sections, subsections
         │         │    - Generate node summaries
         │         │         │
         │         │         ▼
         │         │    PageIndex Tree (JSON)
         │         │    stored in data/knowledge_bases/{kb_name}/pageindex/
         │         │
         │         └──► Vector KB Builder
         │                   │
         │                   ▼
         │              LM Studio Embedding API call:
         │              - Chunk text (configurable strategy)
         │              - Generate embeddings
         │                   │
         │                   ▼
         │              Vector Index
         │              stored in data/knowledge_bases/{kb_name}/vectors/
         │
         └──► Numbered Item Extractor (optional)
                   │
                   ▼
              Extracted items catalog
              stored in data/knowledge_bases/{kb_name}/items/
```

### Query and Response Flow (Smart Solver)

```
User enters question in Solver UI
         │
         ▼
WebSocket connection: ws://localhost:8001/api/v1/solve
         │
         ▼
┌─── Analysis Loop ─────────────────────────────┐
│                                                 │
│  InvestigateAgent                               │
│    ├── Tool: PageIndex Tree Search              │
│    │     └── LM Studio call (reasoning over     │
│    │         tree structure)                     │
│    │         [TurboQuant: KV cache compressed    │
│    │          to 4-bit during this call]         │
│    ├── Tool: Hybrid RAG Search                  │
│    │     └── LM Studio Embedding call           │
│    ├── Tool: Web Search (if enabled)            │
│    └── Tool: Code Execution (if needed)         │
│         │                                       │
│         ▼                                       │
│  NoteAgent                                      │
│    └── Synthesizes findings, updates memory     │
│                                                 │
└─────────────────────────────────────────────────┘
         │
         ▼
┌─── Solve Loop ────────────────────────────────┐
│                                                 │
│  PlanAgent → ManagerAgent → SolveAgent          │
│    │                                            │
│    ├── Each agent call routed through           │
│    │   LM Studio with TurboQuant KV cache       │
│    │                                            │
│    └── All intermediate reasoning streamed      │
│        via WebSocket to frontend                │
│         │                                       │
│         ▼                                       │
│  CheckAgent                                     │
│    └── Validates solution correctness           │
│         │                                       │
│         ▼                                       │
│  Format                                         │
│    └── Produces final_answer.md with citations  │
│                                                 │
└─────────────────────────────────────────────────┘
         │
         ▼
Response streamed to UI + saved to
data/user/solve/solve_YYYYMMDD_HHMMSS/
```

### KV Cache Optimization Flow (Per LLM Request)

```
FastAPI backend prepares LLM request
(prompt + system message + retrieved context)
         │
         ▼
Request sent to LM Studio / TurboQuant Server
         │
         ▼
┌─── Prefill Phase ─────────────────────────────┐
│  Process entire input prompt                    │
│  Compute K, V vectors for all input tokens      │
│  [TurboQuant does NOT accelerate this phase]    │
│                                                 │
│  After prefill:                                 │
│  ┌────────────────────────────────────────────┐│
│  │ KV Cache in GPU HBM                        ││
│  │                                            ││
│  │ Recent 128-256 tokens: FP16 (full prec.)   ││
│  │ Older tokens: Quantized via TurboQuant     ││
│  │   1. Random rotation Π applied to K,V      ││
│  │   2. Scalar quantization (b-1 bits)        ││
│  │   3. QJL sign bit stored for residual      ││
│  │                                            ││
│  │ Total: ~4 bits/element (vs 16 FP16)        ││
│  └────────────────────────────────────────────┘│
└─────────────────────────────────────────────────┘
         │
         ▼
┌─── Decode Phase (per token) ──────────────────┐
│  For each new token generated:                  │
│                                                 │
│  1. Compute query vector Q for new token        │
│  2. Load compressed KV cache from HBM → SRAM   │
│     [4x less data to transfer = faster]         │
│  3. Dequantize K,V on-the-fly in SRAM          │
│     (or use fused kernel that skips             │
│      dequant for near-zero attention weights)   │
│  4. Compute attention scores (Q·K^T)            │
│     [Unbiased due to QJL correction]            │
│  5. Apply softmax, multiply by V                │
│  6. Quantize new token's K,V and append         │
│     to compressed cache                         │
│                                                 │
│  Result: Each decode step reads ~4x less        │
│  memory bandwidth → faster generation           │
└─────────────────────────────────────────────────┘
         │
         ▼
Generated tokens streamed back to FastAPI
via OpenAI-compatible streaming response
```

---

## Out of Scope (Version 1.0)

The following are explicitly excluded from this version:

| Item | Rationale |
|---|---|
| Cloud deployment or multi-user authentication | UDIP is a single-user, local-first application. Cloud hosting, user accounts, and access control are deferred. |
| Fine-tuning or model training | The application uses pre-trained models served by LM Studio. No model training or fine-tuning capabilities are included. |
| Real-time collaborative editing | Single-user system; no concurrent document editing or shared sessions. |
| Mobile or tablet UI | Frontend optimized for desktop browsers only. |
| Non-English PageIndex tree generation | PageIndex tree generation assumes English-language documents. Chinese support exists for the DeepTutor UI and Q&A (v0.6.0), but tree index generation for non-English documents requires separate validation. |
| Custom TurboQuant kernel development | The application uses existing community implementations (pip package, llama.cpp integration). No custom CUDA/Triton kernel development is in scope. |
| Vector database servers (Milvus, Qdrant, etc.) | Vector storage uses DeepTutor's built-in embedding pipeline and local file storage. External vector DB integration is deferred. |
| TurboQuant for embedding vector search | While TurboQuant also accelerates nearest-neighbor vector search, this version applies it only to KV cache compression. Embedding search optimization is deferred. |
| Speculative decoding or other inference optimizations | TurboQuant is the only inference optimization in scope. Speculative decoding, continuous batching, and other techniques are deferred. |
| Production-grade secret management | API keys stored in .env file; no vault integration. |

---

## Open Questions and Risks

### Critical — Must Resolve Before Development

| ID | Question/Risk | Impact | Mitigation |
|---|---|---|---|
| OQ-1 | Does LM Studio currently expose `--cache-type-k` / `--cache-type-v` flags or support TurboQuant KV cache types? | Determines TurboQuant integration tier (Tier 1 vs Tier 2/3). Tier 2/3 add deployment complexity and may not cover embedding models. | Test against latest LM Studio release. If unsupported, default to Tier 2 (standalone turboquant-server) or llama.cpp `turboquant_plus` fork. |
| OQ-2 | What is the minimum model size for reliable TurboQuant 4-bit performance? Community reports suggest models below 3B are sensitive to KV quantization noise. | If users run small models (1B-3B class), TurboQuant may degrade output quality. | Default to 4-bit quantization. Show a warning when model < 3B is detected. Allow users to disable TurboQuant per-request. |
| OQ-3 | PageIndex tree generation requires LLM calls. How does latency scale with document length when using a local 7B-8B model vs the default gpt-4o? | PageIndex was benchmarked with gpt-4o. Local models may produce lower-quality trees or take significantly longer. | Benchmark PageIndex tree generation with local models (Llama 3, Qwen2.5, Mistral) at 7B-14B sizes. Define minimum model quality threshold for acceptable tree output. |

### High Priority — Resolve During Design

| ID | Question/Risk | Impact | Mitigation |
|---|---|---|---|
| OQ-4 | How should PageIndex tree search and DeepTutor vector RAG be combined? What query characteristics determine which retrieval mode is optimal? | Poor mode selection wastes context window and increases latency. | Implement a lightweight query classifier that routes based on: single-doc vs multi-doc, specificity level, document type. Allow manual override. |
| OQ-5 | DeepTutor's Deep Research uses web search providers (Perplexity, Tavily, etc.) that require API keys and internet access. This conflicts with the "no cloud dependencies" requirement. | Core research functionality may be degraded offline. | Make web search an explicitly opt-in feature. Ensure research pipeline works in fully offline mode using only local knowledge base retrieval. |
| OQ-6 | The TurboQuant residual window size (128-256 tokens in FP16) may interact with context management strategies in multi-turn conversations. | If the residual window is too small, attention to recent instructions may degrade. | Make residual window size configurable. Default to 256. Monitor attention quality in automated tests. |
| OQ-7 | DeepTutor's embedding pipeline uses text-embedding-3-large (dimension 3072) by default. LM Studio's local embedding models may have different dimensions and quality characteristics. | Embedding dimension mismatch could break vector store compatibility. | Abstract embedding dimensions in the vector store layer. Support configurable dimensions. Document recommended local embedding models. |

### Medium Priority — Monitor During Development

| ID | Question/Risk | Impact | Mitigation |
|---|---|---|---|
| OQ-8 | TurboQuant's official Google implementation is expected Q2 2026. Current community implementations may have bugs or performance gaps. | Possible accuracy or stability issues with community packages. | Pin specific versions of turboquant dependencies. Include regression tests for KV cache quality. Monitor upstream for official releases. |
| OQ-9 | Running PageIndex tree generation, vector embedding, and multi-agent inference concurrently may exceed VRAM on consumer GPUs. | GPU OOM crashes during heavy workloads. | Implement a GPU memory manager that queues inference requests. Separate indexing (batch) from real-time inference (interactive) into priority lanes. |
| OQ-10 | DeepTutor's code execution capability (Python sandbox) introduces security surface. | Malicious or accidental code could damage the local system. | Run code execution in an isolated subprocess/container with restricted filesystem access and resource limits. |
| OQ-11 | The end-to-end performance overhead of TurboQuant (rotation + quantization during prefill) may negate benefits for short queries. Community reports indicate 15-30x prefill slowdown without optimized kernels ([Reddit](https://www.reddit.com/r/LocalLLaMA/comments/1s2su28/google_research_turboquant_redefining_ai/)). | Short queries (< 1K tokens) may actually be slower with TurboQuant. | Implement adaptive KV cache strategy: disable TurboQuant for queries with expected context < 2K tokens, enable for longer contexts. Benchmark prefill overhead with target hardware. |

---

## Appendix A: Environment Variables

Inherited from DeepTutor, extended for UDIP:

| Variable | Required | Description | Default |
|---|---|---|---|
| LLM_MODEL | Yes | Model name for LM Studio | — |
| LLM_API_KEY | Yes | LM Studio API key | — |
| LLM_HOST | Yes | LM Studio API endpoint URL | — |
| EMBEDDING_MODEL | Yes | Embedding model name | — |
| EMBEDDING_API_KEY | Yes | Embedding API key | — |
| EMBEDDING_HOST | Yes | Embedding API endpoint | — |
| BACKEND_PORT | No | Backend port | 8001 |
| FRONTEND_PORT | No | Frontend port | 3782 |
| SEARCH_PROVIDER | No | Web search provider | perplexity |
| SEARCH_API_KEY | No | Search provider API key | — |
| TURBOQUANT_ENABLED | No | Enable KV cache quantization | true |
| TURBOQUANT_BITS | No | KV cache quantization bit-width | 4 |
| TURBOQUANT_RESIDUAL_WINDOW | No | Tokens kept in FP16 | 256 |
| TURBOQUANT_TIER | No | Integration tier (1/2/3) | auto |
| PAGEINDEX_MODEL | No | Model for tree generation | (uses LLM_MODEL) |
| PAGEINDEX_MAX_PAGES_PER_NODE | No | Max pages per tree node | 10 |
| PAGEINDEX_MAX_TOKENS_PER_NODE | No | Max tokens per tree node | 20000 |

## Appendix B: Key Source References

- DeepTutor repository: [github.com/shinshekai/DeepTutor](https://github.com/shinshekai/DeepTutor)
- PageIndex repository: [github.com/shinshekai/PageIndex](https://github.com/shinshekai/PageIndex) (fork of [VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex))
- TurboQuant paper: [arxiv.org/abs/2504.19874](https://arxiv.org/abs/2504.19874) (ICLR 2026)
- Google Research blog: [TurboQuant: Redefining AI efficiency with extreme compression](https://research.google/blog/turboquant-redefining-ai-efficiency-with-extreme-compression/)
- TurboQuant Python package: `pip install turboquant` ([back2matching/turboquant](https://dev.to/arshtechpro/turboquant-what-developers-need-to-know-about-googles-kv-cache-compression-eeg))
- llama.cpp TurboQuant discussion: [ggml-org/llama.cpp#20969](https://github.com/ggml-org/llama.cpp/issues/20969)
- TurboQuant llama.cpp fork (Apple Silicon): turboquant_plus
- PolarQuant companion paper: AISTATS 2026
- QJL companion paper: AAAI 2025
