"""TreeSearch — LLM reasoning-based retrieval over PageIndex trees.

Implements REQ-RET-01: Backend constructs a prompt with query + tree
structure (omitting raw text), LLM reasons over hierarchical summaries.

REQ-RET-02: Backend parses LLM response to extract node_ids, maps to
page ranges, extracts raw text from source PDF.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from app.services.text_extractor import TextExtractor

logger = logging.getLogger(__name__)

TREE_SCORE_PROMPT = """You are a document retrieval assistant. You will be given:
1. A user query
2. A page index tree from a document showing the hierarchical structure

Your task is to identify which sections (nodes) of the document tree are most
relevant to the query. Return ONLY a JSON array of relevant nodes. Do not
include markdown code fence markers.

For each relevant node, provide:
- "node_id": the exact node_id
- "score": relevance from 0.0 to 1.0
- "reason": brief explanation (1 sentence)

Return nodes in order of relevance (most relevant first).
Only include nodes with actual relevance (score > 0.1).

## PageIndex Tree
{tree_json}

## Query
{query}

## Response (JSON array only)"""

TREE_SCORE_FEW_SHOT_SYSTEM = """You are a document retrieval reasoning system.
You analyze the document hierarchy to find relevant sections.
Consider: title relevance, summary content, document structure.
Return scores as floats 0.0-1.0."""


