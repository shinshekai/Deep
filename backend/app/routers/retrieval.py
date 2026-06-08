"""Retrieval routes: POST /retrieve."""

import sys

from fastapi import APIRouter

from app.services import retrieval_service as _svc
from app.services.retrieval_service import RetrieveRequest
from app.services.retrieval_service import retrieve as _retrieve_impl

router = APIRouter(prefix="/api/v1", tags=["retrieval"])

_load_pageindex_tree = _svc._load_pageindex_tree
_list_pageindex_docs = _svc._list_pageindex_docs
_get_tree_search = _svc._get_tree_search
_get_vector_kb = _svc._get_vector_kb
DATA_DIR = _svc.DATA_DIR


@router.post("/retrieve")
async def retrieve(req: RetrieveRequest):
    _self = sys.modules[__name__]
    _saved = {}
    for _name in (
        "_load_pageindex_tree",
        "_list_pageindex_docs",
        "_get_tree_search",
        "_get_vector_kb",
        "DATA_DIR",
    ):
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
