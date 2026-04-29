# Phase 14: Deep Research Implementation Plan

**Date**: 2026-04-26
**Target FR**: FR-6 (Deep Research)

## Objective
Implement the Deep Research module (FR-6) which manages complex, long-running research tasks via a 3-phase pipeline, a dynamic subtopic queue, and parallel execution. It relies on the local retrieval pipeline to gather context and synthesizes it into a well-cited comprehensive report.

## Architectural Design

The research module will reside in `app/services/deep_research.py`. It orchestrates multiple agents over a background task queue (using `asyncio.TaskGroup` or `asyncio.gather` for parallel processing).

### Three-Phase Pipeline
1. **Planning Phase**: 
   - *RephraseAgent*: Clarifies the user's initial broad query.
   - *DecomposeAgent*: Breaks the query down into 3-5 subtopics and populates the Dynamic Topic Queue.
2. **Researching Phase**:
   - Executes subtopics from the queue (up to 5 concurrently).
   - *ResearchAgent*: Runs queries against the vector/tree KB (`retrieve`).
   - *NoteAgent*: Synthesizes findings and updates the centralized research state.
3. **Reporting Phase**:
   - *ManagerAgent / ReportAgent*: Aggregates all notes from all subtopics into a final, structured markdown report with citations.

### State Management
- Sessions are saved to `data/user/research/session_{session_id}.json`.
- Each subtopic tracks its state: `PENDING`, `RESEARCHING`, `COMPLETED`, `FAILED`.

## Task Breakdown

### Task 1: Create DeepResearchService (`app/services/deep_research.py`)
- Implement `start_research(kb_name, query, mode)`: Initializes the session, runs the Planning phase, populates the queue, and kicks off a background task for the Research phase.
- Implement the async worker `_process_queue(session_id)`: Iterates over the queue in series or parallel (using `asyncio.Semaphore(5)`).
- Implement `_research_subtopic(session_id, subtopic)`: The core research loop that uses the KB to gather context and writes notes.
- Implement `_generate_report(session_id)`: Compiles the final report once all subtopics are completed.
- Implement `get_status(session_id)`: API to poll current progress, subtopic statuses, and the final report.

### Task 2: Implement API Endpoints (`app/routers/agent.py`)
- Update POST `/research`: Accepts research requests and returns the `session_id`.
- Add GET `/research/{session_id}`: Returns the current status of the research session.

### Task 3: Unit Testing
- Create `tests/test_deep_research.py` to test the state machine, subtopic decomposition, and the final report generation. Mock the long-running LLM and retrieval calls.

## Execution Requirements
- Deep research can take minutes. The API must return immediately after the Planning phase (or just after session creation) and let the frontend poll for status.
- Ensure the `LMStudioClient` priority queue can handle the parallel execution without crashing the local LLM.
