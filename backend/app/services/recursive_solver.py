"""Recursive Multi-Agent Solver — inspired by RecursiveMAS.

Implements 4 collaboration patterns adapted for LM Studio inference:
  - Sequential:    Planner → Critic → Solver (with recursive refinement rounds)
  - Mixture:       Domain experts in parallel → Summarizer aggregation
  - Deliberation:  Reflector ↔ Tool-Caller recursive loop
  - Distillation:  Expert (large model) guides Learner (small model)

Key adaptations from the RecursiveMAS paper (arXiv:2604.25917):
  - Compressed context transfer (200-token summaries between agents)
    instead of raw latent vectors (since we use LM Studio API, not PyTorch)
  - Convergence detection via output similarity between rounds
  - Pattern selection driven by complexity scorer

Reference: https://github.com/RecursiveMAS/RecursiveMAS
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Literal

from app.services.lm_studio_client import LMStudioClient

logger = logging.getLogger(__name__)

# ── Agent Persona Prompts ──

AGENT_PERSONAS = {
    # Sequential pattern
    "planner": (
        "You are a Planner agent in a recursive multi-agent system. "
        "Analyze the query and create a structured reasoning plan. "
        "Break the problem into clear sub-steps. Identify what information is needed."
    ),
    "critic": (
        "You are a Critic agent. Review the current solution attempt critically. "
        "Identify logical gaps, unsupported claims, missing information, and errors. "
        "Be specific about what needs improvement and why."
    ),
    "solver": (
        "You are a Solver agent. Execute the plan and produce a comprehensive answer. "
        "Address all points raised by the Critic. Be thorough and precise. "
        "Cite evidence from the provided context when available."
    ),
    # Mixture pattern
    "math_expert": (
        "You are a Mathematics expert. Focus on quantitative analysis, calculations, "
        "statistical reasoning, and mathematical proofs relevant to the query."
    ),
    "code_expert": (
        "You are a Code and Systems expert. Focus on implementation details, algorithms, "
        "data structures, and technical architecture relevant to the query."
    ),
    "science_expert": (
        "You are a Science and Research expert. Focus on scientific methodology, "
        "empirical evidence, theoretical frameworks, and research findings."
    ),
    "summarizer": (
        "You are a Summarizer agent. Synthesize the outputs from multiple domain experts "
        "into a single coherent, well-structured response. Resolve contradictions, "
        "eliminate redundancy, and ensure completeness."
    ),
    # Deliberation pattern
    "reflector": (
        "You are a Reflector agent. Analyze the current state of reasoning. "
        "Identify what is known, what is uncertain, and what needs external verification. "
        "Suggest specific retrieval queries to fill knowledge gaps."
    ),
    "tool_caller": (
        "You are a Tool-Caller agent. Based on the Reflector's analysis, "
        "formulate precise queries to retrieve relevant information. "
        "Integrate retrieved evidence into a coherent response."
    ),
    # Distillation pattern
    "expert": (
        "You are an Expert agent (large model). Provide detailed, thorough reasoning "
        "for the query. Show your chain of thought explicitly so a smaller model can learn."
    ),
    "learner": (
        "You are a Learner agent. Study the Expert's reasoning and produce your own "
        "response that captures the key insights. Be concise but accurate."
    ),
    # Compression
    "compressor": (
        "Compress the following text into a dense summary of at most 200 tokens. "
        "Preserve all key facts, reasoning steps, and conclusions. "
        "Output ONLY the compressed summary, nothing else."
    ),
}


@dataclass
class RecursionRound:
    """Record of a single recursion round."""

    round_num: int
    agent: str
    content: str
    compressed: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class RecursiveSolveResult:
    """Result of a recursive solve session."""

    answer: str
    pattern: str
    rounds_used: int
    max_rounds: int
    converged: bool
    agent_trace: list[RecursionRound]
    elapsed_seconds: float
    token_savings_pct: float = 0.0


class RecursiveSolver:
    """Recursive multi-agent collaboration adapted for LM Studio inference.

    Instead of RecursiveLink latent-space transfer (requires PyTorch),
    we use LLM-generated compressed summaries (~200 tokens) between agents,
    achieving similar information density reduction.
    """

    PATTERNS = {
        "sequential": ["planner", "critic", "solver"],
        "mixture": ["math_expert", "code_expert", "science_expert", "summarizer"],
        "deliberation": ["reflector", "tool_caller"],
        "distillation": ["expert", "learner"],
    }

    def __init__(self, lm_client: LMStudioClient):
        self.lm_client = lm_client

    async def solve(
        self,
        query: str,
        context: str = "",
        pattern: Literal["sequential", "mixture", "deliberation", "distillation"] = "sequential",
        model_id: str = "Qwen3-1.7B-Q4_K_M",
        expert_model_id: str | None = None,
        max_rounds: int = 3,
        convergence_threshold: float = 0.85,
        ws_send=None,
    ) -> RecursiveSolveResult:
        """Run recursive multi-agent collaboration.

        Args:
            query: User query
            context: Retrieved context from RAG pipeline
            pattern: Collaboration pattern to use
            model_id: Primary model for inference
            expert_model_id: Larger model for distillation Expert (optional)
            max_rounds: Maximum recursion rounds
            convergence_threshold: Similarity threshold to stop early
            ws_send: Optional WebSocket callback for streaming
        """
        from app.services.telemetry import trace_span

        start_time = time.time()

        with trace_span(
            "recursive_solver.solve",
            {
                "pattern": pattern,
                "model_id": model_id,
                "max_rounds": max_rounds,
            },
        ):
            if pattern == "sequential":
                result = await self._run_sequential(
                    query, context, model_id, max_rounds, convergence_threshold, ws_send
                )
            elif pattern == "mixture":
                result = await self._run_mixture(query, context, model_id, ws_send)
            elif pattern == "deliberation":
                result = await self._run_deliberation(
                    query, context, model_id, max_rounds, convergence_threshold, ws_send
                )
            elif pattern == "distillation":
                result = await self._run_distillation(
                    query, context, model_id, expert_model_id or model_id, max_rounds, ws_send
                )
            else:
                raise ValueError(f"Unknown pattern: {pattern}")

        result.elapsed_seconds = round(time.time() - start_time, 2)
        return result

    # ──────────────────────────────────────────
    # Sequential Pattern: Planner → Critic → Solver (recursive)
    # ──────────────────────────────────────────

    async def _run_sequential(
        self,
        query: str,
        context: str,
        model_id: str,
        max_rounds: int,
        convergence_threshold: float,
        ws_send,
    ) -> RecursiveSolveResult:
        """Planner → Critic → Solver, iterated until convergence."""
        trace: list[RecursionRound] = []
        previous_answer = ""
        converged = False

        for round_num in range(1, max_rounds + 1):
            round_context = context
            if previous_answer:
                round_context += f"\n\nPrevious attempt (round {round_num - 1}):\n{previous_answer}"

            # Planner
            plan = await self._call_agent(
                "planner", query, round_context, model_id, ws_send, round_num
            )
            plan_compressed = await self._compress(plan, model_id)
            trace.append(RecursionRound(round_num, "planner", plan, plan_compressed))

            # Critic (reviews the plan + previous answer)
            critic_context = f"Plan:\n{plan_compressed}"
            if previous_answer:
                critic_context += f"\n\nPrevious answer to critique:\n{previous_answer[:500]}"
            critique = await self._call_agent(
                "critic", query, critic_context, model_id, ws_send, round_num
            )
            critique_compressed = await self._compress(critique, model_id)
            trace.append(RecursionRound(round_num, "critic", critique, critique_compressed))

            # Solver (gets plan + critique as compressed context)
            solve_context = (
                f"{round_context}\n\nPlan: {plan_compressed}\n\nCritique: {critique_compressed}"
            )
            answer = await self._call_agent(
                "solver", query, solve_context, model_id, ws_send, round_num
            )
            trace.append(RecursionRound(round_num, "solver", answer, ""))

            # Convergence check
            if previous_answer and self._check_convergence(
                previous_answer, answer, convergence_threshold
            ):
                converged = True
                logger.info(f"Sequential converged at round {round_num}")
                break

            previous_answer = answer

        # Calculate token savings from compression
        total_raw = sum(len(r.content.split()) for r in trace)
        total_compressed = sum(len(r.compressed.split()) for r in trace if r.compressed)
        savings = ((total_raw - total_compressed) / max(total_raw, 1)) * 100

        return RecursiveSolveResult(
            answer=previous_answer,
            pattern="sequential",
            rounds_used=trace[-1].round_num if trace else 0,
            max_rounds=max_rounds,
            converged=converged,
            agent_trace=trace,
            elapsed_seconds=0,
            token_savings_pct=round(savings, 1),
        )

    # ──────────────────────────────────────────
    # Mixture Pattern: Domain experts in parallel → Summarizer
    # ──────────────────────────────────────────

    async def _run_mixture(
        self,
        query: str,
        context: str,
        model_id: str,
        ws_send,
    ) -> RecursiveSolveResult:
        """Domain experts process in parallel; summarizer aggregates."""
        trace: list[RecursionRound] = []
        experts = ["math_expert", "code_expert", "science_expert"]

        # Run domain experts in parallel
        tasks = [
            self._call_agent(expert, query, context, model_id, ws_send, 1) for expert in experts
        ]
        expert_outputs = await asyncio.gather(*tasks, return_exceptions=True)

        expert_summaries = []
        for expert, output in zip(experts, expert_outputs):
            if isinstance(output, Exception):
                content = f"[{expert}] Error: {output!s}"
            else:
                content = output or f"[{expert}] No response."
            compressed = await self._compress(content, model_id)
            trace.append(RecursionRound(1, expert, content, compressed))
            expert_summaries.append(f"[{expert}]: {compressed}")

        # Summarizer aggregates
        summary_context = "\n\n".join(expert_summaries)
        answer = await self._call_agent(
            "summarizer",
            query,
            f"{context}\n\nExpert outputs:\n{summary_context}",
            model_id,
            ws_send,
            1,
        )
        trace.append(RecursionRound(1, "summarizer", answer, ""))

        return RecursiveSolveResult(
            answer=answer,
            pattern="mixture",
            rounds_used=1,
            max_rounds=1,
            converged=True,
            agent_trace=trace,
            elapsed_seconds=0,
        )

    # ──────────────────────────────────────────
    # Deliberation Pattern: Reflector ↔ Tool-Caller (recursive)
    # ──────────────────────────────────────────

    async def _run_deliberation(
        self,
        query: str,
        context: str,
        model_id: str,
        max_rounds: int,
        convergence_threshold: float,
        ws_send,
    ) -> RecursiveSolveResult:
        """Reflector and Tool-Caller alternate in a recursive loop."""
        trace: list[RecursionRound] = []
        accumulated_evidence = context
        previous_reflection = ""
        converged = False

        for round_num in range(1, max_rounds + 1):
            # Reflector: analyze state, identify gaps
            reflect_context = f"Evidence so far:\n{accumulated_evidence[:1000]}"
            if previous_reflection:
                reflect_context += f"\n\nPrevious reflection:\n{previous_reflection[:300]}"

            reflection = await self._call_agent(
                "reflector", query, reflect_context, model_id, ws_send, round_num
            )
            reflection_compressed = await self._compress(reflection, model_id)
            trace.append(RecursionRound(round_num, "reflector", reflection, reflection_compressed))

            # Tool-Caller: use reflection to build response
            tool_context = f"{accumulated_evidence}\n\nReflection: {reflection_compressed}"
            response = await self._call_agent(
                "tool_caller", query, tool_context, model_id, ws_send, round_num
            )
            response_compressed = await self._compress(response, model_id)
            trace.append(RecursionRound(round_num, "tool_caller", response, response_compressed))

            # Accumulate evidence
            accumulated_evidence += f"\n\nRound {round_num} findings:\n{response_compressed}"

            # Convergence check
            if previous_reflection and self._check_convergence(
                previous_reflection, reflection, convergence_threshold
            ):
                converged = True
                logger.info(f"Deliberation converged at round {round_num}")
                break

            previous_reflection = reflection

        # Final answer is the last tool_caller output
        final = trace[-1].content if trace else "No response generated."

        return RecursiveSolveResult(
            answer=final,
            pattern="deliberation",
            rounds_used=trace[-1].round_num if trace else 0,
            max_rounds=max_rounds,
            converged=converged,
            agent_trace=trace,
            elapsed_seconds=0,
        )

    # ──────────────────────────────────────────
    # Distillation Pattern: Expert → Learner (recursive transfer)
    # ──────────────────────────────────────────

    async def _run_distillation(
        self,
        query: str,
        context: str,
        learner_model: str,
        expert_model: str,
        max_rounds: int,
        ws_send,
    ) -> RecursiveSolveResult:
        """Expert provides detailed reasoning; Learner refines."""
        trace: list[RecursionRound] = []

        # Expert generates detailed reasoning with the larger model
        expert_output = await self._call_agent("expert", query, context, expert_model, ws_send, 1)
        expert_compressed = await self._compress(expert_output, learner_model)
        trace.append(RecursionRound(1, "expert", expert_output, expert_compressed))

        # Learner produces refined output using expert's guidance
        learner_context = f"{context}\n\nExpert reasoning:\n{expert_compressed}"
        learner_output = await self._call_agent(
            "learner", query, learner_context, learner_model, ws_send, 1
        )
        trace.append(RecursionRound(1, "learner", learner_output, ""))

        return RecursiveSolveResult(
            answer=learner_output,
            pattern="distillation",
            rounds_used=1,
            max_rounds=max_rounds,
            converged=True,
            agent_trace=trace,
            elapsed_seconds=0,
        )

    # ──────────────────────────────────────────
    # Core utilities
    # ──────────────────────────────────────────

    async def _call_agent(
        self,
        agent: str,
        query: str,
        context: str,
        model_id: str,
        ws_send,
        round_num: int,
    ) -> str:
        """Call a single agent with the LM Studio API."""
        persona = AGENT_PERSONAS.get(agent, "You are a helpful assistant.")
        messages = [
            {"role": "system", "content": persona},
            {"role": "user", "content": f"Query: {query}\n\nContext:\n{context[:2000]}"},
        ]

        # Stream progress to WebSocket
        if ws_send:
            await ws_send(
                {
                    "type": "agent_step",
                    "agent": agent,
                    "delta": f"\n[Round {round_num} — {agent}] Processing...\n",
                    "timestamp": time.time(),
                    "metadata": {"pattern": "recursive", "round": round_num},
                }
            )

        try:
            full_content = ""

            async def on_chunk(tok: str):
                nonlocal full_content
                full_content += tok
                if ws_send:
                    await ws_send(
                        {
                            "type": "agent_step",
                            "agent": agent,
                            "delta": tok,
                            "timestamp": time.time(),
                        }
                    )

            result = await self.lm_client.stream_chat_completion(
                model=model_id,
                messages=messages,
                max_tokens=2048,
                chunk_callback=on_chunk,
            )

            if result and result.get("content"):
                return result["content"]
            return full_content or f"[{agent}] No response from model."

        except Exception as e:
            logger.error(f"Agent {agent} failed: {e}", exc_info=True)
            return f"[{agent}] Error: {e!s}"

    async def _compress(self, text: str, model_id: str) -> str:
        """Compress text to ~200 tokens using LLM.

        This simulates RecursiveLink's latent-space compression:
        instead of transferring raw latent vectors between agents,
        we create dense text summaries that capture the essential information.
        """
        if len(text.split()) <= 200:
            return text  # Already short enough

        messages = [
            {"role": "system", "content": AGENT_PERSONAS["compressor"]},
            {"role": "user", "content": text[:3000]},
        ]

        try:
            result = await self.lm_client.stream_chat_completion(
                model=model_id,
                messages=messages,
                max_tokens=300,
            )
            if result and result.get("content"):
                return result["content"]
        except Exception as e:
            logger.warning(f"Compression failed, using truncation: {e}")

        # Fallback: simple truncation
        words = text.split()
        return " ".join(words[:200])

    def _check_convergence(self, prev: str, curr: str, threshold: float) -> bool:
        """Check if two outputs are similar enough to stop recursion.

        Uses Jaccard similarity on word sets as a fast proxy.
        In production, this could use embedding cosine similarity.
        """
        prev_words = set(prev.lower().split())
        curr_words = set(curr.lower().split())

        if not prev_words or not curr_words:
            return False

        intersection = prev_words & curr_words
        union = prev_words | curr_words
        similarity = len(intersection) / len(union) if union else 0

        return similarity >= threshold

    @staticmethod
    def select_pattern(
        query: str,
        complexity_score: float,
        retrieved_chunks: int = 0,
    ) -> str:
        """Select the optimal collaboration pattern based on query characteristics.

        Mapping inspired by RecursiveMAS paper:
        - Simple queries → sequential (fast, 3 agents)
        - Multi-domain queries → mixture (parallel experts)
        - Research-heavy queries → deliberation (iterative retrieval)
        - High-complexity with available large model → distillation
        """
        lower = query.lower()

        # Multi-domain detection
        domain_keywords = {
            "math": ["calculate", "equation", "formula", "derivative", "integral"],
            "code": ["implement", "function", "algorithm", "code", "program"],
            "science": ["experiment", "hypothesis", "theory", "research", "study"],
        }
        domains_detected = sum(
            1 for keywords in domain_keywords.values() if any(kw in lower for kw in keywords)
        )

        if domains_detected >= 2:
            return "mixture"

        # Research-heavy: needs iterative retrieval
        research_signals = ["compare", "analyze", "investigate", "what are all", "comprehensive"]
        if any(sig in lower for sig in research_signals) and retrieved_chunks > 3:
            return "deliberation"

        # High complexity → distillation if we have multi-tier models
        if complexity_score > 0.7:
            return "distillation"

        # Default: sequential (most efficient)
        return "sequential"
