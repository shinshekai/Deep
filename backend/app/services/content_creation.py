import os
import json
import time
import logging
import asyncio
from typing import Dict, Any, List, Optional

from app.services.lm_studio_client import LMStudioClient
from app.services.retrieval_service import retrieve as run_retrieval, RetrieveRequest
from app.services.task_registry import _global_registry

logger = logging.getLogger(__name__)

class NotebookService:
    def __init__(self):
        self.notebooks_dir = "data/user/notebooks"
        os.makedirs(self.notebooks_dir, exist_ok=True)

    def _get_path(self, notebook_id: str) -> str:
        return os.path.join(self.notebooks_dir, f"{notebook_id}.json")

    def create_notebook(self, title: str, description: str = "", device_id: str = "") -> Dict[str, Any]:
        nb_id = f"nb_{int(time.time())}"
        data = {
            "id": nb_id,
            "title": title,
            "description": description,
            "notes": [],
            "created_at": time.time(),
            "updated_at": time.time()
        }
        try:
            with open(self._get_path(nb_id), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logger.error(f"Failed to create notebook {nb_id}: {e}")
            raise
        from app import state
        if state.memory_service and device_id:
            try:
                _global_registry.spawn(state.memory_service.store_episode(
                    device_id=device_id, query=f"Create notebook: {title}", answer="",
                    agents=["content_creator"], session_type="content",
                ))
            except Exception:
                pass
        return data

    def list_notebooks(self) -> List[Dict[str, Any]]:
        notebooks = []
        try:
            entries = os.listdir(self.notebooks_dir)
        except OSError as e:
            logger.error(f"Failed to list notebooks directory: {e}")
            return notebooks
        for filename in entries:
            if not filename.endswith(".json"):
                continue
            path = os.path.join(self.notebooks_dir, filename)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    notebooks.append(json.load(f))
            except (OSError, json.JSONDecodeError) as e:
                # Skip corrupted files but keep going so one bad apple
                # doesn't sink the entire list endpoint.
                logger.warning(f"Skipping unreadable notebook {path}: {e}")
                continue
        return notebooks

    def get_notebook(self, notebook_id: str) -> Dict[str, Any]:
        path = self._get_path(notebook_id)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Notebook {notebook_id} not found.")
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Notebook {notebook_id} is corrupted: {e}")
            raise ValueError(f"Notebook {notebook_id} is corrupted.") from e

    def add_note(self, notebook_id: str, content: str, source: str = "manual", device_id: str = "") -> Dict[str, Any]:
        data = self.get_notebook(notebook_id)
        note = {
            "id": f"note_{int(time.time()*1000)}",
            "content": content,
            "source": source,
            "timestamp": time.time()
        }
        data["notes"].append(note)
        data["updated_at"] = time.time()
        try:
            with open(self._get_path(notebook_id), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except OSError as e:
            logger.error(f"Failed to persist note for {notebook_id}: {e}")
            raise
        from app import state
        if state.memory_service and device_id:
            try:
                _global_registry.spawn(state.memory_service.store_fact(
                    device_id=device_id,
                    content=f"Note '{content[:50]}': {content[:200]}",
                    source_type="note",
                    source_id=note["id"],
                    confidence=0.6,
                ))
            except Exception:
                pass
        return note

class CoWriterService:
    def __init__(self, lm_client: LMStudioClient):
        self.lm_client = lm_client

    async def edit_text(self, text: str, action: str, instruction: str = "", model_id: str = "Qwen3-1.7B-Q4_K_M") -> dict:
        """Actions: rewrite, shorten, expand. Returns {text, provenance}."""
        system_prompt = "You are an expert AI Co-Writer. Your goal is to improve and edit the user's text based on their instructions."
        
        if action == "shorten":
            user_prompt = f"Please rewrite the following text to be more concise and shorter, keeping the core meaning:\n\n{text}"
        elif action == "expand":
            user_prompt = f"Please expand the following text, adding more detail and elaboration while maintaining the original tone:\n\n{text}"
        elif action == "rewrite":
            user_prompt = f"Please rewrite the following text according to this instruction: '{instruction}'\n\nText:\n{text}"
        else:
            return {"text": text, "provenance": {"action": action, "model": model_id, "sources": []}}

        response = await self.lm_client.stream_chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=2000
        )
        result_text = response.get("content", text).strip()
        return {
            "text": result_text,
            "provenance": {
                "action": action,
                "model": model_id,
                "timestamp": time.time(),
                "sources": [],
            }
        }

    async def auto_annotate(self, text: str, kb_name: str, retrieval_pipeline: str = "tree", model_id: str = "Qwen3-1.7B-Q4_K_M") -> dict:
        """Suggests annotations/citations based on the Knowledge Base. Returns {text, provenance}."""
        req = RetrieveRequest(query=text, kb_name=kb_name, retrieval_pipeline=retrieval_pipeline, top_k=3)
        retrieval_resp = await run_retrieval(req)
        rag_results = retrieval_resp.get("results", [])
        
        # Collect provenance sources
        provenance_sources = []
        context_text = ""
        for i, res in enumerate(rag_results):
            content = res.get('content', '') or res.get('summary', '')
            doc_id = res.get('doc_id', 'unknown')
            page = res.get('page', 'unknown')
            score = res.get('relevance_score', 0)
            context_text += f"--- Source {i+1} ---\n{content}\n\n"
            provenance_sources.append({
                "doc_id": doc_id,
                "page": page,
                "relevance_score": score,
                "snippet": content[:200] if content else "",
            })

        system_prompt = (
            "You are an annotation assistant. Review the user's text and the provided Knowledge Base context. "
            "Insert relevant [Citation X] markers into the user's text where the context supports it, "
            "and append a References section at the end detailing the citations."
        )

        user_prompt = f"Context:\n{context_text}\n\nUser Text:\n{text}"

        response = await self.lm_client.stream_chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=2000
        )
        result_text = response.get("content", text).strip()
        return {
            "text": result_text,
            "provenance": {
                "action": "annotate",
                "model": model_id,
                "kb_name": kb_name,
                "retrieval_pipeline": retrieval_pipeline,
                "timestamp": time.time(),
                "sources": provenance_sources,
            }
        }


