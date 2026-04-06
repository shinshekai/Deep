"""Complexity scorer for tier routing decisions.

From CLAUDE.md Section 6.6:
| Signal                | Weight | Source                          |
|-----------------------|--------|---------------------------------|
| Query Complexity      | 0.35   | Token count, reasoning keywords  |
| Document Size         | 0.25   | Total pages, tokens in chunks    |
| Retrieved Chunk Count | 0.15   | Chunks above relevance threshold |
| Available VRAM        | 0.25   | Current free VRAM from pynvml    |

Decision: score < 0.3 → T1 | 0.3-0.6 → T2 | > 0.6 → T3
"""

from typing import Optional

REASONING_KEYWORDS = [
    "compare", "contrast", "analyze", "synthesize", "explain why",
    "how does", "what are the implications", "multi-hop", "relationship",
    "evaluate", "critique", "justify", "derive", "prove",
]

CODE_KEYWORDS = ["implement", "write code", "algorithm", "function", "class"]


def score_query_complexity(
    query_text: str,
    doc_pages: int = 0,
    retrieved_chunks: int = 0,
    free_vram_mb: float = float("inf"),
) -> tuple[float, int]:
    """Return (complexity_score 0-1, target_tier 1/2/3)."""
    # 1. Query complexity (0.35)
    tokens = len(query_text.split())
    query_signal = min(tokens / 200.0, 1.0)  # normalize: 200 tokens = 1.0

    # Boost for reasoning keywords
    lower = query_text.lower()
    if any(kw in lower for kw in REASONING_KEYWORDS):
        query_signal = min(query_signal + 0.2, 1.0)

    # Boost for multi-part queries
    if "?" in query_text and query_text.count("?") >= 2:
        query_signal = min(query_signal + 0.15, 1.0)

    # 2. Document size (0.25)
    doc_signal = min(doc_pages / 300.0, 1.0)  # normalize: 300 pages = 1.0

    # 3. Retrieved chunk count (0.15)
    chunk_signal = min(retrieved_chunks / 10.0, 1.0)  # normalize: 10 chunks = 1.0

    # 4. Available VRAM (0.25) — inverse: less VRAM = higher score
    # We want to penalize (higher score → higher tier) when VRAM is available,
    # but cap it when VRAM is low.
    vram_signal = 1.0 - min(free_vram_mb / 8192.0, 1.0)  # normalize: 8GB free = 0

    # Weighted sum
    score = (
        query_signal * 0.35
        + doc_signal * 0.25
        + chunk_signal * 0.15
        + vram_signal * 0.25
    )

    # Tier decision
    if score < 0.3:
        tier = 1
    elif score < 0.6:
        tier = 2
    else:
        tier = 3

    return round(score, 3), tier
