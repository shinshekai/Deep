"""Prompt registry — YAML-backed prompt management with semantic versioning.

Loads prompt definitions from ``app/prompts/*.yaml`` files, validates them,
and provides a typed lookup API. Tracks version hashes for audit trails.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@dataclass
class PromptDef:
    name: str
    version: str
    content: str
    max_tokens: int = 2048
    temperature: float = 0.7
    variables: list[str] = field(default_factory=list)
    source_file: str = ""

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode()).hexdigest()[:12]

    def render(self, **kwargs: str) -> str:
        result = self.content
        for key, value in kwargs.items():
            result = result.replace("{" + key + "}", value)
        return result


class PromptRegistry:
    def __init__(self, prompts_dir: str | Path | None = None):
        self._dir = Path(prompts_dir) if prompts_dir else _PROMPTS_DIR
        self._prompts: dict[str, PromptDef] = {}
        self._versions: dict[str, list[str]] = {}

    def load(self) -> int:
        count = 0
        if not self._dir.exists():
            logger.warning("Prompts directory not found: %s", self._dir)
            return 0
        for yaml_file in sorted(self._dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                file_version = data.get("version", "0.0.0")
                for name, prompt_data in data.get("prompts", {}).items():
                    pd = PromptDef(
                        name=name,
                        version=prompt_data.get("version", file_version),
                        content=prompt_data["content"].strip(),
                        max_tokens=prompt_data.get("max_tokens", 2048),
                        temperature=prompt_data.get("temperature", 0.7),
                        variables=prompt_data.get("variables", []),
                        source_file=yaml_file.name,
                    )
                    self._prompts[name] = pd
                    self._versions.setdefault(name, []).append(pd.version)
                    count += 1
                logger.debug(
                    "Loaded %d prompts from %s", len(data.get("prompts", {})), yaml_file.name
                )
            except Exception as e:
                logger.error("Failed to load prompts from %s: %s", yaml_file.name, e)
        logger.info("Prompt registry loaded %d prompts", count)
        return count

    def get(self, name: str) -> PromptDef | None:
        return self._prompts.get(name)

    def render(self, name: str, **kwargs: str) -> str:
        pd = self._prompts.get(name)
        if pd is None:
            raise KeyError(f"Prompt not found: {name}")
        return pd.render(**kwargs)

    def list_prompts(self) -> list[dict]:
        return [
            {
                "name": pd.name,
                "version": pd.version,
                "hash": pd.content_hash,
                "source": pd.source_file,
                "max_tokens": pd.max_tokens,
            }
            for pd in self._prompts.values()
        ]


_registry: PromptRegistry | None = None


def get_prompt_registry() -> PromptRegistry:
    global _registry
    if _registry is None:
        _registry = PromptRegistry()
        _registry.load()
    return _registry
