---
name: llm-wiki-template
description: Build and maintain a Karpathy-style persistent LLM wiki: immutable raw sources, citation-linked wiki pages, entity/concept pages, query filing, lint reports, and index maintenance. Use when the user asks to set up an LLM wiki, ingest notes/documents into a structured wiki, answer from a local wiki with wikilink citations, file a synthesis as a permanent wiki page, lint wiki pages for contradictions/orphans/stubs/broken links, or adapt IvanKRZ/LLM-Wiki-Template workflows.
---

# LLM Wiki Template

## Overview

Maintain a local knowledge base as a compiled artifact: sources stay immutable, and the agent updates structured wiki pages with citations, links, index entries, and an append-only log.

Use this skill for wiki operations, not general RAG. The user remains the architect: ask before filing new permanent pages, never write to `raw/`, and never auto-fix lint findings without approval.

Adapted for Codex from IvanKRZ/LLM-Wiki-Template.

## Workspace Shape

Create or preserve this layout in the target wiki folder:

```text
raw/              # immutable user-managed source documents
wiki/             # agent-maintained pages
wiki/sources/
wiki/entities/
wiki/concepts/
wiki/comparisons/
wiki/overviews/
wiki/analyses/
wiki/lint-reports/
wiki/index.md
wiki/log.md
_page-templates/  # copy templates from assets/page-templates when bootstrapping
tools/            # optional utilities
```

## Operations

For setup/bootstrap:
- Create the workspace shape above.
- Copy `assets/page-templates/*.md` into `_page-templates/`.
- Initialize `wiki/index.md` and `wiki/log.md` if absent.
- Make no assumptions about source language or scope; ask the user for the wiki domain and preferred language if unclear.

For ingest:
- Read from `raw/` or from a user-provided source path. If the user provides a URL, save or ask them to place a source artifact before ingestion.
- Ask 2-3 clarifying questions about focus, priority, and target language when the source scope is broad.
- Create/update a Source page plus relevant Entity, Concept, Comparison, Overview, or Analysis pages using the matching template.
- Cite claims with `[[sources/slug]]` wikilinks. Put unsupported or conflicting claims under `Open Questions` or `Contradictions`.
- Update `wiki/index.md`, append `wiki/log.md`, and report the changed pages.

For query:
- Read `wiki/index.md`, identify relevant pages with title/link search, then read those pages in full.
- Answer with `[[page]]` citations for factual claims.
- Do not write the answer into the wiki unless the user explicitly asks to file it.

For filing:
- Save a durable synthesis under `wiki/analyses/` or `wiki/overviews/` using a clear slug.
- Update index and log in the same change.

For lint:
- Produce `wiki/lint-reports/YYYY-MM-DD.md`.
- Check contradictions, orphan pages, stubs, missing concepts, stale claims, broken wikilinks, and index drift.
- Report findings; do not fix automatically.

## References

- Read `references/schema.md` for page types, naming, link conventions, index format, and log format.
- Read `references/workflow.md` for operation cadence and the ingest/query/lint playbooks.

Template files live in `assets/page-templates/`. Copy them as starting points; adapt only when the user changes the schema.
