import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = (
    "Extract key facts from this Q&A pair. Return a JSON array of objects "
    'with "content" (string) and "confidence" (0.0-1.0) keys. '
    "Only extract genuinely useful, reusable facts. Return empty array if nothing notable.\n\n"
    "Q: {query}\n\nA: {answer}"
)


async def extract_and_store_facts(
    device_id: str,
    query: str,
    answer: str,
    source_id: str,
    lm_client,
    memory_service,
    model_id: str = "Qwen3-1.7B-Q4_K_M",
) -> list[str]:
    if not answer.strip():
        return []

    try:
        prompt = EXTRACTION_PROMPT.format(query=query[:500], answer=answer[:1000])
        result = await lm_client.stream_chat_completion(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
        )
        if result is None or result.get("error"):
            logger.debug(f"Fact extraction LLM call failed: {result}")
            return []

        raw = result.get("content", "").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        facts = json.loads(raw)
        if not isinstance(facts, list):
            return []

        stored_ids = []
        for fact in facts:
            content = fact.get("content", "").strip()
            confidence = float(fact.get("confidence", 0.5))
            if content and 0 < confidence <= 1.0:
                fid = await memory_service.store_fact(
                    device_id=device_id,
                    content=content,
                    source_type="conversation",
                    source_id=source_id,
                    confidence=confidence,
                )
                stored_ids.append(fid)

        if stored_ids:
            logger.info(f"Stored {len(stored_ids)} facts for device {device_id}")

        if memory_service:
            profile_updates = {}
            if query:
                profile_updates["last_query_topic"] = query[:100]
            if source_id:
                profile_updates["last_interaction_type"] = "conversation"
            if profile_updates:
                await memory_service.update_profile(device_id, profile_updates)

        return stored_ids

    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.debug(f"Fact extraction parse error: {e}")
        return []
    except Exception as e:
        logger.warning(f"Fact extraction failed: {e}")
        return []
