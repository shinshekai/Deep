"""Subagent system — optional local CLI agents consulted as external advisors.

Backend-driven: Claude Code (claude -p) and Codex are auto-discovered.
Each backend can `detect()` whether the CLI is installed, then `consult()`
by spawning an async subprocess and capturing stdout.
"""

import asyncio
import logging
import shutil
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class SubagentBackend(ABC):
    """A local CLI agent that can be used as an advisor subagent."""

    name: str = ""

    @abstractmethod
    async def detect(self) -> bool:
        """Return True if this backend is available on the system."""
        ...

    @abstractmethod
    async def consult(self, prompt: str, *, timeout: float = 120.0) -> str:
        """Send a prompt to the subagent and return its response."""
        ...


class ClaudeCodeBackend(SubagentBackend):
    name = "claude-code"

    async def detect(self) -> bool:
        return shutil.which("claude") is not None

    async def consult(self, prompt: str, *, timeout: float = 120.0) -> str:
        try:
            proc = await asyncio.create_subprocess_exec(
                "claude", "-p", prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return stdout.decode("utf-8", errors="replace").strip() if stdout else stderr.decode("utf-8", errors="replace").strip()
        except asyncio.TimeoutError:
            return f"[claude-code timed out after {timeout}s]"
        except Exception as e:
            return f"[claude-code error: {e}]"


class CodexBackend(SubagentBackend):
    name = "codex"

    async def detect(self) -> bool:
        return shutil.which("codex") is not None

    async def consult(self, prompt: str, *, timeout: float = 120.0) -> str:
        try:
            proc = await asyncio.create_subprocess_exec(
                "codex", "exec", prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return stdout.decode("utf-8", errors="replace").strip() if stdout else stderr.decode("utf-8", errors="replace").strip()
        except asyncio.TimeoutError:
            return f"[codex timed out after {timeout}s]"
        except Exception as e:
            return f"[codex error: {e}]"


class SubagentRegistry:
    """Auto-discovers available subagent backends."""

    def __init__(self):
        self._backends: dict[str, SubagentBackend] = {}
        self._discovered = False

    async def discover(self) -> list[str]:
        """Scan for available backends. Returns list of names found."""
        if self._discovered:
            return list(self._backends.keys())

        candidates: list[SubagentBackend] = [ClaudeCodeBackend(), CodexBackend()]
        for backend in candidates:
            try:
                if await backend.detect():
                    self._backends[backend.name] = backend
                    logger.info("Subagent discovered: %s", backend.name)
            except Exception as e:
                logger.debug("Subagent %s detection failed: %s", backend.name, e)

        self._discovered = True
        return list(self._backends.keys())

    async def consult(self, backend_name: str, prompt: str, *, timeout: float = 120.0) -> str:
        """Consult a specific subagent backend."""
        if not self._discovered:
            await self.discover()

        backend = self._backends.get(backend_name)
        if backend is None:
            return f"[subagent '{backend_name}' not available]"
        return await backend.consult(prompt, timeout=timeout)

    @property
    def available(self) -> list[str]:
        return list(self._backends.keys())
