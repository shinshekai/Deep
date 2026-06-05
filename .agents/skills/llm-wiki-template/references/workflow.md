# LLM Wiki Workflow

## Cadence

| Cadence | Operation | Trigger |
| --- | --- | --- |
| Per source | ingest | New useful source material |
| Ad hoc | query | User asks what the wiki says |
| Ad hoc | file | Query result is worth preserving |
| Weekly | lint | Regular quality control |
| Monthly | reindex | Bulk changes or drift |

## Bootstrap

1. Create `raw/`, `wiki/`, `_page-templates/`, and optional `tools/`.
2. Create wiki subfolders: `sources`, `entities`, `concepts`, `comparisons`, `overviews`, `analyses`, `lint-reports`.
3. Copy page templates from the skill assets into `_page-templates/`.
4. Initialize `wiki/index.md` and `wiki/log.md`.
5. Ask the user for the wiki scope, preferred language, and source curation rule.

## Ingest Flow

```text
User provides source
  -> read source
  -> ask focus questions if needed
  -> write Source page
  -> update Entity and Concept pages
  -> update Comparisons/Overviews/Analyses if justified
  -> update index
  -> append log
  -> report diff summary
```

Prefer updating existing pages over creating near-duplicates. Preserve the user's wording when the user curated a claim manually.

## Query Flow

```text
User asks a question
  -> read wiki/index.md
  -> search wiki titles, links, and headings
  -> read relevant pages fully
  -> answer with wikilink citations
  -> offer filing only when the answer has durable value
```

No writes during query unless the user explicitly requests filing or page updates.

## Lint Flow

Create `wiki/lint-reports/YYYY-MM-DD.md` with:

- Contradictions: pages with contradiction sections or incompatible claims.
- Orphans: pages with no inbound wikilinks.
- Stubs: pages with little body content.
- Missing concepts: important repeated terms with no concept page.
- Stale claims: dated claims that need refresh.
- Broken links: `[[...]]` targets that do not exist.
- Index drift: pages missing from index or index entries whose files are gone.

Report findings and wait for user direction before fixing.

## Human-in-the-Loop Rules

- The user curates sources.
- The user decides whether query answers become permanent pages.
- The user decides how lint findings are resolved.
- The agent writes wiki pages, detects contradictions, maintains index/log, and reports exactly what changed.
