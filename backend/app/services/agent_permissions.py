"""Agent permissions — boundaries, privileged action gating, and rate limiting.

Patterns validated against:
- FastAPI rate limiting (Context7: /fastapi/fastapi)
- Sliding window counter algorithm (StackOverflow, Medium)
- AI agent RBAC (Supertokens, NeuralTrust, WorkOS 2026)
- Python asyncio.Lock for thread-safe deque (Python docs 3.14)
"""

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class AgentAction(Enum):
    READ_MEMORY = "read_memory"
    WRITE_MEMORY = "write_memory"
    DELETE_MEMORY = "delete_memory"
    READ_KB = "read_kb"
    WRITE_KB = "write_kb"
    DELETE_KB = "delete_kb"
    EXECUTE_QUERY = "execute_query"
    MODIFY_CONFIG = "modify_config"
    ACCESS_SYSTEM = "access_system"


@dataclass
class AgentPermissionSet:
    agent_type: str
    allowed_actions: set[AgentAction] = field(default_factory=set)
    requires_confirmation: set[AgentAction] = field(default_factory=set)
    max_actions_per_minute: int = 10


AGENT_PERMISSIONS = {
    "smart_solve": AgentPermissionSet(
        agent_type="smart_solve",
        allowed_actions={AgentAction.READ_MEMORY, AgentAction.WRITE_MEMORY, AgentAction.EXECUTE_QUERY},
    ),
    "deep_research": AgentPermissionSet(
        agent_type="deep_research",
        allowed_actions={AgentAction.READ_MEMORY, AgentAction.WRITE_MEMORY, AgentAction.READ_KB},
    ),
    "guided_learning": AgentPermissionSet(
        agent_type="guided_learning",
        allowed_actions={AgentAction.READ_MEMORY, AgentAction.WRITE_MEMORY},
    ),
    "recursive_solver": AgentPermissionSet(
        agent_type="recursive_solver",
        allowed_actions={AgentAction.READ_MEMORY, AgentAction.WRITE_MEMORY, AgentAction.EXECUTE_QUERY},
    ),
    "batch_resolve": AgentPermissionSet(
        agent_type="batch_resolve",
        allowed_actions={AgentAction.READ_MEMORY, AgentAction.WRITE_MEMORY, AgentAction.DELETE_MEMORY},
        max_actions_per_minute=5,
    ),
}


class SlidingWindowRateLimiter:
    """Sliding window rate limiter using deque + asyncio.Lock.

    Pattern from: StackOverflow lock-free rate limiter discussion,
    Python asyncio docs, and Cloudflare/Stripe production implementations.
    More accurate than fixed window — no boundary burst issue.
    """

    def __init__(self, max_requests: int, window_seconds: float = 60.0):
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        async with self._lock:
            now = time.monotonic()
            window_start = now - self._window_seconds

            while self._timestamps and self._timestamps[0] <= window_start:
                self._timestamps.popleft()

            if len(self._timestamps) >= self._max_requests:
                wait_until = self._timestamps[0] + self._window_seconds
                wait_time = wait_until - now
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                self._timestamps.popleft()

            self._timestamps.append(time.monotonic())
            return True


class ActionGate:
    DESTRUCTIVE_ACTIONS = {
        AgentAction.DELETE_MEMORY,
        AgentAction.DELETE_KB,
        AgentAction.MODIFY_CONFIG,
        AgentAction.ACCESS_SYSTEM,
    }

    def __init__(self):
        self._limiters: dict[str, SlidingWindowRateLimiter] = {}
        self._pending_confirmations: dict[str, dict] = {}

    async def check(
        self, agent_type: str, action: AgentAction, device_id: str
    ) -> dict:
        permissions = AGENT_PERMISSIONS.get(agent_type)
        if not permissions:
            raise PermissionError(f"Unknown agent type: {agent_type}")

        if action not in permissions.allowed_actions:
            raise PermissionError(
                f"Agent {agent_type} cannot perform {action.value}"
            )

        limiter = self._get_limiter(agent_type, device_id, permissions.max_actions_per_minute)
        await limiter.acquire()

        if action in self.DESTRUCTIVE_ACTIONS or action in permissions.requires_confirmation:
            confirmation_id = f"{agent_type}:{action.value}:{device_id}:{time.time()}"
            self._pending_confirmations[confirmation_id] = {
                "agent_type": agent_type,
                "action": action,
                "device_id": device_id,
                "requested_at": time.time(),
            }
            return {"needs_confirmation": True, "confirmation_id": confirmation_id}

        return {"needs_confirmation": False}

    def confirm(self, confirmation_id: str) -> dict:
        pending = self._pending_confirmations.pop(confirmation_id, None)
        if not pending:
            raise ValueError("Invalid or expired confirmation ID")
        if time.time() - pending["requested_at"] > 300:
            raise ValueError("Confirmation expired (5 minute limit)")
        return {"confirmed": True, "action": pending["action"].value}

    def _get_limiter(
        self, agent_type: str, device_id: str, max_per_minute: int
    ) -> SlidingWindowRateLimiter:
        key = f"{agent_type}:{device_id}"
        if key not in self._limiters:
            self._limiters[key] = SlidingWindowRateLimiter(
                max_requests=max_per_minute, window_seconds=60.0
            )
        return self._limiters[key]


action_gate = ActionGate()
