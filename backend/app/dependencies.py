"""Lightweight dependency-injection container.

Usage:
    from app.dependencies import container

    # Register a factory
    container.register("lm_client", lambda: LMStudioClient(...), singleton=True)

    # Resolve
    client = container.get("lm_client")

    # Override in tests
    container.register("lm_client", lambda: mock_client, singleton=True)
    container.reset()  # clear everything
"""

import enum
from collections.abc import Callable
from typing import Any, TypeVar

T = TypeVar("T")


class Lifetime(enum.Enum):
    SINGLETON = "singleton"
    TRANSIENT = "transient"


class _Registration:
    __slots__ = ("_instance", "factory", "lifetime")

    def __init__(self, factory: Callable, lifetime: Lifetime):
        self.factory = factory
        self.lifetime = lifetime
        self._instance: Any = None

    def resolve(self) -> Any:
        if self.lifetime is Lifetime.SINGLETON:
            if self._instance is None:
                self._instance = self.factory()
            return self._instance
        return self.factory()


class Container:
    def __init__(self):
        self._services: dict[str, _Registration] = {}
        self._overrides: dict[str, _Registration] = {}

    def register(
        self,
        name: str,
        factory: Callable[[], Any],
        singleton: bool = True,
    ) -> None:
        lifetime = Lifetime.SINGLETON if singleton else Lifetime.TRANSIENT
        self._services[name] = _Registration(factory, lifetime)

    def get(self, name: str) -> Any:
        reg = self._overrides.get(name) or self._services.get(name)
        if reg is None:
            raise KeyError(f"Service '{name}' not registered")
        return reg.resolve()

    def has(self, name: str) -> bool:
        return name in self._overrides or name in self._services

    def override(self, name: str, factory: Callable[[], Any], singleton: bool = True) -> None:
        lifetime = Lifetime.SINGLETON if singleton else Lifetime.TRANSIENT
        self._overrides[name] = _Registration(factory, lifetime)

    def reset(self) -> None:
        self._services.clear()
        self._overrides.clear()


container = Container()


def get_service(name: str) -> Any:
    return container.get(name)


def get_container() -> Container:
    """Return the global container (may be replaced by state.ServiceContainer)."""
    global container
    return container


def set_container(c: Container) -> None:
    """Replace the global container (used by state.py to share the instance)."""
    global container
    container = c
