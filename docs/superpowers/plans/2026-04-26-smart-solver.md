# Phase 11: Smart Solver Dual-Loop Agents (FR-3)

## Objective
Implement the full dual-loop agent architecture for the Smart Solver, enabling real-time streaming of reasoning steps, integration with the Vector KB (from Phase 10), and persistent memory storage.

## Requirements Addressed
* **FR-3.1**: Dual-loop architecture processes user questions (Analysis Loop + Solve Loop).
* **FR-3.2**: Reasoning streams in real-time via WebSocket.
* **FR-3.3**: Solver uses RAG (Vector Search) as tools.
* **FR-3.4**: Final answers include step-by-step solutions stored in `data/user/solve/solve_YYYYMMDD_HHMMSS/`.

## Current State
* `solve_orchestrator.py` exists but uses a linear, non-tool-calling prompt chain.
* Streaming is "fake" (it waits for the full completion and doesn't stream tokens).
* No integration with `HybridRAGSearch` or `VectorKBService`.
* No file-based persistence for memory and artifacts.

## Step-by-Step Implementation Plan

### Step 1: Real-Time Token Streaming via WebSocket
* Update `LMStudioClient` to support a `yield_chat` or callback mechanism that yields tokens as they arrive.
* Update `solve_orchestrator.py` to stream these tokens to the frontend using the `agent_step` WebSocket frame.

### Step 2: Agent Tools Integration (Vector RAG)
* Refactor the Analysis Loop (`investigate`, `note`) and Solve Loop (`plan`, `solve`, `check`, `format`).
* Inject the `HybridRAGSearch` service into the `solve` and `investigate` agents.
* Allow agents to issue search queries and append the retrieved snippets to their context before generating the final answer.

### Step 3: Session Persistence
* Create a directory manager that creates `data/user/solve/solve_{timestamp}/` for each session.
* Save the full transcript, notes, plan, and final answer (`final_answer.md`) to this directory.
* Emit the directory path in the final `complete` WebSocket frame.

### Step 4: Testing & Validation
* Create `test_solve_orchestrator.py` to test the dual-loop execution and streaming logic.
* Ensure tool calls properly fetch documents using mock KBs.
