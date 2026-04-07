"""VectorKBService — vector and keyword retrieval over knowledge bases.

Provides interfaces for:
- naive_search: Pure vector similarity (returns empty until FR-1.3)
- hybrid_search: Vector + keyword RRF merge (returns empty until FR-1.3)
- keyword_search: BM25-style search over raw document text

When vector data is unavailable (FR-1.3 not implemented), returns empty
results with an info log. Interface is ready for when data arrives.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

UPLOAD_BASE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "knowledge_bases" / "uploads"


class VectorKBService:
    """Vector and keyword retrieval service."""

    def __init__(self, kb_base: Path):
        self.kb_base = kb_base

    def naive_search(
        self, query: str, kb_name: str, top_k: int = 5, min_score: float = 0.3
    ) -> list[dict]:
        """Pure vector similarity search."""
        vector_dir = self.kb_base / kb_name / "vectors"
        if not vector_dir.exists() or not any(vector_dir.iterdir()):
            logger.info(
                f"VectorKB: no vector data in {vector_dir}, "
                "returning empty results for naive search"
            )
            return []

        # When FR-1.3 (Vector KB Builder) creates vector data:
        # 1. Embed the query
        # 2. Compute cosine similarity against all stored vectors
        # 3. Return top_k above min_score
        return []

    def hybrid_search(
        self, query: str, kb_name: str, top_k: int = 5, min_score: float = 0.3
    ) -> list[dict]:
        """Hybrid vector + keyword retrieval with RRF merge."""
        vector_results = self.naive_search(query, kb_name, top_k * 2, min_score)
        keyword_results = self._keyword_search(query, kb_name, top_k * 2)

        if not vector_results and not keyword_results:
            return []

        return _rrf_merge(vector_results, keyword_results, top_k)

    def keyword_search(
        self, query: str, kb_name: str, top_k: int = 5
    ) -> list[dict]:
        """Pure keyword search over raw document text."""
        return self._keyword_search(query, kb_name, top_k)

    def _keyword_search(
        self, query: str, kb_name: str, top_k: int
    ) -> list[dict]:
        """Search over uploaded document files."""
        upload_dir = UPLOAD_BASE / kb_name
        if not upload_dir.exists():
            return []

        return self._keyword_search_in_directory(query, upload_dir, top_k)

    def _keyword_search_in_directory(
        self, query: str, search_dir: Path, top_k: int
    ) -> list[dict]:
        """Search all text files in a directory."""
        query_terms = set(query.lower().split())
        if not query_terms:
            return []

        results = []

        for file_path in search_dir.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix not in (".txt", ".md", ".pdf"):
                continue

            try:
                if file_path.suffix == ".pdf":
                    import fitz
                    doc = fitz.open(str(file_path))
                    text = "\n".join(
                        page.get_text("text") for page in doc
                    )
                    doc.close()
                else:
                    text = file_path.read_text(encoding="utf-8")
            except (OSError, Exception):
                continue

            score = sum(
                1 for t in query_terms if t in text.lower()
            )
            if score > 0:
                max_possible = len(query_terms)
                results.append({
                    "doc_id": file_path.stem,
                    "section": file_path.name,
                    "content": text[:500],
                    "relevance_score": round(score / max_possible, 3),
                    "score": round(score / max_possible, 3),
                    "page": 0,
                    "page_end": 0,
                    "node_id": "",
                })

        results.sort(
            key=lambda r: r.get("relevance_score", 0), reverse=True
        )
        return results[:top_k]


def _rrf_merge(
    vector_results: list[dict],
    keyword_results: list[dict],
    top_k: int = 5,
) -> list[dict]:
    """Reciprocal Rank Fusion merge of two ranked result lists.

    Uses default k=60 as established in RRF literature.
    Deduplicates by (doc_id, section) key, keeping higher RRF score.
    """
    k = 60

    # Compute ranks
    scores: dict[tuple, tuple[float, dict]] = {}

    def process(results: list[dict]):
        for rank, result in enumerate(results):
            key = (result.get("doc_id", ""), result.get("section", ""))
            rrf = 1.0 / (k + rank + 1)

            if key in scores:
                old_score, old_result = scores[key]
                scores[key] = (old_score + rrf, result)
            else:
                scores[key] = (rrf, result)

    process(vector_results)
    process(keyword_results)

    merged = []
    for key, (rrf_score, result) in scores.items():
        r = dict(result)
        r["rrf_score"] = round(rrf_score, 4)
        r["relevance_score"] = round(rrf_score, 4)
        merged.append(r)

    merged.sort(key=lambda r: r.get("rrf_score", 0), reverse=True)
    return merged[:top_k]

