"""Retrieval routes: POST /retrieve."""

import sys

from fastapi import APIRouter

from app.services.retrieval_service import (
    RetrieveRequest,
    retrieve as _retrieve_impl,
    DATA_DIR,
    _load_pageindex_tree,
    _list_pageindex_docs,
    _get_tree_search,
    _get_vector_kb,
)
from app.services import retrieval_service as _svc

router = APIRouter(prefix="/api/v1", tags=["retrieval"])


@router.post("/retrieve")
async def retrieve(req: RetrieveRequest):
    _self = sys.modules[__name__]
    _saved = {}
    for _name in ("_load_pageindex_tree", "_list_pageindex_docs", "_get_tree_search", "_get_vector_kb", "DATA_DIR"):
        _self_val = getattr(_self, _name)
        _svc_val = getattr(_svc, _name)
        if _self_val is not _svc_val:
            _saved[_name] = _svc_val
            setattr(_svc, _name, _self_val)
    try:
        return await _retrieve_impl(req)
    finally:
        for _name, _val in _saved.items():
            setattr(_svc, _name, _val)
