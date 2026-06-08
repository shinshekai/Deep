# Research Foundations: RecursiveMAS

## Core Concept

**Latent-space recursion** — agents communicate through continuous latent representations (not token sequences) via learned adapter modules.

## Architecture

### Two-Layer Adapter System
- **Inner Adapters**: Per-agent, operates within single model's hidden space (MLP + LayerNorm)
- **Outer Adapters**: Per-agent-pair, maps hidden states from source to target agent's space

### Collaboration Topologies (4 Patterns)
1. **Sequential**: Planner → Critic → Solver (ring with feedback)
2. **Mixture**: Math ⊕ Code ⊕ Science → Summarizer (hub-and-spoke)
3. **Distillation**: Expert ↔ Learner (teacher-student loop)
4. **Deliberation**: Reflector ↔ ToolCaller (peer deliberation)

### Key Innovation
Prompts use template placeholders (`<<LATENT_PLANNER_SLOT>>`) replaced with latent embeddings (not text). Model processes mixed token-embedding sequences.

## Technical Decisions

| Decision | Rationale |
|----------|-----------|
| Latent-space over token-space | 2-4x faster, 75% fewer tokens |
| Inner + outer adapter split | Inner = thinking harder; Outer = talking to someone else |
| Ring topology with feedback | Solver output feeds back to Planner for iterative convergence |
| CPU-staged latents | Memory efficiency — only one agent on GPU at a time |
| Heterogeneous base models | Each agent specialized for its role |

## Relevance to Our Project

RecursiveMAS operates at the **model architecture level** (latent-space adapters between heterogeneous models). Our project operates at the **application level** (LLM API calls with prompt engineering). Different abstraction layers.

However, the **pattern** of separating intra-agent refinement (inner adapters) from inter-agent communication (outer adapters) is relevant to our agent orchestration architecture.
