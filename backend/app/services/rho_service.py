"""RHO: Agent self-improvement via coreset selection and harness optimization.

Algorithm from arXiv:2606.05922 (RHO: Self-Supervised Harness Optimization)
Code reference: https://github.com/wbopan/retro-harness

Patterns validated against:
- DPPy library for DPP sampling (MIT)
- DeepCore coreset selection methods
- sentence-transformers BAAI/bge-large-en-v1.5 for embeddings
- Fast greedy MAP inference for DPP (O(k*n^2))
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field

import numpy as np

from app.services.memory_service import MemoryService
from app.services.lm_studio_client import LMStudioClient

logger = logging.getLogger(__name__)


@dataclass
class EpisodeJudgment:
    episode_id: str
    difficulty: float = 0.0
    fingerprint: str = ""
    embedding: list[float] = field(default_factory=list)


@dataclass
class Diagnosis:
    task_id: str
    validation_analysis: str = ""
    consistency_analysis: str = ""
    severity: str = "low"


@dataclass
class HarnessCandidate:
    candidate_id: str
    harness_snapshot: dict = field(default_factory=dict)
    score: float = 0.0
    per_task_scores: list[float] = field(default_factory=list)


class RHOService:
    def __init__(
        self,
        memory_service: MemoryService,
        llm_client: LMStudioClient,
    ):
        self.memory = memory_service
        self.llm = llm_client
        self._embedder = None

    async def _get_embedder(self):
        if self._embedder is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._embedder = SentenceTransformer(
                    "BAAI/bge-large-en-v1.5",
                    device="cuda" if self._cuda_available() else "cpu",
                )
            except ImportError:
                logger.warning("sentence-transformers not installed, using fallback")
                self._embedder = "fallback"
        return self._embedder

    def _cuda_available(self) -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    async def select_coreset(
        self, device_id: str, k: int = 10, theta: float = 0.7
    ) -> list[dict]:
        episodes = await self.memory.list_episodes(device_id, limit=1000)
        if not episodes:
            return []
        if len(episodes) <= k:
            return episodes

        judgments = await asyncio.gather(*[
            self._judge_episode(ep) for ep in episodes
        ])

        embedder = await self._get_embedder()
        if embedder == "fallback":
            embeddings = np.array([[hash(j.fingerprint) % 1000 / 1000] for j in judgments])
        else:
            embeddings = embedder.encode(
                [j.fingerprint for j in judgments],
                normalize_embeddings=True,
            )

        r = np.array([max(j.difficulty / 10, 0.1) for j in judgments])
        alpha = theta / (2 * max(1 - theta, 1e-6))
        r_scaled = (r / r.max()) ** alpha

        S = self._cosine_similarity(embeddings)
        L = np.diag(r_scaled) @ S @ np.diag(r_scaled)

        picks = self._fast_greedy_map(L, k)
        return [episodes[i] for i in picks]

    async def _judge_episode(self, episode: dict) -> EpisodeJudgment:
        prompt = f"""Analyze this episode and provide:
1. Difficulty score (0-10): How hard was this task?
2. Fingerprint: A 1-sentence summary of the core challenge.

Episode:
Query: {episode.get('query', '')}
Answer: {episode.get('answer', '')[:500]}
Model: {episode.get('model_used', 'unknown')}
Outcome: {episode.get('outcome_rating', 'unknown')}

