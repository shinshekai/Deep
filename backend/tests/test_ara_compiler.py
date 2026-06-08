"""Tests for the ARA Compiler Service."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.ara_compiler import (
    ARACompiler,
    ARArtifact,
    Claim,
    Concept,
    ExplorationNode,
    Heuristic,
)


@pytest.fixture
def mock_lm_client():
    client = MagicMock()

    async def mock_stream(*args, **kwargs):
        messages = kwargs.get("messages", [])
        prompt = messages[0]["content"]

        # Determine what to return based on the prompt
        if "manifest" in prompt:
            return {"content": "Test Document Summary"}
        elif "claims" in prompt:
            return {
                "content": '[{"statement": "Test Claim 1", "evidence_hints": ["Ref 1"]}, {"statement": "Test Claim 2", "evidence_hints": []}]'
            }
        elif "concepts" in prompt:
            return {
                "content": '[{"name": "Concept A", "definition": "Def A", "related": ["Concept B"]}]'
            }
        elif "heuristics" in prompt:
            return {
                "content": '```json\n[{"description": "Heuristic 1", "rationale": "Reason 1", "constraints": ["Constraint 1"]}]\n```'
            }
        elif "architecture" in prompt:
            return {"content": "This is the architecture description."}
        elif "exploration" in prompt:
            return {
                "content": '[{"type": "experiment", "description": "Test experiment", "outcome": "success"}]'
            }
        return {"content": "Unknown step output"}

    client.stream_chat_completion = AsyncMock(side_effect=mock_stream)
    return client


@pytest.fixture
def sample_artifact():
    return ARArtifact(
        doc_id="test_doc_123",
        title="Test Document",
        summary="Test Summary",
        claims=[
            Claim(claim_id="CLM-001", statement="Test claim A", evidence_refs=["pg1"]),
            Claim(claim_id="CLM-002", statement="Another claim B", evidence_refs=["pg2"]),
        ],
        concepts=[
            Concept(
                concept_id="CON-001",
                name="Test Concept",
                definition="Test def",
                related_concepts=["Other"],
            )
        ],
        heuristics=[
            Heuristic(
                heuristic_id="HEU-001",
                description="Fast heuristic",
                rationale="Speed",
                constraints=["Memory"],
            )
        ],
        architecture="Simple architecture",
        exploration_nodes=[
            ExplorationNode(
                node_id="EXP-001", node_type="experiment", description="Test 1", outcome="success"
            )
        ],
    )


@pytest.mark.asyncio
async def test_compile(mock_lm_client):
    """Test full compilation pipeline."""
    compiler = ARACompiler(lm_client=mock_lm_client)

    artifact = await compiler.compile(
        doc_id="doc_1",
        text="This is a test document text.",
        title="Test Title",
    )

    assert isinstance(artifact, ARArtifact)
    assert artifact.doc_id == "doc_1"
    assert artifact.title == "Test Title"
    assert artifact.summary == "Test Document Summary"

    # Check parsed lists
    assert len(artifact.claims) == 2
    assert artifact.claims[0].statement == "Test Claim 1"
    assert artifact.claims[0].claim_id == "CLM-001"

    assert len(artifact.concepts) == 1
    assert artifact.concepts[0].name == "Concept A"

    assert len(artifact.heuristics) == 1
    assert artifact.heuristics[0].description == "Heuristic 1"

    assert artifact.architecture == "This is the architecture description."

    assert len(artifact.exploration_nodes) == 1
    assert artifact.exploration_nodes[0].node_type == "experiment"


@pytest.mark.asyncio
async def test_compile_api_error_fallback(mock_lm_client):
    """Test that extraction errors return empty results but don't crash."""
    mock_lm_client.stream_chat_completion.side_effect = Exception("API Error")
    compiler = ARACompiler(lm_client=mock_lm_client)

    artifact = await compiler.compile(
        doc_id="doc_error",
        text="Text",
    )

    assert artifact.doc_id == "doc_error"
    assert artifact.summary == ""
    assert len(artifact.claims) == 0
    assert len(artifact.concepts) == 0
    assert len(artifact.heuristics) == 0


def test_safe_parse_json():
    """Test robust JSON array parsing."""
    # Direct valid JSON
    assert ARACompiler._safe_parse_json('[{"a": 1}]') == [{"a": 1}]

    # Valid dict (should wrap in list)
    assert ARACompiler._safe_parse_json('{"a": 1}') == [{"a": 1}]

    # Markdown wrapped JSON
    markdown_json = 'Here is the output:\n```json\n[{"b": 2}]\n```\nDone.'
    assert ARACompiler._safe_parse_json(markdown_json) == [{"b": 2}]

    # Substring JSON
    substring_json = 'Output: [{"c": 3}] end.'
    assert ARACompiler._safe_parse_json(substring_json) == [{"c": 3}]

    # Invalid JSON
    assert ARACompiler._safe_parse_json("Not a json array") == []
    assert ARACompiler._safe_parse_json("") == []


