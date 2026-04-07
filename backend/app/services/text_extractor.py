"""TextExtractor — maps PageIndex node_ids to raw PDF text.

Implements REQ-RET-02: Extract node_ids → map to page ranges →
extract raw document text from source PDF files.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

UPLOAD_BASE = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "data"
    / "knowledge_bases"
    / "uploads"
)


class TextExtractor:
    """Extract raw text from PDF files based on page ranges."""

    def __init__(self, kb_base: Path):
        self.kb_base = kb_base

    def extract_for_pages(
        self, pdf_path: str, page_start: int = 0, page_end: int = 0
    ) -> Optional[str]:
        """Extract text from a PDF for the given page range (0-indexed).

        Returns concatenated text for pages [page_start, page_end].
        Returns None if file cannot be opened.
        """
        import fitz

        # Handle same-page case
        if page_end == 0:
            page_end = page_start

        try:
            doc = fitz.open(pdf_path)
            pages_to_read = range(page_start, page_end + 1)
            texts = []
            for page_idx in pages_to_read:
                if 0 <= page_idx < doc.page_count:
                    texts.append(doc[page_idx].get_text("text"))
            doc.close()
            return "\n\n".join(texts) if texts else ""
        except Exception as e:
            logger.warning(f"Cannot extract text from {pdf_path}: {e}")
            return None

    def extract_for_node(
        self, kb_name: str, doc_id: str, tree: dict, node: dict
    ) -> Optional[str]:
        """Extract raw text for a specific tree node.

        Finds the source PDF from uploads, maps node page_start/page_end
        to actual document text.
        """
        page_start = node.get("page_start", 0)
        page_end = node.get("page_end", 0)

        # Find source PDF file
        upload_path = UPLOAD_BASE / kb_name / doc_id
        if not upload_path.exists():
            # Try with common extensions
            for ext in [".pdf", ".txt", ".md"]:
                candidate = UPLOAD_BASE / kb_name / (doc_id + ext)
                if candidate.exists():
                    upload_path = candidate
                    break

        if not upload_path.exists():
            logger.warning(f"Source document not found for {kb_name}/{doc_id}")
            return None

        return self.extract_for_pages(str(upload_path), page_start, page_end)
