import os
import json
import time
import asyncio
import logging
from typing import Dict, Any, List

from app.services.lm_studio_client import LMStudioClient
from app.routers.retrieval import retrieve as run_retrieval, RetrieveRequest

logger = logging.getLogger(__name__)

class DeepResearchService:
    def __init__(self, lm_client: LMStudioClient):
        self.lm_client = lm_client
        self.sessions_dir = "data/user/research"
        os.makedirs(self.sessions_dir, exist_ok=True)
        # We store active background tasks here so they don't get garbage collected
        self.active_tasks = set()
        self._locks: Dict[str, asyncio.Lock] = {}

    def _get_lock(self, session_id: str) -> asyncio.Lock:
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        return self._locks[session_id]

    def _get_session_path(self, session_id: str) -> str:
        return os.path.join(self.sessions_dir, f"session_{session_id}.json")

    def _load_session(self, session_id: str) -> Dict[str, Any]:
        path = self._get_session_path(session_id)
        if not os.path.exists(path):
            raise ValueError(f"Session {session_id} not found.")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load deep research session {session_id}: {e}")
            raise

    def _save_session(self, session_id: str, data: Dict[str, Any]):
        path = self._get_session_path(session_id)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logger.error(f"Failed to save deep research session {session_id}: {e}")
            raise

    async def start_research(
        self, kb_name: str, query: str, mode: str = "parallel", retrieval_pipeline: str = "combined", model_id: str = "Qwen3-1.7B-Q4_K_M", device_id: str = ""
    ) -> str:
        """Phase 1: Planning. Returns session_id immediately and starts background research."""
        session_id = f"research_{int(time.time())}"
        
        # 1. Rephrase & Decompose
        system_prompt = (
            "You are the DecomposeAgent for a Deep Research system.\n"
            "Analyze the user's research query and break it down into 3 to 5 distinct, focused subtopics.\n"
            "Return a raw JSON array of strings, where each string is a subtopic query.\n"
            "Do not include markdown blocks or any other text."
        )

        response = await self.lm_client.stream_chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Research Query: {query}"}
            ],
            max_tokens=1000
        )
        
        content = response.get("content", "").strip()
        if content.startswith("```json"): content = content[7:]
        if content.startswith("```"): content = content[3:]
        if content.endswith("```"): content = content[:-3]
        content = content.strip()

        try:
            subtopics = json.loads(content)
            if not isinstance(subtopics, list):
                subtopics = [f"Overview of {query}", f"Key details of {query}"]
        except Exception:
            subtopics = [f"Overview of {query}", f"Key details of {query}"]

        # 2. Initialize State
        queue = [{"id": f"sub_{i}", "query": st, "status": "PENDING", "notes": ""} for i, st in enumerate(subtopics)]
        
        session_data = {
            "session_id": session_id,
            "query": query,
            "kb_name": kb_name,
            "retrieval_pipeline": retrieval_pipeline,
            "model_id": model_id,
            "mode": mode,
            "queue": queue,
            "status": "RESEARCHING",
            "final_report": None
        }
        await asyncio.to_thread(self._save_session, session_id, session_data)

        from app import state
        if state.memory_service and device_id:
            try:
                await state.memory_service.store_episode(
                    device_id=device_id, query=query, answer="",
                    agents=["decompose", "research", "note", "report"],
                    model_used=model_id, session_type="research",
                )
            except Exception:
                pass

        # 3. Kick off Phase 2 in the background
        task = asyncio.create_task(self._process_queue(session_id, device_id))
        self.active_tasks.add(task)
        # Update Prometheus gauge
        try:
            from app.services.metrics import DEEP_RESEARCH_ACTIVE
            DEEP_RESEARCH_ACTIVE.set(len(self.active_tasks))
        except Exception:
            pass

        def _on_done(t):
            self.active_tasks.discard(t)
            try:
                from app.services.metrics import DEEP_RESEARCH_ACTIVE
                DEEP_RESEARCH_ACTIVE.set(len(self.active_tasks))
            except Exception:
                pass

        task.add_done_callback(_on_done)
        # Also register with the app-level background task set so the
        # lifespan shutdown handler can cancel and await it. This is
        # a no-op if state isn't importable (e.g. in unit tests).
        try:
            from app import state as _state
            _state.track_background_task(task)
        except Exception:
            pass

        return session_id

    async def _process_queue(self, session_id: str, device_id: str = ""):
        """Phase 2: Researching. Processes the subtopic queue.

        Wraps the whole phase in a try/except so a fatal failure
        (missing session, corrupt JSON, etc.) is recorded in the
        session file as FAILED rather than disappearing into the
        asyncio task graveyard — callers polling ``get_status``
        would otherwise see the session stuck in RESEARCHING forever.
        """
        from app.services.telemetry import trace_span
        try:
            session_data = await asyncio.to_thread(self._load_session, session_id)
            mode = session_data.get("mode", "parallel")
            queue = session_data["queue"]

            with trace_span("deep_research.process_queue", {
                "session_id": session_id,
                "mode": mode,
                "subtopic_count": len(queue),
            }):
                if mode == "parallel":
                    # Process up to 5 concurrently
                    sem = asyncio.Semaphore(5)

                    async def bounded_research(subtopic):
                        async with sem:
                            await self._research_subtopic(session_id, subtopic["id"], device_id)

                    tasks = [bounded_research(st) for st in queue]
                    await asyncio.gather(*tasks)
                else:
                    # Series
                    for st in queue:
                        await self._research_subtopic(session_id, st["id"], device_id)

            # Phase 3: Reporting
            with trace_span("deep_research.generate_report", {"session_id": session_id}):
                await self._generate_report(session_id, device_id)
        except Exception as e:
            logger.error(f"Deep research task {session_id} failed: {e}", exc_info=True)
            # Best-effort: record the failure on the session file so
            # the polling endpoint surfaces it. If _save_session itself
            # fails, we still log the error.
            try:
                async with self._get_lock(session_id):
                    session_data = await asyncio.to_thread(self._load_session, session_id)
                    session_data["status"] = "FAILED"
                    session_data["error"] = f"{type(e).__name__}: {e}"
                    await asyncio.to_thread(self._save_session, session_id, session_data)
            except Exception as inner:
                logger.error(f"Could not record FAILED status for {session_id}: {inner}")

    async def _research_subtopic(self, session_id: str, subtopic_id: str, device_id: str = ""):
        """ResearchAgent + NoteAgent: Retrieves context and synthesizes notes for one subtopic."""
        async with self._get_lock(session_id):
            session_data = await asyncio.to_thread(self._load_session, session_id)

            # Find the subtopic
            subtopic = next((st for st in session_data["queue"] if st["id"] == subtopic_id), None)
            if not subtopic: return

            # Update status
            subtopic["status"] = "RESEARCHING"
            await asyncio.to_thread(self._save_session, session_id, session_data)

            kb_name = session_data["kb_name"]
            retrieval_pipeline = session_data["retrieval_pipeline"]
            model_id = session_data["model_id"]
            topic_query = subtopic["query"]

        # 1. Retrieval
        try:
            req = RetrieveRequest(
                query=topic_query, 
                kb_name=kb_name, 
                retrieval_pipeline=retrieval_pipeline, 
                top_k=5
            )
            retrieval_resp = await run_retrieval(req)
            rag_results = retrieval_resp.get("results", [])
            
            context_text = ""
            for i, res in enumerate(rag_results):
                content = res.get('content', '') or res.get('summary', '')
                doc_id = res.get('doc_id', 'unknown')
                page = res.get('page', 'unknown')
                context_text += f"--- Source {i+1} [Doc: {doc_id}, Page: {page}] ---\n{content}\n\n"

            if not context_text.strip():
                context_text = "No document context available."

            # 2. NoteAgent Synthesizes
            system_prompt = (
                "You are the NoteAgent. Review the context below and write concise, well-structured notes "
                "addressing the specific subtopic query. Include source citations where possible."
            )
            
            response = await self.lm_client.stream_chat_completion(
                model=model_id,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Subtopic: {topic_query}\n\nContext:\n{context_text}"}
                ],
                max_tokens=1500
            )
            
            notes = response.get("content", "Failed to generate notes.")
            subtopic["status"] = "COMPLETED"
            subtopic["notes"] = notes

        except Exception as e:
            logger.error(f"Error researching subtopic {subtopic_id}: {e}")
            subtopic["status"] = "FAILED"
            subtopic["notes"] = f"Error: {str(e)}"

        # Reload and save to avoid race conditions in parallel mode
        async with self._get_lock(session_id):
            current_data = await asyncio.to_thread(self._load_session, session_id)
            for st in current_data["queue"]:
                if st["id"] == subtopic_id:
                    st["status"] = subtopic["status"]
                    st["notes"] = subtopic["notes"]
                    break
            await asyncio.to_thread(self._save_session, session_id, current_data)

            from app import state
            if state.memory_service and device_id:
                try:
                    quality = 0.8 if subtopic["status"] == "COMPLETED" else 0.2
                    await state.memory_service.record_agent_outcome(
                        agent_type="research", query_pattern=topic_query[:100],
                        strategy="retrieval_synthesis", outcome_quality=quality,
                        model_used=model_id, device_id=device_id,
                    )
                except Exception:
                    pass


    async def _generate_report(self, session_id: str, device_id: str = ""):
        """Phase 3: Reporting. Aggregates notes into a final report."""
        session_data = await asyncio.to_thread(self._load_session, session_id)
        model_id = session_data["model_id"]
        main_query = session_data["query"]

        all_notes = ""
        for st in session_data["queue"]:
            if st["status"] == "COMPLETED":
                all_notes += f"### {st['query']}\n{st['notes']}\n\n"

        system_prompt = (
            "You are the ReportAgent. Compile the provided research notes into a final, comprehensive Markdown report.\n"
            "Structure it with an Introduction, Body Paragraphs based on the subtopics, and a Conclusion.\n"
            "Ensure citations from the notes are preserved."
        )

        user_prompt = f"Main Research Query: {main_query}\n\nAggregated Notes:\n{all_notes}"

        response = await self.lm_client.stream_chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=4000
        )
        
        final_report = response.get("content", "Failed to generate report.")
        
        async with self._get_lock(session_id):
            session_data = await asyncio.to_thread(self._load_session, session_id)
            session_data["final_report"] = final_report
            session_data["status"] = "COMPLETED"
            await asyncio.to_thread(self._save_session, session_id, session_data)

        from app import state
        if state.memory_service and device_id:
            try:
                await state.memory_service.store_episode(
                    device_id=device_id, query=main_query, answer=final_report,
                    agents=["decompose", "research", "note", "report"],
                    model_used=model_id, session_type="research",
                )
                from app.services.fact_extractor import extract_and_store_facts
                asyncio.create_task(extract_and_store_facts(
                    device_id=device_id, query=main_query, answer=final_report,
                    source_id=session_id, lm_client=self.lm_client,
                    memory_service=state.memory_service,
                ))
            except Exception:
                pass

    def get_status(self, session_id: str) -> Dict[str, Any]:
        """Returns the current state of the research session."""
        return self._load_session(session_id)
