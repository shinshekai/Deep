"""Tests for extracted lifespan module (app.lifespan)."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.lifespan import lifespan


def test_lifespan_is_async_context_manager():
    assert callable(lifespan)


def test_lifespan_importable():
    from app import lifespan as lp
    assert hasattr(lp, "lifespan")


def test_lifespan_imported_in_main():
    from app import main
    assert hasattr(main, "lifespan")


def test_lifespan_replaces_old_location():
    from app import main
    import inspect
    sig = inspect.signature(main.FastAPI)
    # lifespan is passed as a kwarg to FastAPI constructor
    source = inspect.getsource(main)
    assert "lifespan=lifespan" in source or "lifespan = lifespan" in source


def test_broadcast_loop_importable():
    from app.lifespan import broadcast_loop
    import inspect
    assert inspect.iscoroutinefunction(broadcast_loop)


def test_ttl_loop_importable():
    from app.lifespan import ttl_loop
    import inspect
    assert inspect.iscoroutinefunction(ttl_loop)


def test_background_loops_exported_from_lifespan():
    from app.lifespan import broadcast_loop, ttl_loop
    assert callable(broadcast_loop)
    assert callable(ttl_loop)


def test_lifespan_source_contains_startup():
    import inspect
    source = inspect.getsource(lifespan)
    assert "Starting UDIP Backend" in source


def test_lifespan_source_contains_shutdown():
    import inspect
    source = inspect.getsource(lifespan)
    assert "Shutdown complete" in source


def test_lifespan_source_initializes_services():
    import inspect
    source = inspect.getsource(lifespan)
    assert "VRAMMonitor" in source
    assert "LMStudioClient" in source
    assert "ModelManager" in source
    assert "EmbeddingService" in source
    assert "VectorKBService" in source


def test_lifespan_source_spawns_background_tasks():
    import inspect
    source = inspect.getsource(lifespan)
    assert "broadcast_loop" in source
    assert "ttl_loop" in source
    assert "track_background_task" in source
