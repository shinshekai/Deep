"""Agent-Native Research Artifact (ARA) Compiler Service.

Converts documents into structured, machine-executable knowledge packages
following the ARA protocol from Orchestra Research.

ARA organizes knowledge into 4 interlocking layers:
  - Logic Layer:    claims, concepts, experiments, problem definitions
  - Solution Layer: architecture, algorithms, constraints, heuristics
  - Trace Layer:    exploration DAG preserving dead-ends and decisions
  - Evidence Layer: raw proof tables, figures, extracted data

Key features:
  - Progressive disclosure (PAPER.md ~200 tokens → deeper files on demand)
  - Cross-layer forensic bindings (claims → evidence → code)
  - Dead-end preservation (failed approaches are first-class nodes)
  - Provenance tagging (user, ai-suggested, ai-executed, user-revised)

Reference: https://github.com/Orchestra-Research/Agent-Native-Research-Artifact
"""

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from app.services.lm_studio_client import LMStudioClient

logger = logging.getLogger(__name__)

# Provenance tags per ARA spec
ProvenanceTag = Literal["user", "ai-suggested", "ai-executed", "user-revised"]


@dataclass
class Claim:
    """A falsifiable assertion extracted from the document."""

    claim_id: str
    statement: str
    evidence_refs: list[str] = field(default_factory=list)
    status: str = "unverified"  # unverified, supported, refuted
    provenance: ProvenanceTag = "ai-suggested"


@dataclass
class Concept:
    """A formal definition or key concept."""

    concept_id: str
    name: str
    definition: str
    related_concepts: list[str] = field(default_factory=list)
    provenance: ProvenanceTag = "ai-suggested"


@dataclass
class Heuristic:
    """An implementation trick or practical insight."""

    heuristic_id: str
    description: str
    rationale: str
    constraints: list[str] = field(default_factory=list)
    provenance: ProvenanceTag = "ai-suggested"


@dataclass
class ExplorationNode:
    """A node in the research exploration DAG."""

    node_id: str
    node_type: str  # hypothesis, experiment, dead-end, pivot, result
    description: str
    parent_id: str | None = None
    children: list[str] = field(default_factory=list)
    outcome: str = ""  # success, failure, partial, abandoned
    provenance: ProvenanceTag = "ai-suggested"


@dataclass
class ARArtifact:
    """Complete ARA knowledge package for a document."""

    doc_id: str
    title: str
    summary: str  # ~200 tokens for progressive disclosure
    # Logic layer
    claims: list[Claim] = field(default_factory=list)
    concepts: list[Concept] = field(default_factory=list)
    # Solution layer
    heuristics: list[Heuristic] = field(default_factory=list)
    architecture: str = ""
    constraints: list[str] = field(default_factory=list)
    # Trace layer
    exploration_nodes: list[ExplorationNode] = field(default_factory=list)
    # Metadata
    created_at: float = field(default_factory=time.time)
    provenance: ProvenanceTag = "ai-executed"

    def to_dict(self) -> dict:
        return asdict(self)


# ── LLM Prompts for the 4-stage epistemic protocol ──

EXTRACTION_PROMPTS = {
    "manifest": (
        "You are an ARA Compiler. Generate a concise manifest (~200 tokens) for this document. "
        "Include: title, core thesis, key contribution, target audience, and domain. "
        "This manifest helps agents quickly determine if the document is relevant.\n\n"
        "Output ONLY the manifest text, no markdown headers."
    ),
    "claims": (
        "Extract all falsifiable claims from this text. A claim is a specific, testable assertion. "
        "For each claim, output JSON array with objects: "
        '{{"statement": "...", "evidence_hints": ["..."]}}\n'
        "Output ONLY valid JSON array. No explanation."
    ),
    "concepts": (
        "Extract all key concepts and formal definitions from this text. "
        "For each concept, output JSON array with objects: "
        '{{"name": "...", "definition": "...", "related": ["..."]}}\n'
        "Output ONLY valid JSON array. No explanation."
    ),
    "heuristics": (
        "Extract all implementation heuristics, practical tricks, and non-obvious insights. "
        "For each, output JSON array with objects: "
        '{{"description": "...", "rationale": "...", "constraints": ["..."]}}\n'
        "Output ONLY valid JSON array. No explanation."
    ),
    "architecture": (
        "Describe the system architecture or methodology presented in this text. "
        "Include component relationships, data flow, and design decisions. "
        "Output a structured description in plain text."
    ),
    "exploration": (
        "Reconstruct the research exploration graph from this text. "
        "Identify: hypotheses tested, experiments run, dead-ends encountered, and pivots made. "
        "Output JSON array with objects: "
        '{{"type": "hypothesis|experiment|dead-end|pivot|result", '
        '"description": "...", "outcome": "success|failure|partial|abandoned", '
        '"parent": null}}\n'
        "Output ONLY valid JSON array."
    ),
}


