"""Tests for src.tutor.server."""

import json
import threading
import time
import urllib.request
import urllib.error
from http.server import HTTPServer
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.tutor.server import (
    TutorHandler,
    build_chat_request,
    execute_tools,
    make_tools,
    run_tool_use_loop,
    load_textbook,
)


def dummy_textbook():
    return {
        "meta": {"title": "Тестовый учебник", "authors": "Тест", "year": 2025, "publisher": "Тест"},
        "toc": [{"type": "topic", "title": "Тема 1", "part": 1, "pdf_page": 5, "number": "§ 1"}],
        "pages": [
            {"part": 1, "pdf_page": 5, "printed_page": 4, "text": "Текст страницы 5"},
            {"part": 1, "pdf_page": 6, "printed_page": 5, "text": "Текст страницы 6"},
        ],
        "_page_index": {
            (1, 5): {"part": 1, "pdf_page": 5, "printed_page": 4, "text": "Текст страницы 5"},
            (1, 6): {"part": 1, "pdf_page": 6, "printed_page": 5, "text": "Текст страницы 6"},
        },
    }


# ── Textbook loading ────────────────────────────────────────────────────────


class TestLoadTextbook:
    def test_loads_valid_json(self, tmp_path):
        tb = tmp_path / "tb.json"
        tb.write_text(json.dumps(dummy_textbook()), encoding="utf-8")
        data = load_textbook(str(tb))
        assert data["meta"]["title"] == "Тестовый учебник"

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_textbook("/nonexistent/path.json")


# ── Tools definition ─────────────────────────────────────────────────────────


class TestMakeTools:
    def test_returns_list_of_tools(self):
        tools = make_tools()
        assert isinstance(tools, list)
        assert len(tools) == 2

    def test_show_toc_tool(self):
        tools = make_tools()
        toc = [t for t in tools if t["name"] == "show_toc"][0]
        assert toc["description"]
        assert toc["input_schema"]["type"] == "object"
        assert toc["input_schema"]["properties"] == {}

    def test_get_page_tool(self):
        tools = make_tools()
        gp = [t for t in tools if t["name"] == "get_page"][0]
        assert "part" in gp["input_schema"]["properties"]
        assert "page" in gp["input_schema"]["properties"]
        assert "part" in gp["input_schema"]["required"]
        assert "page" in gp["input_schema"]["required"]


# ── Tool execution ───────────────────────────────────────────────────────────


class TestExecuteTools:
    def test_executes_show_toc(self):
        tb = dummy_textbook()
        results = execute_tools([{"name": "show_toc", "input": {}}], tb)
        assert len(results) == 1
        assert results[0]["type"] == "tool_result"
        assert "Тема 1" in results[0]["content"]

    def test_executes_get_page(self):
        tb = dummy_textbook()
        results = execute_tools([{"name": "get_page", "input": {"part": 1, "page": 5}}], tb)
        assert len(results) == 1
        assert results[0]["type"] == "tool_result"
        assert "Текст страницы 5" in results[0]["content"]

    def test_get_page_invalid_part(self):
        tb = dummy_textbook()
        results = execute_tools([{"name": "get_page", "input": {"part": 99, "page": 5}}], tb)
        assert "error" in results[0]["content"].lower() or "не найден" in results[0]["content"].lower()

    def test_get_page_not_found(self):
        tb = dummy_textbook()
        results = execute_tools([{"name": "get_page", "input": {"part": 1, "page": 999}}], tb)
        assert "error" in results[0]["content"].lower() or "не найд" in results[0]["content"].lower()

    def test_unknown_tool(self):
        tb = dummy_textbook()
        results = execute_tools([{"name": "unknown_tool", "input": {}}], tb)
        assert len(results) == 1
        assert "error" in results[0]["content"].lower() or "неизвест" in results[0]["content"].lower()

    def test_multiple_tools(self):
        tb = dummy_textbook()
        results = execute_tools(
            [
                {"name": "show_toc", "input": {}},
                {"name": "get_page", "input": {"part": 1, "page": 6}},
            ],
            tb,
        )
        assert len(results) == 2
        assert results[0]["type"] == "tool_result"
        assert results[1]["type"] == "tool_result"


# ── Chat request building ────────────────────────────────────────────────────


class TestBuildChatRequest:
    def test_url_and_headers(self):
        url, headers, body = build_chat_request("sk-test-key", [{"role": "user", "content": "Привет"}])
        assert url == "https://api.deepseek.com/anthropic/v1/messages"
        assert headers["x-api-key"] == "sk-test-key"
        assert headers["content-type"] == "application/json"
        assert "anthropic-version" in headers

    def test_body_structure(self):
        _, _, body = build_chat_request("sk-test", [{"role": "user", "content": "Привет"}])
        assert body["model"] == "deepseek-v4-pro"
        assert body["max_tokens"] == 4096
        assert body["stream"] is True
        assert body["system"]  # system prompt injected
        assert body["messages"] == [{"role": "user", "content": "Привет"}]

    def test_system_prompt_injected(self):
        _, _, body = build_chat_request("sk-test", [{"role": "user", "content": "Привет"}])
        assert "репетитор" in body["system"].lower()
        assert "русск" in body["system"].lower()

    def test_progress_context_injected(self):
        _, _, body = build_chat_request(
            "sk-test",
            [{"role": "user", "content": "Привет"}],
            progress_context="Завершено: 3 из 15",
        )
        assert "Завершено: 3 из 15" in body["system"]

    def test_current_task_injected(self):
        _, _, body = build_chat_request(
            "sk-test",
            [{"role": "user", "content": "Привет"}],
            current_task="К1. Осложненное списывание",
        )
        assert "К1. Осложненное списывание" in body["system"]

    def test_tools_included(self):
        _, _, body = build_chat_request("sk-test", [{"role": "user", "content": "Привет"}])
        assert "tools" in body
        tool_names = [t["name"] for t in body["tools"]]
        assert "show_toc" in tool_names
        assert "get_page" in tool_names


