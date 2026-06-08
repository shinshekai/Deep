import os
import tempfile

import pytest

from app.services.memory_service import MemoryService


@pytest.fixture
async def isolated_service():
    tmpdir = tempfile.mkdtemp()
    svc = MemoryService(db_path=os.path.join(tmpdir, "tx_test.db"))
    await svc.initialize()
    yield svc
    await svc.close()


class TestTransactionRollback:
    async def test_rollback_on_second_statement_failure(self, isolated_service):
        svc = isolated_service
        device_id = "tx-test-device"

        with pytest.raises(Exception):
            async with svc._transaction():
                db = await svc._get_db()
                await db.execute(
                    """INSERT INTO episodes
                       (id, device_id, session_type, query, answer, agents,
                        model_used, tier, citations, outcome_rating, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        "ep_rollback_1",
                        device_id,
                        "chat",
                        "q1",
                        "a1",
                        "[]",
                        "",
                        0,
                        "[]",
                        0.0,
                        1000.0,
                    ),
                )
                await db.execute(
                    """INSERT INTO fact_relationships
                       (source_fact_id, target_fact_id, relation_type, confidence)
                       VALUES (?, ?, ?, ?)""",
                    ("does_not_exist", "does_not_exist", "related", 0.5),
                )

        db = await svc._get_db()
        rows = await db.execute_fetchall("SELECT id FROM episodes WHERE id = ?", ("ep_rollback_1",))
        assert len(rows) == 0

    async def test_commit_on_success(self, isolated_service):
        svc = isolated_service
        device_id = "tx-test-device"

        async with svc._transaction():
            db = await svc._get_db()
            await db.execute(
                """INSERT INTO episodes
                   (id, device_id, session_type, query, answer, agents,
                    model_used, tier, citations, outcome_rating, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("ep_commit_1", device_id, "chat", "q1", "a1", "[]", "", 0, "[]", 0.0, 1000.0),
            )

        db = await svc._get_db()
        rows = await db.execute_fetchall("SELECT id FROM episodes WHERE id = ?", ("ep_commit_1",))
        assert len(rows) == 1

    async def test_recall_facts_atomic_on_write_failure(self, isolated_service):
        svc = isolated_service
        device_id = "atomic-recall-dev"

        await svc.store_fact(device_id, "Python is a programming language")

        db = await svc._get_db()
        rows = await db.execute_fetchall(
            "SELECT id, access_count FROM facts WHERE device_id = ?", (device_id,)
        )
        assert len(rows) == 1
        fact_id, initial_count = rows[0]

        with pytest.raises(Exception):
            async with svc._transaction():
                await db.execute(
                    "UPDATE facts SET last_accessed = ?, access_count = access_count + 1 WHERE id = ?",
                    (2000.0, fact_id),
                )
                await db.execute(
                    "INSERT INTO fact_relationships (source_fact_id, target_fact_id, relation_type, confidence) VALUES (?, ?, ?, ?)",
                    ("bad_ref_1", "bad_ref_2", "x", 0.1),
                )

        rows = await db.execute_fetchall("SELECT access_count FROM facts WHERE id = ?", (fact_id,))
        assert rows[0][0] == initial_count
