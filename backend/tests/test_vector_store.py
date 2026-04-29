"""Tests for VectorKBService vector storage and search."""

import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("numpy", reason="numpy required for vector store tests")
import numpy as np

from app.services.vector_kb import VectorKBService, _rrf_merge


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def tmp_kb(tmp_path):
    """Return a VectorKBService with a temporary KB base directory."""
    lm = MagicMock()
    svc = VectorKBService(kb_base=tmp_path, lm_client=lm)
    return svc, tmp_path, lm


def _make_embeddings(n: int, dim: int = 4) -> np.ndarray:
    """Create deterministic synthetic embeddings."""
    rng = np.random.default_rng(42)
    vecs = rng.standard_normal((n, dim)).astype(np.float32)
    # L2-normalise so cosine == dot
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs / norms


def _make_chunks(n: int, doc_id: str = "doc.pdf") -> list[dict]:
    return [
        {"text": f"Chunk {i}", "chunk_index": i, "doc_id": doc_id, "page_start": i + 1}
        for i in range(n)
    ]


# ── store_vectors / delete_vectors ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_store_creates_npy_and_json(tmp_kb):
    svc, base, _ = tmp_kb
    emb = _make_embeddings(3)
    chunks = _make_chunks(3)

    count = await svc.store_vectors("kb1", "doc.pdf", emb, chunks)

    assert count == 3
    assert (base / "kb1" / "vectors" / "doc.pdf_embeddings.npy").exists()
    assert (base / "kb1" / "vectors" / "doc.pdf_metadata.json").exists()


@pytest.mark.asyncio
async def test_store_load_roundtrip(tmp_kb):
    svc, base, _ = tmp_kb
    emb = _make_embeddings(5, dim=8)
    chunks = _make_chunks(5)

    await svc.store_vectors("kb1", "doc.pdf", emb, chunks)
    loaded_emb, loaded_chunks = svc._load_all_vectors("kb1")

    assert loaded_emb is not None
    assert loaded_emb.shape == (5, 8)
    assert len(loaded_chunks) == 5
    assert loaded_chunks[0]["chunk_index"] == 0


@pytest.mark.asyncio
async def test_store_empty_embeddings_returns_zero(tmp_kb):
    svc, _, _ = tmp_kb
    emb = np.array([], dtype=np.float32).reshape(0, 4)
    count = await svc.store_vectors("kb1", "doc.pdf", emb, [])
    assert count == 0


@pytest.mark.asyncio
async def test_delete_vectors_removes_files(tmp_kb):
    svc, base, _ = tmp_kb
    emb = _make_embeddings(2)
    chunks = _make_chunks(2)
    await svc.store_vectors("kb1", "doc.pdf", emb, chunks)

    removed = svc.delete_vectors("kb1", "doc.pdf")

    assert removed is True
    assert not (base / "kb1" / "vectors" / "doc.pdf_embeddings.npy").exists()
    assert not (base / "kb1" / "vectors" / "doc.pdf_metadata.json").exists()


def test_delete_vectors_missing_doc_returns_false(tmp_kb):
    svc, _, _ = tmp_kb
    removed = svc.delete_vectors("kb1", "nonexistent.pdf")
    assert removed is False


# ── naive_search ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_naive_search_returns_closest_chunk(tmp_kb):
    svc, _, lm = tmp_kb
    dim = 4

    # 3 chunks with known directions
    emb = np.zeros((3, dim), dtype=np.float32)
    emb[0] = [1, 0, 0, 0]
    emb[1] = [0, 1, 0, 0]
    emb[2] = [0, 0, 1, 0]

    chunks = _make_chunks(3)
    await svc.store_vectors("kb1", "doc.pdf", emb, chunks)

    # Query vector most similar to chunk[1]
    query_vec = [0.0, 1.0, 0.0, 0.0]
    lm.embed = AsyncMock(return_value=[query_vec])

    results = await svc.naive_search("query", "kb1", top_k=1, min_score=0.0)

    assert len(results) == 1
    assert results[0]["chunk_index"] == 1


@pytest.mark.asyncio
async def test_naive_search_empty_kb(tmp_kb):
    svc, _, lm = tmp_kb
    lm.embed = AsyncMock(return_value=[[1.0, 0.0]])

    results = await svc.naive_search("query", "kb_empty", top_k=5, min_score=0.0)
    assert results == []


@pytest.mark.asyncio
async def test_naive_search_no_lm_client(tmp_path):
    svc = VectorKBService(kb_base=tmp_path, lm_client=None)
    results = await svc.naive_search("query", "kb1")
    assert results == []


@pytest.mark.asyncio
async def test_naive_search_embed_failure(tmp_kb):
    svc, _, lm = tmp_kb
    emb = _make_embeddings(3)
    await svc.store_vectors("kb1", "doc.pdf", emb, _make_chunks(3))

    lm.embed = AsyncMock(return_value=[])
    results = await svc.naive_search("query", "kb1", min_score=0.0)
    assert results == []


# ── hybrid_search ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_hybrid_search_no_data_returns_empty(tmp_kb):
    svc, _, lm = tmp_kb
    lm.embed = AsyncMock(return_value=[[1.0, 0.0]])
    results = await svc.hybrid_search("query", "nonexistent_kb")
    assert results == []


# ── _rrf_merge ────────────────────────────────────────────────────────────────


def test_rrf_merge_deduplicates():
    vec = [{"doc_id": "a", "section": "s1", "score": 0.9}]
    kw = [{"doc_id": "a", "section": "s1", "score": 0.5}]
    merged = _rrf_merge(vec, kw, top_k=5)
    # Same (doc_id, section) — should appear once
    assert len(merged) == 1
    assert merged[0]["rrf_score"] > 0


def test_rrf_merge_top_k_limit():
    vec = [{"doc_id": f"doc{i}", "section": f"s{i}", "score": 1.0} for i in range(10)]
    kw = []
    merged = _rrf_merge(vec, kw, top_k=3)
    assert len(merged) == 3


def test_rrf_merge_empty_lists():
    assert _rrf_merge([], [], top_k=5) == []


# ── load_all_vectors — multi-doc ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_load_all_vectors_multi_doc(tmp_kb):
    svc, _, _ = tmp_kb
    emb1 = _make_embeddings(3, dim=4)
    emb2 = _make_embeddings(4, dim=4)

    await svc.store_vectors("kb1", "doc1.pdf", emb1, _make_chunks(3, "doc1.pdf"))
    await svc.store_vectors("kb1", "doc2.pdf", emb2, _make_chunks(4, "doc2.pdf"))

    combined, chunks = svc._load_all_vectors("kb1")
    assert combined.shape == (7, 4)
    assert len(chunks) == 7
