"""Outer reflection loop — post-solve analysis for autonomous improvement.

Reviews solve transcripts, extracts patterns, updates agent strategies,
and generates improvement hypotheses as staged observations.
"""

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

REFLECTION_PROMPT = (
    "Review the following solve session transcript. Extract:\n"
    "1. What worked well? (keep doing this)\n"
    "2. What went wrong? (avoid in future)\n"
    "3. Improvement suggestions for the next similar query\n"
    "Return a concise analysis in 2-3 sentences."
)


async def run_outer_reflection(
    query: str,
    transcript: str,
    answer: str,
    lm_client,
    model_id: str,
    memory_service,
    device_id: str,
) -> dict[str, Any]:
    """Run the outer reflection loop after a solve completes.

    1. Review agent steps from transcript
    2. Extract patterns (what worked / what failed)
    3. Update agent strategies via memory service
    4. Generate improvement hypotheses → store as staged observations
    """
    if not memory_service or not lm_client:
        return {"mode": "outer_reflection", "status": "skipped", "reason": "no memory or LLM"}

    try:
        result = await lm_client.stream_chat_completion(
            model=model_id,
            messages=[
                {"role": "system", "content": "You are a meta-analyst. Review solve sessions and extract insights."},
                {"role": "user", "content": f"Query: {query}\n\nTranscript summary: {transcript[:2000]}\n\nAnswer: {answer[:1000]}\n\n{REFLECTION_PROMPT}"},
            ],
            max_tokens=512,
        )
        reflection = result.get("content", "")

        if reflection:
            await memory_service.store_episode(
                device_id=device_id,
                query=f"Reflection on: {query[:120]}",
                answer=reflection,
                agents=["outer_reflection"],
                model_used=model_id,
                session_type="reflection",
                outcome_rating=0.8,
            )

            await memory_service.stage_observation(
                device_id=device_id,
                content=reflection[:500],
                source_type="outer_reflection",
                source_id=f"reflection_{int(time.time())}",
                confidence=0.7,
            )

            logger.info("Outer reflection completed for device %s", device_id[:8])
            return {"mode": "outer_reflection", "status": "completed", "insights": reflection[:200]}
    except Exception as e:
        logger.warning("Outer reflection failed: %s", e)

    return {"mode": "outer_reflection", "status": "failed"}
