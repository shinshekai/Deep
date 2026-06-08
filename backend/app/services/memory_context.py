import logging

logger = logging.getLogger(__name__)

DEFAULT_TOKEN_BUDGET = 2000
CHARS_PER_TOKEN = 4


def build_memory_context(
    profile: dict | None,
    episodes: list[dict],
    facts: list[dict],
    agent_strategies: list[dict] | None = None,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
) -> str:
    parts = []
    used_tokens = 0

    if profile and profile.get("profile"):
        static = profile["profile"].get("static", {})
        dynamic = profile["profile"].get("dynamic", {})
        profile_text = _format_profile(static, dynamic)
        profile_tokens = _estimate_tokens(profile_text)
        if used_tokens + profile_tokens <= token_budget:
            parts.append(f"User Profile:\n{profile_text}")
            used_tokens += profile_tokens

    if episodes:
        episode_lines = []
        for ep in episodes[:5]:
            query = ep.get("query", "")[:200]
            answer = ep.get("answer", "")[:300]
            score = ep.get("score", 0)
            line = f"- [{ep.get('session_type', 'unknown')}] Q: {query}\n  A: {answer}"
            line_tokens = _estimate_tokens(line)
            if used_tokens + line_tokens <= token_budget:
                episode_lines.append(line)
                used_tokens += line_tokens
            else:
                break
        if episode_lines:
            parts.append("Past Conversations:\n" + "\n".join(episode_lines))

    if facts:
        fact_lines = []
        for fact in facts[:10]:
            content = fact.get("content", "")[:200]
            confidence = fact.get("confidence", 0)
            if confidence < 0.3:
                continue
            line = f"- {content} (confidence: {confidence:.1f})"
            line_tokens = _estimate_tokens(line)
            if used_tokens + line_tokens <= token_budget:
                fact_lines.append(line)
                used_tokens += line_tokens
            else:
                break
        if fact_lines:
            parts.append("Known Facts:\n" + "\n".join(fact_lines))

    if agent_strategies:
        strategy_lines = []
        for strat in agent_strategies[:3]:
            line = f"- {strat.get('agent_type', '')}: {strat.get('best_strategy', '')} (success: {strat.get('success_rate', 0):.0%})"
            line_tokens = _estimate_tokens(line)
            if used_tokens + line_tokens <= token_budget:
                strategy_lines.append(line)
                used_tokens += line_tokens
            else:
                break
        if strategy_lines:
            parts.append("Proven Strategies:\n" + "\n".join(strategy_lines))

    if not parts:
        return ""

    header = f"[Memory Context — {used_tokens} tokens]"
    return header + "\n\n" + "\n\n".join(parts)


def _format_profile(static: dict, dynamic: dict) -> str:
    lines = []
    for key, value in static.items():
        if value:
            lines.append(f"  {key}: {value}")
    recent_topics = dynamic.get("recent_topics", [])
    if recent_topics:
        lines.append(f"  Recent topics: {', '.join(str(t) for t in recent_topics[:5])}")
    preferred_style = dynamic.get("communication_style", "")
    if preferred_style:
        lines.append(f"  Style: {preferred_style}")
    return "\n".join(lines) if lines else ""


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)
