"""Property-based tests using Hypothesis for data transformations."""

from hypothesis import assume, given
from hypothesis import strategies as st
from hypothesis.strategies import floats, text

TEXT_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_"


class TestComplexityScorerProperties:
    """Property-based tests for complexity scoring."""

    @given(query=text(min_size=1, max_size=500))
    def test_score_in_valid_range(self, query):
        from app.services.complexity_scorer import score_query_complexity

        score, tier = score_query_complexity(query)
        assert 0.0 <= score <= 1.0
        assert tier in [1, 2, 3]

    @given(query=text(min_size=1, max_size=500))
    def test_score_is_deterministic(self, query):
        from app.services.complexity_scorer import score_query_complexity

        score1, tier1 = score_query_complexity(query)
        score2, tier2 = score_query_complexity(query)
        assert score1 == score2
        assert tier1 == tier2

    @given(
        simple=st.sampled_from(["hi", "hello", "yes", "no"]),
        complex=st.sampled_from(
            [
                "Explain the difference between quantum entanglement and superposition",
                "What are the implications of Gödel's incompleteness theorem for AI?",
            ]
        ),
    )
    def test_simple_queries_score_lower(self, simple, complex):
        from app.services.complexity_scorer import score_query_complexity

        simple_score, _ = score_query_complexity(simple)
        complex_score, _ = score_query_complexity(complex)
        assert simple_score <= complex_score


class TestModelManagerProperties:
    """Property-based tests for model manager tier assignment."""

    @given(tier=st.sampled_from([1, 2, 3]))
    def test_tier_mapping_returns_valid_tier(self, tier):
        from app.services.model_manager import MODEL_TIERS

        assert tier in MODEL_TIERS

    @given(model_id=text(min_size=1, max_size=100))
    def test_unknown_model_returns_zero_tier(self, model_id):
        from app.services.model_manager import ModelManager

        assume(
            model_id
            not in [
                "google/gemma-4-e2b",
                "google/gemma-4-e4b",
                "qwen/qwen3.5-9b",
                "zai-org/glm-4.7-flash",
                "google/gemma-4-26b-a4b",
                "google/gemma-4-12b",
            ]
        )
        from unittest.mock import MagicMock

        mgr = ModelManager(MagicMock())
        assert mgr.get_tier_for_model(model_id) == 0

    @given(complexity=floats(min_value=0.0, max_value=1.0))
    def test_tier_from_complexity_in_range(self, complexity):
        from unittest.mock import MagicMock

        from app.services.model_manager import ModelManager

        mgr = ModelManager(MagicMock())
        tier = mgr.get_tier_from_complexity(complexity)
        assert tier in [1, 2, 3]


class TestSecurityProperties:
    """Property-based tests for security functions."""

    @given(token=text(min_size=1, max_size=100))
    def test_validate_model_id_rejects_dangerous_input(self, token):
        import pytest

        from app.services.lm_studio_client import _validate_model_id

        if any(c in token for c in [";", "|", "&", "$", "`", "(", ")", "{", "}"]):
            with pytest.raises(ValueError):
                _validate_model_id(token)

    @given(
        url=st.sampled_from(
            [
                "http://169.254.169.254/latest/meta-data/",
                "https://169.254.169.254/latest/meta-data/",
                "http://169.254.169.254:80/",
            ]
        )
    )
    def test_is_safe_base_url_rejects_metadata(self, url):
        from app.services.security import is_safe_base_url

        assert not is_safe_base_url(url)


class TestPromptRegistryProperties:
    """Property-based tests for prompt registry."""

    @given(name=text(min_size=1, max_size=50, alphabet=TEXT_ALPHABET))
    def test_get_nonexistent_returns_none(self, name):
        from app.services.prompt_registry import PromptRegistry

        assume(name.isidentifier())
        registry = PromptRegistry()
        assert registry.get(name) is None
