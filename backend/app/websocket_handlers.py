"""WebSocket handlers — extracted from main.py for modularity.

Handles: /api/v1/solve (Smart Solve dual-loop), /ws/metrics (broadcast)
"""

import asyncio
import contextlib
import logging
import time
import uuid

from fastapi import WebSocket, WebSocketDisconnect

from app import state

logger = logging.getLogger(__name__)

_metrics_history: list = []


async def _run_solve_pipeline_for_message(ws: WebSocket, data: dict, state) -> None:
    import time as _t

    query = data.get("query", "")
    if not query.strip():
        await ws.send_json(
            {
                "type": "error",
                "error": "empty_query",
                "message": "Query cannot be empty.",
            }
        )
        return

    from app.services.security import safe_name as _safe_name

    session_id = _safe_name(
        data.get("session_id", f"solve_{int(_t.time())}"),
        default=f"solve_{int(_t.time())}",
        max_len=64,
    )
    kb_name = _safe_name(data.get("kb_name", ""), default="")
    mode = data.get("mode", "auto")
    retrieval_pipeline = data.get("retrieval_pipeline", "tree")
    device_id = data["device_id"]

    await ws.send_json(
        {
            "type": "agent_step",
            "agent": "investigate",
            "content": f"Analyzing query: {query[:100]}...",
            "timestamp": _t.time(),
        }
    )

    lm_ok = await state.lm_client.check_health()
    if lm_ok:
        from app.services.recursive_solver import RecursiveSolver
        from app.services.solve_orchestrator import run_solve_pipeline

        if mode == "recursive" or (mode == "auto" and "recursive" in query.lower()):
            solver = RecursiveSolver(state.lm_client)
            from app.services.complexity_scorer import score_query_complexity

            score, target_tier = score_query_complexity(query)
            pattern = solver.select_pattern(query, score)

            await ws.send_json(
                {
                    "type": "agent_step",
                    "agent": "system",
                    "content": f"[RecursiveMAS Activated: {pattern} pattern]\n",
                    "timestamp": _t.time(),
                }
            )

            context = ""
            if kb_name:
                from app.routers.retrieval import RetrieveRequest
                from app.routers.retrieval import retrieve as run_retrieval

                req = RetrieveRequest(
                    query=query,
                    kb_name=kb_name,
                    retrieval_pipeline=retrieval_pipeline,
                    top_k=3,
                )
                retrieval_resp = await run_retrieval(req)
                rag_results = retrieval_resp.get("results", [])
                if rag_results:
                    for i, res in enumerate(rag_results):
                        context += f"--- Chunk {i + 1} ---\n{res.get('content', '')}\n\n"

            memory_context = ""
            if state.memory_service:
                try:
                    from app.services.memory_context import build_memory_context

                    recall = await state.memory_service.recall_episodes(device_id, query)
                    facts = await state.memory_service.recall_facts(device_id, query)
                    profile = await state.memory_service.get_profile(device_id)
                    memory_context = build_memory_context(profile, recall, facts)
                except Exception as e:
                    logger.warning(f"Memory recall failed: {e}")

            if memory_context:
                context = f"{memory_context}\n\n{context}" if context else memory_context

            model_id = (
                await state.model_manager.get_best_available_model(target_tier)
                or "Qwen3-1.7B-Q4_K_M"
            )
            result = await solver.solve(
                query=query,
                context=context,
                pattern=pattern,
                model_id=model_id,
                ws_send=ws.send_json,
            )

            await ws.send_json(
                {
                    "type": "complete",
                    "answer": result.answer,
                    "citations": [],
                    "session_id": session_id,
                    "solve_dir": f"data/user/solve/{session_id}",
                    "metadata": {
                        "pattern": result.pattern,
                        "rounds_used": result.rounds_used,
                        "converged": result.converged,
                        "token_savings_pct": result.token_savings_pct,
                        "elapsed_seconds": result.elapsed_seconds,
                    },
                }
            )
        else:
            memory_context = ""
            if state.memory_service:
                try:
                    from app.services.memory_context import build_memory_context

                    recall = await state.memory_service.recall_episodes(device_id, query)
                    facts = await state.memory_service.recall_facts(device_id, query)
                    profile = await state.memory_service.get_profile(device_id)
                    memory_context = build_memory_context(profile, recall, facts)
                except Exception as e:
                    logger.warning(f"Memory recall failed: {e}")

            await run_solve_pipeline(
                query=query,
                kb_name=kb_name,
                mode=mode,
                retrieval_pipeline=retrieval_pipeline,
                lm_client=state.lm_client,
                model_manager=state.model_manager,
                session_id=session_id,
                ws_send=ws.send_json,
                device_id=device_id,
                memory_context=memory_context,
            )
        return

    steps = [
        ("note", f"No knowledge base loaded. Query: {query[:80]}"),
        ("plan", "Structuring response..."),
        ("solve", "Generating answer..."),
        ("check", "Validating accuracy..."),
        ("format", "Polishing output..."),
    ]
    full_answer = ""
    for label, content in steps:
        await ws.send_json(
            {
                "type": "agent_step",
                "agent": label,
                "content": content,
                "timestamp": _t.time(),
            }
        )
        await asyncio.sleep(0.3)
        full_answer += f"{content}\n\n"

    await ws.send_json(
        {
            "type": "complete",
            "answer": full_answer.strip()
            + "\n\n— *Connect LM Studio at localhost:1234 for real multi-agent reasoning.*",
            "citations": [],
            "session_id": session_id,
            "solve_dir": f"data/user/solve/{session_id}",
        }
    )


