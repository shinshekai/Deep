"""RAG evaluation service — lightweight replacement for ragas.

Implements REQ-6.3: Faithfulness >= 0.85, AnswerRelevancy.

Metrics:
- Faithfulness: Are answer claims supported by the context?
- AnswerRelevancy: Is the answer relevant to the question?
- ContextPrecision: Are retrieved contexts precise?
- ContextRecall: Do contexts cover ground truth?

Uses keyword overlap and n-gram heuristics for scoring.
No external LLM-based evaluation dependency.
"""

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]


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


@dataclass
class RAGEvaluator:
    llm_client: object | None = None

    @property
    def is_available(self) -> bool:
        return True

    async def compute_faithfulness(
        self, question: str, answer: str, contexts: list[str]
    ) -> float:
        return faithfulness(answer, contexts)

    async def evaluate_sample(
        self,
        question: str,
        answer: str,
        contexts: list[str],
        ground_truth: str | None = None,
    ) -> dict:
        gt = ground_truth or ""
        return {
            "faithfulness": faithfulness(answer, contexts),
            "answer_relevancy": answer_relevancy(question, answer),
            "context_precision": context_precision(contexts, gt),
            "context_recall": context_recall(contexts, gt),
        }

    async def evaluate_dataset(self, dataset_path: str) -> dict:
        logger.info(f"Loading dataset from {dataset_path}")
        return {"status": "not_implemented", "dataset": dataset_path}