# ── Tool-use loop ────────────────────────────────────────────────────────────


class TestToolUseLoop:
    def test_returns_assistant_text_on_no_tool_use(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Привет! Чем помочь?"}],
            "stop_reason": "end_turn",
        }

        with patch("src.tutor.server.requests.post", return_value=mock_response):
            result = run_tool_use_loop(
                "sk-test",
                [{"role": "user", "content": "Привет!"}],
                make_tools(),
                dummy_textbook(),
            )

        assert result["stop_reason"] == "end_turn"
        assert any(c["type"] == "text" for c in result["content"])

    def test_executes_tool_use_and_retries(self):
        tb = dummy_textbook()

        call1 = MagicMock()
        call1.json.return_value = {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "tool_use", "name": "show_toc", "input": {}}],
            "stop_reason": "tool_use",
        }

        call2 = MagicMock()
        call2.json.return_value = {
            "id": "msg_2",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Вот содержание учебника..."}],
            "stop_reason": "end_turn",
        }

        with patch("src.tutor.server.requests.post", side_effect=[call1, call2]):
            result = run_tool_use_loop(
                "sk-test",
                [{"role": "user", "content": "Что в учебнике?"}],
                make_tools(),
                tb,
            )

        assert result["stop_reason"] == "end_turn"

    def test_max_iterations_prevents_infinite_loop(self):
        tb = dummy_textbook()

        always_tool = MagicMock()
        always_tool.json.return_value = {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "tool_use", "name": "show_toc", "input": {}}],
            "stop_reason": "tool_use",
        }

        with patch("src.tutor.server.requests.post", return_value=always_tool):
            result = run_tool_use_loop(
                "sk-test",
                [{"role": "user", "content": "?"}],
                make_tools(),
                tb,
                max_iterations=2,
            )

        # Should exit after max_iterations with whatever response
        assert result is not None


# ── Context compaction in loop ───────────────────────────────────────────────


class TestCompactionInLoop:
    def test_compacts_long_history(self):
        tb = dummy_textbook()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Короткий ответ"}],
            "stop_reason": "end_turn",
        }

        long_msg = {"role": "user", "content": "x" * 2000}
        messages = [long_msg] * 100  # ~200K chars, well over threshold

        with patch("src.tutor.server.requests.post", return_value=mock_response) as mock_post:
            result = run_tool_use_loop("sk-test", messages, make_tools(), tb)

        # Verify compaction happened: the sent messages should be fewer than original
        sent_messages = mock_post.call_args[0][1]["messages"]
        assert len(sent_messages) < len(messages)
        assert result["stop_reason"] == "end_turn"


# ── Error handling ───────────────────────────────────────────────────────────


class TestErrorHandling:
    def test_invalid_api_key_401(self):
        import requests as real_requests

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"error": {"message": "Invalid API key"}}
        mock_resp.raise_for_status.side_effect = real_requests.HTTPError("401", response=mock_resp)

        with patch("src.tutor.server.requests.post", return_value=mock_resp):
            with pytest.raises(real_requests.HTTPError):
                run_tool_use_loop(
                    "sk-bad-key",
                    [{"role": "user", "content": "Привет"}],
                    make_tools(),
                    dummy_textbook(),
                )

    def test_network_error(self):
        with patch("src.tutor.server.requests.post", side_effect=ConnectionError("Network unreachable")):
            with pytest.raises(ConnectionError):
                run_tool_use_loop(
                    "sk-test",
                    [{"role": "user", "content": "Привет"}],
                    make_tools(),
                    dummy_textbook(),
                )


# ── TOC endpoint via HTTP ────────────────────────────────────────────────────


class TestTocEndpoint:
    @pytest.fixture
    def server_url(self, tmp_path):
        """Start a test server on a random port, return its base URL."""
        tb_path = tmp_path / "textbook.json"
        tb_path.write_text(json.dumps(dummy_textbook()), encoding="utf-8")

        # Patch the handler's textbook path
        with patch.object(TutorHandler, "textbook_path", str(tb_path)):
            server = HTTPServer(("127.0.0.1", 0), TutorHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            yield f"http://{host}:{port}"
            server.shutdown()

    def test_toc_returns_json(self, server_url):
        req = urllib.request.Request(f"{server_url}/api/toc")
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode())
            assert isinstance(data, list)
            assert any("Тема 1" in str(e) for e in data)
