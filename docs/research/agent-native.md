# Research Foundations: Agent-Native Research Artifacts (ARA)

## Paper
"The Last Human-Written Paper" (arXiv:2604.24658, Liu et al., 2026)

## Core Thesis

Traditional research compiles a **branching, iterative knowledge tree** into a **linear narrative** (PDF). This imposes:
- **Storytelling Tax**: Failed experiments (90.2% of RE-Bench cost) are discarded
- **Engineering Tax**: Tacit knowledge between paper and code is unwritten (only 45.4% of reproduction requirements specified)

"Agent-native" = replacing narrative document with **machine-executable knowledge package**. Primary consumer is AI agent, not human reader.

## Four-Layer Architecture

```
PAPER.md              # Root manifest (~200 tokens)
logic/                # Cognitive layer — What & Why (MUTABLE)
src/                  # Physical layer — How (Mutable)
trace/                # Exploration graph — Journey (APPEND-ONLY)
evidence/             # Raw proof (Append-only)
```

### Key Design Principles

1. **Progressive disclosure**: PAPER.md tells agents relevance; deeper files load on demand
2. **Cross-layer binding**: Claims → experiments → evidence → code
3. **Dead ends preserved**: Failed approaches are first-class nodes
4. **Provenance tracking**: `user` / `ai-suggested` / `ai-executed` / `user-revised`

### Progressive Crystallization
- Staged observations → crystallize only on closure signals
- Default to non-promotion (premature crystallization is the failure mode)
- Contradiction handling: never silently overwrite, flag both, append `unresolved` decision node

## Evaluation Results

| Task | PDF + Repo | ARA | Delta |
|------|-----------|-----|-------|
| Question answering | 72.4% | 93.7% | +21.3 |
| Failure knowledge recovery | 15.7% | 81.4% | +65.7 |
| Reproduction | 57.4% | 64.4% | +7.0 |
| Extension (time to first move) | 395 min | 9 min | -386 min |

## Relevance to Our Project

| ARA Pattern | Our Implementation | Gap |
|-------------|-------------------|-----|
| Append-only trace (trace/) | Episodes table (compact mutates) | VIOLATION |
| Progressive crystallization | store_episode is immediate | MISSING |
| Mutable vs append-only split | No layer separation | MISSING |
| Dead ends as first-class | Not represented | MISSING |
| Provenance tracking | Not implemented | MISSING |
| Contradiction deferral | batch_resolve archives both sides | DIFFERENT |
