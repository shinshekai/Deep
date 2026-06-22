"""Agentic tree navigation — multi-turn LLM-guided traversal of PageIndex trees.

Replaces single-call tree scoring with iterative exploration:
1. Start at root — ask LLM which top-level branches are relevant
2. Navigate into relevant branches — repeat until reach leaf nodes
3. Collect accumulated context from all visited leaves
"""

import json
import logging
from pathlib import Path

from app.services.text_extractor import TextExtractor

logger = logging.getLogger(__name__)

NAVIGATE_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "navigate_tree",
        "description": "Navigate the document knowledge tree to find relevant information. Use this for multi-hop research that requires exploring multiple sections.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for in the tree"}
            },
            "required": ["query"],
        },
    },
}

MAX_NAV_DEPTH = 5


class AgenticTreeNavigator:
    """Multi-turn LLM-guided traversal of PageIndex trees."""

    def __init__(self, kb_name: str):
        self.kb_name = kb_name
        self._pi_dir = Path("data/knowledge_bases") / kb_name / "pageindex"
        self._text_extractor = TextExtractor(Path("data/knowledge_bases"))

    async def navigate(self, query: str, lm_client, model_id: str) -> str:
        """Navigate the tree agentically and return collected context."""
        trees = self._load_trees()
        if not trees:
            return "No document trees available for this knowledge base."

        collected: list[str] = []
        visited: set[str] = set()

        for tree in trees:
            root = tree.get("root", {})
            doc_id = tree.get("doc_id", "")
            await self._explore_node(root, query, collected, visited, doc_id, depth=0, lm_client=lm_client, model_id=model_id)

        if collected:
            return "Agentic tree navigation results:\n\n" + "\n---\n".join(collected)
        return "Tree navigation found no relevant content."

    async def _explore_node(self, node: dict, query: str, collected: list, visited: set, doc_id: str, depth: int, lm_client, model_id: str) -> None:
        if depth >= MAX_NAV_DEPTH or not node:
            return

        node_id = node.get("id", "")
        if node_id in visited:
            return
        visited.add(node_id)

        children = node.get("nodes", []) or node.get("children", [])
        if not children:
            # Leaf node — extract content
            text = await self._text_extractor.extract_for_node(self.kb_name, doc_id, {"root": node}, node)
            if text:
                collected.append(f"[{node.get('title', 'Untitled')} p.{node.get('page_index', '?')}]\n{text[:800]}")
            return

        # Ask LLM which children are relevant
        relevant = await self._ask_llm_which_children(node, children, query, lm_client, model_id)
        for child in relevant:
            await self._explore_node(child, query, collected, visited, doc_id, depth + 1, lm_client, model_id)

    async def _ask_llm_which_children(self, parent: dict, children: list, query: str, lm_client, model_id: str) -> list[dict]:
        """Ask LLM which child nodes to explore."""
        if len(children) <= 2:
            return children

        summaries = []
        for i, c in enumerate(children):
            summaries.append(f"[{i}] {c.get('title', 'Untitled')}: {c.get('summary', '')[:200]}")

        prompt = f"""Query: {query}

You are navigating a document tree. The current node is '{parent.get('title', 'Untitled')}'.
Below are its child nodes. Select which ones are RELEVANT to the query.

Children:
{chr(10).join(summaries)}

Return ONLY a JSON array of indices: [0, 2] or [] if none are relevant."""
        try:
            result = await lm_client.stream_chat_completion(
                model=model_id,
                messages=[
                    {"role": "system", "content": "You are a document tree navigator. Return only JSON arrays of child indices."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=200,
            )
            content = result.get("content", "[]")
            start = content.find("[")
            end = content.rfind("]")
            if start >= 0 and end > start:
                indices = json.loads(content[start:end+1])
                return [children[i] for i in indices if 0 <= i < len(children)]
        except Exception:
            pass
        return children

    def _load_trees(self) -> list[dict]:
        """Load all PageIndex trees for the KB."""
        trees = []
        if self._pi_dir.exists():
            for tree_file in sorted(self._pi_dir.glob("*.json")):
                try:
                    tree = json.loads(tree_file.read_text())
                    tree["doc_id"] = tree_file.stem
                    trees.append(tree)
                except (json.JSONDecodeError, OSError):
                    pass
        return trees
