"""RAG evaluation service — keyword heuristic + LLM-judge hybrid.

Implements REQ-6.3: Faithfulness >= 0.85, AnswerRelevancy.

Metrics (keyword heuristic fallback):
- Faithfulness: Are answer claims supported by the context?
- AnswerRelevancy: Is the answer relevant to the question?
- ContextPrecision: Are retrieved contexts precise?
- ContextRecall: Do contexts cover ground truth?

Metrics (LLM-judge, 5-criteria single-call rubric):
- faithfulness, relevance, coherence, groundedness, hallucination

Falls back to keyword heuristic when LLM client is unavailable.
"""

import json
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
JUDGE_METRICS = ["faithfulness", "relevance", "coherence", "groundedness", "hallucination"]

_JUDGE_PROMPT = (
    "You are a strict RAG quality evaluator. Score the following response on 5 criteria. "
    "Return ONLY a JSON object with these keys and float values 0.0-1.0.\n\n"
    "Criteria:\n"
    "- faithfulness: Are all claims in the answer supported by the provided context?\n"
    "- relevance: Does the answer directly address the question asked?\n"
    "- coherence: Is the answer well-structured, logical, and easy to follow?\n"
    "- groundedness: Are specific facts/details from the context cited or referenced?\n"
    "- hallucination: Does the answer contain information NOT present in the context? "
    "(1.0 = no hallucination, 0.0 = fully hallucinated)\n\n"
    "Question: {question}\n"
    "Context: {context}\n"
    "Answer: {answer}"
)


@dataclass
class EvalResult:
    score: float
    metric: str


def _tokenize(text: str) -> list[str]:
    return [w for w in re.split(r"\W+", text.lower()) if len(w) > 2]


def _ngrams(tokens: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def faithfulness(answer: str, contexts: list[str]) -> float:
    if not answer or not contexts:
        return 0.0
    ans_tokens = _tokenize(answer)
    ctx_text = " ".join(contexts)
    ctx_tokens = _tokenize(ctx_text)
    ans_set = set(ans_tokens)
    ctx_set = set(ctx_tokens)
    overlap = len(ans_set & ctx_set) / max(len(ans_set), 1)
    ans_ngrams = _ngrams(ans_tokens, 2)
    ctx_ngrams = _ngrams(ctx_tokens, 2)
    ngram_overlap = len(ans_ngrams & ctx_ngrams) / max(len(ans_ngrams), 1)
    score = 0.6 * overlap + 0.4 * ngram_overlap
    return round(min(1.0, score), 3)


def answer_relevancy(question: str, answer: str) -> float:
    if not question or not answer:
        return 0.0
    q_tokens = set(_tokenize(question))
    a_tokens = set(_tokenize(answer))
    if not q_tokens:
        return 0.0
    shared = q_tokens & a_tokens
    q_weighted = len(shared) / max(len(q_tokens), 1)
    a_weighted = len(shared) / max(len(a_tokens), 1)
    score = 0.5 * q_weighted + 0.5 * a_weighted
    return round(min(1.0, score), 3)


def context_precision(contexts: list[str], ground_truth: str) -> float:
    if not contexts or not ground_truth:
        return 0.0
    gt_tokens = set(_tokenize(ground_truth))
    precisions = []
    for ctx in contexts:
        ctx_tokens = set(_tokenize(ctx))
        if ctx_tokens:
            precisions.append(len(ctx_tokens & gt_tokens) / max(len(ctx_tokens), 1))
    return round(sum(precisions) / len(precisions), 3) if precisions else 0.0


def context_recall(contexts: list[str], ground_truth: str) -> float:
    if not contexts or not ground_truth:
        return 0.0
    gt_tokens = set(_tokenize(ground_truth))
    ctx_tokens = set()
    for ctx in contexts:
        ctx_tokens |= set(_tokenize(ctx))
    if not gt_tokens:
        return 0.0
    recall = len(gt_tokens & ctx_tokens) / len(gt_tokens)
    return round(min(1.0, recall), 3)


def _parse_judge_response(raw: str) -> dict[str, float]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        scores = json.loads(text)
        return {k: round(min(1.0, max(0.0, float(scores.get(k, 0.5)))), 3) for k in JUDGE_METRICS}
    except (json.JSONDecodeError, TypeError, ValueError):
        logger.warning("Failed to parse LLM judge response: %s", raw[:200])
        return {k: 0.5 for k in JUDGE_METRICS}


@dataclass
class RAGEvaluator:
    llm_client: object | None = None
    model_id: str = ""

    @property
    def is_available(self) -> bool:
        return self.llm_client is not None and bool(self.model_id)

    async def compute_faithfulness(self, question: str, answer: str, contexts: list[str]) -> float:
        if self.llm_client and self.model_id:
            scores = await self.llm_judge(question, answer, contexts)
            return scores.get("faithfulness", faithfulness(answer, contexts))
        return faithfulness(answer, contexts)

    async def llm_judge(
        self,
        question: str,
        answer: str,
        contexts: list[str],
    ) -> dict[str, float]:
        if not self.llm_client:
            return {k: 0.5 for k in JUDGE_METRICS}
        context_text = "\n---\n".join(contexts[:5]) if contexts else "(no context)"
        prompt = _JUDGE_PROMPT.format(
            question=question[:2000],
            context=context_text[:4000],
            answer=answer[:4000],
        )
        try:
            result = await self.llm_client.stream_chat_completion(
                model=self.model_id,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=256,
            )
            if result is None or result.get("error"):
                logger.warning("LLM judge call failed: %s", result)
                return {k: 0.5 for k in JUDGE_METRICS}
            return _parse_judge_response(result.get("content", ""))
        except Exception as e:
            logger.warning("LLM judge exception: %s", e)
            return {k: 0.5 for k in JUDGE_METRICS}

    async def evaluate_sample(
        self,
        question: str,
        answer: str,
        contexts: list[str],
        ground_truth: str | None = None,
    ) -> dict:
        gt = ground_truth or ""
        if self.llm_client and self.model_id:
            judge_scores = await self.llm_judge(question, answer, contexts)
            return {
                "faithfulness": judge_scores.get("faithfulness", faithfulness(answer, contexts)),
                "answer_relevancy": judge_scores.get("answer_relevancy", answer_relevancy(question, answer)),
                "context_precision": judge_scores.get("context_precision", context_precision(contexts, gt)),
                "context_recall": judge_scores.get("context_recall", context_recall(contexts, gt)),
                "method": "llm_judge",
            }
        return {
            "faithfulness": faithfulness(answer, contexts),
            "answer_relevancy": answer_relevancy(question, answer),
            "context_precision": context_precision(contexts, gt),
            "context_recall": context_recall(contexts, gt),
            "method": "keyword_heuristic",
        }

    async def evaluate_dataset(self, dataset_path: str) -> dict:
        logger.info(f"Loading dataset from {dataset_path}")
        return {"status": "not_implemented", "dataset": dataset_path}