class IdeaGenService:
    def __init__(self, lm_client: LMStudioClient, notebook_service: NotebookService):
        self.lm_client = lm_client
        self.notebook_service = notebook_service

    async def generate_ideas(self, notebook_ids: List[str], model_id: str = "Qwen3-1.7B-Q4_K_M") -> List[str]:
        # Stage 1: Extraction
        all_notes = ""
        for nb_id in notebook_ids:
            try:
                nb = await asyncio.to_thread(self.notebook_service.get_notebook, nb_id)
                for note in nb.get("notes", []):
                    all_notes += f"- {note['content']}\n"
            except Exception as e:
                logger.error(f"Error reading notebook {nb_id}: {e}")

        if not all_notes.strip():
            return ["No notebook content found to generate ideas from."]

        # Stage 2 & 3: Synthesis and Proposal
        system_prompt = (
            "You are an expert Idea Generator. Analyze the provided notebook contents. "
            "Connect disparate concepts and synthesize 3 to 5 novel research directions or project ideas.\n"
            "Return ONLY a raw JSON array of strings, where each string is a detailed idea paragraph."
        )

        user_prompt = f"Notebook Contents:\n{all_notes}\n\nGenerate the JSON array of ideas:"

        response = await self.lm_client.stream_chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=2000
        )
        
        content = response.get("content", "").strip()
        if content.startswith("```json"): content = content[7:]
        if content.startswith("```"): content = content[3:]
        if content.endswith("```"): content = content[:-3]
        content = content.strip()

        try:
            ideas = json.loads(content)
            if isinstance(ideas, list):
                return ideas
        except Exception:
            pass
            
        return ["Failed to generate structured ideas. Please try again or add more notes."]
