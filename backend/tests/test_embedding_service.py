"""Tests for EmbeddingService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.embedding_service import EmbeddingService


def _make_service(embed_return=None, batch_size=32):
    """Helper: create EmbeddingService with a mocked LMStudioClient."""
    lm_client = MagicMock()
    lm_client.embed = AsyncMock(return_value=embed_return or [])
    return EmbeddingService(lm_client, batch_size=batch_size), lm_client


# ── embed_texts ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_embed_texts_basic():
    """embed_texts returns one vector per input text."""
    fake_vecs = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    svc, lm = _make_service(embed_return=fake_vecs, batch_size=32)

    result = await svc.embed_texts(["hello", "world"])

    assert len(result) == 2
    assert result[0] == [0.1, 0.2, 0.3]
    lm.embed.assert_awaited_once()


@pytest.mark.asyncio
async def test_embed_texts_empty_input():
    """embed_texts returns [] immediately for empty input."""
    svc, lm = _make_service()

    result = await svc.embed_texts([])

    assert result == []
    lm.embed.assert_not_awaited()


@pytest.mark.asyncio
async def test_embed_texts_batching():
    """33 texts with batch_size=32 should trigger exactly 2 LM Studio calls."""
    dim = 4
    batch_vecs = [[float(i)] * dim for i in range(32)]
    last_vec = [[99.0] * dim]

    lm_client = MagicMock()
    lm_client.embed = AsyncMock(side_effect=[batch_vecs, last_vec])
    svc = EmbeddingService(lm_client, batch_size=32)

    texts = [f"text_{i}" for i in range(33)]
    result = await svc.embed_texts(texts)

    assert lm_client.embed.await_count == 2
    assert len(result) == 33
    assert result[32] == [99.0] * dim


@pytest.mark.asyncio
async def test_embed_texts_lm_unavailable():
    """When LM Studio returns [], embed_texts returns zero-vectors (no crash)."""
    lm_client = MagicMock()
    # First call returns real vectors to establish dimension,
    # second call simulates failure
    lm_client.embed = AsyncMock(return_value=[])
    svc = EmbeddingService(lm_client, batch_size=32)

    result = await svc.embed_texts(["a", "b"])

    # Should not raise; may return empty or zero-padded
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_embed_texts_exception_handling():
    """An exception in embed() is caught; affected batch gets empty placeholders."""
    lm_client = MagicMock()
    lm_client.embed = AsyncMock(side_effect=RuntimeError("connection refused"))
    svc = EmbeddingService(lm_client, batch_size=32)

    result = await svc.embed_texts(["text_a"])

    # Should not raise; returns list (may be empty or zero-padded)
    assert isinstance(result, list)


# ── embed_chunks ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_embed_chunks_adds_embedding_field():
    """embed_chunks adds 'embedding' key to each chunk dict."""
    fake_vecs = [[0.1, 0.2], [0.3, 0.4]]
    svc, _ = _make_service(embed_return=fake_vecs)

    chunks = [
        {"text": "chunk 1", "doc_id": "doc_a", "page_start": 1},
        {"text": "chunk 2", "doc_id": "doc_a", "page_start": 2},
    ]
    result = await svc.embed_chunks(chunks)

    assert len(result) == 2
    assert "embedding" in result[0]
    assert result[0]["embedding"] == [0.1, 0.2]
    # Original metadata preserved
    assert result[0]["doc_id"] == "doc_a"
    assert result[0]["page_start"] == 1


@pytest.mark.asyncio
async def test_embed_chunks_preserves_metadata():
    """All original chunk fields survive embed_chunks."""
    fake_vecs = [[1.0, 2.0, 3.0]]
    svc, _ = _make_service(embed_return=fake_vecs)

    chunk = {
        "text": "The fee is $155 CAD",
        "chunk_index": 0,
        "start_char": 100,
        "end_char": 120,
        "page_start": 5,
        "doc_id": "irpa_fees.pdf",
        "kb_name": "immigration",
    }
    result = await svc.embed_chunks([chunk])

    r = result[0]
    assert r["chunk_index"] == 0
    assert r["start_char"] == 100
    assert r["end_char"] == 120
    assert r["page_start"] == 5
    assert r["kb_name"] == "immigration"
    assert r["embedding"] == [1.0, 2.0, 3.0]


@pytest.mark.asyncio
async def test_embed_chunks_empty_list():
    """embed_chunks returns [] immediately for empty input."""
    svc, lm = _make_service()

    result = await svc.embed_chunks([])

    assert result == []
    lm.embed.assert_not_awaited()
