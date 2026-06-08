#!/usr/bin/env python3
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def scan_solve_sessions(base_dir: str) -> list[dict]:
    sessions = []
    solve_dir = Path(base_dir) / "user" / "solve"
    if not solve_dir.exists():
        return sessions

    for session_dir in solve_dir.iterdir():
        if not session_dir.is_dir():
            continue
        query_response = session_dir / "query_response.md"
        final_answer = session_dir / "final_answer.md"
        transcript = session_dir / "transcript.md"

        query = ""
        answer = ""

        source = (
            query_response
            if query_response.exists()
            else transcript if transcript.exists() else None
        )
        if source:
            try:
                text = source.read_text(encoding="utf-8")
                if "## Query" in text:
                    parts = text.split("## Query")
                    if len(parts) > 1:
                        query = parts[1].split("##")[0].strip()[:500]
                elif "## Question" in text:
                    parts = text.split("## Question")
                    if len(parts) > 1:
                        query = parts[1].split("##")[0].strip()[:500]
            except Exception:
                pass

        answer_file = (
            final_answer
            if final_answer.exists()
            else query_response if query_response.exists() else None
        )
        if answer_file:
            try:
                text = answer_file.read_text(encoding="utf-8")
                if "## Answer" in text:
                    parts = text.split("## Answer")
                    if len(parts) > 1:
                        answer = parts[1].split("##")[0].strip()[:5000]
                else:
                    answer = text[:5000]
            except Exception:
                pass

        if query or answer:
            sessions.append(
                {
                    "session_id": session_dir.name,
                    "query": query or f"Session {session_dir.name}",
                    "answer": answer,
                    "session_type": "solve",
                    "dir_path": str(session_dir),
                }
            )

    return sessions


def scan_research_sessions(base_dir: str) -> list[dict]:
    sessions = []
    research_dir = Path(base_dir) / "user" / "research"
    if not research_dir.exists():
        return sessions

    for f in research_dir.glob("session_*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            query = data.get("query", "")
            report = data.get("final_report", "")
            if query:
                sessions.append(
                    {
                        "session_id": data.get("session_id", f.stem),
                        "query": query,
                        "answer": report or "",
                        "session_type": "research",
                        "dir_path": str(f),
                    }
                )
        except Exception:
            continue

    return sessions


def scan_guide_sessions(base_dir: str) -> list[dict]:
    sessions = []
    guide_dir = Path(base_dir) / "user" / "guide"
    if not guide_dir.exists():
        return sessions

    for f in guide_dir.glob("session_*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            topic = data.get("topic", "")
            points = data.get("points", [])
            chat_history = data.get("chat_history", [])

            query = f"Learning: {topic}"
            answer = "\n".join(f"- {p}" for p in points) if points else ""
            if chat_history:
                answer += "\n\nChat history:\n"
                for msg in chat_history[-5:]:
                    answer += f"Q: {msg.get('user', '')}\nA: {msg.get('assistant', '')}\n"

            if topic:
                sessions.append(
                    {
                        "session_id": data.get("session_id", f.stem),
                        "query": query,
                        "answer": answer[:5000],
                        "session_type": "learning",
                        "dir_path": str(f),
                    }
                )
        except Exception:
            continue

    return sessions


async def migrate(dry_run: bool = False, device_id: str | None = None):
    from app.services.memory_service import MemoryService

    if device_id is None:
        print("ERROR: --device-id is required to attribute migrated sessions to a namespace.")
        print(
            "Legacy session files do not carry device information; refusing to import into a shared namespace."
        )
        return

    base_dir = "data"

    print("Scanning session files...")
    solve_sessions = scan_solve_sessions(base_dir)
    research_sessions = scan_research_sessions(base_dir)
    guide_sessions = scan_guide_sessions(base_dir)

    all_sessions = solve_sessions + research_sessions + guide_sessions
    print(
        f"Found {len(all_sessions)} sessions ({len(solve_sessions)} solve, "
        f"{len(research_sessions)} research, {len(guide_sessions)} guide)"
    )

    if not all_sessions:
        print("No sessions to migrate.")
        return

    if dry_run:
        print("\n[DRY RUN] Would import:")
        for s in all_sessions[:10]:
            print(f"  [{s['session_type']}] {s['query'][:80]}...")
        if len(all_sessions) > 10:
            print(f"  ... and {len(all_sessions) - 10} more")
        return

    db_path = "data/memory/deep_memory.db"
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    svc = MemoryService(db_path=db_path)
    await svc.initialize()

    print(f"\nImporting sessions into {db_path}...")
    imported = 0
    skipped = 0

    for session in all_sessions:
        try:
            existing = await svc.recall_episodes(device_id, session["query"][:100])
            if any(session["query"][:50] in ep.get("query", "") for ep in existing):
                skipped += 1
                continue

            await svc.store_episode(
                device_id=device_id,
                query=session["query"],
                answer=session["answer"],
                session_type=session["session_type"],
                agents=["migration"],
            )
            imported += 1

            if imported % 10 == 0:
                print(f"  Imported {imported}/{len(all_sessions)}...")
        except Exception as e:
            print(f"  Error importing {session['session_id']}: {e}")
            continue

    await svc.close()
    print(f"\nMigration complete: {imported} imported, {skipped} skipped")


def main():
    parser = argparse.ArgumentParser(description="Migrate session files to memory database")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be imported without actually importing",
    )
    parser.add_argument(
        "--device-id", default=None, help="Device ID for migrated sessions (required)"
    )
    args = parser.parse_args()

    asyncio.run(migrate(dry_run=args.dry_run, device_id=args.device_id))


if __name__ == "__main__":
    main()
