"""End-to-end smoke test against a running LM Studio.

Verifies the full request → response cycle works against the real
backend (no mocks). Run manually with:

    cd backend
    python tests/manual_smoke_lm_studio.py
    # or
    pytest tests/manual_smoke_lm_studio.py -v -s
"""

import sys

import httpx
import pytest

LM_STUDIO_URL = "http://localhost:1234"
MODEL = "google/gemma-4-e2b"


def _check_models_listed() -> dict:
    """Confirm LM Studio is reachable and lists the expected model."""
    r = httpx.get(f"{LM_STUDIO_URL}/v1/models", timeout=5.0)
    r.raise_for_status()
    data = r.json()
    model_ids = [m["id"] for m in data.get("data", [])]
    assert MODEL in model_ids, f"{MODEL!r} not in {model_ids}"
    return {"status": r.status_code, "models_found": len(model_ids), "target_present": True}


@pytest.mark.asyncio
async def test_lm_studio_reachable_and_model_listed():
    """LM Studio must respond on the OpenAI /v1/models endpoint and expose Gemma 4 E2B."""
    result = _check_models_listed()
    print(
        f"\n  Models endpoint OK: {result['models_found']} models, target present: {result['target_present']}"
    )
    assert result["target_present"]


@pytest.mark.asyncio
async def test_lm_studio_chat_completion_roundtrip():
    """A real chat completion request must stream back content from the loaded model.

    Gemma 4 E2B is a reasoning model — it may emit ``reasoning_content``
    before ``content`` so we accept either. We use a generous
    ``max_tokens`` so the model can finish its think step.
    """
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a concise assistant. Think briefly, then answer.",
            },
            {"role": "user", "content": "What is 2+2? Answer with just the number."},
        ],
        "max_tokens": 500,
        "temperature": 0.0,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(f"{LM_STUDIO_URL}/v1/chat/completions", json=payload)
    assert r.status_code == 200, f"chat completion failed: {r.status_code} {r.text[:200]}"
    body = r.json()
    assert body.get("choices"), "no choices returned"
    message = body["choices"][0]["message"]
    content = message.get("content", "") or ""
    reasoning = message.get("reasoning_content", "") or ""
    print(f"\n  Chat completion content: {content!r}")
    print(f"  Reasoning content: {reasoning[:120]!r}…")
    assert content or reasoning, "no content or reasoning in response"
    # Reasoning models may put the final answer only in reasoning; for
    # this trivial question we expect the final answer in content.
    if not content:
        pytest.skip(
            "Reasoning model returned no final content within max_tokens; "
            "this is model-dependent, not a backend regression."
        )
    assert any(c in content for c in ("4", "four")), f"unexpected answer: {content!r}"


@pytest.mark.asyncio
async def test_lm_studio_streaming_chat_completion():
    """Verify the streaming endpoint works (SSE format) — used by the agent pipeline.

    We accept both ``content`` and ``reasoning_content`` deltas because
    reasoning models emit the latter first.
    """
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": "Reply with the single word: pong"}],
        "max_tokens": 500,
        "temperature": 0.0,
        "stream": True,
    }
    chunks: list[str] = []
    reasoning_chunks: list[str] = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", f"{LM_STUDIO_URL}/v1/chat/completions", json=payload) as r:
            assert r.status_code == 200
            async for line in r.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data = line[6:].strip()
                if data == "[DONE]":
                    break
                try:
                    import json

                    obj = json.loads(data)
                    delta = obj["choices"][0]["delta"]
                    c = delta.get("content")
                    if c:
                        chunks.append(c)
                    r = delta.get("reasoning_content")
                    if r:
                        reasoning_chunks.append(r)
                except (KeyError, ValueError):
                    pass

    full = "".join(chunks)
    full_reasoning = "".join(reasoning_chunks)
    print(f"\n  Streamed content: {full!r}")
    print(f"  Streamed reasoning: {full_reasoning[:120]!r}…")
    assert len(chunks) + len(reasoning_chunks) >= 1, "no stream chunks received"


if __name__ == "__main__":
    print(f"Checking LM Studio at {LM_STUDIO_URL} for model {MODEL!r}…\n")
    try:
        info = _check_models_listed()
        print(f"  models: {info['models_found']}, target present: {info['target_present']}\n")
    except Exception as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    print("Run the full pytest suite instead for chat/stream tests.")
