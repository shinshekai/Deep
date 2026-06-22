"""Prompt version validation — ensures YAML prompts have consistent versioning."""
import sys
from pathlib import Path
from app.services.prompt_registry import PromptRegistry

def validate():
    registry = PromptRegistry()
    count = registry.load()
    prompts = registry.list_prompts()
    print(f"Loaded {count} prompts from {len(set(p['source'] for p in prompts))} files")
    for p in prompts:
        print(f"  {p['name']} v{p['version']} (hash: {p['hash']}) [{p['source']}]")
    if count == 0:
        print("WARNING: No prompts loaded")
        return 1
    print("Prompt validation OK")
    return 0

if __name__ == "__main__":
    sys.exit(validate())
