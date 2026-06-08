"""Hybrid RAG — delegates to VectorKBService for vector + keyword retrieval.

Now backed by real vector data (FR-1.3). Delegates to VectorKBService which
handles both vector similarity and keyword search with RRF merge.

HybridRAGSearch is kept as a thin façade so existing callers (retrieval.py,
query_router.py) don't need changes — they already construct this class.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.lm_studio_client import LMStudioClient

from app.services.vector_kb import VectorKBService

logger = logging.getLogger(__name__)

KB_BASE = Path("data/knowledge_bases")


class HybridRAGSearch:
    """Hybrid retrieval combining vector similarity and keyword matching.

    Wraps VectorKBService. Both naive (vector-only) and hybrid (vector +
    keyword RRF) modes are supported.
    """

    def __init__(
        self,
        vram_monitor=None,
        lm_client: "LMStudioClient | None" = None,
    ):
        self.vram_monitor = vram_monitor
        self.lm_client = lm_client
        self._vector_svc = VectorKBService(KB_BASE, lm_client=lm_client)

    async def search(
        self,
        query: str,
        kb_name: str,
        top_k: int = 5,
        min_score: float = 0.3,
    ) -> list[dict]:
        """Hybrid vector + keyword search with RRF merge.

        Returns list of {content, score, doc_id, page, section, ...}.
        Falls back to keyword-only when no vector data exists.
        """
        results = await self._vector_svc.hybrid_search(
            query=query,
            kb_name=kb_name,
            top_k=top_k,
            min_score=min_score,
        )
        if not results:
            logger.info(
                f"HybridRAGSearch: no results for '{kb_name}' "
                "(no vector data or LM Studio unavailable — keyword-only fallback)"
            )
            # Pure keyword as last resort
            results = self._vector_svc.keyword_search(query, kb_name, top_k)
        return results

    async def naive_search(
        self,
        query: str,
        kb_name: str,
        top_k: int = 5,
        min_score: float = 0.3,
    ) -> list[dict]:
        """Pure vector similarity search (no keyword component)."""
        results = await self._vector_svc.naive_search(
            query=query,
            kb_name=kb_name,
            top_k=top_k,
            min_score=min_score,
        )
        if not results:
            logger.info(f"NaiveRAGSearch: no vector data for '{kb_name}'")
        return results
