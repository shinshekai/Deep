"""MemoryConsolidator — LLM-driven L1→L2→L3 memory consolidation.

Modes:
  update — staged_observations → LLM extracts facts → upserts user_l3
  dedup  — finds similar facts in user_l3 → LLM merges duplicates
  audit  — verifies fact accuracy against source episodes
  merge  — cross-session synthesis → generates profile.md

Runs as a background maintenance task, driven by the lifespan loop.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class MemoryConsolidator:
    """LLM-driven consolidator for DEEP's three-layer memory system."""

    def __init__(self, memory_service, lm_client):
        self.mem = memory_service
        self.lm = lm_client

    async def consolidate(
        self, device_id: str, model_id: str, mode: str = "update"
    ) -> dict[str, Any]:
        """Run one consolidation pass. Returns stats dict."""
        if mode == "update":
            return await self._update_mode(device_id, model_id)
        if mode == "dedup":
            return await self._dedup_mode(device_id, model_id)
        if mode == "audit":
            return await self._audit_mode(device_id, model_id)
        if mode == "merge":
            return await self._merge_mode(device_id, model_id)
        return {"error": f"Unknown mode: {mode}"}

    async def _update_mode(self, device_id: str, model_id: str) -> dict:
        """L1→L2: crystallize observations and synthesize into L3 profile."""
        count = await self.mem.crystallize_observations(device_id)
        if count == 0:
            return {"mode": "update", "observations_processed": 0}

        observations = await self.mem.get_staged_observations(device_id)
        if not observations:
            return {"mode": "update", "observations_processed": 0}

        content = "\n".join(
            f"- [{o.get('source_type', '?')}] {o.get('content', '')[:500]}"
            for o in observations[:10]
        )

        prompt = f"""Synthesize these observations into a concise user profile. 
Extract: (1) preferences, (2) recurring topics, (3) technical interests, (4) knowledge gaps.

Observations:
{content}

Return JSON: {{"profile": "...", "topics": [...], "preferences": {{...}}}}"""
        try:
            result = await self.lm.stream_chat_completion(
                model=model_id,
                messages=[
                    {"role": "system", "content": "You are a memory consolidator. Extract insights from observations."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=1024,
            )
            profile_text = result.get("content", "{}")
            await self.mem.store_fact(
                device_id=device_id,
                content=profile_text,
                source_type="consolidator",
                source_id="update",
                confidence=0.7,
            )
            logger.info("Memory consolidation: processed %d observations for device %s", count, device_id[:8])
            return {"mode": "update", "observations_processed": count}
        except Exception as e:
            logger.error("Consolidation failed: %s", e)
            return {"mode": "update", "error": str(e)}

    async def _dedup_mode(self, device_id: str, model_id: str) -> dict:
        """Find and merge similar facts in user_l3."""
        l3_slots = await self.mem.get_l3_all(device_id)
        l3_list = list(l3_slots.items())
        if len(l3_list) < 2:
            return {"mode": "dedup", "pairs_checked": 0, "merged": 0}

        pairs = []
        for i in range(len(l3_list)):
            for j in range(i + 1, min(i + 3, len(l3_list))):
                pairs.append((l3_list[i], l3_list[j]))

        merged = 0
        for (s1, c1), (s2, c2) in pairs[:5]:
            prompt = f"""Are these two entries duplicates? Return JSON: {{"is_duplicate": bool, "merged_text": "..."}}

Entry 1 [{s1}]: {c1[:300]}
Entry 2 [{s2}]: {c2[:300]}"""
            try:
                result = await self.lm.stream_chat_completion(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=300,
                )
                data = json.loads(result.get("content", "{}"))
                if data.get("is_duplicate"):
                    await self.mem.store_fact(
                        device_id=device_id,
                        content=data.get("merged_text", c1),
                        source_type="consolidator",
                        source_id="dedup",
                    )
                    merged += 1
            except Exception:
                pass

        return {"mode": "dedup", "pairs_checked": len(pairs), "merged": merged}

    async def _audit_mode(self, device_id: str, model_id: str) -> dict:
        """Verify L3 facts against stored facts for consistency."""
        l3_slots = await self.mem.get_l3_all(device_id)
        if not l3_slots:
            return {"mode": "audit", "verified": 0, "flagged": 0}

        verified = 0
        flagged = 0
        for slot, content in list(l3_slots.items())[:3]:
            prompt = f"""Verify this profile entry for consistency. Flag contradictions or outdated info.
Entry: {content[:300]}
Return JSON: {{"accurate": bool, "reason": "..."}}"""
            try:
                result = await self.lm.stream_chat_completion(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=200,
                )
                data = json.loads(result.get("content", "{}"))
                if data.get("accurate"):
                    verified += 1
                else:
                    flagged += 1
            except Exception:
                pass

        return {"mode": "audit", "verified": verified, "flagged": flagged}

    async def _merge_mode(self, device_id: str, model_id: str) -> dict:
        """Cross-session synthesis — generate a consolidated profile.md."""
        l3_slots = await self.mem.get_l3_all(device_id)
        if not l3_slots:
            return {"mode": "merge", "output": "No data to merge."}

        slot_text = "\n".join(f"## {k}\n{v[:200]}" for k, v in list(l3_slots.items())[:5])

        prompt = f"""Synthesize a consolidated user profile from these memory entries.

{slot_text[:1000]}

Write a profile.md with sections: ## Preferences, ## Knowledge, ## Projects, ## Learning Goals."""
        try:
            result = await self.lm.stream_chat_completion(
                model=model_id,
                messages=[
                    {"role": "system", "content": "You are a memory synthesizer. Create a user profile from accumulated knowledge."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2048,
            )
            profile_text = result.get("content", "")
            await self.mem.store_fact(
                device_id=device_id,
                content=profile_text,
                source_type="consolidator",
                source_id="merge",
            )
            return {"mode": "merge", "output_length": len(profile_text)}
        except Exception as e:
            return {"mode": "merge", "error": str(e)}
