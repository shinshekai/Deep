"""Plugin-based model provider registry with auto-discovery.

Each BaseModelProvider subclass auto-registers via __init_subclass__.
Provider metadata lives on the class, not in separate lists.
Callers discover providers through BaseModelProvider.get_*() classmethods.
"""

from __future__ import annotations

from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import Any


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    name: str
    source: str
    api_key_env: str | tuple[str, ...] | None = None
    base_url_env: str | None = None
    default_base_url: str | None = None
    models_path: str = "/v1/models"
    auth_style: str = "bearer"
    openai_compatible: bool = False
    enabled_without_config: bool = False
    cost_hint: str = "Free"
    latency_hint: str = "Fast"
    description: str = ""
    setup_docs_url: str = ""


class BaseModelProvider(ABC):
    """Auto-registering model provider plugin.

    Subclasses are automatically registered when defined.
    Metadata fields replace the old ProviderSpec lists.
    """

    _registry: dict[str, type["BaseModelProvider"]] = {}

    id: str = ""
    name: str = ""
    kind: str = "local"
    api_key_env: str | tuple[str, ...] | None = None
    base_url_env: str | None = None
    default_base_url: str | None = None
    models_path: str = "/v1/models"
    auth_style: str = "bearer"
    openai_compatible: bool = False
    enabled_without_config: bool = False
    cost_hint: str = "Free"
    latency_hint: str = "Fast"
    description: str = ""
    setup_docs_url: str = ""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.id:
            BaseModelProvider._registry[cls.id] = cls

    @classmethod
    def get_all(cls) -> list[type["BaseModelProvider"]]:
        return list(cls._registry.values())

    @classmethod
    def get(cls, provider_id: str) -> type["BaseModelProvider"] | None:
        return cls._registry.get(provider_id)

    @classmethod
    def get_all_specs(cls) -> list["ProviderSpec"]:
        return [c.to_spec() for c in cls._registry.values()]

    @classmethod
    def get_local_specs(cls) -> list["ProviderSpec"]:
        return [c.to_spec() for c in cls._registry.values() if c.kind == "local"]

    @classmethod
    def get_cloud_specs(cls) -> list["ProviderSpec"]:
        return [c.to_spec() for c in cls._registry.values() if c.kind == "cloud"]

    @classmethod
    def get_spec(cls, provider_id: str) -> "ProviderSpec | None":
        provider_cls = cls._registry.get(provider_id)
        return provider_cls.to_spec() if provider_cls else None

    @classmethod
    def to_spec(cls) -> "ProviderSpec":
        return ProviderSpec(
            id=cls.id,
            name=cls.name,
            source=cls.kind,
            api_key_env=cls.api_key_env,
            base_url_env=cls.base_url_env,
            default_base_url=cls.default_base_url,
            models_path=cls.models_path,
            auth_style=cls.auth_style,
            openai_compatible=cls.openai_compatible,
            enabled_without_config=cls.enabled_without_config,
            cost_hint=cls.cost_hint,
            latency_hint=cls.latency_hint,
            description=cls.description,
            setup_docs_url=cls.setup_docs_url,
        )

    @abstractmethod
    async def discover(self, discovery_service) -> dict[str, Any]:
        ...

    @abstractmethod
    async def health_check(self, discovery_service, api_key: str = "") -> dict[str, Any]:
        ...


class LMStudioProvider(BaseModelProvider):
    id = "lm_studio"
    name = "LM Studio"
    kind = "local"
    base_url_env = "LLM_HOST"
    default_base_url = "http://localhost:1234"
    models_path = "/v1/models"
    openai_compatible = True
    enabled_without_config = True
    cost_hint = "Free (Local)"
    latency_hint = "Ultra-Fast"
    description = "Local LLM server. Launch LM Studio, load your model, and enable the Developer server."
    setup_docs_url = "https://lmstudio.ai"

    async def discover(self, discovery_service) -> dict:
        return await discovery_service._discover_lm_studio(self.to_spec())

    async def health_check(self, discovery_service, api_key: str = "") -> dict:
        return await discovery_service._check_http_provider(self.to_spec(), api_key)


