"""Smart Solve dual-loop orchestrator.

Analysis Loop: Invest → Note
Solve Loop:    Plan → Solve → Check → Format

Streams agent_step, citation, and complete frames over WebSocket.
"""

import asyncio
import json
import time
from app.services.telemetry import trace_span, add_event
import logging
import os
from typing import AsyncGenerator
from app.services.task_registry import _global_registry

from app.services.complexity_scorer import score_query_complexity
from app.services.lm_studio_client import LMStudioClient
from app.services.model_manager import ModelManager
from app.services.fact_extractor import extract_and_store_facts
from app.services.retrieval_service import retrieve as run_retrieval, RetrieveRequest
from app import state

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
    retrieval_pipeline: str,
    lm_client: LMStudioClient,
    model_manager: ModelManager,
    session_id: str,
    ws_send,
    device_id: str | None = None,
    memory_context: str = "",
):
    """Execute the dual-loop solve pipeline and stream frames to WebSocket."""
    start_time = time.time()

    with trace_span("solve.pipeline", {"session_id": session_id, "mode": mode, "kb_name": kb_name}):

      # ── Step 1: Complexity scoring and tier routing ──
      # Resolve real VRAM from monitor
      from app.state import vram_monitor, get_metrics
      free_vram_mb = float("inf")
      try:
          vram_status = await state.vram_monitor.poll_once()
          total_mb = vram_status.get("vram_total_mb", 0)
          used_mb = vram_status.get("vram_used_mb", 0)
          free_vram_mb = (total_mb - used_mb) if total_mb > 0 else float("inf")
      except Exception:
          # Fall back to cached metrics
          metrics = get_metrics()
          total_mb = metrics.get("vram_total_mb", 0)
          used_mb = metrics.get("vram_used_mb", 0)
          if total_mb > 0:
              free_vram_mb = total_mb - used_mb

      # Resolve doc page count from KB PageIndex
      doc_pages = 0
      try:
          from pathlib import Path as _P
          pi_dir = _P("data/knowledge_bases") / kb_name / "pageindex"
          if pi_dir.exists():
              import json
              for tree_file in pi_dir.glob("*.json"):
                  tree_data = json.loads(tree_file.read_text())
                  root = tree_data.get("root", {})
                  doc_pages += root.get("page_end", 0) + 1
      except Exception:
          pass

      score, target_tier = score_query_complexity(
          query_text=query,
          doc_pages=doc_pages,
          retrieved_chunks=0,
          free_vram_mb=free_vram_mb,
      )
      add_event("complexity_scored", {"score": score, "tier": target_tier, "vram_free_mb": free_vram_mb, "doc_pages": doc_pages})
      logger.info(f"Solve session {session_id}: score={score}, tier={target_tier}, mode={mode}, vram_free={free_vram_mb:.0f}MB, pages={doc_pages}")

      # ── Step 2: Find the best available model ──
      model_id = await model_manager.get_best_available_model(target_tier) or "Qwen3-1.7B-Q4_K_M"
      add_event("model_selected", {"model_id": model_id})

      # ── Step 3: Run the dual-loop ──
      try:
          full_answer, transcript = await _run_dual_loop(
              query=query,
              kb_name=kb_name,
              mode=mode,
              retrieval_pipeline=retrieval_pipeline,
              lm_client=lm_client,
              model_id=model_id,
              session_id=session_id,
              ws_send=ws_send,
              memory_context=memory_context,
          )

          if full_answer is None:
              full_answer = "I was unable to generate a response. The model may be unavailable."
              transcript += f"\n\n[System] Fallback triggered. Final answer: {full_answer}"

          # ── Step 4: Session Persistence ──
          solve_dir = f"data/user/solve/{session_id}"
          os.makedirs(solve_dir, exist_ok=True)
          
          with open(f"{solve_dir}/final_answer.md", "w", encoding="utf-8") as f:
              f.write(full_answer)
              
          with open(f"{solve_dir}/transcript.md", "w", encoding="utf-8") as f:
              f.write(transcript)

          elapsed = time.time() - start_time
          add_event("solve_complete", {"elapsed_s": round(elapsed, 2), "model": model_id})
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

          if state.memory_service:
              if device_id is None:
                  logger.warning(f"Solve session {session_id}: device_id is None; skipping memory write")
              else:
                  async def _run_with_telemetry():
                      try:
                          await extract_and_store_facts(
                              device_id=device_id, query=query, answer=full_answer or "",
                              source_id=session_id, lm_client=lm_client, memory_service=state.memory_service,
                          )
                      except Exception as e:
                          logger.error(f"fact_extraction_failed: {e}", exc_info=False)
                          try:
                              from app.services.metrics import FACT_EXTRACTION_FAILURES
                              FACT_EXTRACTION_FAILURES.inc()
                          except ImportError:
                              pass
                  _global_registry.spawn(_run_with_telemetry())
                  _global_registry.spawn(state.memory_service.store_episode(
                      device_id=device_id, query=query, answer=full_answer or "",
                      agents=["investigate", "note", "plan", "solve", "check", "format"],
                      model_used=model_id, session_type="solve",
                  ))

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
    retrieval_pipeline: str,
    lm_client: LMStudioClient,
    model_id: str,
    session_id: str,
    ws_send,
    memory_context: str = "",
) -> tuple[str | None, str]:
    """Run Analysis Loop + Solve Loop, streaming frames. Returns (final_answer, transcript)."""

    transcript = f"# Smart Solver Session: {session_id}\n\n## Query\n{query}\n\n"

    # ── Analysis Loop ──
    analysis_steps = [
        ("investigate", "investigate"),
        ("note", "note"),
    ]
    analysis_context = []

    for agent_key, agent_label in analysis_steps:
        # Step 2: Use RAG tool during investigate
        tool_context = ""
        if agent_key == "investigate" and kb_name:
            await ws_send({
                "type": "agent_step",
                "agent": "investigate",
                "delta": f"\n[System: Running {retrieval_pipeline} retrieval pipeline...]\n",
                "timestamp": time.time(),
            })
            
            req = RetrieveRequest(query=query, kb_name=kb_name, retrieval_pipeline=retrieval_pipeline, top_k=3)
            retrieval_resp = await run_retrieval(req)
            rag_results = retrieval_resp.get("results", [])
            
            if rag_results:
                tool_context = "Extracted Knowledge Base Context:\n"
                for i, res in enumerate(rag_results):
                    content = res.get('content', '') or res.get('summary', '')
                    tool_context += f"--- Chunk {i+1} ---\n{content}\n\n"
        
        user_prompt = query
        if memory_context:
            user_prompt = f"{memory_context}\n\nOriginal query: {query}"
        if tool_context:
            user_prompt += f"\n\n{tool_context}"
            
        messages = [
            {"role": "system", "content": AGENT_PROMPTS[agent_key]},
            {"role": "user", "content": user_prompt},
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
            transcript += f"### Agent: {agent_label}\n{step_content}\n\n"

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
        if memory_context:
            user_prompt = f"{memory_context}\n\nOriginal query: {query}"
        if agent_key in ("solve", "check", "format") and context_summary:
            if memory_context:
                user_prompt = f"{memory_context}\n\nContext from analysis: {context_summary}\n\nOriginal query: {query}"
            else:
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
            
        if step_content:
            transcript += f"### Agent: {agent_label}\n{step_content}\n\n"

    return final_answer, transcript


async def _stream_agent_step(
    agent_label: str,
    lm_client: LMStudioClient,
    model_id: str,
    messages: list[dict],
    ws_send,
) -> str:
    """Call LLM and stream content as agent_step frames. Returns full content."""
    
    async def on_chunk(tok: str):
        # Stream the delta token over WebSocket
        await ws_send({
            "type": "agent_step",
            "agent": agent_label.replace(" ", "").lower(),
            "delta": tok,
            "timestamp": time.time(),
        })

    result = await lm_client.stream_chat_completion(
        model=model_id,
        messages=messages,
        max_tokens=2048,
        chunk_callback=on_chunk,
    )

    if result is None or result.get("error"):
        # Fallback: send a minimal step
        content = f"[{agent_label}] No response from model."
        await ws_send({
            "type": "agent_step",
            "agent": agent_label.replace(" ", "").lower(),
            "delta": content,
            "timestamp": time.time(),
        })
        return content

    return result.get("content", f"[{agent_label}] completed.")
