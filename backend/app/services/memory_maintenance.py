import asyncio
import logging
import time

logger = logging.getLogger(__name__)

DECAY_INTERVAL = 3600
DECAY_DAYS = 30
DECAY_RATE = 0.1
COMPACT_DAYS = 90


async def memory_maintenance_loop(memory_service=None, interval: int = DECAY_INTERVAL):
    while True:
        try:
            await asyncio.sleep(interval)
            if memory_service is None:
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
        except asyncio.CancelledError:
            logger.info("Memory maintenance loop cancelled")
            break
        except Exception as e:
            logger.error(f"Memory maintenance error: {e}", exc_info=True)
            await asyncio.sleep(60)
