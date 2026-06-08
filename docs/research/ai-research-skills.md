# Research Foundations: AI Research SKILLs (Orchestra-Research)

## Core Pattern: Two-Loop Orchestration

```
BOOTSTRAP (once)
  Scope question → search literature → form hypotheses

INNER LOOP (fast, repeating)
  Pick hypothesis → experiment → measure → record → next

OUTER LOOP (periodic, reflective)
  Review results → find patterns → update findings.md → new hypotheses

FINALIZE
  Write paper → final presentation → archive
```

## Skill Definition Format

```
skill-name/
├── SKILL.md              # 200-300 lines, YAML frontmatter + guidance
├── references/           # 300KB+ documentation from official sources
├── scripts/              # Optional helper scripts
└── assets/               # Optional templates/examples
```

### Key Design Decisions
1. **Markdown over code**: Skills are markdown docs, not executable modules
2. **Progressive disclosure**: SKILL.md for quick reference, references/ for depth
3. **Git as temporal proof**: Protocol commits must precede result commits
4. **Negative results are first-class**: Failed hypotheses logged with what they rule out
5. **Autonomy by default**: Agent runs continuously without human confirmation on routine decisions

## ARA Pattern (Same as Agent-Native)

Cognitive Layer (logic/) → Physical Layer (src/) → Exploration Graph (trace/)

## Relevance to Our Project

| AI Research SKILLs Pattern | Our Implementation | Gap |
|---------------------------|-------------------|-----|
| Two-loop orchestration | Analysis + Solve loops in solve_orchestrator | PARTIAL |
| Progressive disclosure | Prompt registry YAML (flat) | MISSING |
| Git as temporal proof | No prompt versioning tied to commits | MISSING |
| Negative results as first-class | Not represented | MISSING |
