"""Document processor — extract text from PDF/TXT/MD files."""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


async def extract_text_from_pdf(file_path: Path) -> Optional[str]:
    """Extract text and page boundaries from PDF using PyMuPDF."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        pages = []
        for i in range(len(doc)):
            page = doc[i]
            pages.append({
                "page_num": i + 1,
                "text": page.get_text(),
                "width": page.rect.width,
                "height": page.rect.height,
            })
        doc.close()
        return pages
    except ImportError:
        logger.warning("PyMuPDF not installed — cannot process PDFs")
        return None
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        return None


async def extract_text(file_path: Path) -> Optional[dict]:
    """Extract text from any supported format. Returns {type, content, pages}."""
    ext = file_path.suffix.lower()
    if ext == ".pdf":
        pages = await extract_text_from_pdf(file_path)
        if pages is None:
            return None
        full_text = "\n".join(p["text"] for p in pages)
        return {
            "type": "pdf",
            "content": full_text,
            "pages": pages,
            "page_count": len(pages),
        }
    elif ext in (".txt", ".md"):
        text = file_path.read_text(encoding="utf-8")
        return {
            "type": ext.lstrip("."),
            "content": text,
            "pages": [{"page_num": 1, "text": text}],
            "page_count": 1,
        }
    else:
        logger.error(f"Unsupported file type: {ext}")
        return None


def recursive_chunk(text: str, chunk_size: int = 512, overlap: int = 64) -> list[dict]:
    """Split text into chunks with overlap."""
    tokens = text.split()
    chunks = []
    i = 0
    chunk_idx = 0
    while i < len(tokens):
        chunk_tokens = tokens[i:i + chunk_size]
        if len(chunk_tokens) < chunk_size // 2 and chunk_idx > 0:
            break
        chunks.append({
            "chunk_id": chunk_idx,
            "text": " ".join(chunk_tokens),
            "token_count": len(chunk_tokens),
            "start_token": i,
            "end_token": i + len(chunk_tokens),
        })
        i += chunk_size - overlap
        chunk_idx += 1
    return chunks
