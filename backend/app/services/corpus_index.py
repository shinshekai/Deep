"""Corpus-level KB index — virtual root node above all document PageIndex trees.

Enables cross-document reasoning by letting the LLM first see a corpus overview
before deciding which specific document trees to search deeply.

PageIndex File System pattern: query → select documents → search selected trees.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


async def build_corpus_index(kb_name: str) -> dict:
    """Build a corpus-level root node from all PageIndex trees in a KB.

    Returns a dict with:
      - title: KB name
      - documents: list of {doc_id, title, summary, node_count, page_count}
    """
    pi_dir = Path("data/knowledge_bases") / kb_name / "pageindex"
    if not pi_dir.exists():
        return {"title": kb_name, "documents": []}

    documents = []
    for tree_file in sorted(pi_dir.glob("*.json")):
        try:
            tree = json.loads(tree_file.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        root = tree.get("root", {})
        doc_title = root.get("title", tree_file.stem)
        summary = root.get("summary", "")
        start_page = root.get("start_index", root.get("page_index", 0)) or 0
        end_page = root.get("end_index", root.get("page_index", 0)) or 0
        children = root.get("nodes", root.get("children", [])) or []
        node_count = 1 + _count_nodes(children)

        documents.append({
            "doc_id": tree_file.stem,
            "title": doc_title,
            "summary": (summary or "")[:200],
            "node_count": node_count,
            "pages": f"{start_page}-{end_page}" if end_page > start_page else str(start_page),
        })

    logger.info("Corpus index built for KB '%s': %d documents", kb_name, len(documents))
    return {"title": kb_name, "documents": documents}


def _count_nodes(nodes: list) -> int:
    count = len(nodes)
    for node in nodes:
        children = node.get("nodes", node.get("children", [])) or []
        count += _count_nodes(children)
    return count


def get_corpus_summary_prompt(kb_name: str, corpus: dict) -> str:
    """Generate a prompt that lets the LLM select which documents to search."""
    docs = corpus.get("documents", [])
    if not docs:
        return f"Knowledge Base '{kb_name}' has no indexed documents."

    doc_list = []
    for i, d in enumerate(docs):
        doc_list.append(f"[{i}] {d['title']} ({d['node_count']} sections, {d['pages']} pages): {d['summary']}")

    return (
        f"Available documents in '{kb_name}':\n"
        + "\n".join(doc_list)
        + "\n\nSelect document indices relevant to the query. Return JSON: {\"selected\": [0, 2]} or {\"selected\": []} if none."
    )
