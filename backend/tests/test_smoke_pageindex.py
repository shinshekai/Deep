"""Smoke test: PDF extraction and PageIndex tree generation."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest


def _generate_synthetic_pdf(path: Path) -> None:
    """Write a minimal but valid 2-page PDF to ``path`` for the smoke test.

    Building a real PDF byte-by-byte (no library dependency) keeps the
    test self-contained. The structure follows the PDF 1.4 spec
    well enough that PyMuPDF / pdfplumber can parse it.
    """
    content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]
   /Contents 5 0 R /Resources << /Font << /F1 6 0 R >> >> >>
endobj
4 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]
   /Contents 7 0 R /Resources << /Font << /F1 6 0 R >> >> >>
endobj
5 0 obj
<< /Length 64 >>
stream
BT /F1 12 Tf 50 750 Td (Page 1: Introduction) Tj ET
BT /F1 12 Tf 50 700 Td (Sample content for smoke test.) Tj ET
endstream
endobj
6 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
7 0 obj
<< /Length 54 >>
stream
BT /F1 12 Tf 50 750 Td (Page 2: Methods) Tj ET
BT /F1 12 Tf 50 700 Td (Smoke test data.) Tj ET
endstream
endobj
xref
0 8
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000248 00000 n
0000000381 00000 n
0000000497 00000 n
0000000564 00000 n
trailer
<< /Size 8 /Root 1 0 R >>
startxref
660
%%EOF
"""
    path.write_bytes(content)


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    pdf = tmp_path / "test.pdf"
    _generate_synthetic_pdf(pdf)
    return pdf


def test_pageindex_from_sample_pdf(sample_pdf: Path):
    """Verify tree generation produces valid output for a real PDF."""
    from app.services.document_processor import extract_text
    from app.services.pageindex_generator import PageIndexTreeGenerator

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
