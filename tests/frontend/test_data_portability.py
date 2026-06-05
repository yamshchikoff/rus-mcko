"""Round-trip tests for progress and chat history data portability.

These tests verify that data survives a full export → import cycle without
loss or corruption. They exercise the JSON format used by the frontend
export/import functions.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest


# ── Progress round-trip helpers ──────────────────────────────────────────────


def simulate_progress_export(progress: dict, answers: dict | None = None) -> str:
    """Simulate what ``exportProgress()`` writes to disk."""
    return json.dumps(
        {
            "progress": progress,
            "answers": answers or {},
            "exported": datetime.now(timezone.utc).isoformat(),
        },
        ensure_ascii=False,
        indent=2,
    )


def simulate_progress_import(json_str: str) -> dict:
    """Simulate what ``importProgress()`` reads from disk.

    Returns the parsed data or raises ValueError for invalid input.
    """
    if not json_str or not json_str.strip():
        raise ValueError("Empty file")

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")

    if not isinstance(data, dict):
        raise ValueError("Top-level must be an object")

    if "progress" not in data:
        raise ValueError("Missing 'progress' field")

    if not isinstance(data["progress"], dict):
        raise ValueError("'progress' must be an object")

    # Validate answers if present
    answers = data.get("answers", {})
    if not isinstance(answers, dict):
        raise ValueError("'answers' must be an object")

    # Validate answer key format: "{variant}-{issue}"
    for key in answers:
        parts = key.split("-")
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
            raise ValueError(f"Invalid answer key format: {key}")

    return data


# ── Chat round-trip helpers ──────────────────────────────────────────────────


def simulate_chat_export(messages: list[dict], current_variant: int = 0) -> str:
    """Simulate what ``exportChatHistory()`` writes to disk."""
    return json.dumps(
        {
            "exported": datetime.now(timezone.utc).isoformat(),
            "currentVariant": current_variant,
            "messages": messages,
        },
        ensure_ascii=False,
        indent=2,
    )


def simulate_chat_import(json_str: str) -> list[dict]:
    """Simulate what ``importChatHistory()`` reads from disk.

    Returns the messages array or raises ValueError for invalid input.
    """
    if not json_str or not json_str.strip():
        raise ValueError("Empty file")

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")

    if not isinstance(data, dict):
        raise ValueError("Top-level must be an object")

    if "messages" not in data:
        raise ValueError("Missing 'messages' field")

    messages = data["messages"]
    if not isinstance(messages, list):
        raise ValueError("'messages' must be an array")

    for i, msg in enumerate(messages):
        if not isinstance(msg, dict):
            raise ValueError(f"Message {i}: must be an object")
        if "role" not in msg:
            raise ValueError(f"Message {i}: missing 'role'")
        if msg["role"] not in ("user", "assistant"):
            raise ValueError(
                f"Message {i}: role must be 'user' or 'assistant', got '{msg['role']}'"
            )
        if "content" not in msg:
            raise ValueError(f"Message {i}: missing 'content'")
        if not isinstance(msg["content"], str):
            raise ValueError(f"Message {i}: 'content' must be a string")

    return messages


# ── Progress tests ───────────────────────────────────────────────────────────


class TestProgressRoundTrip:
    """Round-trip: progress data survives export → import intact."""

    def test_round_trip_full_data(self):
        """Full progress with answers survives the round trip."""
        original_progress = {
            "1": {
                "completed": "2026-06-04T15:30:00",
                "scores": {"1": 2, "2": 3, "3": 1, "4": 0, "5": 2, "6": 1, "7": 3},
            },
            "3": {
                "completed": "2026-06-05T10:15:00",
                "scores": {"1": 1, "2": 2, "3": 0, "4": 1, "5": 3, "6": 2, "7": 0},
            },
        }
        original_answers = {
            "1-1": "Ответ на задание К1 варианта 1",
            "1-2": "Ответ на задание К2 варианта 1",
            "3-1": "Ответ на К1 варианта 3",
        }

        exported = simulate_progress_export(original_progress, original_answers)
        imported = simulate_progress_import(exported)

        assert imported["progress"] == original_progress
        assert imported["answers"] == original_answers
        assert "exported" in imported

    def test_round_trip_empty_progress(self):
        """Empty progress dict survives the round trip."""
        exported = simulate_progress_export({}, {})
        imported = simulate_progress_import(exported)

        assert imported["progress"] == {}
        assert imported["answers"] == {}

    def test_round_trip_special_characters(self):
        """Unicode and potentially dangerous content preserved exactly."""
        progress = {
            "5": {
                "completed": "2026-06-04T12:00:00",
                "scores": {"1": 0, "2": 1, "3": 0, "4": 0, "5": 1, "6": 0, "7": 1},
            }
        }
        answers = {
            "5-1": "Текст с юникодом: 日本語, émojis 🎉, право на ошибку",
            "5-2": '<script>alert("xss")</script>',
            "5-3": "Многострочный\nответ\nна три строки",
        }

        exported = simulate_progress_export(progress, answers)
        imported = simulate_progress_import(exported)

        assert imported["progress"] == progress
        assert imported["answers"] == answers
        assert imported["answers"]["5-1"] == "Текст с юникодом: 日本語, émojis 🎉, право на ошибку"
        assert imported["answers"]["5-2"] == '<script>alert("xss")</script>'

    def test_import_invalid_json(self):
        """Corrupted JSON raises ValueError."""
        try:
            simulate_progress_import("not valid json {{{")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Invalid JSON" in str(e)

    def test_import_empty_string(self):
        """Empty string raises ValueError."""
        try:
            simulate_progress_import("")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Empty" in str(e)

    def test_import_wrong_structure(self):
        """JSON without 'progress' field raises ValueError."""
        try:
            simulate_progress_import('{"answers": {}, "exported": "2026"}')
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Missing 'progress'" in str(e)

    def test_import_progress_not_object(self):
        """'progress' field that is not an object raises ValueError."""
        try:
            simulate_progress_import('{"progress": [1,2,3]}')
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "'progress' must be an object" in str(e)

    def test_import_bad_answer_keys(self):
        """Badly formed answer keys raise ValueError."""
        try:
            simulate_progress_import(
                json.dumps({
                    "progress": {},
                    "answers": {"bad-key": "value", "1-2-3": "extra"},
                    "exported": "2026",
                })
            )
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Invalid answer key format" in str(e)

    def test_structure_matches_export_format(self):
        """Exported format has the three top-level keys expected by consumers."""
        exported = simulate_progress_export({"1": {"completed": "2026", "scores": {}}})
        data = json.loads(exported)

        assert set(data.keys()) == {"progress", "answers", "exported"}
        assert isinstance(data["exported"], str)
        # ISO 8601 timestamp
        assert "T" in data["exported"]


# ── Chat history tests ───────────────────────────────────────────────────────


class TestChatRoundTrip:
    """Round-trip: chat history survives export → import intact."""

    def test_round_trip_chat_history(self):
        """Chat messages survive the round trip unchanged."""
        original = [
            {"role": "user", "content": "Как отличить причастие от деепричастия?"},
            {"role": "assistant", "content": "Причастие обозначает признак по действию (какой? что делающий?), а деепричастие — добавочное действие (что делая? что сделав?)."},
            {"role": "user", "content": "Спасибо, понял!"},
            {"role": "assistant", "content": "Рад помочь. Давай потренируемся на примерах из § 14."},
        ]

        exported = simulate_chat_export(original, current_variant=3)
        imported = simulate_chat_import(exported)

        assert imported == original
        assert len(imported) == 4
        for msg in imported:
            assert "role" in msg
            assert "content" in msg
            assert msg["role"] in ("user", "assistant")

    def test_round_trip_empty_chat(self):
        """Empty chat survives the round trip."""
        exported = simulate_chat_export([])
        imported = simulate_chat_import(exported)

        assert imported == []

    def test_round_trip_max_messages(self):
        """100 messages (the cap) survive the round trip."""
        original = []
        for i in range(100):
            original.append({"role": "user", "content": f"Вопрос {i+1}"})
            original.append({"role": "assistant", "content": f"Ответ {i+1}"})

        # Trim to 100
        original = original[:100]

        exported = simulate_chat_export(original)
        imported = simulate_chat_import(exported)

        assert len(imported) == 100
        assert imported == original

    def test_chat_message_structure(self):
        """Every imported message has role and content fields."""
        messages = [
            {"role": "user", "content": "Привет"},
            {"role": "assistant", "content": "Здравствуй!"},
        ]

        exported = simulate_chat_export(messages)
        imported = simulate_chat_import(exported)

        for msg in imported:
            assert isinstance(msg, dict)
            assert set(msg.keys()) == {"role", "content"}
            assert isinstance(msg["role"], str)
            assert isinstance(msg["content"], str)

    def test_import_invalid_chat_json(self):
        """Corrupted chat JSON raises ValueError."""
        try:
            simulate_chat_import("this is not json")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Invalid JSON" in str(e)

    def test_import_chat_empty_string(self):
        """Empty chat file raises ValueError."""
        try:
            simulate_chat_import("")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Empty" in str(e)

    def test_import_missing_messages_field(self):
        """JSON without 'messages' field raises ValueError."""
        try:
            simulate_chat_import('{"exported": "2026", "currentVariant": 1}')
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Missing 'messages'" in str(e)

    def test_import_messages_not_array(self):
        """'messages' that is not an array raises ValueError."""
        try:
            simulate_chat_import('{"messages": "not an array"}')
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "'messages' must be an array" in str(e)

    def test_import_bad_role(self):
        """Message with invalid role raises ValueError."""
        try:
            simulate_chat_import(
                json.dumps({
                    "messages": [{"role": "admin", "content": "test"}]
                })
            )
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "role must be" in str(e)

    def test_import_missing_content(self):
        """Message without content raises ValueError."""
        try:
            simulate_chat_import(
                json.dumps({"messages": [{"role": "user"}]})
            )
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "missing 'content'" in str(e)

    def test_import_content_not_string(self):
        """Message with non-string content raises ValueError."""
        try:
            simulate_chat_import(
                json.dumps({"messages": [{"role": "user", "content": 123}]})
            )
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "'content' must be a string" in str(e)

    def test_import_message_not_object(self):
        """Non-object message raises ValueError."""
        try:
            simulate_chat_import(
                json.dumps({"messages": ["not an object"]})
            )
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "must be an object" in str(e)


# ── Integration tests: verify HTML contains required functions ───────────────

INDEX_HTML = Path(__file__).resolve().parent.parent.parent / "src" / "frontend" / "legacy" / "index.html"


def _read_index_js() -> str:
    """Extract inline <script> content from index.html."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    match = re.search(r"<script(?![^>]*src=)[^>]*>(.*?)</script>", html, re.DOTALL)
    assert match, "No inline <script> block found in index.html"
    return match.group(1)


