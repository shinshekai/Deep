import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.hybrid_rag import HybridRAGSearch

@pytest.mark.asyncio
async def test_hybrid_search(monkeypatch):
    rag = HybridRAGSearch()
    
    # Mock VectorKBService.hybrid_search
    mock_hybrid = AsyncMock(return_value=[{"content": "hybrid result"}])
    monkeypatch.setattr(rag._vector_svc, "hybrid_search", mock_hybrid)
    
    res = await rag.search("query", "kb")
    assert len(res) == 1
    assert res[0]["content"] == "hybrid result"

@pytest.mark.asyncio
async def test_hybrid_search_fallback(monkeypatch):
    rag = HybridRAGSearch()
    
    # Mock VectorKBService to return empty for hybrid, and mock keyword search
    mock_hybrid = AsyncMock(return_value=[])
    monkeypatch.setattr(rag._vector_svc, "hybrid_search", mock_hybrid)
    
    mock_keyword = MagicMock(return_value=[{"content": "keyword result"}])
    monkeypatch.setattr(rag._vector_svc, "keyword_search", mock_keyword)
    
    res = await rag.search("query", "kb")
    assert len(res) == 1
    assert res[0]["content"] == "keyword result"

@pytest.mark.asyncio
async def test_naive_search(monkeypatch):
    rag = HybridRAGSearch()
    
    mock_naive = AsyncMock(return_value=[{"content": "naive result"}])
    monkeypatch.setattr(rag._vector_svc, "naive_search", mock_naive)
    
    res = await rag.naive_search("query", "kb")
    assert len(res) == 1
    assert res[0]["content"] == "naive result"
