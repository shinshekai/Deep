import pytest
import time
from app.services.memory_service import MemoryService


@pytest.mark.asyncio
async def test_recall_latency(tmp_path):
    """Recall should complete within 50ms for a modest dataset."""
    svc = MemoryService(db_path=str(tmp_path / "test_memory.db"))
    await svc.initialize()
    for i in range(50):
        await svc.store_episode(
            device_id="dev1",
            query=f"Question about topic {i % 10}",
            answer=f"Answer for item {i}",
            agents=["solve"],
            model_used="test",
        )
    start = time.perf_counter()
    for _ in range(10):
        await svc.recall_episodes("dev1", "question about topic 3")
    elapsed_ms = (time.perf_counter() - start) / 10 * 1000
    assert elapsed_ms < 50, f"Recall latency {elapsed_ms:.1f}ms exceeds 50ms target"
    await svc.close()


@pytest.mark.asyncio
async def test_store_episode_latency(tmp_path):
    """Storing an episode should complete within 20ms."""
    svc = MemoryService(db_path=str(tmp_path / "test_memory.db"))
    await svc.initialize()
    latencies = []
    for i in range(20):
        start = time.perf_counter()
        await svc.store_episode(
            device_id="dev1",
            query=f"Query {i}",
            answer=f"Answer {i}",
            agents=["solve"],
            model_used="test",
        )
        latencies.append((time.perf_counter() - start) * 1000)
    avg_ms = sum(latencies) / len(latencies)
    assert avg_ms < 20, f"Store episode avg latency {avg_ms:.1f}ms exceeds 20ms target"
    await svc.close()


@pytest.mark.asyncio
async def test_store_fact_latency(tmp_path):
    """Storing a fact should complete within 20ms."""
    svc = MemoryService(db_path=str(tmp_path / "test_memory.db"))
    await svc.initialize()
    latencies = []
    for i in range(20):
        start = time.perf_counter()
        await svc.store_fact(device_id="dev1", content=f"Fact number {i}")
        latencies.append((time.perf_counter() - start) * 1000)
    avg_ms = sum(latencies) / len(latencies)
    assert avg_ms < 20, f"Store fact avg latency {avg_ms:.1f}ms exceeds 20ms target"
    await svc.close()


@pytest.mark.asyncio
async def test_concurrent_writes(tmp_path):
    """SQLite should handle sequential writes without locking errors."""
    svc = MemoryService(db_path=str(tmp_path / "test_memory.db"))
    await svc.initialize()
    errors = []
    for i in range(100):
        try:
            await svc.store_episode(
                device_id="dev1",
                query=f"Query {i}",
                answer=f"Answer {i}",
            )
            await svc.store_fact(device_id="dev1", content=f"Fact {i}")
        except Exception as e:
            errors.append(str(e))
    assert len(errors) == 0, f"Got {len(errors)} errors: {errors[:3]}"
    stats = await svc.get_stats("dev1")
    assert stats["episodes"] == 100
    assert stats["facts"] == 100
    await svc.close()


@pytest.mark.asyncio
async def test_token_budget_adherence(tmp_path):
    """Memory context should not exceed token budget."""
    from app.services.memory_context import build_memory_context
    svc = MemoryService(db_path=str(tmp_path / "test_memory.db"))
    await svc.initialize()
    for i in range(30):
        await svc.store_episode(
            device_id="dev1",
            query=f"Very detailed question about machine learning topic number {i} with lots of context",
            answer=f"Comprehensive answer discussing multiple aspects of machine learning topic {i} including neural networks, transformers, and applications",
        )
    for i in range(30):
        await svc.store_fact(device_id="dev1", content=f"Important fact about {i}: this is a detailed fact that contains significant information about the topic")
    episodes = await svc.recall_episodes("dev1", "machine learning")
    facts = await svc.recall_facts("dev1", "machine learning")
    context = build_memory_context(None, episodes, facts, token_budget=2000)
    token_estimate = len(context) / 4
    assert token_estimate < 2500, f"Context too long: ~{token_estimate:.0f} tokens (budget 2000)"
    await svc.close()
