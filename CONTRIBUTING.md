# Contributing to Deep

Thanks for your interest in contributing to Deep. This document explains
how to set up your development environment, run tests, and submit a PR.

## Development Setup

1. **Clone the repo** and ensure the submodule is checked out:
   ```bash
   git clone https://github.com/shinshekai/Deep.git
   cd Deep
   git submodule update --init --recursive
   ```

2. **Backend** (Python 3.10+):
   ```bash
   cd backend
   pip install -e ".[dev,type-check,gpu]"
   ```

3. **Frontend** (Node.js 20+):
   ```bash
   cd frontend
   npm install
   ```

## Running Tests

- Backend: `cd backend && pytest`
- Frontend: `cd frontend && npm test`
- Lint: `cd backend && ruff check . && mypy app` and `cd frontend && npm run lint`

## Pre-commit Hooks

The repo ships a `.pre-commit-config.yaml` that runs basic sanity checks
(whitespace, EOF, YAML/JSON/TOML validity, merge-conflict markers, large
files) and the project's existing formatters / linters (ruff, black,
isort, mypy, prettier) on every commit.

```bash
pip install pre-commit
pre-commit install            # one-time, wires the hooks into .git/hooks
pre-commit run --all-files    # optional: run the full suite once
```

Hooks run against staged files only, so existing code is left alone
until you touch it. CI remains the source of truth — pre-commit is an
early-warning signal, not a gate.

## Project Conventions

- **Style:** Pydantic v2 discipline, type hints everywhere, no comments unless asked
- **Commits:** Conventional Commits (`feat:`, `fix:`, `docs:`, etc.)
- **Branches:** `master` is the protected main branch

## Architecture

See `ARCHITECTURE.md` for the high-level architecture. See `docs/adr/`
for the Architecture Decision Records (ADRs) that explain why key
decisions were made.

## Submitting a PR

1. Fork the repo and create a feature branch
2. Make your changes + add tests
3. Run the full test + lint suite
4. Open a PR against `master` with a clear description
5. Wait for CI to pass + a maintainer review
