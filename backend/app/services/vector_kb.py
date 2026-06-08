"""VectorKBService — local numpy-based vector storage and retrieval.

Storage layout per knowledge base:
  data/knowledge_bases/{kb}/vectors/{doc_id}_embeddings.npy   — float32 array (N × dim)
  data/knowledge_bases/{kb}/vectors/{doc_id}_metadata.json    — list of chunk dicts

Provides:
- store_vectors()   Save embeddings + metadata for a document
- delete_vectors()  Remove a document's vector data
- naive_search()    Pure cosine-similarity vector search
- hybrid_search()   Vector + keyword RRF merge
- keyword_search()  BM25-style keyword-only search

Vector ops require numpy. If numpy is not installed or LM Studio is
unavailable for query embedding, methods degrade gracefully to [].
"""

import json
import logging
import time
from collections import OrderedDict
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.lm_studio_client import LMStudioClient

logger = logging.getLogger(__name__)

UPLOAD_BASE = (
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "knowledge_bases" / "uploads"
)


class VectorKBService:
    """Vector and keyword retrieval service backed by local numpy files."""

    def __init__(
        self,
        kb_base: Path,
        lm_client: "LMStudioClient | None" = None,
    ):
        self.kb_base = kb_base
        self.lm_client = lm_client
        # LRU cache for loaded vectors: {kb_name: (timestamp, embeddings, chunks)}
        self._vector_cache: OrderedDict[str, tuple[float, object, list]] = OrderedDict()
        self._cache_max = 8  # max KBs cached
        self._cache_ttl = 300.0  # seconds

    # ── Storage ──────────────────────────────────────────────────────────────

    async def store_vectors(
        self,
        kb_name: str,
        doc_id: str,
        embeddings,  # np.ndarray (N × dim)
        chunks: list[dict],
    ) -> int:
        """Persist embeddings + metadata for one document.

        Args:
            kb_name:    Knowledge base name.
            doc_id:     Document identifier (filename).
            embeddings: numpy float32 array of shape (N, dim).
            chunks:     Parallel list of chunk dicts (metadata).

        Returns:
            Number of vectors stored, or 0 on failure.
        """
        try:
            import numpy as np
        except ImportError:
            logger.error("numpy is required for vector storage. Run: pip install numpy")
            return 0

        if embeddings is None or len(embeddings) == 0:
            logger.warning(f"store_vectors: no embeddings for {doc_id}")
            return 0

        vec_dir = self.kb_base / kb_name / "vectors"
        vec_dir.mkdir(parents=True, exist_ok=True)

        npy_path = vec_dir / f"{doc_id}_embeddings.npy"
        meta_path = vec_dir / f"{doc_id}_metadata.json"

        try:
            # Save vectors and metadata. Use atomic writes where possible:
            # write metadata to a temp file first, then os.replace. For numpy
            # .npy files, direct write is used (numpy handles its own atomicity
            # via file creation flags on most platforms).
            meta_tmp = meta_path.with_suffix(".json.tmp")
            meta_tmp.write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
            np.save(str(npy_path), embeddings.astype(np.float32))
            import os

            os.replace(str(meta_tmp), str(meta_path))
            count = len(embeddings)
            logger.info(f"Stored {count} vectors for {kb_name}/{doc_id}")
            self._vector_cache.pop(kb_name, None)
            return count
        except Exception as e:
            logger.error(f"store_vectors failed for {doc_id}: {e}")
            return 0

    def delete_vectors(self, kb_name: str, doc_id: str) -> bool:
        """Remove vector data files for a single document."""
        vec_dir = self.kb_base / kb_name / "vectors"
        npy_path = vec_dir / f"{doc_id}_embeddings.npy"
        meta_path = vec_dir / f"{doc_id}_metadata.json"

        removed = False
        for p in (npy_path, meta_path):
            if p.exists():
                p.unlink()
                removed = True

        if removed:
            logger.info(f"Deleted vector data for {kb_name}/{doc_id}")
            self._vector_cache.pop(kb_name, None)
        return removed

    # ── Loading ───────────────────────────────────────────────────────────────

    def _load_all_vectors(self, kb_name: str):
        """Load all embeddings + metadata across every doc in a KB.

        Uses an in-memory LRU cache (TTL-based) to avoid re-reading from
        disk on repeated queries against the same knowledge base.

        Returns:
            (embeddings: np.ndarray | None, chunks: list[dict])
        """
        # Check cache
        now = time.monotonic()
        if kb_name in self._vector_cache:
            ts, emb, chunks = self._vector_cache[kb_name]
            if now - ts < self._cache_ttl:
                self._vector_cache.move_to_end(kb_name)
                logger.debug(f"Cache hit for KB '{kb_name}'")
                return emb, chunks
            else:
                del self._vector_cache[kb_name]

        try:
            import numpy as np
        except ImportError:
            return None, []

        vec_dir = self.kb_base / kb_name / "vectors"
        if not vec_dir.exists():
            return None, []

        all_embeddings = []
        all_chunks = []

        for npy_path in sorted(vec_dir.glob("*_embeddings.npy")):
            meta_path = npy_path.with_name(
                npy_path.name.replace("_embeddings.npy", "_metadata.json")
            )
            if not meta_path.exists():
                continue
            try:
                emb = np.load(str(npy_path))
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                if len(emb) != len(meta):
                    logger.warning(f"Shape mismatch in {npy_path.name} — skipping")
                    continue
                all_embeddings.append(emb)
                all_chunks.extend(meta)
            except Exception as e:
                logger.error(f"Failed to load {npy_path}: {e}")

        if not all_embeddings:
            return None, []

        combined = np.concatenate(all_embeddings, axis=0).astype(np.float32)

        # Store in cache
        self._vector_cache[kb_name] = (now, combined, all_chunks)
        self._vector_cache.move_to_end(kb_name)
        while len(self._vector_cache) > self._cache_max:
            self._vector_cache.popitem(last=False)
        logger.debug(f"Cached vectors for KB '{kb_name}' ({len(combined)} vectors)")

        return combined, all_chunks

    # ── Search ────────────────────────────────────────────────────────────────

    async def naive_search(
        self,
        query: str,
        kb_name: str,
        top_k: int = 5,
        min_score: float = 0.3,
    ) -> list[dict]:
        """Pure cosine-similarity vector search.

        Embeds the query via LM Studio, computes cosine similarity against
        all stored vectors, and returns the top_k above min_score.
        Returns [] when no vector data or LM Studio is unavailable.
        """
        if not self.lm_client:
            logger.warning("naive_search: no lm_client set — returning empty")
            return []

        embeddings, chunks = self._load_all_vectors(kb_name)
        if embeddings is None or len(chunks) == 0:
            logger.info(f"naive_search: no vector data for KB '{kb_name}'")
            return []

        try:
            import numpy as np
        except ImportError:
            logger.error("numpy not installed — cannot run vector search")
            return []

        # Embed the query
        vecs = await self.lm_client.embed([query])
        if not vecs:
            logger.warning("naive_search: query embedding returned empty")
            return []

        query_vec = np.array(vecs[0], dtype=np.float32)

        # Cosine similarity
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return []

        norms = np.linalg.norm(embeddings, axis=1)
        norms[norms == 0] = 1e-9  # prevent division by zero

        scores = (embeddings @ query_vec) / (norms * query_norm)

        # Get top_k above threshold
        top_indices = np.argsort(scores)[::-1]
        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score < min_score:
                break
            if len(results) >= top_k:
                break
            chunk = dict(chunks[idx])
            chunk["relevance_score"] = round(score, 4)
            chunk["score"] = round(score, 4)
            results.append(chunk)

        return results

    async def hybrid_search(
        self,
        query: str,
        kb_name: str,
        top_k: int = 5,
        min_score: float = 0.3,
    ) -> list[dict]:
        """Hybrid vector + keyword retrieval with RRF merge."""
        vector_results = await self.naive_search(query, kb_name, top_k * 2, min_score)
        keyword_results = self._keyword_search(query, kb_name, top_k * 2)

        if not vector_results and not keyword_results:
            return []

        return _rrf_merge(vector_results, keyword_results, top_k)

    def keyword_search(
        self,
        query: str,
        kb_name: str,
        top_k: int = 5,
    ) -> list[dict]:
        """Pure keyword search over raw document text."""
        return self._keyword_search(query, kb_name, top_k)

    def _keyword_search(
        self,
        query: str,
        kb_name: str,
        top_k: int,
    ) -> list[dict]:
        """BM25-style term-overlap search over uploaded document files."""
        upload_dir = UPLOAD_BASE / kb_name
        if not upload_dir.exists():
            return []
        return self._keyword_search_in_directory(query, upload_dir, top_k)

    def _keyword_search_in_directory(
        self,
        query: str,
        search_dir: Path,
        top_k: int,
    ) -> list[dict]:
        """Search all text/PDF files in a directory by term overlap."""
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
                    text = "\n".join(page.get_text("text") for page in doc)
                    doc.close()
                else:
                    text = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            score = sum(1 for t in query_terms if t in text.lower())
            if score > 0:
                max_possible = len(query_terms)
                results.append(
                    {
                        "doc_id": file_path.stem,
                        "section": file_path.name,
                        "content": text[:500],
                        "relevance_score": round(score / max_possible, 3),
                        "score": round(score / max_possible, 3),
                        "page": 0,
                        "page_end": 0,
                        "node_id": "",
                    }
                )

        results.sort(key=lambda r: r.get("relevance_score", 0), reverse=True)
        return results[:top_k]


# ── RRF merge (module-level, used by both VectorKBService and HybridRAGSearch) ──


def _rrf_merge(
    vector_results: list[dict],
    keyword_results: list[dict],
    top_k: int = 5,
) -> list[dict]:
    """Reciprocal Rank Fusion merge of two ranked result lists.

    k=60 per the original RRF paper (Cormack et al., 2009).
    Deduplicates by (doc_id, section) key, accumulating RRF scores.
    """
    k = 60
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
    for _key, (rrf_score, result) in scores.items():
        r = dict(result)
        r["rrf_score"] = round(rrf_score, 4)
        r["relevance_score"] = round(rrf_score, 4)
        merged.append(r)

    merged.sort(key=lambda r: r.get("rrf_score", 0), reverse=True)
    return merged[:top_k]
