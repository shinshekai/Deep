"""Service registry — auto-discovers services and registers them with the DI container."""

from pathlib import Path
from typing import TypeVar, Generic, get_type_hints
import importlib
import pkgutil

from app.dependencies import container

T = TypeVar("T")

_SERVICES_DIR = Path(__file__).parent


class ServiceRegistry(Generic[T]):
    def __init__(self, service_type: type[T], name: str | None = None):
        self._type = service_type
        self._name = name or service_type.__name__

    def get(self) -> T:
        return container.get(self._name)

    def register(self, factory, singleton: bool = True) -> None:
        container.register(self._name, factory, singleton=singleton)

    def override(self, factory, singleton: bool = True) -> None:
        container.override(self._name, factory, singleton=singleton)

    @property
    def name(self) -> str:
        return self._name


def discover_services() -> dict[str, type]:
    package = _SERVICES_DIR
    services: dict[str, type] = {}
    for _, module_name, _ in pkgutil.iter_modules([str(package)]):
        if module_name.startswith("_") or module_name in ("base", "logging_config", "metrics", "security", "audit", "secrets", "telemetry"):
            continue
        try:
            mod = importlib.import_module(f"app.services.{module_name}")
        except Exception:
            continue
        for attr_name in dir(mod):
            obj = getattr(mod, attr_name)
            if isinstance(obj, type) and obj.__module__ == f"app.services.{module_name}":
                services[attr_name] = obj
    return services
