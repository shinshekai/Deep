"""Query router tests — pipeline selection with complexity awareness."""


def test_explicit_pipeline_is_respected():
    """Explicit pipeline parameter always wins."""
    from app.services.query_router import route_query

    result = route_query("anything", "kb", doc_id=None, retrieval_pipeline="hybrid")
    assert result == "hybrid"

    result = route_query("anything", "kb", doc_id=None, retrieval_pipeline="naive")
    assert result == "naive"


def test_doc_id_routes_to_tree():
    """When doc_id specified, tree search for precision."""
    from app.services.query_router import route_query

    result = route_query("query", "kb", doc_id="specific_doc")
    assert result == "tree"


def test_complex_query_routes_to_tree():
    """Long or specific queries go to tree for precision."""
    from app.services.query_router import route_query

    result = route_query(
        "What are the key differences between supervised and "
        "unsupervised learning approaches in deep neural networks?",
        "kb",
    )
    assert result == "tree"


def test_no_data_sources_returns_tree_with_warning():
    """When no vectors exist, fall back to tree."""
    from app.services.query_router import RouteContext, route_query

    ctx = RouteContext(has_trees=True, has_vectors=False)
    result = route_query("short query", "kb", context=ctx)
    # Should fall back to tree since no vectors
    assert result == "tree"


def test_no_treeses_falls_back_to_naive():
    """When no PageIndex trees exist, fall back to naive/hybrid."""
    from app.services.query_router import RouteContext, route_query

    ctx = RouteContext(has_trees=False, has_vectors=True)
    result = route_query("query", "kb", context=ctx)
    # Should use available retrieval
    assert result in ("hybrid", "naive")


def test_unknown_pipeline_defaults_to_tree():
    """Invalid pipeline parameter defaults to tree."""
    from app.services.query_router import route_query

    result = route_query("q", "kb", retrieval_pipeline="banana")
    assert result == "tree"


def test_short_query_routes_to_tree_when_no_vectors():
    """Short query routes to tree when vectors unavailable."""
    from app.services.query_router import RouteContext, route_query

    ctx = RouteContext(has_trees=True, has_vectors=False, complexity=0.2)
    result = route_query("data", "kb", context=ctx)
    assert result == "tree"