class OllamaProvider(BaseModelProvider):
    id = "ollama"
    name = "Ollama"
    kind = "local"
    base_url_env = "OLLAMA_HOST"
    default_base_url = "http://localhost:11434"
    models_path = "/api/tags"
    openai_compatible = True
    enabled_without_config = True
    cost_hint = "Free (Local)"
    latency_hint = "Ultra-Fast"
    description = "Run large language models locally. Install Ollama and pull any GGUF models."
    setup_docs_url = "https://ollama.com"

    async def discover(self, discovery_service) -> dict:
        return await discovery_service._discover_http_provider(self.to_spec())

    async def health_check(self, discovery_service, api_key: str = "") -> dict:
        return await discovery_service._check_http_provider(self.to_spec(), api_key)


class LlamaCppProvider(BaseModelProvider):
    id = "llama_cpp"
    name = "llama.cpp OpenAI server"
    kind = "local"
    base_url_env = "LLAMA_CPP_HOST"
    models_path = "/v1/models"
    openai_compatible = True
    cost_hint = "Free (Local)"
    latency_hint = "Ultra-Fast"
    description = "Ultra-fast, lightweight C++ inference backend. Start the server with a GGUF model."
    setup_docs_url = "https://github.com/ggerganov/llama.cpp"

    async def discover(self, discovery_service) -> dict:
        return await discovery_service._discover_http_provider(self.to_spec())

    async def health_check(self, discovery_service, api_key: str = "") -> dict:
        return await discovery_service._check_http_provider(self.to_spec(), api_key)


class VLMProvider(BaseModelProvider):
    id = "vlm"
    name = "VLM OpenAI-compatible server"
    kind = "local"
    base_url_env = "VLM_HOST"
    models_path = "/v1/models"
    openai_compatible = True
    cost_hint = "Free (Local)"
    latency_hint = "Ultra-Fast"
    description = "Vision-language model server. Configure the VLM base URL endpoint."
    setup_docs_url = "https://github.com/vllm-project/vllm"

    async def discover(self, discovery_service) -> dict:
        return await discovery_service._discover_http_provider(self.to_spec())

    async def health_check(self, discovery_service, api_key: str = "") -> dict:
        return await discovery_service._check_http_provider(self.to_spec(), api_key)


class OpenaiProvider(BaseModelProvider):
    id = "openai"
    name = "OpenAI"
    kind = "cloud"
    api_key_env = "OPENAI_API_KEY"
    default_base_url = "https://api.openai.com"
    models_path = "/v1/models"
    openai_compatible = True
    cost_hint = "$ (Variable)"
    latency_hint = "Fast"
    description = "Industry standard LLMs including GPT-4o and o1. Get an API key from the OpenAI Dashboard."
    setup_docs_url = "https://platform.openai.com/api-keys"

    async def discover(self, discovery_service) -> dict:
        return await discovery_service._discover_http_provider(self.to_spec())

    async def health_check(self, discovery_service, api_key: str = "") -> dict:
        return await discovery_service._check_http_provider(self.to_spec(), api_key)


class AnthropicProvider(BaseModelProvider):
    id = "anthropic"
    name = "Claude / Anthropic"
    kind = "cloud"
    api_key_env = "ANTHROPIC_API_KEY"
    default_base_url = "https://api.anthropic.com"
    models_path = "/v1/models"
    auth_style = "anthropic"
    cost_hint = "$$ (Premium)"
    latency_hint = "Medium"
    description = "Advanced reasoning models like Claude 3.5 Sonnet. Acquire keys from the Anthropic Console."
    setup_docs_url = "https://console.anthropic.com/settings/keys"

    async def discover(self, discovery_service) -> dict:
        return await discovery_service._discover_http_provider(self.to_spec())

    async def health_check(self, discovery_service, api_key: str = "") -> dict:
        return await discovery_service._check_http_provider(self.to_spec(), api_key)