async def _watch_ws_disconnect(ws: WebSocket) -> None:
    await ws.receive()


async def ws_solve(ws: WebSocket):
    from app.config import get_settings
    from app.services.security import safe_compare

    settings = get_settings()
    token = ws.query_params.get("token")
    if settings.ws_auth_token and not safe_compare(token, settings.ws_auth_token):
        client = ws.client.host if ws.client else "unknown"
        logger.warning("ws_auth_failure: endpoint=/api/v1/solve remote=%s", client)
        from app.services.audit import audit

        audit("auth.ws_failure", endpoint="/api/v1/solve", remote=client)
        await ws.close(code=1008, reason="Unauthorized")
        return

    await ws.accept()
    device_id = str(uuid.uuid4())
    in_flight: asyncio.Task | None = None
    from app.services.metrics import ACTIVE_WS_CONNECTIONS

    ACTIVE_WS_CONNECTIONS.inc()
    try:
        while True:
            try:
                data = await ws.receive_json()
                data["device_id"] = device_id

                if in_flight is not None and not in_flight.done():
                    in_flight.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await in_flight
                    in_flight = None

                in_flight = asyncio.create_task(_run_solve_pipeline_for_message(ws, data, state))
                try:
                    await in_flight
                finally:
                    in_flight = None
            except WebSocketDisconnect:
                raise
            except Exception as e:
                logger.error(f"Solve pipeline error: {e}", exc_info=True)
                try:
                    await ws.send_json(
                        {
                            "type": "error",
                            "error": "pipeline_failure",
                            "message": "An internal error occurred while solving. Please try again.",
                            "timestamp": time.time(),
                        }
                    )
                except Exception as send_err:
                    logger.warning(f"Solve WS error frame send failed: {send_err}")
                    return
                continue
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Solve WS error: {e}", exc_info=True)
    finally:
        if in_flight is not None and not in_flight.done():
            in_flight.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await in_flight
        ACTIVE_WS_CONNECTIONS.dec()


async def ws_metrics(ws: WebSocket):
    from app.config import get_settings
    from app.services.security import safe_compare

    settings = get_settings()
    token = ws.query_params.get("token")
    if settings.ws_auth_token and not safe_compare(token, settings.ws_auth_token):
        client = ws.client.host if ws.client else "unknown"
        logger.warning("ws_auth_failure: endpoint=/ws/metrics remote=%s", client)
        from app.services.audit import audit

        audit("auth.ws_failure", endpoint="/ws/metrics", remote=client)
        await ws.close(code=1008, reason="Unauthorized")
        return

    await ws.accept()
    # Send initial metrics frame immediately so client doesn't wait
    try:
        await ws.send_json(dict(state._latest_metrics))
    except Exception as e:
        logger.warning(f"Failed to send initial metrics frame: {e}")
        await ws.close()
        return
    state.add_ws(ws)
    from app.services.metrics import ACTIVE_WS_CONNECTIONS

    ACTIVE_WS_CONNECTIONS.inc()
    try:
        while True:
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        state.remove_ws(ws)
        ACTIVE_WS_CONNECTIONS.dec()


async def broadcast_loop():
    global _metrics_history
    while True:
        await asyncio.sleep(2.0)
        dead = []
        for ws in list(state._metrics_ws):
            try:
                await ws.send_json(dict(state._latest_metrics))
            except Exception:
                dead.append(ws)
        for ws in dead:
            state._metrics_ws.discard(ws)
        _metrics_history.append(dict(state._latest_metrics))
        if len(_metrics_history) > 30:
            _metrics_history = _metrics_history[-30:]
        from app.routers import system as sm

        sm._metrics_history = _metrics_history


async def ttl_loop():
    while True:
        await asyncio.sleep(60)
        evicted = state.model_manager.check_ttl_evictions()
        if evicted:
            logger.info(f"TTL evictions: {evicted}")
        try:
            from app.services.alerting import check_alerts

            await check_alerts()
        except Exception as e:
            logger.debug(f"Alert check failed (non-fatal): {e}")
        if not ttl_loop._last_cleanup or (time.time() - ttl_loop._last_cleanup > 86400):
            ttl_loop._last_cleanup = time.time()
            try:
                from app.services.session_cleanup import run_cleanup

                result = run_cleanup()
                if result.deleted_files or result.deleted_dirs:
                    logger.info(
                        f"Periodic cleanup removed {result.deleted_files} "
                        f"files, {result.deleted_dirs} dirs"
                    )
            except Exception as e:
                logger.warning(f"Periodic session cleanup failed: {e}")


ttl_loop._last_cleanup = 0.0
