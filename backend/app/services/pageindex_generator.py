"""PageIndex tree generator — 3-pass hierarchical document indexing.

Pass 1: TOC Extraction -- LLM identifies section headings
Pass 2: Content Matching -- assign page ranges to each heading
Pass 3: Node Summarization -- LLM generates per-node summaries
"""

import asyncio
import json
import logging
import re

logger = logging.getLogger(__name__)

# Prompt templates
HEADING_EXTRACTION_PROMPT = (
    "You are a document structure analysis expert. Analyze the following document text "
    "and extract all section headings and their hierarchy as a JSON array. Each entry "
    "should have exactly two fields: 'title' (string) and 'depth' (integer, 1 for top-level, "
    "2 for subsection, etc.). Do not include page numbers or other metadata. "
    "Only output valid JSON, no markdown or explanation.\n\n"
    'Return format: [{"title": "Introduction", "depth": 1}, '
    '{"title": "Background", "depth": 2}]'
)

SUMMARY_PROMPT = (
    "Summarize the following document section in 2-3 sentences. Focus on the key points, "
    "main arguments, and conclusions. Do not include specific page references. "
    "Only output the summary text, no markdown or labels.\n\n"
)

# Tunable constants
TOC_MAX_PAGES = 20  # First N pages used for heading extraction
HEADING_EXTRACT_MAX_CHARS = 60000  # Max text sent to LLM for heading extraction
HEADING_EXTRACT_MAX_TOKENS = 4096  # Max LLM output tokens for headings
REGEX_HEADING_MAX_LEN = 120  # Skip lines longer than this in regex fallback
FALLBACK_MAX_HEADINGS = 30  # Cap on regex-detected headings
HEADING_SEARCH_PREFIX = 30  # Characters for partial heading match
CHARS_PER_TOKEN = 4  # Rough chars-to-tokens multiplier
SUMMARY_MAX_TOKENS = 512  # Max LLM output tokens per summary
SUMMARIZE_CONCURRENCY = 3  # Max concurrent summarization LLM calls