class TestFrontendIntegration:
    """Verify the actual HTML contains required export/import functions."""

    @pytest.fixture(scope="class")
    def js(self) -> str:
        return _read_index_js()

    def test_function_importProgress_exists(self, js):
        """importProgress() function is defined."""
        assert re.search(r'function\s+importProgress\s*\(', js), \
            "importProgress function not found in index.html"

    def test_function_exportChatHistory_exists(self, js):
        """exportChatHistory() function is defined."""
        assert re.search(r'function\s+exportChatHistory\s*\(', js), \
            "exportChatHistory function not found in index.html"

    def test_function_importChatHistory_exists(self, js):
        """importChatHistory() function is defined."""
        assert re.search(r'function\s+importChatHistory\s*\(', js), \
            "importChatHistory function not found in index.html"

    def test_progress_file_input_exists(self, js):
        """Hidden file input for progress import exists."""
        html = INDEX_HTML.read_text(encoding="utf-8")
        assert 'progress-file-input' in html, \
            "progress-file-input element not found in index.html"

    def test_chat_file_input_exists(self, js):
        """Hidden file input for chat import exists."""
        html = INDEX_HTML.read_text(encoding="utf-8")
        assert 'chat-file-input' in html, \
            "chat-file-input element not found in index.html"

    def test_importProgress_uses_FileReader(self, js):
        """importProgress() uses FileReader to read the selected file."""
        assert 'FileReader' in js, \
            "importProgress must use FileReader API"

    def test_importChatHistory_uses_FileReader(self, js):
        """importChatHistory() uses FileReader to read the selected file."""
        body = INDEX_HTML.read_text(encoding="utf-8")
        # FileReader should appear in the inline script
        inline = re.search(r"<script(?![^>]*src=)[^>]*>(.*?)</script>", body, re.DOTALL)
        assert inline, "No inline script block"
        # Count FileReader occurrences — need at least 2 (progress + chat import)
        count = inline.group(1).count("FileReader")
        assert count >= 2, f"Expected >= 2 FileReader usages, found {count}"
