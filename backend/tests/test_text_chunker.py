"""Tests for TextChunker."""

import pytest

from app.services.text_chunker import TextChunk, TextChunker


# ── Basic chunking ────────────────────────────────────────────────────────────


def test_chunk_returns_list_of_text_chunks():
    """chunk_text returns a non-empty list of TextChunk objects."""
    chunker = TextChunker(chunk_size=50, chunk_overlap=5)
    text = "word " * 300  # ~1500 chars
    chunks = chunker.chunk_text(text, doc_id="test_doc", kb_name="test_kb")

    assert len(chunks) > 0
    assert all(isinstance(c, TextChunk) for c in chunks)


def test_chunk_covers_full_text():
    """All chunks together cover the full original text length."""
    chunker = TextChunker(chunk_size=50, chunk_overlap=0, min_chunk_size=0)
    # Build a text with clear paragraph breaks
    paragraphs = ["Paragraph number " + str(i) + " with some words." for i in range(20)]
    text = "\n\n".join(paragraphs)

    chunks = chunker.chunk_text(text)

    combined = " ".join(c.text for c in chunks)
    # Every paragraph should appear in at least one chunk
    for para in paragraphs:
        assert any(para[:20] in c.text for c in chunks), f"Missing: {para[:20]}"


def test_chunk_size_roughly_respected():
    """Chunk sizes stay close to target (within 2x for pathological inputs)."""
    chunk_size_tokens = 30  # 30 * 4 = 120 chars
    chunker = TextChunker(chunk_size=chunk_size_tokens, chunk_overlap=5, min_chunk_size=0)
    text = "A" * 1000  # Single long string, forces word-level split
    chunks = chunker.chunk_text(text)

    target = chunk_size_tokens * 4  # chars
    for c in chunks:
        assert len(c.text) <= target * 2 + 50, f"Chunk too large: {len(c.text)}"


def test_chunk_indices_are_sequential():
    """chunk_index values are sequential starting at 0."""
    chunker = TextChunker(chunk_size=30, chunk_overlap=3)
    text = ("Short paragraph.\n\n" * 20)
    chunks = chunker.chunk_text(text)

    for i, c in enumerate(chunks):
        assert c.chunk_index == i


def test_chunk_doc_id_and_kb_name_propagated():
    """doc_id and kb_name are set on every TextChunk."""
    chunker = TextChunker(chunk_size=50, chunk_overlap=5)
    text = "Some text. " * 100
    chunks = chunker.chunk_text(text, doc_id="myfile.pdf", kb_name="mybase")

    for c in chunks:
        assert c.doc_id == "myfile.pdf"
        assert c.kb_name == "mybase"


def test_empty_text_returns_empty_list():
    """Empty or whitespace-only input returns []."""
    chunker = TextChunker()
    assert chunker.chunk_text("") == []
    assert chunker.chunk_text("   \n\n  ") == []


def test_text_shorter_than_chunk_size_single_chunk():
    """Text shorter than chunk_size returns exactly one chunk."""
    chunker = TextChunker(chunk_size=500, chunk_overlap=0)
    text = "Hello world. This is a short document."
    chunks = chunker.chunk_text(text)

    assert len(chunks) == 1
    assert chunks[0].text.strip() == text.strip()


# ── Overlap ───────────────────────────────────────────────────────────────────


def test_overlap_not_negative():
    """No chunk should have a negative start_char."""
    chunker = TextChunker(chunk_size=30, chunk_overlap=10)
    text = "Word " * 200
    chunks = chunker.chunk_text(text)

    for c in chunks:
        assert c.start_char >= 0, f"Negative start_char: {c.start_char}"


# ── Page metadata ─────────────────────────────────────────────────────────────


def test_chunk_with_pages_assigns_page_numbers():
    """chunk_with_pages assigns page_start and page_end to each chunk."""
    chunker = TextChunker(chunk_size=30, chunk_overlap=3)
    pages = [
        {"page_num": 1, "text": "Page one content. " * 20},
        {"page_num": 2, "text": "Page two content. " * 20},
        {"page_num": 3, "text": "Page three content. " * 20},
    ]
    chunks = chunker.chunk_with_pages(pages, doc_id="doc.pdf", kb_name="kb")

    assert len(chunks) > 0
    for c in chunks:
        assert c.page_start is not None
        assert c.page_end is not None
        assert c.page_start >= 1
        assert c.page_end >= c.page_start


def test_chunk_with_pages_empty_input():
    """chunk_with_pages returns [] for empty pages list."""
    chunker = TextChunker()
    assert chunker.chunk_with_pages([]) == []


# ── to_dict ───────────────────────────────────────────────────────────────────


def test_text_chunk_to_dict():
    """TextChunk.to_dict() returns all fields as a plain dict."""
    chunk = TextChunk(
        text="hello",
        chunk_index=0,
        start_char=0,
        end_char=5,
        page_start=1,
        page_end=1,
        doc_id="d.pdf",
        kb_name="kb",
    )
    d = chunk.to_dict()
    assert d["text"] == "hello"
    assert d["chunk_index"] == 0
    assert d["page_start"] == 1
    assert d["doc_id"] == "d.pdf"