class PageIndexTreeGenerator:
    """Generate hierarchical PageIndex tree from document content."""

    def __init__(self, lm_client):
        self.lm_client = lm_client
        self._summarize_sem = asyncio.Semaphore(SUMMARIZE_CONCURRENCY)

    async def build_tree(
        self,
        doc_content: dict,
        model_id: str,
        doc_id: str,
    ) -> dict | None:
        """Build the full PageIndexTree from parsed document content."""
        pages = doc_content.get("pages", [])
        if not pages:
            logger.warning("No pages found in doc_content")
            return self._empty_tree(doc_id, "Unknown")

        total_pages = len(pages)
        toc_nodes = await self._extract_headings(pages, model_id)
        if not toc_nodes:
            logger.info("No headings identified -- creating single-node tree")
            toc_nodes = [{"title": "Document", "depth": 1}]

        nodes_with_ranges = self._assign_page_ranges(pages, toc_nodes)

        # For single-node fallback ("Document"), use full page range
        if len(nodes_with_ranges) == 1 and nodes_with_ranges[0]["title"] == "Document":
            total_pg = len(pages)
            nodes_with_ranges[0]["page_start"] = 1
            nodes_with_ranges[0]["page_end"] = total_pg
            nodes_with_ranges[0]["start_index"] = 0
            nodes_with_ranges[0]["end_index"] = sum(len(p.get("text", "")) for p in pages)

        # Concurrent summarization for performance
        results = await asyncio.gather(
            *(self._summarize_node(node, pages, model_id) for node in nodes_with_ranges),
        )
        for node, summary in zip(nodes_with_ranges, results, strict=False):
            node["summary"] = summary

        return self._structure_tree(nodes_with_ranges, doc_id, total_pages, doc_id)

    # -- Pass 1: Heading Extraction --

    def _extract_toc_candidates(self, pages: list[dict]) -> str:
        candidate_pages = pages[:TOC_MAX_PAGES]
        parts = []
        for page_info in candidate_pages:
            text = page_info.get("text", "").strip()
            if text:
                parts.append(f"[Page {page_info.get('page_num', '?')}]\n{text}")
        return "\n---\n".join(parts)

    async def _extract_headings(self, pages: list[dict], model_id: str) -> list[dict]:
        toc_text = self._extract_toc_candidates(pages)
        if not toc_text.strip():
            return []

        if len(toc_text) > HEADING_EXTRACT_MAX_CHARS:
            toc_text = toc_text[:HEADING_EXTRACT_MAX_CHARS] + "\n...[truncated]"

        try:
            result = await self.lm_client.stream_chat(
                messages=[
                    {"role": "system", "content": HEADING_EXTRACTION_PROMPT},
                    {"role": "user", "content": toc_text},
                ],
                model=model_id,
                max_tokens=HEADING_EXTRACT_MAX_TOKENS,
                temperature=0.1,
            )
            if result is None:
                logger.warning("LLM returned None for heading extraction")
                return self._regex_heading_fallback(toc_text)
            return self._parse_heading_json(result)
        except Exception as e:
            logger.error(f"Heading extraction failed: {e}")
            return self._regex_heading_fallback(toc_text)

    def _parse_heading_json(self, raw_text: str) -> list[dict]:
        text = raw_text.strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:-1])
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1:
            logger.warning(f"No JSON array found: {text[:200]}")
            return []
        json_str = text[start : end + 1]
        try:
            headings = json.loads(json_str)
            if not isinstance(headings, list):
                return []
            result = []
            for h in headings:
                if isinstance(h, dict) and "title" in h:
                    result.append(
                        {
                            "title": str(h["title"]).strip(),
                            "depth": int(h.get("depth", 1)),
                        }
                    )
            return result
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}")
            return []

    def _regex_heading_fallback(self, text: str) -> list[dict]:
        headings = []
        seen = set()
        patterns = [
            r"^(?:\d+\.\d*\s+|\d+\.\s+|\d+\s*[-\u2013\u2014]\s+)([A-Z].+?)$",
            r"^(?:Chapter\s+\d+\s*)(.*)$",
        ]
        for line in text.split("\n"):
            line = line.strip()
            if not line or len(line) > REGEX_HEADING_MAX_LEN:
                continue
            if line.count(".") > 3 and not re.match(r"\d+\.", line):
                continue
            for pattern in patterns:
                m = re.match(pattern, line, re.IGNORECASE)
                if m:
                    title = m.group(1) or m.group(0)
                    if title not in seen:
                        heading = {"title": title, "depth": 1}
                        if re.match(r"\d+\.\d+", m.group(0)):
                            heading["depth"] = 2
                        headings.append(heading)
                        seen.add(title)
                    break
        return headings[:FALLBACK_MAX_HEADINGS]

    # -- Pass 2: Content Matching --

    def _assign_page_ranges(self, pages: list[dict], toc_nodes: list[dict]) -> list[dict]:
        full_text = "\n".join(p.get("text", "") for p in pages)

        page_offsets = []
        position = 0
        for page_info in pages:
            text = page_info.get("text", "")
            page_offsets.append(
                {
                    "page_num": page_info.get("page_num", 0),
                    "start": position,
                    "end": position + len(text),
                }
            )
            position += len(text) + 1

        enriched = []
        for node in toc_nodes:
            start_index = self._find_heading_position(node["title"], full_text)
            page_start = self._char_to_page(start_index, page_offsets)
            enriched.append(
                {
                    "title": node["title"],
                    "depth": node["depth"],
                    "start_index": start_index,
                    "page_start": page_start,
                    "page_end": page_start,
                }
            )

        if not enriched:
            return enriched

        for i, node in enumerate(enriched):
            if i + 1 < len(enriched):
                node["end_index"] = enriched[i + 1]["start_index"]
                node["page_end"] = enriched[i + 1]["page_start"]
            else:
                node["end_index"] = len(full_text)
                node["page_end"] = page_offsets[-1]["page_num"] if page_offsets else 1

            if node["page_start"] > node["page_end"]:
                node["page_end"] = node["page_start"]

        return enriched

    def _find_heading_position(self, heading: str, full_text: str) -> int:
        pos = full_text.find(heading)
        if pos != -1:
            return pos
        pos = full_text.lower().find(heading.lower())
        if pos != -1:
            return pos
        partial = heading[:HEADING_SEARCH_PREFIX].strip()
        if partial:
            pos = full_text.find(partial)
            if pos != -1:
                return pos
        logger.warning(f"Heading not found: '{heading}'")
        return 0

    def _char_to_page(self, char_pos: int, page_offsets: list[dict]) -> int:
        for offset in page_offsets:
            if offset["start"] <= char_pos < offset["end"]:
                return offset["page_num"]
        return page_offsets[-1]["page_num"] if page_offsets else 1

    # -- Pass 3: Node Summarization --

    async def _summarize_node(
        self,
        node: dict,
        pages: list[dict],
        model_id: str,
    ) -> str:
        """Summarize a single node's content using LLM, with concurrency control."""
        from app.config import get_settings

        settings = get_settings()
        max_tokens = settings.pageindex_max_tokens_per_node

        page_start = node.get("page_start", 1)
        page_end = node.get("page_end", 1)

        node_pages = [p for p in pages if page_start <= p.get("page_num", 1) <= page_end]
        if not node_pages:
            return f"Section: {node['title']}"

        node_text = "\n".join(p.get("text", "") for p in node_pages)
        if len(node_text) > max_tokens * CHARS_PER_TOKEN:
            node_text = node_text[: max_tokens * CHARS_PER_TOKEN] + "\n...[truncated]"

        try:
            async with self._summarize_sem:
                result = await self.lm_client.stream_chat(
                    messages=[
                        {"role": "system", "content": SUMMARY_PROMPT},
                        {"role": "user", "content": node_text},
                    ],
                    model=model_id,
                    max_tokens=SUMMARY_MAX_TOKENS,
                    temperature=0.3,
                )
            if result:
                return result.strip()
        except Exception as e:
            logger.error(f"Summarization failed for '{node['title']}': {e}")

        return f"Section covering pages {page_start}-{page_end}."

    # -- Tree Structure --

    def _structure_tree(
        self,
        nodes: list[dict],
        doc_id: str,
        total_pages: int,
        doc_title: str,
    ) -> dict:
        root = {
            "node_id": "root",
            "title": doc_title,
            "summary": f"Document with {total_pages} pages",
            "start_index": 0,
            "end_index": 0,
            "page_start": 1,
            "page_end": total_pages,
            "children": [],
        }

        if not nodes:
            return {"doc_id": doc_id, "title": doc_title, "total_pages": total_pages, "root": root}

        stack = []
        for i, node in enumerate(nodes):
            depth = node.get("depth", 1)
            node_id = f"node_{depth}_{i}"

            child_node = {
                "node_id": node_id,
                "title": node["title"],
                "summary": node.get("summary", f"Section: {node['title']}"),
                "start_index": node.get("start_index", 0),
                "end_index": node.get("end_index", 0),
                "page_start": node.get("page_start", 1),
                "page_end": node.get("page_end", 1),
                "children": [],
            }

            while stack and stack[-1][0] >= depth:
                stack.pop()

            if stack:
                stack[-1][1]["children"].append(child_node)
            else:
                root["children"].append(child_node)

            stack.append((depth, child_node))

        if nodes:
            root["end_index"] = nodes[-1].get("end_index", 0)
            root["page_end"] = nodes[-1].get("page_end", 1)
        root["start_index"] = nodes[0].get("start_index", 0)
        root["page_start"] = nodes[0].get("page_start", 1)

        return {
            "doc_id": doc_id,
            "title": doc_title,
            "total_pages": total_pages,
            "root": root,
        }

    def _empty_tree(self, doc_id: str, title: str = "Unknown") -> dict:
        return {
            "doc_id": doc_id,
            "title": title,
            "total_pages": 0,
            "root": {
                "node_id": "root",
                "title": title,
                "summary": "No content to index",
                "start_index": 0,
                "end_index": 0,
                "page_start": 1,
                "page_end": 1,
                "children": [],
            },
        }
