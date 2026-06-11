"""Agent scoring (Nobody-Editable)

This file defines HOW to measure success.
It is locked — neither humans nor agents modify this file.
The scoring criteria are the ground truth for optimization.
"""

SCORE_CRITERIA = {
    "correctness": {
        "weight": 0.4,
        "description": "Does the solution work as intended?",
        "pass_threshold": 7,
    },
    "simplicity": {
        "weight": 0.3,
        "description": "Is the solution minimal and focused?",
        "pass_threshold": 6,
    },
    "style": {
        "weight": 0.2,
        "description": "Does it match existing code patterns?",
        "pass_threshold": 6,
    },
    "safety": {
        "weight": 0.1,
        "description": "Does it follow safety rules?",
        "pass_threshold": 8,
    },
}

PASS_THRESHOLD = 7.0


def compute_score(scores: dict[str, int]) -> float:
    total = 0.0
    for criterion, config in SCORE_CRITERIA.items():
        if criterion in scores:
            total += scores[criterion] * config["weight"]
    return total


def is_passing(score: float) -> bool:
    return score >= PASS_THRESHOLD


def get_failure_reason(scores: dict[str, int]) -> str | None:
    if not scores:
        return "No scores provided"
    for criterion, config in SCORE_CRITERIA.items():
        if criterion in scores and scores[criterion] < config["pass_threshold"]:
            return f"Failed {criterion}: {scores[criterion]}/{config['pass_threshold']}"
    total = compute_score(scores)
    if total < PASS_THRESHOLD:
        return f"Aggregate score {total:.1f} below threshold {PASS_THRESHOLD}"
    return None