# Phase 15: Content Creation (IdeaGen & Co-Writer) Implementation Plan

**Date**: 2026-04-26
**Target FR**: FR-7 (Content Creation)

## Objective
Implement the Content Creation module (FR-7) encompassing AI-assisted Co-Writing, automated Idea Generation, and a unified Notebook management system. 

## Architectural Design

The system will reside primarily in `app/services/content_creation.py`, split into three components:
1. **CoWriterService**: Exposes tools for rewriting, shortening, expanding, and annotating markdown text.
2. **IdeaGenService**: Analyzes notebook content through a multi-stage filtering pipeline to propose novel research directions.
3. **NotebookService**: Manages user learning records, storing them centrally in `data/user/notebooks/`.

## Task Breakdown

### Task 1: Create NotebookService
- Manage unified learning records across the app.
- Provide functions to save notes, retrieve notebook contents, and list available notebooks.
- Data stored in `data/user/notebooks/{notebook_id}.json`.

### Task 2: Create CoWriterService
- Provide `rewrite(text, instruction)`: Rewrites text according to user instructions.
- Provide `shorten(text)` and `expand(text)`: Adjust text length while maintaining core meaning.
- Provide `auto_annotate(text, kb_name)`: Suggests annotations/citations based on the Knowledge Base.

### Task 3: Create IdeaGenService
- Implement `generate_ideas(notebook_ids)`:
  - Stage 1: Extraction - Parses all notes from selected notebooks.
  - Stage 2: Synthesis - Connects disparate concepts.
  - Stage 3: Proposal - Suggests 3 novel research ideas.

### Task 4: Implement API Endpoints
- In `app/routers/agent.py` (or a dedicated `content.py` router):
  - POST `/notebooks` (Create), GET `/notebooks` (List), PUT `/notebooks/{id}` (Update)
  - POST `/cowriter/edit` (Rewrite/Shorten/Expand)
  - POST `/ideagen/generate` (Generate ideas)

### Task 5: Unit Testing
- Create `tests/test_content_creation.py` testing Notebook CRUD, CoWriter transformations, and IdeaGen pipelines.

## Execution Requirements
- Ensure prompts enforce markdown formatting where appropriate.
- CoWriter operations should be fast and stateless.
