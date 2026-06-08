"""TextExtractor — maps PageIndex node_ids to raw PDF text.

Implements REQ-RET-02: Extract node_ids → map to page ranges →
extract raw document text from source PDF files.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

UPLOAD_BASE = Path(__file__).resolve().parent.parent.parent / "data" / "knowledge_bases" / "uploads"


class TextExtractor:
    """Extract raw text from PDF files based on page ranges."""

    def __init__(self, kb_base: Path):
        self.kb_base = kb_base

    async def extract_for_pages(
        self, file_path: str, page_start: int = 0, page_end: int = 0
    ) -> str | None:
        """Extract text from a file for the given page range (0-indexed).

        Returns concatenated text for pages [page_start, page_end].
        Returns None if file cannot be opened.
        """
        import fitz

        # Handle same-page case
        if page_end == 0:
            page_end = page_start

        try:
            ext = Path(file_path).suffix.lower()
            if ext in (
                ".txt",
                ".md",
                ".py",
                ".js",
                ".ts",
                ".cpp",
                ".c",
                ".h",
                ".java",
                ".json",
                ".yaml",
                ".yml",
                ".xml",
            ):
                # For flat files, we just return the whole content
                return Path(file_path).read_text(encoding="utf-8", errors="ignore")
            elif ext in (
                ".xls",
                ".xlsx",
                ".csv",
                ".docx",
                ".jpg",
                ".png",
                ".bmp",
                ".gif",
                ".jpeg",
                ".pptx",
                ".html",
                ".htm",
                ".odt",
                ".rtf",
                ".epub",
                ".msg",
                ".eml",
                ".zip",
            ):
                from app.services.document_processor import extract_text

                result = await extract_text(Path(file_path))
                if result and result.get("content"):
                    return result["content"]
                return ""

            doc = fitz.open(file_path)
            pages_to_read = range(page_start, page_end + 1)
            texts = []
            for page_idx in pages_to_read:
                if 0 <= page_idx < doc.page_count:
                    texts.append(doc[page_idx].get_text("text"))
            doc.close()
            return "\n\n".join(texts) if texts else ""
        except Exception as e:
            logger.warning(f"Cannot extract text from {file_path}: {e}")
            return None

    async def extract_for_node(
        self, kb_name: str, doc_id: str, tree: dict, node: dict
    ) -> str | None:
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
            for ext in [
                ".pdf",
                ".txt",
                ".md",
                ".csv",
                ".xls",
                ".xlsx",
                ".docx",
                ".jpg",
                ".png",
                ".bmp",
                ".gif",
                ".jpeg",
                ".pptx",
                ".html",
                ".htm",
                ".odt",
                ".rtf",
                ".epub",
                ".msg",
                ".eml",
                ".zip",
            ]:
                candidate = UPLOAD_BASE / kb_name / (doc_id + ext)
                if candidate.exists():
                    upload_path = candidate
                    break

        if not upload_path.exists():
            logger.warning(f"Source document not found for {kb_name}/{doc_id}")
            return None

        return await self.extract_for_pages(str(upload_path), page_start, page_end)
