# Frontend Integration Plan

**Date**: 2026-04-26

## Objective
With the backend fully implemented across all functional requirements (FR-1 to FR-7), this plan details the final phase: integrating the React/Next.js frontend with the newly exposed API endpoints.

## Task Breakdown

### Task 1: Questions Page (FR-4)
**Target:** `app/(platform)/questions/page.tsx`
- **UI Components:**
  - Form to select Knowledge Base, Topic, Difficulty (Easy, Medium, Hard), Question Type, and Count.
  - Optional upload/text area for "Reference Exam" to trigger Exam Mimicry mode.
  - Results view to display generated questions, correct answers, and explanations.
- **API Integration:**
  - `POST /api/v1/questions/generate`

### Task 2: Guided Learning Page (FR-5)
**Target:** `app/(platform)/guide/page.tsx`
- **UI Components:**
  - Setup screen to select KB and Topic.
  - Learning Path Sidebar: Displays the 3-5 progressive knowledge points.
  - Main Content Area: Renders the raw HTML returned by the `InteractiveAgent`.
  - Chat Widget: A contextual chat box to talk to the `ChatAgent`.
  - Summary Modal: Displays the `SummaryAgent`'s final review.
- **API Integration:**
  - `POST /api/v1/learning/start`
  - `POST /api/v1/learning/{session_id}/page`
  - `POST /api/v1/learning/{session_id}/chat`
  - `POST /api/v1/learning/{session_id}/end`

### Task 3: Deep Research Page (FR-6)
**Target:** `app/(platform)/research/page.tsx`
- **UI Components:**
  - Setup screen for entering the broad research query and selecting parallel vs series mode.
  - Dynamic Topic Queue Component: Visualizes subtopics transitioning from `PENDING` -> `RESEARCHING` -> `COMPLETED`.
  - Polling mechanism to refresh status every 2-3 seconds.
  - Final Report View: Renders the compiled Markdown report with citations.
- **API Integration:**
  - `POST /api/v1/research` (Start)
  - `GET /api/v1/research/{session_id}` (Poll status)

### Task 4: Content Creation — Notebooks & CoWriter (FR-7)
**Target:** New pages `app/(platform)/notebooks/page.tsx` and `app/(platform)/cowriter/page.tsx` (if they don't exist yet)
- **UI Components (Notebooks):**
  - List view of all notebooks.
  - Markdown editor for adding notes.
  - Button to trigger Idea Generation on selected notebooks.
- **UI Components (CoWriter):**
  - AI Toolbar in the editor: "Rewrite", "Shorten", "Expand", "Auto-Annotate".
- **API Integration:**
  - `GET /api/v1/notebooks`
  - `POST /api/v1/notebooks`
  - `POST /api/v1/notebooks/{id}/notes`
  - `POST /api/v1/ideagen/generate`
  - `POST /api/v1/cowriter/edit`
  - `POST /api/v1/cowriter/annotate`

## Next Steps
We will begin tackling these tasks sequentially, starting with Task 1 (Questions Page).
