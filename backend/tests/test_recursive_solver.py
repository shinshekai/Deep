"""Tests for the Recursive Multi-Agent Solver."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.recursive_solver import RecursiveSolver


@pytest.fixture
def mock_lm_client():
    client = MagicMock()

    # Track calls to return different things
    call_count = {"count": 0}

    async def mock_stream(*args, **kwargs):
        call_count["count"] += 1

        # If testing compression
        messages = kwargs.get("messages", [])
        if messages and "Compress the following text" in messages[0]["content"]:
            return {"content": "Compressed summary."}

        # Return generic responses that simulate progress
        # For convergence testing, we return similar strings
        if call_count["count"] > 3:
            return {"content": "Final stable answer that repeats."}

        return {"content": f"Response step {call_count['count']}"}

    client.stream_chat_completion = AsyncMock(side_effect=mock_stream)
    return client


@pytest.mark.asyncio
async def test_solve_sequential_pattern(mock_lm_client):
    """Test sequential Planner -> Critic -> Solver pattern with convergence."""
    solver = RecursiveSolver(lm_client=mock_lm_client)

    # We set a low convergence threshold to trigger it quickly,
    # or let it hit max_rounds.
    result = await solver.solve(
        query="Test query",
        context="Test context",
        pattern="sequential",
        max_rounds=2,
    )

    assert result.pattern == "sequential"
    assert result.max_rounds == 2
    assert len(result.agent_trace) > 0
    # Should contain planner, critic, solver calls
    agents_used = [r.agent for r in result.agent_trace]
    assert "planner" in agents_used
    assert "critic" in agents_used
    assert "solver" in agents_used
    assert result.answer is not None


@pytest.mark.asyncio
async def test_solve_mixture_pattern(mock_lm_client):
    """Test mixture pattern with parallel domain experts and summarizer."""
    solver = RecursiveSolver(lm_client=mock_lm_client)

    result = await solver.solve(
        query="Test mixture query",
        context="Test context",
        pattern="mixture",
    )

    assert result.pattern == "mixture"
    assert result.rounds_used == 1

    agents = [r.agent for r in result.agent_trace]
    assert "math_expert" in agents
    assert "code_expert" in agents
    assert "science_expert" in agents
    assert "summarizer" in agents


@pytest.mark.asyncio
async def test_solve_deliberation_pattern(mock_lm_client):
    """Test deliberation pattern with Reflector <-> ToolCaller."""
    solver = RecursiveSolver(lm_client=mock_lm_client)

    result = await solver.solve(
        query="Test deliberation query",
        context="Test context",
        pattern="deliberation",
        max_rounds=2,
    )

    assert result.pattern == "deliberation"
    agents = [r.agent for r in result.agent_trace]
    assert "reflector" in agents
    assert "tool_caller" in agents


@pytest.mark.asyncio
async def test_solve_distillation_pattern(mock_lm_client):
    """Test distillation pattern with Expert -> Learner."""
    solver = RecursiveSolver(lm_client=mock_lm_client)

    result = await solver.solve(
        query="Test distillation query",
        context="Test context",
        pattern="distillation",
        expert_model_id="Large-Model-Id",
    )

    assert result.pattern == "distillation"
    agents = [r.agent for r in result.agent_trace]
    assert "expert" in agents
    assert "learner" in agents


@pytest.mark.asyncio
async def test_solve_unknown_pattern(mock_lm_client):
    """Test invalid pattern raises error."""
    solver = RecursiveSolver(lm_client=mock_lm_client)

    with pytest.raises(ValueError, match="Unknown pattern"):
        await solver.solve(query="Test", pattern="unknown_pattern")  # type: ignore


@pytest.mark.asyncio
async def test_compress_fallback(mock_lm_client):
    """Test _compress fallback when LLM fails."""
    # Setup client to raise error
    mock_lm_client.stream_chat_completion.side_effect = Exception("API Error")

    solver = RecursiveSolver(lm_client=mock_lm_client)

    # Generate long text > 200 words
    long_text = "word " * 250

    compressed = await solver._compress(long_text, "test_model")

    # Should use truncation fallback
    assert len(compressed.split()) == 200


def test_check_convergence():
    """Test Jaccard similarity convergence detection."""
    solver = RecursiveSolver(lm_client=MagicMock())

    # Exact match
    assert solver._check_convergence("This is a test.", "This is a test.", 0.9) is True

    # Completely different
    assert solver._check_convergence("Apples and oranges", "Cats and dogs", 0.5) is False

    # Similar (intersection / union)
    # prev: "a b c d" -> set(a,b,c,d) = 4
    # curr: "a b c e" -> set(a,b,c,e) = 4
    # intersection: a,b,c (3)
    # union: a,b,c,d,e (5)
    # similarity: 3/5 = 0.6

    # 0.6 >= 0.5 -> True
    assert solver._check_convergence("a b c d", "a b c e", 0.5) is True

    # 0.6 >= 0.8 -> False
    assert solver._check_convergence("a b c d", "a b c e", 0.8) is False

    # Empty strings
    assert solver._check_convergence("", "", 0.5) is False


def test_select_pattern():
    """Test collaboration pattern selection logic."""
    # Simple query -> sequential
    assert RecursiveSolver.select_pattern("What is the capital of France?", 0.3) == "sequential"

    # High complexity -> distillation
    assert RecursiveSolver.select_pattern("Explain quantum mechanics.", 0.8) == "distillation"

    # Research heavy -> deliberation
    assert (
        RecursiveSolver.select_pattern(
            "Investigate and compare the effects of X and Y comprehensively.",
            0.5,
            retrieved_chunks=5,
        )
        == "deliberation"
    )

    # Multi-domain -> mixture
    assert (
        RecursiveSolver.select_pattern(
            "Implement a function to calculate the integral using scientific research.", 0.5
        )
        == "mixture"
    )


@pytest.mark.asyncio
async def test_ws_send_callback(mock_lm_client):
    """Test WebSocket callback is called during execution."""
    solver = RecursiveSolver(lm_client=mock_lm_client)

    ws_mock = AsyncMock()

    await solver.solve(query="Test query", pattern="sequential", max_rounds=1, ws_send=ws_mock)

    # The callback should be called multiple times for agent steps
    assert ws_mock.call_count > 0

    # Verify the structure of at least one call
    first_call_args = ws_mock.call_args_list[0][0][0]
    assert "type" in first_call_args
    assert first_call_args["type"] == "agent_step"
    assert "agent" in first_call_args


@pytest.mark.asyncio
async def test_mixture_agent_failure(mock_lm_client):
    """Test mixture pattern handles individual expert failures."""

    async def mock_stream(*args, **kwargs):
        if "math" in kwargs.get("messages", [])[0]["content"].lower():
            raise Exception("Math expert crashed")
        return {"content": "Success"}

    mock_lm_client.stream_chat_completion.side_effect = mock_stream

    solver = RecursiveSolver(lm_client=mock_lm_client)

    result = await solver.solve(
        query="Test query",
        pattern="mixture",
    )

    # Shouldn't crash the whole solve process
    assert result.pattern == "mixture"
    assert "Math expert crashed" in str(result.agent_trace)
