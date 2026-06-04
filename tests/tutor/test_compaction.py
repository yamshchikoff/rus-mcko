"""Tests for src.tutor.compaction."""

import pytest
from src.tutor.compaction import estimate_tokens, compact_history


def make_msg(role: str, content: str) -> dict:
    return {"role": role, "content": content}


class TestEstimateTokens:
    def test_empty_list(self):
        assert estimate_tokens([]) == 0

    def test_single_short_message(self):
        msg = make_msg("user", "Привет")
        expected = len("Привет") / 3.5
        assert estimate_tokens([msg]) == pytest.approx(expected)

    def test_multiple_messages(self):
        msgs = [
            make_msg("system", "Ты репетитор." * 50),
            make_msg("user", "Привет!"),
        ]
        total_chars = sum(len(m["content"]) for m in msgs)
        assert estimate_tokens(msgs) == pytest.approx(total_chars / 3.5)

    def test_handles_missing_content(self):
        msgs = [{"role": "user"}]
        assert estimate_tokens(msgs) == 0


class TestCompactHistory:
    def test_short_history_unchanged(self):
        msgs = [
            make_msg("system", "Системный промпт"),
            make_msg("user", "Привет"),
            make_msg("assistant", "Здравствуй!"),
            make_msg("user", "Как дела?"),
            make_msg("assistant", "Хорошо!"),
        ]
        result = compact_history(msgs, max_tokens=100_000)
        assert len(result) == len(msgs)
        assert result == msgs

    def test_system_prompt_preserved(self):
        sys_msg = make_msg("system", "Ты репетитор по русскому языку. " * 30)
        long_msg = make_msg("user", "x" * 5000)
        msgs = [sys_msg] + [long_msg] * 50
        result = compact_history(msgs, max_tokens=500)
        assert result[0] == sys_msg

    def test_keeps_last_exchanges(self):
        sys_msg = make_msg("system", "Ты репетитор.")
        msgs = [sys_msg]
        for i in range(30):
            msgs.append(make_msg("user", f"Вопрос {i}: " + "a" * 500))
            msgs.append(make_msg("assistant", f"Ответ {i}: " + "b" * 500))
        result = compact_history(msgs, max_tokens=7000)
        assert result[0] == sys_msg
        assert len(result) < len(msgs)
        # The last exchange should be preserved
        assert result[-1]["role"] == "assistant"
        assert "Ответ 29" in result[-1]["content"]

    def test_empty_list_does_not_crash(self):
        result = compact_history([], max_tokens=1000)
        assert result == []

    def test_no_system_prompt_still_compacts(self):
        msgs = [make_msg("user", "x" * 1000) for _ in range(50)]
        result = compact_history(msgs, max_tokens=2000)
        # Should still trim, just without system prompt anchoring
        assert len(result) < len(msgs)
        assert len(result) >= 2  # at least one exchange

    def test_exactly_at_threshold(self):
        # 1000 chars / 3.5 ≈ 286 tokens
        msgs = [
            make_msg("system", "Система"),
            make_msg("user", "x" * 500),
            make_msg("assistant", "y" * 490),
        ]
        total_tokens = estimate_tokens(msgs)
        result = compact_history(msgs, max_tokens=int(total_tokens) + 1)
        assert len(result) == len(msgs)
