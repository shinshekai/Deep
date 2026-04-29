"""TextChunker — recursive character-based text splitting with overlap.

Splits document text into overlapping chunks suitable for embedding.
Respects natural document boundaries: paragraph → sentence → word.
Preserves page-level metadata when page boundaries are supplied.

Default configuration (matches PRD):
  chunk_size    = 512 tokens  (~2048 characters at ~4 chars/token)
  chunk_overlap = 64 tokens   (~256 characters)
  min_chunk_size = 50 characters
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field

logger = logging.getLogger(__name__)

# Approximate characters per token for typical English text
_CHARS_PER_TOKEN = 4


@dataclass
class TextChunk:
    """A single chunk of text with positional and citation metadata."""

    text: str
    chunk_index: int
    start_char: int
    end_char: int
    page_start: int | None = None
    page_end: int | None = None
    doc_id: str = ""
    kb_name: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class TextChunker:
    """Recursive character chunker with configurable size and overlap.

    Args:
        chunk_size:    Target chunk size in tokens.
        chunk_overlap: Overlap in tokens between consecutive chunks.
        min_chunk_size: Minimum chunk size in characters; smaller chunks
                        are merged with the next chunk.
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        min_chunk_size: int = 50,
    ):
        self.chunk_size_chars = chunk_size * _CHARS_PER_TOKEN
        self.overlap_chars = chunk_overlap * _CHARS_PER_TOKEN
        self.min_chunk_size = min_chunk_size

    # ── Public API ──────────────────────────────────────────────────────────

    def chunk_text(
        self,
        text: str,
        doc_id: str = "",
        kb_name: str = "",
    ) -> list[TextChunk]:
        """Chunk plain text into overlapping segments.

        Returns list of TextChunk. Positions refer to character offsets
        in the original `text` string.
        """
        if not text or not text.strip():
            return []

        raw_chunks = self._split(text)
        return self._to_text_chunks(raw_chunks, text, doc_id, kb_name)

    def chunk_with_pages(
        self,
        pages: list[dict],
        doc_id: str = "",
        kb_name: str = "",
    ) -> list[TextChunk]:
        """Chunk page-structured text, preserving page number metadata.

        Args:
            pages: list of {"page_num": int, "text": str}

        Returns TextChunk list where page_start/page_end are populated.
        """
        if not pages:
            return []

        # Build a single concatenated text with page boundary markers
        # so we can map char offsets back to page numbers
        page_map: list[tuple[int, int, int]] = []  # (start_char, end_char, page_num)
        combined_parts: list[str] = []
        pos = 0

        for page in pages:
            page_text = page.get("text", "")
            page_num = page.get("page_num", 0)
            if not page_text:
                continue
            start = pos
            combined_parts.append(page_text)
            pos += len(page_text)
            # Separator between pages
            combined_parts.append("\n\n")
            pos += 2
            page_map.append((start, pos, page_num))

        full_text = "".join(combined_parts)
        chunks = self.chunk_text(full_text, doc_id, kb_name)

        # Annotate each chunk with page numbers
        for chunk in chunks:
            chunk.page_start = self._page_at(chunk.start_char, page_map)
            chunk.page_end = self._page_at(chunk.end_char, page_map)

        return chunks

    # ── Internal splitting ───────────────────────────────────────────────────

    def _split(self, text: str) -> list[str]:
        """Recursively split text into raw string segments."""
        if len(text) <= self.chunk_size_chars:
            return [text] if text.strip() else []

        # Level 1: split on paragraph boundaries (\n\n)
        segments = re.split(r"\n\n+", text)
        if len(segments) > 1:
            return self._merge_segments(segments)

        # Level 2: split on sentence boundaries
        segments = re.split(r"(?<=[.!?])\s+", text)
        if len(segments) > 1:
            return self._merge_segments(segments)

        # Level 3: split on word boundaries (hard fallback)
        words = text.split(" ")
        if len(words) > 1:
            segments = []
            current: list[str] = []
            current_len = 0
            for word in words:
                word_len = len(word) + 1
                if current_len + word_len > self.chunk_size_chars and current:
                    segments.append(" ".join(current))
                    current = []
                    current_len = 0
                current.append(word)
                current_len += word_len
            if current:
                segments.append(" ".join(current))
            return self._merge_segments(segments)

        # Level 4: hard character slice (no whitespace at all — pathological)
        result: list[str] = []
        for i in range(0, len(text), self.chunk_size_chars):
            result.append(text[i : i + self.chunk_size_chars])
        return result

    def _merge_segments(self, segments: list[str]) -> list[str]:
        """Merge small segments and enforce chunk_size_chars limit."""
        merged: list[str] = []
        current_parts: list[str] = []
        current_len = 0

        for seg in segments:
            seg = seg.strip()
            if not seg:
                continue
            seg_len = len(seg)

            if current_len + seg_len + 2 > self.chunk_size_chars and current_parts:
                chunk = "\n\n".join(current_parts)
                # Recursively split if still too large
                if len(chunk) > self.chunk_size_chars:
                    merged.extend(self._split(chunk))
                else:
                    merged.append(chunk)
                current_parts = []
                current_len = 0

            current_parts.append(seg)
            current_len += seg_len + 2

        if current_parts:
            chunk = "\n\n".join(current_parts)
            if len(chunk) > self.chunk_size_chars:
                merged.extend(self._split(chunk))
            else:
                merged.append(chunk)

        # Filter out tiny chunks (merge into previous)
        final: list[str] = []
        for chunk in merged:
            if not chunk.strip():
                continue
            if len(chunk) < self.min_chunk_size and final:
                final[-1] = final[-1] + "\n\n" + chunk
            else:
                final.append(chunk)

        return final

    def _to_text_chunks(
        self,
        raw_chunks: list[str],
        original_text: str,
        doc_id: str,
        kb_name: str,
    ) -> list[TextChunk]:
        """Convert raw string segments into TextChunk objects with positions and overlap."""
        result: list[TextChunk] = []
        search_from = 0

        for idx, raw in enumerate(raw_chunks):
            if not raw.strip():
                continue

            # Find start position in original text
            start = original_text.find(raw[:50], search_from)
            if start == -1:
                start = search_from

            # Add overlap from previous chunk's tail
            if idx > 0 and self.overlap_chars > 0:
                overlap_start = max(start - self.overlap_chars, 0)
                prefix = original_text[overlap_start:start].strip()
                if prefix:
                    raw = prefix + " " + raw
                    start = overlap_start

            end = start + len(raw)
            search_from = end - self.overlap_chars

            result.append(
                TextChunk(
                    text=raw.strip(),
                    chunk_index=idx,
                    start_char=start,
                    end_char=end,
                    doc_id=doc_id,
                    kb_name=kb_name,
                )
            )

        return result

    @staticmethod
    def _page_at(char_pos: int, page_map: list[tuple[int, int, int]]) -> int | None:
        """Return the page number that contains `char_pos`."""
        for start, end, page_num in page_map:
            if start <= char_pos < end:
                return page_num
        if page_map:
            return page_map[-1][2]  # default to last page
        return None
