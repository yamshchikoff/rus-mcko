"""Context compaction: keep history within token budgets.

Strategy (MVP): preserve the system prompt, then trim oldest messages from the
front until the total fits.  v2 may add LLM summarisation of trimmed prefix.
"""

from __future__ import annotations


def estimate_tokens(messages: list[dict]) -> float:
    """Rough token count: total chars / 3.5."""
    total = 0
    for m in messages:
        content = m.get("content", "")
        if content:
            total += len(content)
    return total / 3.5


def compact_history(
    messages: list[dict],
    max_tokens: float = 170_000,
) -> list[dict]:
    """Return a prefix of *messages* that fits within *max_tokens*.

    The first message is treated as the system prompt and always kept.
    After it, messages are kept from the end (most recent) backwards.
    """
    if not messages:
        return []

    if estimate_tokens(messages) <= max_tokens:
        return list(messages)

    # System prompt stays (assumed to be the first message)
    has_system = messages[0].get("role") == "system"
    system = messages[:1] if has_system else []
    rest = messages[1:] if has_system else messages

    budget = max_tokens - estimate_tokens(system)
    if budget <= 0:
        return system

    # Walk from the end, keep the last N messages that fit
    kept: list[dict] = []
    for m in reversed(rest):
        trial = [m] + kept
        if estimate_tokens(trial) <= budget:
            kept = trial
        else:
            break

    return system + kept
