"""Query Router — retrieval mode selector with complexity awareness.

Routes queries to appropriate pipeline (tree/hybrid/naive/combined) based on:
- Explicit pipeline parameter (always wins)
- Document targeting (doc_id → tree)
- Available data sources (no vectors → tree, no trees → naive)
- Query complexity (from ComplexityScorer)
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

VALID_PIPELINES = {"tree", "hybrid", "naive", "combined"}


@dataclass
class RouteContext:
    """Context for routing decisions."""

    has_trees: bool = True
    has_vectors: bool = False
    complexity: float = 0.5
    doc_pages: int = 0


def route_query(
    query: str,
    kb_name: str,
    doc_id: str | None = None,
    retrieval_pipeline: str | None = None,
    context: RouteContext | None = None,
) -> str:
    """Determine the best retrieval pipeline for a query.

    Returns: pipeline name: "tree", "hybrid", "naive", or "combined".
    """
    # Explicit override wins
    if retrieval_pipeline:
        if retrieval_pipeline not in VALID_PIPELINES:
            logger.warning(
                f"Unknown retrieval pipeline '{retrieval_pipeline}', defaulting to 'tree'"
            )
            return "tree"
        return retrieval_pipeline

    ctx = context or RouteContext()

    # If specific document targeted → tree
    if doc_id:
        return "tree"

    # Check data source availability
    if not ctx.has_trees and ctx.has_vectors:
        logger.warning("No PageIndex trees — falling back to vector search")
        return "hybrid"

    if not ctx.has_trees and not ctx.has_vectors:
        logger.warning("No retrieval data available")
        return "tree"

    # Complexity-aware routing
    query_terms = len(query.split())

    if ctx.complexity > 0.6:
        # High complexity → tree for precision
        return "tree"
    elif ctx.complexity < 0.3:
        if query_terms <= 3:
            # Short, simple → hybrid for recall
            return "hybrid" if ctx.has_vectors else "tree"
        else:
            return "tree"
    else:
        # Medium complexity → combined when both sources available
        if ctx.has_trees and ctx.has_vectors:
            return "combined"
        elif ctx.has_trees:
            return "tree"
        else:
            return "hybrid"
