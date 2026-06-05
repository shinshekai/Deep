# LLM Wiki Schema

## Layers

- `raw/`: immutable source layer. Read only. If asked to write here, explain that the user should place the source manually, then request ingestion.
- `wiki/`: agent-maintained working layer.
- `_page-templates/`: read-only page skeletons.
- `tools/`: optional utility scripts.
- `wiki/index.md`: navigational index.
- `wiki/log.md`: append-only operation log.

## Page Types

| Type | Purpose | Path | Naming |
| --- | --- | --- | --- |
| Source | Summary of a raw source | `wiki/sources/<slug>.md` | kebab-case slug from title |
| Entity | Person, company, product, tool, standard, dataset, or project | `wiki/entities/<Name>.md` | PascalCase, disambiguated when needed |
| Concept | Topic, method, theorem, feature, pattern, or idea | `wiki/concepts/<name>.md` | kebab-case |
| Comparison | Structured A vs. B analysis | `wiki/comparisons/<a>-vs-<b>.md` | kebab-case |
| Overview | Top-level synthesis of a domain | `wiki/overviews/<domain>.md` | kebab-case |
| Analysis | Cross-source synthesis or filed query answer | `wiki/analyses/<slug>.md` | kebab-case |

Use the matching template from `_page-templates/`. Do not invent free-form heading structures unless the user asks to evolve the schema.

## Citation Rules

- Use Obsidian wikilinks: `[[EntityName]]`, `[[concepts/concept-name]]`, or `[[sources/source-slug]]`.
- Every factual claim should link to a source page or be placed under `Open Questions`.
- Use explicit paths when short names are ambiguous.
- For quotes, keep excerpts short and respect copyright limits.

## Ingest Checklist

1. Read the source.
2. Ask 2-3 clarifying questions when the source is broad or the desired focus is unclear.
3. Create/update the Source page.
4. Create/update Entity pages for important people, organizations, tools, models, datasets, papers, products, APIs, or projects.
5. Create/update Concept pages for key ideas, methods, terms, assumptions, or claims.
6. Add contradictions where a new claim conflicts with existing pages.
7. Update `wiki/index.md`.
8. Append `wiki/log.md`.
9. Report changed pages and unresolved questions.

## Index Format

```markdown
# Wiki Index
_Last updated: YYYY-MM-DD_

## Sources (N)
- [[sources/slug]] - Short description

## Entities (N)
- [[EntityName]] - Short description

## Concepts (N)
- [[concepts/concept-name]] - Short description

## Comparisons (N)
- [[comparisons/a-vs-b]] - Short description

## Overviews (N)
- [[overviews/domain]] - Short description

## Analyses (N)
- [[analyses/slug]] - Short description
```

## Log Format

```markdown
## [YYYY-MM-DD HH:MM] <operation> | <short-title>

- Pages created: [[page1]], [[page2]]
- Pages updated: [[page3]]
- Contradictions found: [[page4]] vs [[page5]]
- Notes: ...
```

## Schema Evolution

When adding new page types or conventions, update this reference or the target wiki's schema file and append a `schema-update` entry to `wiki/log.md`.
