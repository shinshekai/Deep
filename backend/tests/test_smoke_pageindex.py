"""Smoke test: PDF extraction and PageIndex tree generation."""

import pytest
from pathlib import Path


def test_pageindex_from_sample_pdf():
    """If a test PDF exists, verify tree generation produces valid output."""
    sample_pdf = Path(__file__).parent.parent / "data" / "test.pdf"
    if not sample_pdf.exists():
        pytest.skip("No test PDF available")

    import asyncio
    from app.services.document_processor import extract_text
    from app.services.pageindex_generator import PageIndexTreeGenerator
    from unittest.mock import AsyncMock

    async def run_test():
        doc_content = await extract_text(sample_pdf)
        assert doc_content is not None
        assert "pages" in doc_content
        assert len(doc_content["pages"]) > 0

        mock_client = AsyncMock()
        mock_client.stream_chat.return_value = (
            '[{"title": "Introduction", "depth": 1}, '
            '{"title": "Methods", "depth": 1}]'
        )
        gen = PageIndexTreeGenerator(mock_client)
        tree = await gen.build_tree(doc_content, "Qwen3-4B-Q4_K_M", "test.pdf")
        assert tree is not None
        assert "root" in tree
        assert "children" in tree["root"]

    asyncio.run(run_test())
