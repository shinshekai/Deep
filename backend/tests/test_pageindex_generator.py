"""Tests for PageIndexTreeGenerator."""

import pytest


@pytest.fixture
def sample_pages():
    return [
        {
            "page_num": 1,
            "text": (
                "Introduction\n\n"
                "Welcome to this document about machine learning.\n"
                "This section provides background information.\n"
            ),
        },
        {
            "page_num": 2,
            "text": ("Introduction continued with more details.\n"),
        },
        {
            "page_num": 3,
            "text": (
                "1. Neural Networks\n\n"
                "Neural networks are computational models inspired by brains.\n"
            ),
        },
        {
            "page_num": 4,
            "text": (
                "1.1 Deep Learning\n\n"
                "Deep learning refers to neural networks with many layers.\n"
            ),
        },
        {
            "page_num": 5,
            "text": (
                "2. Training Methods\n\n" "Training involves feeding data through the network.\n"
            ),
        },
    ]


@pytest.fixture
def mock_lm_client():
    import json
    from unittest.mock import AsyncMock

    client = AsyncMock()

    def heading_side_effect(messages, model=None, max_tokens=2048, temperature=0.7):
        user_content = [m["content"] for m in messages if m["role"] == "user"][0]
        if "document structure analysis" in user_content.lower():
            return json.dumps(
                [
                    {"title": "Introduction", "depth": 1},
                    {"title": "1. Neural Networks", "depth": 1},
                    {"title": "1.1 Deep Learning", "depth": 2},
                    {"title": "2. Training Methods", "depth": 1},
                ]
            )
        elif "Summarize" in user_content:
            return "This section covers the topic in detail."
        return None

    client.stream_chat.side_effect = heading_side_effect
    return client


# -- Unit tests --


def test_parse_heading_json():
    from app.services.pageindex_generator import PageIndexTreeGenerator

    gen = PageIndexTreeGenerator(None)
    headings = gen._parse_heading_json(
        '[{"title": "Section 1", "depth": 1}, ' '{"title": "Subsection 1.1", "depth": 2}]'
    )
    assert len(headings) == 2
    assert headings[0]["title"] == "Section 1"
    assert headings[0]["depth"] == 1
    assert headings[1]["depth"] == 2


def test_parse_heading_json_with_markdown_fence():
    from app.services.pageindex_generator import PageIndexTreeGenerator

    gen = PageIndexTreeGenerator(None)
    headings = gen._parse_heading_json('```json\n[{"title": "Header", "depth": 1}]\n```')
    assert len(headings) == 1
    assert headings[0]["title"] == "Header"


def test_parse_heading_json_invalid():
    from app.services.pageindex_generator import PageIndexTreeGenerator

    gen = PageIndexTreeGenerator(None)
    assert gen._parse_heading_json("not json") == []


def test_parse_heading_json_missing_depth():
    from app.services.pageindex_generator import PageIndexTreeGenerator

    gen = PageIndexTreeGenerator(None)
    headings = gen._parse_heading_json('[{"title": "Header"}]')
    assert len(headings) == 1
    assert headings[0]["title"] == "Header"


def test_regex_heading_fallback():
    from app.services.pageindex_generator import PageIndexTreeGenerator

    gen = PageIndexTreeGenerator(None)
    text = (
        "1. Introduction\n"
        "Some body text.\n"
        "1.1 Background\n"
        "More text.\n"
        "2. Methods\n"
        "2.1 Data Collection\n"
    )
    headings = gen._regex_heading_fallback(text)
    assert len(headings) >= 2
    assert any("Introduction" in h["title"] for h in headings)
    assert any(h["depth"] == 2 for h in headings)


