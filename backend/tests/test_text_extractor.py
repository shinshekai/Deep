"""Text extractor service tests."""

import pytest
import io
from pathlib import Path
from unittest.mock import patch, MagicMock
import fitz

TEST_KB_BASE = Path("data/knowledge_bases")


class FakeDoc:
    """Fake PDF document that returns text for page lookups."""
    def __init__(self, page_texts: dict[int, str]):
        self._page_texts = page_texts
        self.page_count = max(page_texts.keys()) + 1 if page_texts else 0

    def __getitem__(self, idx: int):
        text = self._page_texts.get(idx, "")
        page_mock = MagicMock()
        page_mock.get_text.return_value = text
        return page_mock

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


@patch("fitz.open")
def test_extract_for_pages_returns_text(mock_fitz_open):
    from app.services.text_extractor import TextExtractor

    fake_doc = FakeDoc({
        0: "Title page",
        1: "Introduction text here",
        2: "Chapter one details",
        3: "More chapter content",
        4: "Conclusion",
    })
    mock_fitz_open.return_value = fake_doc

    extractor = TextExtractor(TEST_KB_BASE)
    result = extractor.extract_for_pages(
        "/fake/path.pdf", page_start=1, page_end=3
    )
    assert "Introduction text here" in result
    assert "Chapter one details" in result
    assert "More chapter content" in result
    fake_doc.close()


@patch("fitz.open")
def test_extract_for_pages_handles_missing_file(mock_fitz_open):
    from app.services.text_extractor import TextExtractor

    mock_fitz_open.side_effect = FileNotFoundError("not found")
    extractor = TextExtractor(TEST_KB_BASE)
    result = extractor.extract_for_pages("/nonexistent.pdf", 0, 2)
    assert result is None


@patch("fitz.open")
def test_extract_for_pages_handles_out_of_range(mock_fitz_open):
    from app.services.text_extractor import TextExtractor

    fake_doc = FakeDoc({0: "Only page"})
    mock_fitz_open.return_value = fake_doc

    extractor = TextExtractor(TEST_KB_BASE)
    result = extractor.extract_for_pages(
        "/fake/path.pdf", page_start=0, page_end=10
    )
    assert "Only page" in result
    fake_doc.close()


def test_extract_for_node_returns_none_when_doc_missing():
    from app.services.text_extractor import TextExtractor

    extractor = TextExtractor(TEST_KB_BASE)
    node = {"page_start": 0, "page_end": 2}
    result = extractor.extract_for_node("unknown_kb", "nonexistent", {}, node)
    assert result is None
