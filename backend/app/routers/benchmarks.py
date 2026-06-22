"""Benchmark runner routes."""

from fastapi import APIRouter, HTTPException

from app import state

router = APIRouter(prefix="/api/v1", tags=["benchmarks"])


@router.post("/metrics/benchmarks/run")
async def run_benchmarks(payload: dict | None = None):
    category = "all"
    if payload and "category" in payload:
        category = payload["category"]
    if category not in ("all", "latency", "kv_cache", "quality", "throughput"):
        return {
            "error": f"Unknown category: {category}. Valid: all, latency, kv_cache, quality, throughput"
        }
    run_id = await state.benchmark_runner.start_run(category)
    return {"run_id": run_id, "category": category, "status": "queued"}


@router.get("/metrics/benchmarks/{run_id}")
async def get_benchmark_status(run_id: str):
    run = state.benchmark_runner.get_run(run_id)
    if run is None:
        return {"run_id": run_id, "status": "not_found"}
    return {
        "run_id": run.run_id,
        "category": run.category,
        "status": run.status,
        "progress_pct": run.progress_pct,
        "error": run.error,
        "results": [
            {
                "test_id": r.test_id,
                "category": r.category,
                "test_case": r.test_case,
                "metric": r.metric,
                "value": r.value,
                "threshold": r.threshold,
                "passed": r.passed,
            }
            for r in run.results
        ],
        "started_at": run.started_at,
        "completed_at": run.completed_at,
    }


@router.get("/metrics/benchmarks/latest")
async def get_latest_benchmark():
    run = state.benchmark_runner.get_latest_run()
    if run is None:
        return {"status": "no_runs"}
    return {
        "run_id": run.run_id,
        "category": run.category,
        "status": run.status,
        "progress_pct": run.progress_pct,
        "error": run.error,
        "results": [
            {
                "test_id": r.test_id,
                "category": r.category,
                "test_case": r.test_case,
                "metric": r.metric,
                "value": r.value,
                "threshold": r.threshold,
                "passed": r.passed,
            }
            for r in run.results
        ],
        "started_at": run.started_at,
        "completed_at": run.completed_at,
    }
