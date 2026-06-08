"""Extended tests for knowledge router."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.routers.knowledge import _kb_registry, _process_document, _tasks


@pytest.fixture
def clean_tasks_registry():
    _tasks.clear()
    _kb_registry.clear()
    _kb_registry["test_kb"] = {
        "name": "test_kb",
        "status": "active",
        "total_docs": 0,
        "total_pages": 0,
    }


@pytest.mark.asyncio
async def test_process_document_success(clean_tasks_registry, tmp_path):
    """Test successful document processing pipeline."""
    task_id = "test_task_1"
    _tasks[task_id] = {}
    (tmp_path / "test_kb").mkdir(parents=True, exist_ok=True)

    # Mock extract_text
    with patch(
        "app.routers.knowledge.extract_text", AsyncMock(return_value="Extracted text content")
    ):
        # Mock dependencies
        mock_pg = MagicMock()
        mock_pg.build_tree = AsyncMock(return_value={"total_pages": 2, "root": {}})

        mock_embed = MagicMock()
        mock_chunk = MagicMock()
        mock_vkb = MagicMock()

        # Mock _build_vectors
        with patch("app.routers.knowledge._build_vectors", AsyncMock(return_value=5)):
            # Mock ARACompiler
            mock_ara_inst = MagicMock()
            mock_ara_inst.compile = AsyncMock(return_value=MagicMock())
            mock_ara_inst.persist = MagicMock()

            with patch("app.services.ara_compiler.ARACompiler", return_value=mock_ara_inst):
                with patch("app.routers.knowledge.DATA_DIR", tmp_path):
                    with patch("app.routers.knowledge.KB_UPLOADS_DIR", tmp_path):
                        await _process_document(
                            task_id=task_id,
                            file_bytes=b"dummy",
                            doc_id="doc1",
                            kb_name="test_kb",
                            pageindex_generator=mock_pg,
                            embedding_service=mock_embed,
                            text_chunker=mock_chunk,
                            vector_kb_service=mock_vkb,
                        )

    # Check task status
    assert _tasks[task_id]["status"] == "complete"
    assert _tasks[task_id]["progress"] == 100
    assert "Generated" in _tasks[task_id]["message"]

    # Check KB registry updated
    assert _kb_registry["test_kb"]["total_docs"] == 1
    assert _kb_registry["test_kb"]["total_pages"] == 2

    # Check tree JSON written
    tree_path = tmp_path / "test_kb" / "pageindex" / "doc1.json"
    assert tree_path.exists()


@pytest.mark.asyncio
async def test_process_document_extract_fail(clean_tasks_registry, tmp_path):
    """Test process document when text extraction fails."""
    task_id = "test_task_fail"
    _tasks[task_id] = {}
    (tmp_path / "test_kb").mkdir(parents=True, exist_ok=True)

    with patch("app.routers.knowledge.extract_text", AsyncMock(return_value=None)):
        with patch("app.routers.knowledge.KB_UPLOADS_DIR", tmp_path):
            await _process_document(
                task_id=task_id,
                file_bytes=b"dummy",
                doc_id="doc2",
                kb_name="test_kb",
                pageindex_generator=MagicMock(),
            )

    assert _tasks[task_id]["status"] == "failed"
    assert "Failed to extract text" in _tasks[task_id]["message"]


@pytest.mark.asyncio
async def test_process_document_pipeline_error(clean_tasks_registry, tmp_path):
    """Test process document when pipeline throws an exception."""
    task_id = "test_task_err"
    _tasks[task_id] = {}
    (tmp_path / "test_kb").mkdir(parents=True, exist_ok=True)

    with patch("app.routers.knowledge.extract_text", AsyncMock(return_value="text")):
        mock_pg = MagicMock()
        mock_pg.build_tree = AsyncMock(side_effect=ValueError("Test Pipeline Error"))

        with patch("app.routers.knowledge.KB_UPLOADS_DIR", tmp_path):
            with patch("app.routers.knowledge.DATA_DIR", tmp_path):
                # Ensure ARACompiler mock also handles the call if the execution reaches it
                mock_ara_inst = MagicMock()
                mock_ara_inst.compile = AsyncMock(return_value=MagicMock())
                with patch("app.services.ara_compiler.ARACompiler", return_value=mock_ara_inst):
                    await _process_document(
                        task_id=task_id,
                        file_bytes=b"dummy",
                        doc_id="doc3",
                        kb_name="test_kb",
                        pageindex_generator=mock_pg,
                    )

    assert _tasks[task_id]["status"] == "failed"
    assert "Test Pipeline Error" in _tasks[task_id]["message"]
