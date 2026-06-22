"""Two-layer plugin model: Tools (single-shot) + Capabilities (multi-stage).

Layer 1 — BaseTool: Single-shot operations. LLM picks on demand.
  Registered in ToolRegistry, discoverable by the dispatch loop.
  Supports deferred loading for progressive disclosure.

Layer 2 — BaseCapability: Multi-stage pipelines that own the turn.
  Registered in CapabilityRegistry. Configured with activation gates.
  Can call multiple Tools internally.

Inspired by DeepTutor's tool_protocol.py / capability_protocol.py and
the Agent Tool Protocol (monday.com).
"""

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """A single-shot tool that can be called by the LLM in a dispatch loop."""

    name: str = ""
    description: str = ""
    parameters: dict[str, Any] = {}
    deferred: bool = False

    @abstractmethod
    async def execute(self, args: dict[str, Any], context: dict[str, Any]) -> str:
        """Execute the tool and return a result string for the LLM.

        `context` carries session-scoped values (lm_client, model_id, kb_name,
        retrieval_pipeline, ws_send) so tools can call sub-agents or services.
        """
        ...

    def to_openai_tool(self) -> dict[str, Any]:
        """Convert to OpenAI function-calling tool definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Registry of BaseTool instances. Supports deferred loading."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool
        logger.debug("Tool registered: %s", tool.name)

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def get_openai_tools(self, exclude_deferred: bool = True) -> list[dict[str, Any]]:
        """Return all non-deferred tools as OpenAI-compatible definitions."""
        tools = []
        for t in self._tools.values():
            if exclude_deferred and t.deferred:
                continue
            tools.append(t.to_openai_tool())
        return tools

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    def load_deferred(self) -> int:
        """Activate all deferred tools. Returns count of newly activated tools."""
        count = 0
        for t in self._tools.values():
            if t.deferred:
                t.deferred = False
                count += 1
        logger.info("Activated %d deferred tool(s)", count)
        return count


class BaseCapability(ABC):
    """A multi-stage pipeline that owns the conversation turn.

    Capabilities are NOT individual tools. They are orchestrators that
    manage their own sub-agent workflows. The dispatch loop routes to
    the active capability if one is configured.
    """

    name: str = ""
    description: str = ""

    @abstractmethod
    async def execute(self, context: dict[str, Any]) -> str:
        """Run the capability pipeline and return final output.

        `context` includes query, session_id, lm_client, model_id,
        kb_name, retrieval_pipeline, ws_send, tool_registry, etc.
        """
        ...


class CapabilityRegistry:
    """Registry of BaseCapability instances with activation gates."""

    def __init__(self):
        self._capabilities: dict[str, BaseCapability] = {}
        self._active: str | None = None

    def register(self, capability: BaseCapability) -> None:
        self._capabilities[capability.name] = capability
        logger.debug("Capability registered: %s", capability.name)

    def get(self, name: str) -> BaseCapability | None:
        return self._capabilities.get(name)

    def list_names(self) -> list[str]:
        return list(self._capabilities.keys())

    @property
    def active(self) -> str | None:
        return self._active

    def activate(self, name: str) -> None:
        if name not in self._capabilities:
            raise ValueError(f"Capability not found: {name}")
        self._active = name
        logger.info("Capability activated: %s", name)

    def deactivate(self) -> None:
        self._active = None
        logger.info("Capability deactivated; using default tool dispatch")
