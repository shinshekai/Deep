"""Tests for the dependency injection container and service registry."""

import pytest

from app.dependencies import Container, container
from app.services.base import ServiceRegistry


class TestContainer:
    def test_register_and_get_singleton(self):
        c = Container()
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return "instance"

        c.register("svc", factory, singleton=True)
        result1 = c.get("svc")
        result2 = c.get("svc")
        assert result1 == "instance"
        assert result2 == "instance"
        assert call_count == 1

    def test_register_and_get_transient(self):
        c = Container()
        call_count = 0

        def factory():
            nonlocal call_count
            call_count += 1
            return f"instance_{call_count}"

        c.register("svc", factory, singleton=False)
        r1 = c.get("svc")
        r2 = c.get("svc")
        assert r1 == "instance_1"
        assert r2 == "instance_2"
        assert call_count == 2

    def test_get_unregistered_raises_key_error(self):
        c = Container()
        with pytest.raises(KeyError, match="nonexistent"):
            c.get("nonexistent")

    def test_has(self):
        c = Container()
        assert not c.has("svc")
        c.register("svc", lambda: 42)
        assert c.has("svc")

    def test_override(self):
        c = Container()
        c.register("svc", lambda: "original")
        c.override("svc", lambda: "overridden")
        assert c.get("svc") == "overridden"

    def test_override_takes_precedence(self):
        c = Container()
        c.register("svc", lambda: "original")
        c.override("svc", lambda: 42, singleton=False)
        assert c.get("svc") == 42

    def test_reset_clears_everything(self):
        c = Container()
        c.register("svc", lambda: "val")
        c.override("svc", lambda: "override")
        c.reset()
        assert not c.has("svc")
        with pytest.raises(KeyError):
            c.get("svc")

    def test_default_singleton(self):
        c = Container()
        c.register("svc", lambda: object())
        a = c.get("svc")
        b = c.get("svc")
        assert a is b

    def test_singleton_caches_instance(self):
        c = Container()
        obj = {"key": "value"}
        c.register("svc", lambda: obj)
        assert c.get("svc") is obj

    def test_override_resets_singleton_cache(self):
        c = Container()
        c.register("svc", lambda: "first")
        assert c.get("svc") == "first"
        c.override("svc", lambda: "second")
        assert c.get("svc") == "second"


class TestContainerModuleSingleton:
    def test_container_is_module_level_singleton(self):
        from app.dependencies import container as c1
        from app.dependencies import container as c2

        assert c1 is c2


class TestServiceRegistry:
    def test_register_and_get(self):
        c = Container()
        reg = ServiceRegistry(dict, "test_svc")
        reg.register(lambda: {"hello": "world"})
        result = reg.get()
        assert result == {"hello": "world"}

    def test_override(self):
        c = Container()
        reg = ServiceRegistry(dict, "test_svc")
        reg.register(lambda: {"a": 1})
        reg.override(lambda: {"b": 2})
        assert reg.get() == {"b": 2}

    def test_name_property(self):
        reg = ServiceRegistry(str, "my_str")
        assert reg.name == "my_str"

    def test_default_name_from_type(self):
        reg = ServiceRegistry(int)
        assert reg.name == "int"


class TestContainerIntegration:
    def test_register_multiple_services(self):
        c = Container()
        c.register("service_a", lambda: "a")
        c.register("service_b", lambda: "b")
        c.register("service_c", lambda: "c")
        assert c.get("service_a") == "a"
        assert c.get("service_b") == "b"
        assert c.get("service_c") == "c"

    def test_factory_receives_no_args(self):
        c = Container()
        c.register("svc", lambda: 42)
        assert c.get("svc") == 42

    def test_override_transient(self):
        c = Container()
        c.register("svc", lambda: "orig", singleton=False)
        c.override("svc", lambda: "new", singleton=False)
        assert c.get("svc") == "new"
        assert c.get("svc") == "new"


class TestModuleContainer:
    def test_global_container_is_usable(self):
        container.register("__test__", lambda: "test_value")
        assert container.get("__test__") == "test_value"
        container.reset()