class TreeSearch:
    """LLM-based tree search over PageIndex hierarchical indexes."""

    def __init__(self, lm_client):
        self.lm_client = lm_client
        self.text_extractor = TextExtractor(
            Path(__file__).resolve().parent.parent.parent / "data" / "knowledge_bases"
        )

    async def search(
        self,
        query: str,
        kb_name: str,
        doc_id: Optional[str] = None,
        tree: Optional[dict] = None,
        top_k: int = 5,
        min_score: float = 0.3,
    ) -> list[dict]:
        """Search a PageIndex tree using LLM reasoning.

        Args:
            query: User query string
            kb_name: Knowledge base name
            doc_id: Specific document ID to search (optional)
            tree: Pre-loaded tree dict (optional)
            top_k: Maximum results to return
            min_score: Minimum relevance threshold

        Returns:
            List of scored result dicts with doc_id, page, section,
            summary, relevance_score, node_id, and content (raw text).
        """
        results = []

        if tree:
            scored = await self._score_tree(tree.get("doc_id", ""), tree, query)
            results.extend(scored)
        else:
            # Search across all docs in KB
            pi_dir = Path(__file__).resolve().parent.parent.parent / "data" / "knowledge_bases" / kb_name / "pageindex"
            if pi_dir.exists():
                for tree_file in sorted(pi_dir.glob("*.json")):
                    if doc_id and tree_file.stem != doc_id:
                        continue
                    try:
                        loaded = json.loads(tree_file.read_text())
                    except (json.JSONDecodeError, OSError):
                        continue
                    scored = await self._score_tree(tree_file.stem, loaded, query)
                    results.extend(scored)

        # Filter by min_score, sort, take top_k
        results = [r for r in results if r.get("relevance_score", 0) >= min_score]
        results.sort(key=lambda r: r.get("relevance_score", 0), reverse=True)
        results = results[:top_k]

        # Extract raw text for top results (REQ-RET-02)
        for result in results:
            if tree and result.get("node_id"):
                node = self._find_node_by_id(tree.get("root", {}), result["node_id"])
                if node:
                    raw_text = await self.text_extractor.extract_for_node(
                        kb_name, result.get("doc_id", ""), tree, node
                    )
                    result["content"] = raw_text or ""

        return results

    async def _score_tree(
        self, doc_id: str, tree: dict, query: str
    ) -> list[dict]:
        """Score nodes in a PageIndex tree using LLM reasoning."""
        tree_json = self._serialize_tree_compact(tree.get("root", {}))
        if not tree_json:
            return []

        # Check LM health
        health_ok = await self.lm_client.check_health()
        if not health_ok:
            logger.info("LM Studio unavailable — using keyword fallback")
            return self._keyword_score(doc_id, tree, query)

        # LLM scoring
        prompt = TREE_SCORE_PROMPT.format(
            tree_json=tree_json, query=query
        )
        messages = [
            {"role": "system", "content": TREE_SCORE_FEW_SHOT_SYSTEM},
            {"role": "user", "content": prompt},
        ]

        try:
            llm_response = await self.lm_client.stream_chat(messages=messages)
            parsed = self._parse_llm_results(llm_response or "")
            if parsed is not None:
                return self._build_results(doc_id, tree, parsed)
        except Exception as e:
            logger.warning(f"Tree search LLM call failed: {e}")

        # Fallback
        logger.info("LLM parsing failed — using keyword fallback")
        return self._keyword_score(doc_id, tree, query)

    def _serialize_tree_compact(self, node: dict, depth: int = 0) -> str:
        """Serialize tree to flat text representation (title + summary + node_id)."""
        if not node:
            return ""
        lines = []
        indent = "  " * depth
        title = node.get("title", "")
        nid = node.get("node_id", "")
        summary = node.get("summary", "")
        page_start = node.get("page_start", 0)
        page_end = node.get("page_end", 0)

        lines.append(
            f"{indent}- [{nid}] {title} (pages {page_start}-{page_end}): {summary}"
        )
        for child in node.get("children", []):
            child_text = self._serialize_tree_compact(child, depth + 1)
            if child_text:
                lines.append(child_text)
        return "\n".join(lines)

    def _parse_llm_results(self, response: str) -> Optional[list[dict]]:
        """Parse LLM JSON response into scored node list."""
        text = response.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines)

        try:
            data = json.loads(text)
            if not isinstance(data, list):
                return None
            results = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                if "node_id" not in item:
                    continue
                results.append({
                    "node_id": item["node_id"],
                    "score": float(item.get("score", 0)),
                    "reason": item.get("reason", ""),
                })
            return results
        except (json.JSONDecodeError, ValueError):
            return None

    def _build_results(
        self, doc_id: str, tree: dict, scored_nodes: list[dict]
    ) -> list[dict]:
        """Map scored node_ids to result dicts using tree metadata."""
        results = []
        for scored in scored_nodes:
            node = self._find_node_by_id(
                tree.get("root", {}), scored["node_id"]
            )
            if node:
                results.append({
                    "doc_id": doc_id,
                    "page": node.get("page_start", 0),
                    "page_end": node.get("page_end", 0),
                    "section": node.get("title", ""),
                    "summary": node.get("summary", ""),
                    "relevance_score": round(scored["score"], 3),
                    "node_id": scored["node_id"],
                    "reasoning": scored.get("reason", ""),
                    "content": "",  # Filled by search() caller
                })
        return results

    def _find_node_by_id(self, node: dict, node_id: str) -> Optional[dict]:
        """Recursively find a node by its node_id."""
        if node.get("node_id") == node_id:
            return node
        for child in node.get("children", []):
            found = self._find_node_by_id(child, node_id)
            if found:
                return found
        return None

    def _keyword_score(
        self, doc_id: str, tree: dict, query: str
    ) -> list[dict]:
        """Fallback keyword scoring when LLM is unavailable."""
        results = []
        query_terms = set(query.lower().split())
        if not query_terms:
            return results

        def walk(node: dict):
            title = node.get("title", "").lower()
            summary = node.get("summary", "").lower()
            score = sum(1 for t in query_terms if t in title) * 3
            score += sum(1 for t in query_terms if t in summary)
            if score > 0:
                max_possible = len(query_terms) * 3
                relevance = score / max_possible
                results.append({
                    "doc_id": doc_id,
                    "page": node.get("page_start", 0),
                    "page_end": node.get("page_end", 0),
                    "section": node.get("title", ""),
                    "summary": node.get("summary", ""),
                    "relevance_score": round(relevance, 3),
                    "node_id": node.get("node_id", ""),
                    "reasoning": "",
                    "content": "",
                })
            for child in node.get("children", []):
                walk(child)

        walk(tree.get("root", {}))
        return results