def test_persist(tmp_path, sample_artifact):
    """Test saving artifact to disk."""
    compiler = ARACompiler(lm_client=MagicMock())

    saved_path = compiler.persist(sample_artifact, tmp_path)

    # Check directory structure
    assert saved_path.exists()
    assert (saved_path / "PAPER.md").exists()
    assert (saved_path / "logic" / "claims.json").exists()
    assert (saved_path / "logic" / "concepts.json").exists()
    assert (saved_path / "solution" / "architecture.md").exists()
    assert (saved_path / "solution" / "heuristics.json").exists()
    assert (saved_path / "trace" / "exploration.json").exists()

    # Check content
    paper_content = (saved_path / "PAPER.md").read_text()
    assert "# Test Document" in paper_content
    assert "Test Summary" in paper_content

    claims_json = json.loads((saved_path / "logic" / "claims.json").read_text())
    assert len(claims_json) == 2
    assert claims_json[0]["statement"] == "Test claim A"


def test_load(tmp_path, sample_artifact):
    """Test loading artifact from disk."""
    compiler = ARACompiler(lm_client=MagicMock())
    compiler.persist(sample_artifact, tmp_path)

    loaded_artifact = compiler.load(tmp_path, "test_doc_123")

    assert loaded_artifact is not None
    assert loaded_artifact.doc_id == "test_doc_123"
    assert loaded_artifact.title == "Test Document"
    assert "Test Summary" in loaded_artifact.summary
    assert len(loaded_artifact.claims) == 2
    assert loaded_artifact.claims[0].statement == "Test claim A"
    assert loaded_artifact.architecture == "Simple architecture"


def test_load_not_found(tmp_path):
    """Test loading non-existent artifact."""
    compiler = ARACompiler(lm_client=MagicMock())
    assert compiler.load(tmp_path, "missing_doc") is None


def test_search_claims(sample_artifact):
    """Test claim search."""
    compiler = ARACompiler(lm_client=MagicMock())

    results = compiler.search_claims(sample_artifact, "claim A")
    assert len(results) == 1
    assert results[0].claim_id == "CLM-001"

    results_empty = compiler.search_claims(sample_artifact, "nonexistent")
    assert len(results_empty) == 0


def test_search_heuristics(sample_artifact):
    """Test heuristic search."""
    compiler = ARACompiler(lm_client=MagicMock())

    results = compiler.search_heuristics(sample_artifact, "fast")
    assert len(results) == 1
    assert results[0].heuristic_id == "HEU-001"


def test_get_exploration_trace(sample_artifact):
    """Test getting exploration trace."""
    compiler = ARACompiler(lm_client=MagicMock())
    trace = compiler.get_exploration_trace(sample_artifact)
    assert len(trace) == 1
    assert trace[0].node_id == "EXP-001"


# ── Day 9b: File I/O error handling in persist() ──────────────────────────


def test_persist_continues_when_one_file_fails(tmp_path, sample_artifact, monkeypatch):
    """If one write_text() fails (e.g. disk full), the other files still
    persist — we don't want one transient I/O error to lose the whole
    manifest."""
    compiler = ARACompiler(lm_client=MagicMock())
    real_write_text = Path.write_text

    def maybe_failing_write(self, *args, **kwargs):
        # Fail only on the claims.json path; everything else works.
        if self.name == "claims.json":
            raise OSError("disk full")
        return real_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", maybe_failing_write)

    saved_path = compiler.persist(sample_artifact, tmp_path)
    # The directory still exists; the function returned a Path.
    assert saved_path == tmp_path / "ara" / "test_doc_123"
    # Other files are present.
    assert (saved_path / "PAPER.md").exists()
    assert (saved_path / "logic" / "concepts.json").exists()
    # The claims.json is the one that failed — its absence is the assertion.
    assert not (saved_path / "logic" / "claims.json").exists()


def test_persist_raises_when_directory_creation_fails(tmp_path, sample_artifact, monkeypatch):
    """If the top-level directories cannot be created, persist() raises
    OSError so the caller knows nothing was persisted."""
    compiler = ARACompiler(lm_client=MagicMock())

    def failing_mkdir(self, *args, **kwargs):
        raise PermissionError("read-only filesystem")

    monkeypatch.setattr(Path, "mkdir", failing_mkdir)

    with pytest.raises(OSError):
        compiler.persist(sample_artifact, tmp_path)
    # The directory should not have been created (mkdir was blocked).
    assert not (tmp_path / "ara" / "test_doc_123").exists()