def test_assign_page_ranges(sample_pages):
    from app.services.pageindex_generator import PageIndexTreeGenerator

    gen = PageIndexTreeGenerator(None)
    toc_nodes = [
        {"title": "Introduction", "depth": 1},
        {"title": "1. Neural Networks", "depth": 1},
        {"title": "1.1 Deep Learning", "depth": 2},
        {"title": "2. Training Methods", "depth": 1},
    ]
    nodes = gen._assign_page_ranges(sample_pages, toc_nodes)
    assert len(nodes) == 4
    assert nodes[0]["page_start"] == 1
    assert nodes[1]["page_start"] == 3
    assert nodes[2]["page_start"] == 4
    assert nodes[3]["page_start"] == 5


def test_char_to_page():
    from app.services.pageindex_generator import PageIndexTreeGenerator

    gen = PageIndexTreeGenerator(None)
    offsets = [
        {"page_num": 1, "start": 0, "end": 100},
        {"page_num": 2, "start": 101, "end": 200},
    ]
    assert gen._char_to_page(50, offsets) == 1
    assert gen._char_to_page(150, offsets) == 2


def test_structure_tree():
    from app.services.pageindex_generator import PageIndexTreeGenerator

    gen = PageIndexTreeGenerator(None)
    nodes = [
        {
            "title": "Intro",
            "depth": 1,
            "start_index": 0,
            "end_index": 100,
            "page_start": 1,
            "page_end": 5,
            "summary": "Intro summary",
        },
        {
            "title": "Methods",
            "depth": 1,
            "start_index": 100,
            "end_index": 200,
            "page_start": 6,
            "page_end": 10,
            "summary": "Methods summary",
        },
    ]
    tree = gen._structure_tree(nodes, "doc_test.pdf", 10, "Test Document")
    assert tree["doc_id"] == "doc_test.pdf"
    assert tree["total_pages"] == 10
    assert tree["root"]["node_id"] == "root"
    assert len(tree["root"]["children"]) == 2


def test_structure_tree_nested():
    from app.services.pageindex_generator import PageIndexTreeGenerator

    gen = PageIndexTreeGenerator(None)
    nodes = [
        {
            "title": "Chapter 1",
            "depth": 1,
            "start_index": 0,
            "end_index": 50,
            "page_start": 1,
            "page_end": 3,
            "summary": "Ch1 summary",
        },
        {
            "title": "Section 1.1",
            "depth": 2,
            "start_index": 0,
            "end_index": 25,
            "page_start": 1,
            "page_end": 2,
            "summary": "Sec 1.1 summary",
        },
        {
            "title": "Chapter 2",
            "depth": 1,
            "start_index": 50,
            "end_index": 100,
            "page_start": 4,
            "page_end": 6,
            "summary": "Ch2 summary",
        },
    ]
    tree = gen._structure_tree(nodes, "doc_test.pdf", 6, "Test")
    assert len(tree["root"]["children"]) == 2
    ch1 = tree["root"]["children"][0]
    assert ch1["title"] == "Chapter 1"
    assert len(ch1["children"]) == 1
    assert ch1["children"][0]["title"] == "Section 1.1"


def test_empty_tree():
    from app.services.pageindex_generator import PageIndexTreeGenerator

    gen = PageIndexTreeGenerator(None)
    tree = gen._empty_tree("doc_empty.pdf", "Empty Doc")
    assert tree["doc_id"] == "doc_empty.pdf"
    assert tree["total_pages"] == 0
    assert tree["root"]["children"] == []


@pytest.mark.asyncio
async def test_build_tree_with_mock_client(sample_pages, mock_lm_client):
    from app.services.pageindex_generator import PageIndexTreeGenerator

    gen = PageIndexTreeGenerator(mock_lm_client)
    doc_content = {"type": "pdf", "pages": sample_pages}
    tree = await gen.build_tree(doc_content, "qwen-model", "doc_test.pdf")
    assert tree is not None
    assert tree["doc_id"] == "doc_test.pdf"
    assert tree["total_pages"] == 5
    assert "root" in tree
    assert isinstance(tree["root"]["children"], list)