class ARACompiler:
    """Compiles documents into ARA knowledge packages."""

    def __init__(self, lm_client: LMStudioClient):
        self.lm_client = lm_client

    async def compile(
        self,
        doc_id: str,
        text: str | dict,
        model_id: str = "Qwen3-1.7B-Q4_K_M",
        title: str = "",
    ) -> ARArtifact:
        """Compile text into an ARA artifact using the 4-stage epistemic protocol.

        Stages:
          1. Semantic Deconstruction — extract raw knowledge atoms
          2. Cognitive Mapping — map to claims, concepts, experiments
          3. Physical Stubbing — generate heuristics and architecture
          4. Exploration Graph — reconstruct the research DAG
        """
        logger.info(f"ARA compilation started for doc {doc_id}")

        # Normalize input — extract_text returns dict, but compile expects string
        if isinstance(text, dict):
            text = text.get("content", "") or ""
        elif not isinstance(text, str):
            text = str(text)

        # Truncate to reasonable context for local models
        text_chunk = text[:8000]

        # Stage 1 & 2: Extract manifest + claims + concepts in parallel
        manifest_task = self._extract("manifest", text_chunk, model_id)
        claims_task = self._extract("claims", text_chunk, model_id)
        concepts_task = self._extract("concepts", text_chunk, model_id)

        manifest, claims_raw, concepts_raw = await asyncio.gather(
            manifest_task, claims_task, concepts_task
        )

        # Stage 3: Extract heuristics + architecture
        heuristics_raw, architecture = await asyncio.gather(
            self._extract("heuristics", text_chunk, model_id),
            self._extract("architecture", text_chunk, model_id),
        )

        # Stage 4: Exploration graph
        exploration_raw = await self._extract("exploration", text_chunk, model_id)

        # Parse results
        claims = self._parse_claims(claims_raw)
        concepts = self._parse_concepts(concepts_raw)
        heuristics = self._parse_heuristics(heuristics_raw)
        exploration = self._parse_exploration(exploration_raw)

        artifact = ARArtifact(
            doc_id=doc_id,
            title=title or doc_id,
            summary=manifest,
            claims=claims,
            concepts=concepts,
            heuristics=heuristics,
            architecture=architecture,
            exploration_nodes=exploration,
        )

        logger.info(
            f"ARA compilation complete: {len(claims)} claims, "
            f"{len(concepts)} concepts, {len(heuristics)} heuristics, "
            f"{len(exploration)} exploration nodes"
        )

        return artifact

    async def _extract(self, stage: str, text: str, model_id: str) -> str:
        """Call LLM for a single extraction stage."""
        prompt = EXTRACTION_PROMPTS.get(stage, "Summarize this text.")
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": text},
        ]
        try:
            result = await self.lm_client.stream_chat_completion(
                model=model_id,
                messages=messages,
                max_tokens=2048,
            )
            return (result or {}).get("content", "")
        except Exception as e:
            logger.error(f"ARA extraction stage '{stage}' failed: {e}")
            return ""

    def _parse_claims(self, raw: str) -> list[Claim]:
        """Parse JSON claims from LLM output."""
        items = self._safe_parse_json(raw)
        claims = []
        for i, item in enumerate(items):
            claims.append(
                Claim(
                    claim_id=f"CLM-{i + 1:03d}",
                    statement=item.get("statement", str(item)),
                    evidence_refs=item.get("evidence_hints", []),
                )
            )
        return claims

    def _parse_concepts(self, raw: str) -> list[Concept]:
        """Parse JSON concepts from LLM output."""
        items = self._safe_parse_json(raw)
        concepts = []
        for i, item in enumerate(items):
            concepts.append(
                Concept(
                    concept_id=f"CON-{i + 1:03d}",
                    name=item.get("name", f"Concept {i + 1}"),
                    definition=item.get("definition", str(item)),
                    related_concepts=item.get("related", []),
                )
            )
        return concepts

    def _parse_heuristics(self, raw: str) -> list[Heuristic]:
        """Parse JSON heuristics from LLM output."""
        items = self._safe_parse_json(raw)
        heuristics = []
        for i, item in enumerate(items):
            heuristics.append(
                Heuristic(
                    heuristic_id=f"HEU-{i + 1:03d}",
                    description=item.get("description", str(item)),
                    rationale=item.get("rationale", ""),
                    constraints=item.get("constraints", []),
                )
            )
        return heuristics

    def _parse_exploration(self, raw: str) -> list[ExplorationNode]:
        """Parse JSON exploration nodes from LLM output."""
        items = self._safe_parse_json(raw)
        nodes = []
        for i, item in enumerate(items):
            nodes.append(
                ExplorationNode(
                    node_id=f"EXP-{i + 1:03d}",
                    node_type=item.get("type", "hypothesis"),
                    description=item.get("description", str(item)),
                    outcome=item.get("outcome", ""),
                )
            )
        return nodes

    @staticmethod
    def _safe_parse_json(raw: str) -> list[dict]:
        """Robustly extract JSON array from LLM output."""
        if not raw:
            return []
        # Try direct parse
        try:
            result = json.loads(raw)
            if isinstance(result, list):
                return result
            return [result]
        except json.JSONDecodeError:
            pass
        # Try extracting JSON from markdown code block
        import re

        match = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        # Try finding array substring
        start = raw.find("[")
        end = raw.rfind("]")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
        return []

    def persist(self, artifact: ARArtifact, base_path: Path) -> Path:
        """Persist an ARA artifact to the filesystem in the ARA directory structure.

        Creates:
          {base_path}/ara/{doc_id}/
            ├── PAPER.md           # ~200-token manifest
            ├── logic/
            │   ├── claims.json
            │   └── concepts.json
            ├── solution/
            │   ├── architecture.md
            │   └── heuristics.json
            └── trace/
                └── exploration.json

        Each write is best-effort: an OSError (disk full, permission
        denied, etc.) on one file is logged but does not abort the
        other writes. Returns the directory path on success; if the
        top-level directory cannot be created, raises ``OSError`` so
        the caller knows nothing was persisted.
        """
        ara_dir = base_path / "ara" / artifact.doc_id
        try:
            (ara_dir / "logic").mkdir(parents=True, exist_ok=True)
            (ara_dir / "solution").mkdir(parents=True, exist_ok=True)
            (ara_dir / "trace").mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create ARA directories under {ara_dir}: {e}")
            raise

        # Each write is isolated so one failure doesn't lose everything.
        def _safe_write(path: Path, content: str) -> None:
            try:
                path.write_text(content, encoding="utf-8")
            except OSError as e:
                logger.error(f"Failed to write ARA file {path}: {e}")

        # PAPER.md — progressive disclosure manifest
        _safe_write(ara_dir / "PAPER.md", f"# {artifact.title}\n\n{artifact.summary}\n")

        # Logic layer
        _safe_write(
            ara_dir / "logic" / "claims.json",
            json.dumps([asdict(c) for c in artifact.claims], indent=2),
        )
        _safe_write(
            ara_dir / "logic" / "concepts.json",
            json.dumps([asdict(c) for c in artifact.concepts], indent=2),
        )

        # Solution layer
        _safe_write(ara_dir / "solution" / "architecture.md", artifact.architecture)
        _safe_write(
            ara_dir / "solution" / "heuristics.json",
            json.dumps([asdict(h) for h in artifact.heuristics], indent=2),
        )

        # Trace layer
        _safe_write(
            ara_dir / "trace" / "exploration.json",
            json.dumps([asdict(n) for n in artifact.exploration_nodes], indent=2),
        )

        logger.info(f"ARA artifact persisted to {ara_dir}")
        return ara_dir

    def search_claims(self, artifact: ARArtifact, query: str) -> list[Claim]:
        """Search claims by keyword matching."""
        query_lower = query.lower()
        return [c for c in artifact.claims if query_lower in c.statement.lower()]

    def search_heuristics(self, artifact: ARArtifact, query: str) -> list[Heuristic]:
        """Search heuristics by keyword matching."""
        query_lower = query.lower()
        return [
            h
            for h in artifact.heuristics
            if query_lower in h.description.lower() or query_lower in h.rationale.lower()
        ]

    def get_exploration_trace(self, artifact: ARArtifact) -> list[ExplorationNode]:
        """Return the full exploration DAG."""
        return artifact.exploration_nodes

    def load(self, base_path: Path, doc_id: str) -> ARArtifact | None:
        """Load a persisted ARA artifact from disk."""
        ara_dir = base_path / "ara" / doc_id
        if not ara_dir.exists():
            return None

        try:
            paper_md = (ara_dir / "PAPER.md").read_text(encoding="utf-8")
            lines = paper_md.split("\n")
            title = lines[0].lstrip("# ").strip() if lines else doc_id
            # Skip title line and join the rest as the summary
            summary = "\n".join(lines[2:]) if len(lines) > 2 else ""

            claims_data = (
                json.loads((ara_dir / "logic" / "claims.json").read_text(encoding="utf-8"))
                if (ara_dir / "logic" / "claims.json").exists()
                else []
            )

            concepts_data = (
                json.loads((ara_dir / "logic" / "concepts.json").read_text(encoding="utf-8"))
                if (ara_dir / "logic" / "concepts.json").exists()
                else []
            )

            heuristics_data = (
                json.loads((ara_dir / "solution" / "heuristics.json").read_text(encoding="utf-8"))
                if (ara_dir / "solution" / "heuristics.json").exists()
                else []
            )

            architecture = (
                (ara_dir / "solution" / "architecture.md").read_text(encoding="utf-8")
                if (ara_dir / "solution" / "architecture.md").exists()
                else ""
            )

            exploration_data = (
                json.loads((ara_dir / "trace" / "exploration.json").read_text(encoding="utf-8"))
                if (ara_dir / "trace" / "exploration.json").exists()
                else []
            )

            return ARArtifact(
                doc_id=doc_id,
                title=title,
                summary=summary,
                claims=[Claim(**c) for c in claims_data],
                concepts=[Concept(**c) for c in concepts_data],
                heuristics=[Heuristic(**h) for h in heuristics_data],
                architecture=architecture,
                exploration_nodes=[ExplorationNode(**n) for n in exploration_data],
            )
        except Exception as e:
            logger.error(f"Failed to load ARA artifact for {doc_id}: {e}")
            return None
