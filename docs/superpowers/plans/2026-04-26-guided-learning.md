# Phase 13: Guided Learning Implementation Plan

**Date**: 2026-04-26
**Target FR**: FR-5 (Guided Learning)

## Objective
Implement the Guided Learning module (FR-5) which provides an interactive, progressive learning experience. The system translates concepts into a structured learning path, generates interactive HTML pages for each point, enables contextual Q&A, and produces session summaries.

## Architectural Design

The module will be implemented as a dedicated service `GuidedLearningService` in `app/services/guided_learning.py` with 4 specialized agents:
1. **LocateAgent**: Identifies the 3-5 progressive knowledge points from the requested topic/notebook using the retrieval pipeline.
2. **InteractiveAgent**: Generates rich, interactive HTML learning materials (visual aids, step-by-step breakdowns) for a specific knowledge point.
3. **ChatAgent**: Handles contextual Q&A from the user while they are studying a specific knowledge point.
4. **SummaryAgent**: Concludes the learning session by generating a session summary and saving it to disk.

## Task Breakdown

### Task 1: Create GuidedLearningService (`app/services/guided_learning.py`)
- Implement `start_session(kb_name, topic, retrieval_pipeline)`:
  - Calls `LocateAgent` to retrieve context and outline 3-5 progressive knowledge points.
  - Initializes a session state in `data/user/guide/session_{session_id}.json`.
- Implement `generate_interactive_page(session_id, point_index)`:
  - Calls `InteractiveAgent` to generate the HTML content for the specified knowledge point in the plan.
- Implement `chat(session_id, point_index, user_message)`:
  - Calls `ChatAgent` with the context of the current knowledge point and the user's question.
- Implement `end_session(session_id)`:
  - Calls `SummaryAgent` to review the chat history and progress, generate a summary, and finalize the JSON file.

### Task 2: Implement API Endpoints (`app/routers/agent.py`)
- POST `/learning/start`: Initializes the session and returns the learning plan (knowledge points).
- POST `/learning/{session_id}/page`: Generates and returns the interactive HTML for a specific point.
- POST `/learning/{session_id}/chat`: Sends a message to the ChatAgent and returns the response.
- POST `/learning/{session_id}/end`: Ends the session and returns the summary.

### Task 3: Unit Testing
- Create `tests/test_guided_learning.py` to test the 4-agent flow, session persistence, and API logic.

## Execution Requirements
- Use `app.routers.retrieval.retrieve` for initial context gathering.
- Ensure the `InteractiveAgent` returns clean HTML strings that can be safely rendered by the frontend.
- `session_id` should track progress, chat history, and the initial plan.
