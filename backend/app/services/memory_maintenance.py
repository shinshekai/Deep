import asyncio
import logging
import time

logger = logging.getLogger(__name__)

DECAY_INTERVAL = 3600
DECAY_DAYS = 30
DECAY_RATE = 0.1
COMPACT_DAYS = 90


async def memory_maintenance_loop(memory_service=None, interval: int = DECAY_INTERVAL, task_wal=None):
    iteration = 0
    while True:
        iteration_id = f"mem_maint_{int(time.time())}_{iteration}"
        iteration += 1
        try:
            if task_wal is not None:
                await task_wal.record_start("memory_maintenance", iteration_id, {"interval": interval})
            await asyncio.sleep(interval)
            if memory_service is None:
                if task_wal is not None:
                    await task_wal.record_complete(iteration_id, "completed", {"skipped": True})
                continue

            logger.info("Running memory maintenance...")
            start = time.time()

            decayed = await memory_service.decay_old_facts(days=DECAY_DAYS, decay_rate=DECAY_RATE)
            compacted = await memory_service.compact_episodes(older_than_days=COMPACT_DAYS)

            elapsed = time.time() - start
            logger.info(f"Memory maintenance complete: {decayed} facts decayed, {compacted} episodes compacted in {elapsed:.2f}s")

            from app import state
            if hasattr(state, '_latest_metrics'):
                stats = await memory_service.get_memory_stats_summary()
                state._latest_metrics["memory_episodes"] = stats.get("episodes", 0)
                state._latest_metrics["memory_facts"] = stats.get("facts", 0)

            if task_wal is not None:
                await task_wal.record_complete(iteration_id, "completed", {"decayed": decayed, "compacted": compacted, "elapsed": elapsed})
        except asyncio.CancelledError:
            logger.info("Memory maintenance loop cancelled")
            if task_wal is not None:
                try:
                    await task_wal.record_complete(iteration_id, "failed", {"error": "cancelled"})
                except Exception:
                    pass
            break
        except Exception as e:
            logger.error(f"Memory maintenance error: {e}", exc_info=True)
            if task_wal is not None:
                try:
                    await task_wal.record_complete(iteration_id, "failed", {"error": str(e)})
                except Exception:
                    pass
            await asyncio.sleep(60)
