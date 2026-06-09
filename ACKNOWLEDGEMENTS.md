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

## Infrastructure

### LM Studio

- **Website**: [lmstudio.ai](https://lmstudio.ai)
- **License**: Proprietary (free for personal and commercial use)
- **What we adopted**: Primary local inference backend. DEEP communicates via LM Studio's OpenAI-compatible API for chat completions, embeddings, and model management.

### llama.cpp

- **Repository**: [github.com/ggerganov/llama.cpp](https://github.com/ggerganov/llama.cpp)
- **License**: MIT License
- **What we adopted**: DEEP builds on llama.cpp via LM Studio. TurboQuant+ has active PR preparation for llama.cpp upstream contribution.

## Community

- 30+ TurboQuant testers across diverse hardware (M1–M5 Mac, RTX 3080Ti–5090, AMD 6800XT/9070XT)
- Active collaboration with llama.cpp upstream for TurboQuant contribution
- MLX/Swift community collaboration for Apple Silicon optimization

## License Compliance

All incorporated code and algorithms are used in compliance with their respective licenses:

- **Apache License 2.0** (DeepTutor, RecursiveMAS): Requires copyright notice, state changes, and license inclusion. DEEP retains all original copyright notices and includes license texts.
- **MIT License** (PageIndex, ARA, AI-Research-SKILLs, DeepTutor Claude Skill, llama.cpp): Requires copyright notice and license inclusion. DEEP retains all original copyright notices.
- **CC-BY-4.0** (TurboQuant, PolarQuant): Requires attribution. DEEP cites original papers.
- **ACM** (RRF): Academic citation provided.

For full license texts, see the `LICENSE` file in this repository and the respective upstream repositories.
