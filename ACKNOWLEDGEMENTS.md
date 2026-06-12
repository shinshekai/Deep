# Acknowledgements

DEEP builds upon the work of open-source projects and academic research. We are grateful to the authors and contributors of these projects.

## Research Foundations

### DeepTutor

- **Repository**: [github.com/HKUDS/DeepTutor](https://github.com/HKUDS/DeepTutor)
- **License**: Apache License 2.0
- **Paper**: DeepTutor: Multi-Agent Tutoring Platform (HKU Data Science Lab)
- **What we adopted**: DEEP's guided learning system (4-agent pipeline: Locate → Interactive → Chat → Summary) and the agent architecture evolved from DeepTutor's multi-agent Q&A platform. The dual-loop solver pattern (analysis + solve) was inspired by DeepTutor's research-driven approach to document-grounded tutoring.

### PageIndex

- **Repository**: [github.com/VectifyAI/PageIndex](https://github.com/VectifyAI/PageIndex)
- **License**: MIT License
- **Paper**: PageIndex: Vectorless Hierarchical Document Indexing
- **What we adopted**: DEEP's PageIndex system is a fork of VectifyAI's vectorless hierarchical document indexing project. The 3-pass tree generation algorithm, chunk-level reasoning, and tree traversal search are directly derived from PageIndex's architecture.

### RecursiveMAS

- **Research Paper**: [arXiv:2604.25917](https://arxiv.org/abs/2604.25917)
- **License**: Apache License 2.0 (paper-based, no explicit repository LICENSE file)
- **Paper**: Recursive Multi-Agent System for Complex Problem Solving
- **What we adopted**: DEEP's recursive solver implements 4 collaboration patterns from the RecursiveMAS framework: Sequential, Mixture, Deliberation, and Distillation. These patterns enable multi-agent collaboration for complex tasks where a single agent pass is insufficient.

### Agent-Native Research Artifacts (ARA)

- **Repository**: [github.com/AmberLJC/Agent-Native-Research-Artifacts](https://github.com/AmberLJC/Agent-Native-Research-Artifacts)
- **License**: MIT License
- **Paper**: Agent-Native Research Artifacts (Orchestra Research)
- **What we adopted**: DEEP's ARA Compiler converts documents into a 4-layer knowledge structure: Logic (reasoning chains), Solution (methods), Trace (evidence), and Evidence (citations). This structured representation enables agents to reason over document content with provenance tracking.

### AI Research SKILLs

- **Repository**: [github.com/Orchestra-Research/AI-Research-SKILLs](https://github.com/Orchestra-Research/AI-Research-SKILLs)
- **License**: MIT License
- **Paper**: AI-Research-SKILLs: Modular Research Skills for AI Agents
- **What we adopted**: DEEP's agent skill system and the modular approach to research pipeline design. The decomposition → parallel research → synthesis pattern in DEEP's deep research pipeline draws from AI-Research-SKILLs' methodology for composable research capabilities.

### DeepTutor Claude Skill

- **Repository**: [github.com/ndpvt-web/deeptutor-claude-skill](https://github.com/ndpvt-web/deeptutor-claude-skill)
- **License**: MIT License
- **What we adopted**: Additional reference implementation for agent-based tutoring patterns that informed DEEP's guided learning system design.

## Algorithms & Techniques

### TurboQuant KV Cache Quantization

- **Paper**: TurboQuant (arXiv:2504.19874, ICLR 2026)
- **Authors**: Amir Zandieh, Majid Daliri, Majid Hadian, Vahab Mirrokni (Google Research)
- **License**: CC-BY-4.0 (arXiv)
- **What we adopted**: DEEP implements PolarQuant + QJL algorithms for 3-4 bit KV cache compression, reducing VRAM usage by 40-50% with minimal quality loss.

### PolarQuant

- **Paper**: PolarQuant (arXiv:2502.02617, AISTATS 2026)
- **Authors**: Google Research
- **License**: CC-BY-4.0 (arXiv)
- **What we adopted**: Random rotation + Beta-distributed coordinates + Lloyd-Max scalar quantization for KV cache compression.

### Reciprocal Rank Fusion (RRF)

- **Paper**: "Reciprocal Rank Fusion outperforms Condorcet and individual Rank Learning Methods" (Cormack et al., SIGIR 2009)
- **License**: ACM (academic use)
- **What we adopted**: DEEP uses k=60 RRF merge for hybrid vector + keyword retrieval, following the original parameter recommendation from Cormack et al.

## Frontend Design System

### shadcn/ui

- **Website**: [ui.shadcn.com](https://ui.shadcn.com)
- **Repository**: [github.com/shadcn-ui/ui](https://github.com/shadcn-ui/ui)
- **License**: MIT License
- **Integration**: Base-Nova style with `@base-ui/react` primitives. DEEP uses 18 components: badge, button, card, dialog, input, label, popover, scroll-area, select, separator, sheet, skeleton, sonner, switch, tabs, textarea, tooltip, accordion. All generated via `components.json` config.

### Base UI (base-ui/react)

- **Website**: [base-ui.com](https://base-ui.com)
- **Repository**: [github.com/mui/base-ui](https://github.com/mui/base-ui)
- **License**: MIT License
- **What we adopted**: Unstyled, accessible UI primitives powering shadcn/ui Base-Nova style. DEEP uses Base UI Dialog and Sheet components.

### Tailwind CSS

- **Website**: [tailwindcss.com](https://tailwindcss.com)
- **Repository**: [github.com/tailwindlabs/tailwindcss](https://github.com/tailwindlabs/tailwindcss)
- **License**: MIT License
- **Integration**: Utility-first CSS framework. DEEP uses v4 with CSS-first configuration, oklch color system, and `@tailwindcss/postcss`.

### Sonner

- **Website**: [sonner.emilkowal.ski](https://sonner.emilkowal.ski)
- **Repository**: [github.com/emilkowal斯基/sonner](https://github.com/emilkowal斯基/sonner)
- **License**: MIT License
- **Integration**: Toast notification system. DEEP uses Sonner across all 8 pages (chat, solve, research, cowriter, knowledge, guide, models, documents). Hardcoded dark theme.

### Lucide Icons

- **Website**: [lucide.dev](https://lucide.dev)
- **Repository**: [github.com/lucide-icons/lucide](https://github.com/lucide-icons/lucide)
- **License**: ISC License
- **Integration**: Icon library providing 1000+ consistent icons for all DEEP UI components.

### clsx + tailwind-merge

- **clsx**: [github.com/lukeed/clsx](https://github.com/lukeed/clsx) — MIT License — Tiny utility for constructing className strings
- **tailwind-merge**: [github.com/dcastil/tailwind-merge](https://github.com/dcastil/tailwind-merge) — MIT License — Intelligent merging of Tailwind CSS classes
- **Integration**: Combined in `lib/utils.ts` as `cn()` function for conditional class composition.

### class-variance-authority (cva)

- **Repository**: [github.com/joe-bell/cva](https://github.com/joe-bell/cva)
- **License**: MIT License
- **Integration**: Used by shadcn/ui for type-safe component variant definitions (button variants, badge variants, etc.).

### Recharts

- **Website**: [recharts.org](https://recharts.org)
- **Repository**: [github.com/recharts/recharts](https://github.com/recharts/recharts)
- **License**: MIT License
- **Integration**: React charting library for dashboard telemetry visualizations (VRAM usage, latency, etc.).

### React Markdown + remark-gfm

- **react-markdown**: [github.com/remarkjs/react-markdown](https://github.com/remarkjs/react-markdown) — MIT License — Markdown rendering in React
- **remark-gfm**: [github.com/remarkjs/remark-gfm](https://github.com/remarkjs/remark-gfm) — MIT License — GitHub Flavored Markdown support
- **Integration**: Used for rendering agent responses, synthesis results, and notebook content with tables, strikethrough, and task lists.

### DOMPurify

- **Website**: [cure53.de/DOMPurify](https://cure53.de/DOMPurify)
- **Repository**: [github.com/cure53/DOMPurify](https://github.com/cure53/DOMPurify)
- **License**: Apache License 2.0 / MPL 2.0
- **Integration**: HTML sanitization for user-generated content and agent responses before DOM insertion.

### TanStack Virtual

- **Repository**: [github.com/TanStack/virtual](https://github.com/TanStack/virtual)
- **License**: MIT License
- **Integration**: Virtualized list rendering for large document lists and knowledge base entries.

## Infrastructure

### LM Studio

- **Website**: [lmstudio.ai](https://lmstudio.ai)
- **License**: Proprietary (free for personal and commercial use)
- **What we adopted**: Primary local inference backend. DEEP communicates via LM Studio's OpenAI-compatible API for chat completions, embeddings, and model management.

### llama.cpp

- **Repository**: [github.com/ggerganov/llama.cpp](https://github.com/ggerganov/llama.cpp)
- **License**: MIT License
- **What we adopted**: DEEP builds on llama.cpp via LM Studio. TurboQuant+ has active PR preparation for llama.cpp upstream contribution.

### FastAPI

- **Website**: [fastapi.tiangolo.com](https://fastapi.tiangolo.com)
- **Repository**: [github.com/tiangolo/fastapi](https://github.com/tiangolo/fastapi)
- **License**: MIT License
- **Integration**: Backend framework. Async Python API with automatic OpenAPI docs, WebSocket support, and dependency injection.

### Pydantic

- **Website**: [docs.pydantic.dev](https://docs.pydantic.dev)
- **Repository**: [github.com/pydantic/pydantic](https://github.com/pydantic/pydantic)
- **License**: MIT License
- **Integration**: Data validation and settings management via `pydantic-settings`. DEEP uses 40+ environment variables with type safety.

### aiosqlite

- **Repository**: [github.com/omnilib/aiosqlite](https://github.com/omnilib/aiosqlite)
- **License**: MIT License
- **Integration**: Async SQLite3 wrapper for the 14-table memory system with FTS5 full-text search.

### pynvml

- **Repository**: [github.com/gpuopenanalytics/pynvml](https://github.com/gpuopenanalytics/pynvml)
- **License**: BSD License
- **Integration**: Real-time GPU VRAM monitoring via NVIDIA Management Library. 4-level pressure response (GREEN/YELLOW/ORANGE/RED).

### httpx

- **Repository**: [github.com/encode/httpx](https://github.com/encode/httpx)
- **License**: BSD License
- **Integration**: Async HTTP client for LM Studio API communication.

### Locust

- **Website**: [locust.io](https://locust.io)
- **Repository**: [github.com/locustio/locust](https://github.com/locustio/locust)
- **License**: MIT License
- **Integration**: Load testing framework. 50-user load tests in CI/CD pipeline.

### Hypothesis

- **Website**: [hypothesis.works](https://hypothesis.works)
- **Repository**: [github.com/HypothesisWorks/hypothesis](https://github.com/HypothesisWorks/hypothesis)
- **License**: MPL 2.0
- **Integration**: Property-based testing for data transformations, security invariants, and prompt registry.

## Upgrade Research Foundations

Sources referenced in DEEP's comprehensive upgrade plan (UPGRADE_PLAN.md). Deep code-level research validated against DEEP's existing architecture.

### RHO — Agent Self-Improvement Loop

- **Paper**: [arXiv:2606.05922](https://arxiv.org/abs/2606.05922)
- **Repository**: [github.com/wbopan/retro-harness](https://github.com/wbopan/retro-harness)
- **License**: MIT License
- **Verdict**: NOT APPLICABLE. RHO targets multi-user SWE-Bench with 1000+ episodes. DEEP is local-first single-user with ~10-50 episodes/month — DPP coreset selection not meaningful at this scale.

### AI Harness Engineering — Agent Maturity Framework

- **Paper**: [arXiv:2605.13357](https://arxiv.org/abs/2605.13357)
- **License**: arXiv (open access)
- **Verdict**: SELECTIVE. Adopted H0 (observability via correlation.py + input_origin.py) and H2 (verification via PageIndex). Not applicable: H3 components (permissions, entropy auditor, intervention logger) — designed for multi-user SaaS with permissioned access, not local-first single-user.

### Autoresearch — Autonomous Optimization Patterns

- **Repository**: [github.com/karpathy/autoresearch](https://github.com/karpathy/autoresearch)
- **License**: MIT License
- **Verdict**: NOT APPLICABLE. Requires autonomous code modification loop (agents modify their own code and run experiments). DEEP's agents don't self-modify — they execute predefined pipelines. The three-file architecture (INSTRUCTIONS/PROMPTS/SCORING) is retained in `agent_instructions.md` as human-readable reference only.

### Open Notebook — Knowledge Management Patterns

- **Repository**: [github.com/lfnovo/open-notebook](https://github.com/lfnovo/open-notebook)
- **License**: MIT License
- **What we adopted**: DB-first credential management (encrypted API keys with env-var fallback), content-type-aware chunking (markdown/code/plain detection), command-based background jobs with retry logic. Patterns informed DEEP's credential management and document processing design.

### DOX — Documentation Hierarchy

- **Repository**: [github.com/agent0ai/dox](https://github.com/agent0ai/dox)
- **License**: MIT License
- **What we adopted**: AGENTS.md hierarchy system (root → child → grandchild), read-before-editing protocol (walk from root to each target, read every AGENTS.md), closeout protocol (re-check changed paths, update affected docs). Implemented as root `AGENTS.md` + `backend/AGENTS.md` + `frontend/AGENTS.md` + `backend/app/services/AGENTS.md` + `backend/app/routers/AGENTS.md`.

### Bklit UI — Dashboard Charts

- **Repository**: [github.com/bklit/bklit-ui](https://github.com/bklit/bklit-ui)
- **License**: MIT License
- **What we adopted**: shadcn-compatible chart components (area, line, bar, pie) for dashboard telemetry visualizations. DEEP uses Recharts as the primary charting library with similar component patterns.

### Pake — Desktop Companion App

- **Repository**: [github.com/tw93/Pake](https://github.com/tw93/Pake)
- **License**: GPL-3.0
- **What we adopted**: Desktop wrapper pattern for turning web apps into native desktop applications. Used as reference for potential future desktop companion build. DEEP's web frontend runs as a standalone web app; Pake pattern informs potential future desktop packaging.

### Karpathy Prompt — Optimization Methodology

- **Source**: [joindreamlabs.com/karpathyprompt](https://joindreamlabs.com/karpathyprompt/)
- **What we adopted**: FIT CHECK methodology — validate before optimizing: scored objectively (real number, not vibes), fast feedback (minutes, not weeks), asset accessible (agent has read+write). Applied to DEEP's RAG retrieval, memory recall, agent prompts, and complexity scoring optimization targets.

### Handy — Speech-to-Text Insights

- **Repository**: [github.com/cjpais/Handy](https://github.com/cjpais/Handy)
- **License**: MIT License
- **What we adopted**: Multi-engine STT architecture pattern (primary → fallback → last resort), SmoothedVad with attack/release for voice activity detection, model auto-unload on idle for VRAM savings. Informs DEEP's planned voice input integration.

### Shieldcn — README Badges

- **Repository**: [github.com/jal-co/shieldcn](https://github.com/jal-co/shieldcn)
- **License**: MIT License
- **What we adopted**: Badge generation for README documentation. DEEP uses shields.io badges for version, tests, license, and PR status indicators.

- 30+ TurboQuant testers across diverse hardware (M1–M5 Mac, RTX 3080Ti–5090, AMD 6800XT/9070XT)
- Active collaboration with llama.cpp upstream for TurboQuant contribution
- MLX/Swift community collaboration for Apple Silicon optimization

## License Compliance

All incorporated code and algorithms are used in compliance with their respective licenses:

- **Apache License 2.0** (DeepTutor, RecursiveMAS, DOMPurify): Requires copyright notice, state changes, and license inclusion. DEEP retains all original copyright notices and includes license texts.
- **MIT License** (PageIndex, ARA, AI-Research-SKILLs, DeepTutor Claude Skill, llama.cpp, shadcn/ui, Base UI, Tailwind CSS, Sonner, clsx, tailwind-merge, cva, Recharts, react-markdown, remark-gfm, TanStack Virtual, FastAPI, Pydantic, aiosqlite, Locust, RHO, Autoresearch, Open Notebook, DOX, Bklit UI, Handy, Shieldcn): Requires copyright notice and license inclusion. DEEP retains all original copyright notices.
- **ISC License** (Lucide Icons): Requires copyright notice and license inclusion. DEEP retains all original copyright notices.
- **GPL-3.0** (Pake): DEEP uses Pake only as a build tool reference (no code redistribution). DEEP's own code is licensed under the DEEP License (personal use only). Pake's GPL terms apply to Pake itself, not to applications built with it.
- **CC-BY-4.0** (TurboQuant, PolarQuant): Requires attribution. DEEP cites original papers.
- **ACM** (Reciprocal Rank Fusion): Academic citation provided.
- **BSD License** (pynvml, httpx): Requires copyright notice and license inclusion.
- **MPL 2.0** (Hypothesis): Requires source availability for MPL-licensed modifications. DEEP's Hypothesis usage is test-only.

For full license texts, see the `LICENSE` file in this repository and the respective upstream repositories.