Output JSON: {{"difficulty": <float>, "fingerprint": "<string>"}}"""

        response = await self.llm.stream_chat(
            messages=[{"role": "user", "content": prompt}]
        )
        try:
            import json
            result = json.loads(response)
            return EpisodeJudgment(
                episode_id=episode.get("id", ""),
                difficulty=float(result.get("difficulty", 5.0)),
                fingerprint=result.get("fingerprint", episode.get("query", "")[:100]),
            )
        except Exception:
            return EpisodeJudgment(
                episode_id=episode.get("id", ""),
                difficulty=5.0,
                fingerprint=episode.get("query", "")[:100],
            )

    def _cosine_similarity(self, embeddings: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        normalized = embeddings / norms
        return normalized @ normalized.T

    def _fast_greedy_map(self, L: np.ndarray, k: int, eps: float = 1e-10) -> list[int]:
        M = L.shape[0]
        d2 = np.diag(L).copy()
        c = [np.empty(0) for _ in range(M)]
        picked = []

        first = int(np.argmax(d2))
        picked.append(first)

        while len(picked) < k:
            j = picked[-1]
            dj = np.sqrt(max(d2[j], 0))
            unpicked = [i for i in range(M) if i not in picked]

            for i in unpicked:
                e_val = (L[j, i] - c[i] @ c[j]) / dj if c[j].size else L[j, i] / dj
                c[i] = np.append(c[i], e_val)
                d2[i] = max(d2[i] - e_val ** 2, 0)

            best = max(unpicked, key=lambda i: d2[i])
            if d2[best] <= eps:
                break
            picked.append(best)

        return picked

    async def diagnose_episode(
        self, episode: dict, agent_config: dict, G: int = 3
    ) -> Diagnosis:
        trajectories = await asyncio.gather(*[
            self._solve_episode(episode, agent_config) for _ in range(G)
        ])

        validation_prompt = f"""Analyze this trajectory for correctness:
Task: {episode.get('query', '')}
Trajectory: {trajectories[0][:1000]}

Check: correct approach, dead ends, false assumptions, premature stopping.
Output JSON: {{"analysis": "<string>", "issues": ["<string>"]}}"""

        validation = await self.llm.stream_chat(
            messages=[{"role": "user", "content": validation_prompt}]
        )

        consistency_prompt = f"""Compare these {G} trajectories for the same task:
{[f"Trajectory {i}: {t[:200]}" for i, t in enumerate(trajectories)]}

Rate consistency (high/medium/low) and explain divergences.
Output JSON: {{"consistency": "<high|medium|low>", "analysis": "<string>"}}"""

        consistency = await self.llm.stream_chat(
            messages=[{"role": "user", "content": consistency_prompt}]
        )

        return Diagnosis(
            task_id=episode.get("id", ""),
            validation_analysis=validation,
            consistency_analysis=consistency,
        )

    async def _solve_episode(self, episode: dict, agent_config: dict) -> str:
        prompt = f"""Solve this task step by step:
Query: {episode.get('query', '')}

Provide your solution."""
        return await self.llm.stream_chat(
            messages=[{"role": "user", "content": prompt}]
        )

    async def optimize_harness(
        self,
        diagnoses: list[Diagnosis],
        coreset: list[dict],
        n_candidates: int = 3,
    ) -> HarnessCandidate | None:
        candidates = []
        for j in range(n_candidates):
            candidate = await self._generate_harness_candidate(diagnoses, seed=j)
            score = await self._evaluate_candidate(candidate, coreset)
            candidates.append((candidate, score))

        if not candidates:
            return None

        winner = max(candidates, key=lambda c: c[1])
        if winner[1] > 0:
            return winner[0]
        return None

    async def _generate_harness_candidate(
        self, diagnoses: list[Diagnosis], seed: int
    ) -> HarnessCandidate:
        prompt = f"""Based on these failure diagnoses, generate an improved agent harness configuration.
Diagnoses: {[d.validation_analysis[:200] for d in diagnoses[:5]]}

Generate a JSON harness with improved instructions and tools."""
        response = await self.llm.stream_chat(
            messages=[{"role": "user", "content": prompt}]
        )
        return HarnessCandidate(
            candidate_id=f"candidate_{seed}",
            harness_snapshot={"instructions": response},
        )

    async def _evaluate_candidate(
        self, candidate: HarnessCandidate, coreset: list[dict]
    ) -> float:
        scores = []
        for ep in coreset[:5]:
            prompt = f"""Evaluate this solution quality (0-1):
Query: {ep.get('query', '')[:200]}
Solution: {candidate.harness_snapshot.get('instructions', '')[:200]}

Output JSON: {{"score": <float>}}"""
            response = await self.llm.stream_chat(
                messages=[{"role": "user", "content": prompt}]
            )
            try:
                import json
                result = json.loads(response)
                scores.append(float(result.get("score", 0.5)))
            except Exception:
                scores.append(0.5)
        return sum(scores) / max(len(scores), 1)
