# Phase 12: Question Generator Implementation Plan

**Date**: 2026-04-26
**Target FR**: FR-4 (Question Generator)

## Objective
Implement the Question Generator module (FR-4) which uses the local LLM and the retrieval pipelines (PageIndex/VectorKB) to generate high-quality custom questions or mimic reference exams, complete with answer keys, explanations, and automatic validation.

## Architectural Design

The Question Generator will be implemented as a dedicated service `QuestionGenService` in `app/services/question_generator.py`, exposed via `app/routers/agent.py` endpoints, and will use `app.routers.retrieval.retrieve` to gather context. It will feature a 2-stage agent pipeline:
1. **GeneratorAgent**: Drafts questions based on context and criteria.
2. **ValidatorAgent**: Reviews the drafted questions for accuracy, difficulty alignment, and correct formatting before finalizing.

## Task Breakdown

### Task 1: Create QuestionGenService (`app/services/question_generator.py`)
- Implement `QuestionGenService` class initialized with `LMStudioClient` and `VectorKBService`.
- Create `generate_custom_questions(kb_name, doc_id, topic, difficulty, type, count)`:
  - Calls `retrieve` to get context about the `topic` from the specified KB/document.
  - Formats a prompt for the GeneratorAgent detailing the requirement (e.g. 5 hard multiple-choice questions on X).
  - Parses the structured output (JSON).
- Create `generate_from_exam(kb_name, doc_id, reference_exam_text)`:
  - Analyzes the reference exam's style and difficulty.
  - Retrieves relevant context from the KB.
  - Drafts questions matching the reference style.
- Implement the ValidatorAgent:
  - For each generated question, the ValidatorAgent evaluates correctness, quality, and citations. If a question fails, it regenerates or drops it.

### Task 2: Implement API Endpoints (`app/routers/agent.py`)
- Wire up the pending POST `/questions/generate` endpoint.
- Accept a payload with: `kb_name`, `doc_id`, `mode` (custom vs exam), `topic`, `difficulty`, `question_type`, `count`, and `reference_text` (optional).
- Stream or return the final validated questions in a standardized JSON schema:
  ```json
  {
    "questions": [
      {
        "id": "q1",
        "text": "...",
        "type": "multiple_choice",
        "options": ["A", "B", "C", "D"],
        "correct_answer": "C",
        "explanation": "...",
        "citations": [{"doc_id": "...", "page": 5}]
      }
    ]
  }
  ```

### Task 3: Unit Testing
- Create `tests/test_question_generator.py` to test the `QuestionGenService` with a mocked LLM client.
- Test the validation loop to ensure invalid questions are caught.

### Task 4: Frontend Integration Verification (Optional/Review)
- Verify that the API contract matches what the frontend `app/(platform)/questions/page.tsx` expects.

## Execution Requirements
- Use standard Python `json` for parsing agent responses. Prompts must strictly enforce JSON output format or use tools if necessary.
- Leverage the existing `LMStudioClient` concurrency limits (reasoning tier) for generation.
