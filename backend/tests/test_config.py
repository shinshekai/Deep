"""Tests for config settings."""


def test_pageindex_settings_exist():
    from app.config import get_settings
    settings = get_settings()
    assert hasattr(settings, "pageindex_model")
    assert hasattr(settings, "pageindex_max_pages_per_node")
    assert hasattr(settings, "pageindex_max_tokens_per_node")
    assert settings.pageindex_max_pages_per_node == 10
    assert settings.pageindex_max_tokens_per_node == 20000
