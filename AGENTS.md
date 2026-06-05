# Memory Architecture

## Security Model
- All memory operations are scoped by `device_id` (UUID v4)
- No cross-device data leakage: SQLite queries always filter by `device_id`
- SQL injection prevented: all queries use parameterized statements (aiosqlite)
- Memory service failure degrades gracefully (returns empty, never crashes pipeline)
- Feature flag `memory_enabled` allows complete disable

## Data Isolation
- Each device gets its own episodes, facts, and profile
- Agent strategies are global (agents learn from all users)
- Project profiles are global (KB metadata shared)

## Privacy
- Data stored locally in SQLite (`data/memory/deep_memory.db`)
- No external API calls for memory operations
- Facts extracted via local LLM (LM Studio)
- Device IDs generated client-side (crypto.randomUUID)