class GeminiProvider(BaseModelProvider):
    id = "gemini"
    name = "Google Gemini"
    kind = "cloud"
    api_key_env = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
    default_base_url = "https://generativelanguage.googleapis.com"
    models_path = "/v1beta/models"
    auth_style = "query_key"
    cost_hint = "$ (Competitive)"
    latency_hint = "Fast"
    description = "Fast models with massive context windows (Gemini 2.5 Flash). Create an API key in Google AI Studio."
    setup_docs_url = "https://aistudio.google.com/app/apikey"

    async def discover(self, discovery_service) -> dict:
        return await discovery_service._discover_http_provider(self.to_spec())

    async def health_check(self, discovery_service, api_key: str = "") -> dict:
        return await discovery_service._check_http_provider(self.to_spec(), api_key)


class MistralProvider(BaseModelProvider):
    id = "mistral"
    name = "Mistral"
    kind = "cloud"
    api_key_env = "MISTRAL_API_KEY"
    default_base_url = "https://api.mistral.ai"
    models_path = "/v1/models"
    openai_compatible = True
    cost_hint = "$ (Competitive)"
    latency_hint = "Medium"
    description = "High-performance open-weight models including Mistral Large. Sign up on Mistral La Plateforme."
    setup_docs_url = "https://console.mistral.ai/api-keys/"

    async def discover(self, discovery_service) -> dict:
        return await discovery_service._discover_http_provider(self.to_spec())

    async def health_check(self, discovery_service, api_key: str = "") -> dict:
        return await discovery_service._check_http_provider(self.to_spec(), api_key)


class VertexProvider(BaseModelProvider):
    id = "vertex"
    name = "Google Vertex AI"
    kind = "cloud"
    api_key_env = ("VERTEX_ACCESS_TOKEN", "GOOGLE_VERTEX_ACCESS_TOKEN")
    base_url_env = "VERTEX_MODELS_URL"
    auth_style = "bearer"
    cost_hint = "$$ (Enterprise)"
    latency_hint = "Medium"
    description = "Enterprise-grade access to Gemini models via Google Cloud Platform."
    setup_docs_url = "https://cloud.google.com/vertex-ai"

    async def discover(self, discovery_service) -> dict:
        return await discovery_service._discover_http_provider(self.to_spec())

    async def health_check(self, discovery_service, api_key: str = "") -> dict:
        return await discovery_service._check_http_provider(self.to_spec(), api_key)


class OpenrouterProvider(BaseModelProvider):
    id = "openrouter"
    name = "OpenRouter"
    kind = "cloud"
    api_key_env = "OPENROUTER_API_KEY"
    default_base_url = "https://openrouter.ai/api"
    models_path = "/v1/models"
    openai_compatible = True
    cost_hint = "$ (Unified)"
    latency_hint = "Variable"
    description = "Unified endpoint for 100+ open and proprietary models. Get a key at openrouter.ai."
    setup_docs_url = "https://openrouter.ai/keys"

    async def discover(self, discovery_service) -> dict:
        return await discovery_service._discover_http_provider(self.to_spec())

    async def health_check(self, discovery_service, api_key: str = "") -> dict:
        return await discovery_service._check_http_provider(self.to_spec(), api_key)


class OpencodeProvider(BaseModelProvider):
    id = "opencode"
    name = "OpenCode / OpenAI-compatible"
    kind = "cloud"
    api_key_env = "OPENCODE_API_KEY"
    base_url_env = "OPENCODE_BASE_URL"
    models_path = "/v1/models"
    openai_compatible = True
    cost_hint = "$ (Unified)"
    latency_hint = "Variable"
    description = "Generic endpoint for any custom OpenAI-compatible inference cloud provider."
    setup_docs_url = ""

    async def discover(self, discovery_service) -> dict:
        return await discovery_service._discover_http_provider(self.to_spec())

    async def health_check(self, discovery_service, api_key: str = "") -> dict:
        return await discovery_service._check_http_provider(self.to_spec(), api_key)
