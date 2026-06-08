import json
import logging
from typing import Any

from app.services.lm_studio_client import LMStudioClient
from app.services.retrieval_service import RetrieveRequest
from app.services.retrieval_service import retrieve as run_retrieval

logger = logging.getLogger(__name__)


class QuestionGenService:
    def __init__(self, lm_client: LMStudioClient):
        self.lm_client = lm_client

    async def generate_questions(
        self,
        kb_name: str,
        topic: str,
        count: int = 5,
        difficulty: str = "medium",
        question_type: str = "multiple_choice",
        mode: str = "custom",
        reference_text: str | None = None,
        retrieval_pipeline: str = "tree",
        model_id: str = "Qwen3-1.7B-Q4_K_M",
    ) -> list[dict[str, Any]]:
        """Generate validated questions based on KB content."""

        # 1. Retrieve Context
        req = RetrieveRequest(
            query=topic, kb_name=kb_name, retrieval_pipeline=retrieval_pipeline, top_k=5
        )
        retrieval_resp = await run_retrieval(req)
        rag_results = retrieval_resp.get("results", [])

        context_text = ""
        for i, res in enumerate(rag_results):
            content = res.get("content", "") or res.get("summary", "")
            doc_id = res.get("doc_id", "unknown")
            page = res.get("page", "unknown")
            context_text += f"--- Source {i + 1} [Doc: {doc_id}, Page: {page}] ---\n{content}\n\n"

        if not context_text.strip():
            logger.warning(
                f"No context found in KB '{kb_name}' for topic '{topic}'. Using LLM internal knowledge."
            )
            context_text = "No document context available. Rely on internal knowledge."

        # 2. GeneratorAgent Drafts Questions
        draft_questions = await self._draft_questions(
            topic=topic,
            context=context_text,
            count=count,
            difficulty=difficulty,
            question_type=question_type,
            mode=mode,
            reference_text=reference_text,
            model_id=model_id,
        )

        if not draft_questions:
            return []

        # 3. ValidatorAgent Reviews Questions
        valid_questions = await self._validate_questions(
            draft_questions=draft_questions,
            context=context_text,
            difficulty=difficulty,
            model_id=model_id,
        )

        # 4. Inject Citations if missing
        # We can map back to rag_results roughly, but for now just pass through what Validator returned.
        return valid_questions

    async def _draft_questions(
        self,
        topic: str,
        context: str,
        count: int,
        difficulty: str,
        question_type: str,
        mode: str,
        reference_text: str | None,
        model_id: str,
    ) -> list[dict[str, Any]]:
        system_prompt = (
            "You are an expert Question Generator Agent. Your task is to generate educational questions based ONLY on the provided context.\n"
            "You MUST return the output as a raw JSON array of objects, with no markdown code blocks, no ```json prefixes, and no trailing text.\n"
            "Each question object must follow this exact schema:\n"
            "{\n"
            '  "id": "unique_string",\n'
            '  "text": "The question text",\n'
            '  "type": "multiple_choice" or "short_answer",\n'
            '  "options": ["A", "B", "C", "D"] (only if multiple_choice),\n'
            '  "correct_answer": "The exact correct answer",\n'
            '  "explanation": "Why this answer is correct based on the text"\n'
            "}"
        )

        user_prompt = f"Topic: {topic}\n"
        user_prompt += f"Count: {count}\n"
        user_prompt += f"Difficulty: {difficulty}\n"
        user_prompt += f"Type: {question_type}\n\n"

        if mode == "exam" and reference_text:
            user_prompt += f"Exam Mimicry Mode Active. Please match the style and format of this reference exam:\n{reference_text}\n\n"

        user_prompt += f"Context Documents:\n{context}\n\nGenerate the JSON array now:"

        response = await self.lm_client.stream_chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=3000,
        )

        content = response.get("content", "")
        if not content:
            return []

        # Clean up potential markdown formatting
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        try:
            questions = json.loads(content)
            if isinstance(questions, list):
                return questions
            elif isinstance(questions, dict) and "questions" in questions:
                return questions["questions"]
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse GeneratorAgent JSON: {e}\nContent: {content[:200]}")

        return []

    async def _validate_questions(
        self, draft_questions: list[dict[str, Any]], context: str, difficulty: str, model_id: str
    ) -> list[dict[str, Any]]:
        system_prompt = (
            "You are a Validator Agent. Your job is to review a list of drafted questions against the provided source context.\n"
            "Filter out any questions that are factually incorrect, unanswerable from the context, or do not match the target difficulty.\n"
            "Return a JSON array of the approved questions. You may fix minor errors in the explanation or text. Remove bad questions.\n"
            "Output ONLY a raw JSON array of objects. No markdown."
        )

        user_prompt = f"Target Difficulty: {difficulty}\n\n"
        user_prompt += f"Source Context:\n{context}\n\n"
        user_prompt += f"Draft Questions (JSON):\n{json.dumps(draft_questions, indent=2)}\n\n"
        user_prompt += "Return the validated JSON array:"

        response = await self.lm_client.stream_chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=3000,
        )

        content = response.get("content", "")
        if not content:
            return draft_questions  # fallback to draft if validation fails

        # Clean up potential markdown formatting
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        try:
            questions = json.loads(content)
            if isinstance(questions, list):
                return questions
            elif isinstance(questions, dict) and "questions" in questions:
                return questions["questions"]
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse ValidatorAgent JSON: {e}")

        return draft_questions  # fallback to draft if validation fails to parse
