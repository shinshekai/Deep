# ADR 0001: Record Architecture Decisions

## Status

Accepted

## Context

We need to record the architectural decisions made on this project. Decisions will be captured as Architecture Decision Records (ADRs) following the MADR format.

## Decision

We will use Architecture Decision Records (ADRs) to document significant architectural decisions. Each ADR will be stored in `docs/adr/` with the format `NNNN-kebab-case-title.md`.

### ADR Structure

Each ADR follows the MADR template:

- **Title** — Short noun phrase describing the decision
- **Status** — Proposed, Accepted, Deprecated, Superseded
- **Context** — What is the issue that we're seeing that motivates this decision?
- **Decision** — What is the change that we're proposing and/or doing?
- **Consequences** — What becomes easier or more difficult because of this change?

### When to Write an ADR

- Choosing a framework or library
- Changing the API design
- Introducing a new architectural pattern
- Changing the data model
- Changing the deployment strategy
- Any decision that affects how the system is built or operated

### Numbering

ADRs are numbered sequentially. The number is zero-padded to 4 digits (e.g., `0001`, `0002`).

## Consequences

- **Positive:** Future developers (including ourselves) can understand why decisions were made
- **Positive:** New contributors can read ADRs to understand the project's architecture
- **Positive:** We can revisit decisions with full context
- **Negative:** Small overhead for writing ADRs (mitigated by keeping them short)
