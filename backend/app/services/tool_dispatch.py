"""Tool dispatch orchestrator — LLM-driven agent tool selection via OpenAI function calling.

Uses the two-layer plugin model:
  Layer 1: ToolRegistry — single-shot tools the LLM can call directly
  Layer 2: CapabilityRegistry — multi-stage pipelines that own the turn

The dispatch loop sends registered tools to the LLM, executes selected tools,
and collects results. Falls back to fixed-sequence on failure.
"""

import json
import logging
import time

from app.services.tool_protocol import TOOL_SYSTEM_PROMPT
from app.services.tool_registry import tool_registry

logger = logging.getLogger(__name__)

MAX_DISPATCH_ROUNDS = 8


async def run_tool_dispatch(
    query: str,
    kb_name: str,
    retrieval_pipeline: str,
    lm_client,
    model_id: str,
    ws_send,
    memory_context: str = "",
) -> tuple[str, str]:
    """Run the agentic tool-dispatch loop. Returns (final_answer, transcript)."""

    transcript_parts: list[str] = []
    executed_tools: set[str] = set()

    messages: list[dict] = [
        {"role": "system", "content": TOOL_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Query: {query}\n\nAvailable KB: {kb_name}\nMemory context: {memory_context or 'none'}",
        },
    ]

    final_answer = ""

    context = {
        "lm_client": lm_client,
        "model_id": model_id,
        "query": query,
        "kb_name": kb_name,
        "retrieval_pipeline": retrieval_pipeline,
        "ws_send": ws_send,
    }

    for round_num in range(1, MAX_DISPATCH_ROUNDS + 1):
        logger.info("Dispatch round %d/%d for query: %s...", round_num, MAX_DISPATCH_ROUNDS, query[:80])

        openai_tools = tool_registry.get_openai_tools()
        result = await lm_client.stream_chat_completion(
            model=model_id,
            messages=messages,
            max_tokens=2048,
            tools=openai_tools,
        )

        if "error" in result:
            logger.error("Dispatch round %d failed: %s", round_num, result["error"])
            raise RuntimeError(f"Tool dispatch failed: {result['error']}")

        content = result.get("content", "") or ""
        tool_calls = result.get("tool_calls") or []

        if content:
            await ws_send({
                "type": "agent_step",
                "agent": f"dispatch_r{round_num}",
                "delta": content,
                "timestamp": time.time(),
            })

        if not tool_calls:
            if content.strip():
                final_answer = content
            break

        for tc in tool_calls:
            tool_name = tc["function"]["name"]
            try:
                tool_args = json.loads(tc["function"]["arguments"])
            except json.JSONDecodeError:
                tool_args = {}

            await ws_send({
                "type": "agent_step",
                "agent": tool_name,
                "delta": f"\n[Tool: {tool_name}]\n",
                "timestamp": time.time(),
            })

            tool_result = await _execute_registered_tool(
                tool_name, tool_args, context
            )

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": tool_result,
            })
            transcript_parts.append(f"## Tool: {tool_name}\n{tool_result}\n")

            executed_tools.add(tool_name)

            if tool_name == "finalize_answer":
                final_answer = tool_result
                break

        if tool_calls:
            messages.append({
                "role": "assistant",
                "content": content or "",
                "tool_calls": tool_calls,
            })

        if final_answer:
            break

    if not final_answer:
        final_answer = "I was unable to produce a complete answer. Please try rephrasing your query."

    transcript = "\n\n".join(transcript_parts)
    return final_answer, transcript


async def _execute_registered_tool(
    tool_name: str,
    args: dict,
    context: dict,
) -> str:
    """Execute a tool from the registry by name."""
    tool = tool_registry.get(tool_name)
    if tool is None:
        return f"Unknown tool: {tool_name}"
    try:
        return await tool.execute(args, context)
    except Exception as e:
        logger.error("Tool %s failed: %s", tool_name, e)
        return f"Tool {tool_name} failed: {e}"
