"""Smart Solve dual-loop orchestrator.

Analysis Loop: Invest → Note
Solve Loop:    Plan → Solve → Check → Format

Streams agent_step, citation, and complete frames over WebSocket.
"""

import asyncio
import json
import time
import logging
from typing import AsyncGenerator

from app.services.complexity_scorer import score_query_complexity
from app.services.lm_studio_client import LMStudioClient
from app.services.model_manager import ModelManager

logger = logging.getLogger(__name__)

# System prompts for each agent
AGENT_PROMPTS = {
    "investigate": (
        "You are an Investigate agent. Analyze the user's query to identify key concepts, "
        "required knowledge domains, and the complexity level. Break it down into sub-questions."
    ),
    "note": (
        "You are a Note-taking agent. Synthesize the investigation findings into structured notes. "
        "Identify what is known, what needs verification, and what approach to take."
    ),
    "plan": (
        "You are a Planning agent. Create a step-by-step plan to answer the query based on "
        "the investigation and notes. Decide what information is critical and what order to present it."
    ),
    "solve": (
        "You are the Solve agent. Execute the plan and produce a comprehensive answer. "
        "Be precise, cite sources when possible, and explain your reasoning clearly."
    ),
    "check": (
        "You are a Check agent. Review the answer for accuracy, completeness, and consistency. "
        "Identify any gaps, errors, or areas needing clarification."
    ),
    "format": (
        "You are a Format agent. Ensure the final output is well-structured with proper "
        "headings, lists, code blocks, and citations. Make it polished and readable."
    ),
}


async def run_solve_pipeline(
    query: str,
    kb_name: str,
    mode: str,
    lm_client: LMStudioClient,
    model_manager: ModelManager,
    session_id: str,
    ws_send,
):
    """Execute the dual-loop solve pipeline and stream frames to WebSocket."""
    start_time = time.time()

    # ── Step 1: Complexity scoring and tier routing ──
    score, target_tier = score_query_complexity(
        query_text=query,
        doc_pages=0,  # TODO: resolve from KB
        retrieved_chunks=0,  # TODO: resolve from PageIndex
        free_vram_mb=float("inf"),  # TODO: from VRAMMonitor
    )
    logger.info(f"Solve session {session_id}: score={score}, tier={target_tier}, mode={mode}")

    # ── Step 2: Find the best available model ──
    model_id = model_manager.get_best_available_model() or "Qwen3-1.7B-Q4_K_M"

    # ── Step 3: Run the dual-loop ──
    try:
        full_answer = await _run_dual_loop(
            query=query,
            kb_name=kb_name,
            mode=mode,
            lm_client=lm_client,
            model_id=model_id,
            session_id=session_id,
            ws_send=ws_send,
        )

        if full_answer is None:
            full_answer = "I was unable to generate a response. The model may be unavailable."

        elapsed = time.time() - start_time
        await ws_send({
            "type": "complete",
            "answer": full_answer,
            "citations": [],
            "session_id": session_id,
            "solve_dir": f"data/user/solve/{session_id}",
            "metadata": {
                "complexity_score": score,
                "target_tier": target_tier,
                "model_used": model_id,
                "elapsed_seconds": round(elapsed, 2),
            },
        })
        model_manager.on_query_start(model_id)

    except Exception as e:
        logger.error(f"Solve pipeline error: {e}", exc_info=True)
        await ws_send({
            "type": "error",
            "error": "pipeline_failure",
            "message": f"Failed to process query: {str(e)}",
        })


async def _run_dual_loop(
    query: str,
    kb_name: str,
    mode: str,
    lm_client: LMStudioClient,
    model_id: str,
    session_id: str,
    ws_send,
) -> str | None:
    """Run Analysis Loop + Solve Loop, streaming frames."""

    # ── Analysis Loop ──
    analysis_steps = [
        ("investigate", "investigate"),
        ("note", "note"),
    ]
    analysis_context = []

    for agent_key, agent_label in analysis_steps:
        messages = [
            {"role": "system", "content": AGENT_PROMPTS[agent_key]},
            {"role": "user", "content": query},
        ]

        # Stream tokens from LLM
        step_content = await _stream_agent_step(
            agent_label=agent_label,
            lm_client=lm_client,
            model_id=model_id,
            messages=messages,
            ws_send=ws_send,
        )

        if step_content:
            analysis_context.append(step_content)

    # ── Solve Loop ──
    solve_steps = [
        ("plan", "plan"),
        ("solve", "solve"),
        ("check", "check"),
        ("format", "format"),
    ]
    final_answer = None

    context_summary = " | ".join(analysis_context[-2:])  # last 2 steps

    for agent_key, agent_label in solve_steps:
        # Build messages with accumulated context
        user_prompt = query
        if agent_key in ("solve", "check", "format") and context_summary:
            user_prompt = f"Context from analysis: {context_summary}\n\nOriginal query: {query}"

        messages = [
            {"role": "system", "content": AGENT_PROMPTS[agent_key]},
            {"role": "user", "content": user_prompt},
        ]

        step_content = await _stream_agent_step(
            agent_label=agent_label,
            lm_client=lm_client,
            model_id=model_id,
            messages=messages,
            ws_send=ws_send,
        )

        if agent_key == "format":
            final_answer = step_content
        elif step_content:
            context_summary += f" | {step_content[:100]}"

    return final_answer


async def _stream_agent_step(
    agent_label: str,
    lm_client: LMStudioClient,
    model_id: str,
    messages: list[dict],
    ws_send,
) -> str:
    """Call LLM and stream content as agent_step frames. Returns full content."""
    result = await lm_client.stream_chat_completion(
        model=model_id,
        messages=messages,
        max_tokens=2048,
    )

    if result is None or result.get("error"):
        # Fallback: send a minimal step
        content = f"[{agent_label}] No response from model."
        await ws_send({
            "type": "agent_step",
            "agent": agent_label.replace(" ", "").lower(),
            "content": content,
            "timestamp": time.time(),
        })
        return content

    return result.get("content", f"[{agent_label}] completed.")
