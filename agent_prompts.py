"""Agent prompts (Agent-Editable)

This file contains prompt templates that agents can modify.
The agent_instructions.md file is read-only.
The agent_scoring.py file is read-only.
"""

SYSTEM_PROMPT = """You are a helpful AI assistant for the Deep project.
Follow the instructions in agent_instructions.md.
Be concise, direct, and accurate."""

TASK_PROMPT = """Complete the following task:
{task_description}

Context:
{context}

Provide a clear, minimal solution."""

VERIFY_PROMPT = """Verify this change is correct:
File: {file_path}
Change: {change_description}

Check:
1. Compiles without errors
2. Follows existing patterns
3. Is minimal and reversible
4. Doesn't break existing functionality

Output: PASS or FAIL with reason"""

SCORING_PROMPT = """Score this solution (1-10):
Task: {task}
Solution: {solution}

Criteria:
- Correctness (does it work?)
- Simplicity (is it minimal?)
- Style (does it match existing code?)
- Safety (does it follow rules?)

Output: JSON {{"score": <int>, "reason": "<string>"}}"""


def format_task_prompt(task_description: str, context: str) -> str:
    return TASK_PROMPT.format(
        task_description=task_description,
        context=context,
    )


def format_verify_prompt(file_path: str, change_description: str) -> str:
    return VERIFY_PROMPT.format(
        file_path=file_path,
        change_description=change_description,
    )


def format_scoring_prompt(task: str, solution: str) -> str:
    return SCORING_PROMPT.format(
        task=task,
        solution=solution,
    )