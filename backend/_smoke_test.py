import asyncio
import tempfile
import os
from app.services.memory_service import MemoryService


async def main():
    db = os.path.join(tempfile.mkdtemp(), "smoke.db")
    svc = MemoryService(db_path=db)
    await svc.initialize()
    dev = "dev-test"

    await svc.store_fact(dev, "Python is a compiled language", "conversation", confidence=0.8)
    await svc.store_fact(dev, "Python is an interpreted language", "conversation", confidence=0.9)
    await svc.store_fact(dev, "Java is a compiled language", "conversation", confidence=0.7)

    before = await svc.recall_facts(dev, "Python")
    print(f"Facts before: {len(before)}")
    for f in before:
        print(f"  - {f['content']} (conf={f['confidence']})")

    result = await svc.batch_resolve_contradictions(dev)
    print(f"Result: {result}")

    after = await svc.recall_facts(dev, "Python")
    print(f"Facts after: {len(after)}")
    for f in after:
        print(f"  - {f['content']} (conf={f['confidence']})")

    await svc.close()


asyncio.run(main())
