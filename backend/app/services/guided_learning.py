import os
import json
import time
import logging
import asyncio
from typing import Dict, Any, List

from app.services.lm_studio_client import LMStudioClient
from app.routers.retrieval import retrieve as run_retrieval, RetrieveRequest

logger = logging.getLogger(__name__)

class GuidedLearningService:
    def __init__(self, lm_client: LMStudioClient):
        self.lm_client = lm_client
        self.sessions_dir = "data/user/guide"
        os.makedirs(self.sessions_dir, exist_ok=True)

    def _get_session_path(self, session_id: str) -> str:
        return os.path.join(self.sessions_dir, f"session_{session_id}.json")

    def _load_session(self, session_id: str) -> Dict[str, Any]:
        path = self._get_session_path(session_id)
        if not os.path.exists(path):
            raise ValueError(f"Session {session_id} not found.")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_session(self, session_id: str, data: Dict[str, Any]):
        path = self._get_session_path(session_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    async def start_session(
        self, kb_name: str, topic: str, retrieval_pipeline: str = "tree", model_id: str = "Qwen3-1.7B-Q4_K_M", device_id: str = ""
    ) -> Dict[str, Any]:
        """LocateAgent: Identifies 3-5 progressive knowledge points and initializes session."""
        session_id = f"learn_{int(time.time())}"
        
        # 1. Retrieve Context
        req = RetrieveRequest(
            query=topic, 
            kb_name=kb_name, 
            retrieval_pipeline=retrieval_pipeline, 
            top_k=5
        )
        retrieval_resp = await run_retrieval(req)
        rag_results = retrieval_resp.get("results", [])
        
        context_text = ""
        for i, res in enumerate(rag_results):
            content = res.get('content', '') or res.get('summary', '')
            context_text += f"--- Source {i+1} ---\n{content}\n\n"

        if not context_text.strip():
            context_text = "No document context available. Rely on internal knowledge."

        # 2. LocateAgent Generation
        system_prompt = (
            "You are the LocateAgent for a Guided Learning system.\n"
            "Analyze the topic and context, then generate a progressive learning plan consisting of 3 to 5 knowledge points.\n"
            "Return a raw JSON array of strings, where each string is a knowledge point title/description.\n"
            "Do not include markdown blocks or any other text."
        )

        user_prompt = f"Topic: {topic}\n\nContext:\n{context_text}\n\nReturn the JSON array of 3-5 knowledge points:"

        response = await self.lm_client.stream_chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=1000
        )
        
        content = response.get("content", "").strip()
        if content.startswith("```json"): content = content[7:]
        if content.startswith("```"): content = content[3:]
        if content.endswith("```"): content = content[:-3]
        content = content.strip()

        try:
            points = json.loads(content)
            if not isinstance(points, list):
                points = [f"Introduction to {topic}", f"Core concepts of {topic}", f"Summary of {topic}"]
        except Exception:
            points = [f"Introduction to {topic}", f"Core concepts of {topic}", f"Summary of {topic}"]

        # 3. Initialize Session
        session_data = {
            "session_id": session_id,
            "topic": topic,
            "kb_name": kb_name,
            "context_snapshot": context_text,
            "points": points,
            "current_point_index": 0,
            "chat_history": [],
            "pages": {},
            "status": "active"
        }
        await asyncio.to_thread(self._save_session, session_id, session_data)

        # Memory: store learning episode and update profile
        from app import state
        if state.memory_service and device_id:
            try:
                await state.memory_service.store_episode(
                    device_id=device_id, query=topic, answer="",
                    agents=["locate", "interactive", "chat"],
                    model_used=model_id, session_type="learning",
                )
                await state.memory_service.update_profile(device_id, {
                    "type": "learning_started", "topic": topic, "kb_name": kb_name,
                })
            except Exception:
                pass

        return session_data

    async def generate_interactive_page(self, session_id: str, point_index: int, model_id: str = "Qwen3-1.7B-Q4_K_M", device_id: str = "") -> str:
        """InteractiveAgent: Generates rich HTML learning material for a point."""
        session_data = await asyncio.to_thread(self._load_session, session_id)
        
        if point_index < 0 or point_index >= len(session_data["points"]):
            raise ValueError("Invalid point index.")
            
        point_title = session_data["points"][point_index]
        context_text = session_data["context_snapshot"]

        # Check if already generated
        if str(point_index) in session_data["pages"]:
            return session_data["pages"][str(point_index)]

        system_prompt = (
            "You are the InteractiveAgent. Your task is to generate an interactive, engaging HTML learning page for a specific knowledge point.\n"
            "Use visual aids (CSS-styled divs, emojis, structured layouts), step-by-step breakdowns, and clear explanations.\n"
            "Return ONLY raw HTML. Do NOT include ```html markdown wrappers. Start directly with <div> or <h1>."
        )

        user_prompt = (
            f"Topic Context:\n{context_text}\n\n"
            f"Generate the HTML learning page for this specific knowledge point:\n"
            f"**{point_title}**\n\n"
            f"Output the raw HTML:"
        )

        response = await self.lm_client.stream_chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=4000
        )
        
        html_content = response.get("content", "<div>Error generating content.</div>").strip()
        if html_content.startswith("```html"): html_content = html_content[7:]
        if html_content.startswith("```"): html_content = html_content[3:]
        if html_content.endswith("```"): html_content = html_content[:-3]
        html_content = html_content.strip()

        session_data["pages"][str(point_index)] = html_content
        session_data["current_point_index"] = point_index
        await asyncio.to_thread(self._save_session, session_id, session_data)

        # Memory: record agent outcome
        from app import state
        if state.memory_service and device_id:
            try:
                await state.memory_service.record_agent_outcome(
                    agent_type="learning", query_pattern=point_title[:100],
                    strategy="interactive_generation", outcome_quality=0.7,
                    model_used=model_id, device_id=device_id,
                )
            except Exception:
                pass

        return html_content

    async def chat(self, session_id: str, point_index: int, user_message: str, model_id: str = "Qwen3-1.7B-Q4_K_M", device_id: str = "") -> str:
        """ChatAgent: Contextual Q&A within a specific learning point."""
        session_data = await asyncio.to_thread(self._load_session, session_id)
        point_title = session_data["points"][point_index]
        context_text = session_data["context_snapshot"]
        
        # Append user message
        session_data["chat_history"].append({"role": "user", "content": user_message, "point_index": point_index})
        
        # Build history for this point
        history_msgs = [
            {"role": msg["role"], "content": msg["content"]} 
            for msg in session_data["chat_history"] 
            if msg.get("point_index") == point_index
        ][-5:] # Keep last 5 turns for context limit

        system_prompt = (
            "You are the ChatAgent, a helpful tutor. You are currently teaching the student about: "
            f"{point_title}.\n"
            "Answer the student's questions grounded in the overall topic context.\n"
            "Be encouraging, concise, and pedagogical."
        )

        messages = [{"role": "system", "content": f"{system_prompt}\n\nContext:\n{context_text}"}]
        messages.extend(history_msgs)

        response = await self.lm_client.stream_chat_completion(
            model=model_id,
            messages=messages,
            max_tokens=1000
        )
        
        answer = response.get("content", "I am unable to process that right now.")
        
        # Memory: extract learning facts
        from app import state
        if state.memory_service and device_id:
            try:
                from app.services.fact_extractor import extract_and_store_facts
                asyncio.create_task(extract_and_store_facts(
                    device_id=device_id, query=user_message, answer=answer,
                    source_id=session_id, lm_client=self.lm_client,
                    memory_service=state.memory_service,
                ))
            except Exception:
                pass
        
        # Append assistant message
        session_data["chat_history"].append({"role": "assistant", "content": answer, "point_index": point_index})
        await asyncio.to_thread(self._save_session, session_id, session_data)
        
        return answer

    async def end_session(self, session_id: str, model_id: str = "Qwen3-1.7B-Q4_K_M") -> Dict[str, Any]:
        """SummaryAgent: Concludes the session and generates a learning summary."""
        session_data = await asyncio.to_thread(self._load_session, session_id)
        session_data["status"] = "completed"

        system_prompt = (
            "You are the SummaryAgent. Review the learning session (topic, knowledge points, and chat history) "
            "and produce a concise summary of what was learned, along with encouraging next steps.\n"
            "Return a raw JSON object with keys: 'summary' (string), 'next_steps' (array of strings)."
        )

        chat_history_text = "\n".join([f"{m['role']}: {m['content']}" for m in session_data["chat_history"]])
        
        user_prompt = (
            f"Topic: {session_data['topic']}\n"
            f"Knowledge Points Covered: {', '.join(session_data['points'])}\n"
            f"Chat History:\n{chat_history_text}\n\n"
            f"Generate the JSON summary:"
        )

        response = await self.lm_client.stream_chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=1000
        )
        
        content = response.get("content", "").strip()
        if content.startswith("```json"): content = content[7:]
        if content.startswith("```"): content = content[3:]
        if content.endswith("```"): content = content[:-3]
        content = content.strip()

        try:
            summary_obj = json.loads(content)
        except Exception:
            summary_obj = {
                "summary": "You have completed the learning session.",
                "next_steps": ["Review the notes", "Practice what you learned"]
            }

        session_data["final_summary"] = summary_obj
        await asyncio.to_thread(self._save_session, session_id, session_data)

        return summary_obj
