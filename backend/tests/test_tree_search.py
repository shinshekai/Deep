"""Tree search service tests — LLM reasoning over PageIndex trees."""

from unittest.mock import AsyncMock

import pytest

# Sample PageIndex tree for tests
SAMPLE_TREE = {
    "doc_id": "test_doc",
    "title": "Test Document",
    "total_pages": 10,
    "root": {
        "node_id": "root",
        "title": "Test Document",
        "summary": "A document about machine learning",
        "page_start": 0,
        "page_end": 9,
        "children": [
            {
                "node_id": "node_1_0",
                "title": "Neural Networks",
                "summary": "Overview of neural network architectures and training methods",
                "page_start": 0,
                "page_end": 4,
                "children": [
                    {
                        "node_id": "node_2_0",
                        "title": "Deep Learning",
                        "summary": "Deep learning models including CNNs, RNNs, and transformers",
                        "page_start": 2,
                        "page_end": 4,
                        "children": [],
                    }
                ],
            },
            {
                "node_id": "node_1_1",
                "title": "Training Methods",
                "summary": "Backpropagation, gradient descent, and optimization techniques",
                "page_start": 5,
                "page_end": 7,
                "children": [],
            },
            {
                "node_id": "node_1_2",
                "title": "Evaluation",
                "summary": "Metrics for model evaluation including accuracy and F1 score",
                "page_start": 8,
                "page_end": 9,
                "children": [],
            },
        ],
    },
}


@pytest.fixture
def mock_lm_client():
    client = AsyncMock()

    async def mock_stream_chat(messages, **kwargs):
        return (
            '[{"node_id": "node_1_0", "score": 0.92, "reason": "Covers '
            'neural network architectures and training"}, '
            '{"node_id": "node_1_1", "score": 0.65, "reason": "Training '
            'methods are relevant to building networks"}]'
        )

    client.stream_chat = mock_stream_chat
    client.check_health = AsyncMock(return_value=True)
    return client


@pytest.fixture
def tree_search(mock_lm_client):
    from app.services.tree_search import TreeSearch

    return TreeSearch(lm_client=mock_lm_client)


@pytest.mark.asyncio
async def test_tree_search_returns_scored_nodes(tree_search):
    """LLM scoring returns ranked node_ids with scores."""
    results = await tree_search.search(
        query="How to build a neural network?",
        kb_name="test_kb",
        doc_id="test_doc",
        tree=SAMPLE_TREE,
        top_k=3,
        min_score=0.3,
    )
    assert len(results) > 0
    assert results[0]["doc_id"] == "test_doc"
    assert "score" in results[0] or "relevance_score" in results[0]


@pytest.mark.asyncio
async def test_tree_search_respects_doc_id_filter(tree_search):
    """When doc_id specified, only searches that document's tree."""
    results = await tree_search.search(
        query="training methods",
        kb_name="test_kb",
        doc_id="test_doc",
        tree=SAMPLE_TREE,
        top_k=2,
        min_score=0.3,
    )
    assert all(r.get("doc_id") == "test_doc" for r in results)


@pytest.mark.asyncio
async def test_keyword_fallback_when_llm_unavailable():
    """Falls back to keyword matching when LM Studio is down."""
    from app.services.tree_search import TreeSearch

    client = AsyncMock()
    client.check_health = AsyncMock(return_value=False)

    ts = TreeSearch(lm_client=client)
    results = await ts.search(
        query="neural network",
        kb_name="test_kb",
        doc_id="test_doc",
        tree=SAMPLE_TREE,
        top_k=3,
        min_score=0.1,
    )
    assert len(results) > 0


@pytest.mark.asyncio
async def test_parse_llm_results_strips_markdown():
    """Handles markdown-wrapped JSON from LLM."""
    from app.services.tree_search import TreeSearch

    client = AsyncMock()
    ts = TreeSearch(lm_client=client)

    response = '```json\n[{"node_id": "node_1", "score": 0.8, "reason": "test"}]\n```'
    parsed = ts._parse_llm_results(response)
    assert parsed is not None
    assert len(parsed) == 1
    assert parsed[0]["node_id"] == "node_1"
    assert parsed[0]["score"] == 0.8


@pytest.mark.asyncio
async def test_parse_llm_handles_invalid_json():
    """Returns None for invalid JSON response."""
    from app.services.tree_search import TreeSearch

    client = AsyncMock()
    ts = TreeSearch(lm_client=client)

    parsed = ts._parse_llm_results("not json at all")
    assert parsed is None


@pytest.mark.asyncio
async def test_empty_tree_returns_no_results():
    """Search on empty tree returns empty results."""
    from app.services.tree_search import TreeSearch

    client = AsyncMock()
    client.check_health = AsyncMock(return_value=True)
    client.stream_chat = AsyncMock(return_value="[]")

    ts = TreeSearch(lm_client=client)
    results = await ts.search(
        query="anything",
        kb_name="test_kb",
        doc_id="empty",
        tree={"doc_id": "empty", "root": {"node_id": "root", "children": []}},
        top_k=5,
        min_score=0.3,
    )
    assert results == []


def test_keyword_score_title_weights_higher():
    """Title matches score 3x more than summary matches."""
    from unittest.mock import AsyncMock

    from app.services.tree_search import TreeSearch

    tree = {
        "root": {
            "node_id": "node_a",
            "title": "Transformer Architecture",
            "summary": "Irrelevant text about cooking",
            "page_start": 0,
            "page_end": 5,
            "children": [],
        }
    }
    client = AsyncMock()
    ts = TreeSearch(lm_client=client)
    results = ts._keyword_score("doc1", tree, "transformer architecture")

    assert len(results) == 1
    assert results[0]["relevance_score"] == 1.0
