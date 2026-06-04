"""Context compaction: keep history within token budgets.

Strategy: when total exceeds *max_tokens* (800K), evict the oldest messages
until the remainder fits within *target_tokens* (500K — half of 1M window).
The system prompt (first message) is always preserved.  After compaction
the model still sees its identity, restrictions, moral guidance, and tools
because these live in the system prompt.
"""

from __future__ import annotations

WINDOW_TOKENS = 1_000_000
COMPACTION_THRESHOLD = 800_000
COMPACTION_TARGET = 500_000  # half of the window


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
    max_tokens: float = COMPACTION_THRESHOLD,
    target_tokens: float = COMPACTION_TARGET,
) -> list[dict]:
    """Return a pruned copy of *messages* that fits within *target_tokens*.

    If the total is already ≤ *max_tokens*, return the list unchanged.
    Otherwise, keep the system prompt (first message) plus the most recent
    messages up to *target_tokens*.
    """
    if not messages:
        return []

    if estimate_tokens(messages) <= max_tokens:
        return list(messages)

    # System prompt stays (assumed to be the first message)
    has_system = messages[0].get("role") == "system"
    system = messages[:1] if has_system else []
    rest = messages[1:] if has_system else messages

    budget = target_tokens - estimate_tokens(system)
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
