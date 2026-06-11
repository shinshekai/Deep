# Agent Instructions (Human-Editable)

## Purpose
This file defines HOW the agent should approach tasks.
It is the stable layer that humans edit. Agents never modify this file.

## Task Approach
1. Understand the goal before acting
2. Plan the approach before coding
3. Make minimal, surgical changes
4. Verify changes compile and pass tests
5. Document what was done

## Code Style
- Follow existing patterns in the codebase
- Don't add comments unless asked
- Use type hints
- Keep functions small and focused

## Safety Rules
- Never modify this file
- Never modify scoring.py
- Only modify agent_prompts.py
- Keep changes minimal and reversible