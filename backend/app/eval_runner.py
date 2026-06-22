"""Evaluation benchmark runner — CLI entry point for running benchmarks.

Usage:
    uv run python -m app.eval_runner --kb-name <name> [--output results.json]
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


async def run_benchmark(kb_name: str, model_id: str | None = None) -> dict:
    from app import state
    from app.services.rag_eval import RAGEvaluator

    evaluator = RAGEvaluator(
        llm_client=state.lm_client,
        model_id=model_id or os.environ.get("UDIP_EVAL_MODEL", ""),
    )

    benchmark_path = Path(__file__).resolve().parent.parent / "data" / "evals" / "benchmark_queries.json"
    if not benchmark_path.exists():
        # Generate from benchmark.py
        from data.evals.benchmark import BENCHMARK_QUERIES
        benchmark_path.parent.mkdir(parents=True, exist_ok=True)
        benchmark_path.write_text(json.dumps(BENCHMARK_QUERIES, indent=2))

    result = await evaluator.evaluate_dataset(str(benchmark_path))
    print(json.dumps(result["metrics"], indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run DEEP evaluation benchmark")
    parser.add_argument("--kb-name", default="default", help="Knowledge base to evaluate against")
    parser.add_argument("--model", help="Override model ID for evaluation")
    args = parser.parse_args()
    asyncio.run(run_benchmark(args.kb_name, args.model))
