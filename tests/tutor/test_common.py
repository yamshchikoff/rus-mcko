"""Tests for src.tutor.common — shared constants, tools, and tool execution."""

import pytest


# ── Constants ──────────────────────────────────────────────────────────────────


class TestCommonConstants:
    def test_deepseek_url_is_string(self):
        from src.tutor.common import DEEPSEEK_URL
        assert isinstance(DEEPSEEK_URL, str)
        assert DEEPSEEK_URL.startswith("https://")

    def test_anthropic_version_format(self):
        from src.tutor.common import ANTHROPIC_VERSION
        assert isinstance(ANTHROPIC_VERSION, str)
        assert ANTHROPIC_VERSION.startswith("20")

    def test_model_is_deepseek_v4_pro(self):
        from src.tutor.common import MODEL
        assert MODEL == "deepseek-v4-pro"

    def test_max_tokens_positive(self):
        from src.tutor.common import MAX_TOKENS
        assert MAX_TOKENS > 0

    def test_max_tool_iterations_positive(self):
        from src.tutor.common import MAX_TOOL_ITERATIONS
        assert MAX_TOOL_ITERATIONS > 0


# ── make_tools ─────────────────────────────────────────────────────────────────


class TestMakeTools:
    def test_returns_list_with_two_tools(self):
        from src.tutor.common import make_tools
        tools = make_tools()
        assert len(tools) == 2

    def test_show_toc_tool(self):
        from src.tutor.common import make_tools
        tools = make_tools()
        toc_tool = tools[0]
        assert toc_tool["name"] == "show_toc"
        assert "input_schema" in toc_tool
        assert toc_tool["input_schema"]["properties"] == {}
        assert toc_tool["input_schema"]["required"] == []

    def test_get_page_tool(self):
        from src.tutor.common import make_tools
        tools = make_tools()
        page_tool = tools[1]
        assert page_tool["name"] == "get_page"
        assert "input_schema" in page_tool
        assert "part" in page_tool["input_schema"]["properties"]
        assert "page" in page_tool["input_schema"]["properties"]
        assert page_tool["input_schema"]["required"] == ["part", "page"]


# ── make_tools (review mode) ──────────────────────────────────────────────────


class TestMakeReviewTools:
    def test_review_mode_adds_submit_review_tool(self):
        """make_tools(review_mode=True) returns 3 tools (show_toc, get_page, submit_review)."""
        from src.tutor.common import make_tools
        tools = make_tools(review_mode=True)
        assert len(tools) == 3

    def test_default_mode_still_two_tools(self):
        """make_tools() without args still returns exactly 2 tools."""
        from src.tutor.common import make_tools
        tools = make_tools()
        assert len(tools) == 2

    def test_submit_review_tool_name(self):
        from src.tutor.common import make_tools
        tools = make_tools(review_mode=True)
        names = [t["name"] for t in tools]
        assert "submit_review" in names

    def test_submit_review_has_description(self):
        from src.tutor.common import make_tools
        tools = make_tools(review_mode=True)
        sr = next(t for t in tools if t["name"] == "submit_review")
        assert isinstance(sr["description"], str)
        assert len(sr["description"]) > 10

    def test_submit_review_schema_required_fields(self):
        from src.tutor.common import make_tools
        tools = make_tools(review_mode=True)
        sr = next(t for t in tools if t["name"] == "submit_review")
        req = sr["input_schema"]["required"]
        assert "issue" in req
        assert "score" in req
        assert "max_score" in req
        assert "strengths" in req
        assert "weaknesses" in req
        assert "recommendation" in req

    def test_submit_review_schema_types(self):
        from src.tutor.common import make_tools
        tools = make_tools(review_mode=True)
        sr = next(t for t in tools if t["name"] == "submit_review")
        props = sr["input_schema"]["properties"]
        assert props["issue"]["type"] == "integer"
        assert props["score"]["type"] == "integer"
        assert props["max_score"]["type"] == "integer"
        assert props["strengths"]["type"] == "string"
        assert props["weaknesses"]["type"] == "string"
        assert props["recommendation"]["type"] == "string"
        assert props["textbook_refs"]["type"] == "array"

    def test_max_review_tool_iterations_exists(self):
        from src.tutor.common import MAX_REVIEW_TOOL_ITERATIONS
        assert MAX_REVIEW_TOOL_ITERATIONS > 0


# ── execute_tools ──────────────────────────────────────────────────────────────


def dummy_textbook():
    return {
        "meta": {"title": "Тестовый учебник"},
        "toc": [{"type": "topic", "title": "Тема 1", "part": 1, "pdf_page": 5, "number": "§ 1"}],
        "pages": [
            {"part": 1, "pdf_page": 5, "printed_page": 4, "text": "Текст страницы 5"},
        ],
        "_page_index": {(1, 5): {"part": 1, "pdf_page": 5, "printed_page": 4, "text": "Текст страницы 5"}},
    }


class TestExecuteTools:
    def test_execute_show_toc(self):
        from src.tutor.common import execute_tools
        tb = dummy_textbook()
        calls = [{"name": "show_toc", "input": {}, "id": "tool_1"}]
        results = execute_tools(calls, tb)
        assert len(results) == 1
        assert results[0]["type"] == "tool_result"
        assert results[0]["tool_use_id"] == "tool_1"
        assert "Тема 1" in results[0]["content"]

    def test_execute_get_page(self):
        from src.tutor.common import execute_tools
        tb = dummy_textbook()
        calls = [{"name": "get_page", "input": {"part": 1, "page": 5}, "id": "tool_2"}]
        results = execute_tools(calls, tb)
        assert len(results) == 1
        assert results[0]["type"] == "tool_result"
        assert results[0]["tool_use_id"] == "tool_2"
        assert "Текст страницы 5" in results[0]["content"]

    def test_get_page_not_found(self):
        from src.tutor.common import execute_tools
        tb = dummy_textbook()
        calls = [{"name": "get_page", "input": {"part": 1, "page": 999}, "id": "tool_3"}]
        results = execute_tools(calls, tb)
        assert "Ошибка" in results[0]["content"] or "не найдена" in results[0]["content"]

    def test_unknown_tool(self):
        from src.tutor.common import execute_tools
        tb = dummy_textbook()
        calls = [{"name": "unknown", "input": {}, "id": "tool_4"}]
        results = execute_tools(calls, tb)
        assert "Ошибка" in results[0]["content"]

    def test_multiple_calls(self):
        from src.tutor.common import execute_tools
        tb = dummy_textbook()
        calls = [
            {"name": "show_toc", "input": {}, "id": "tool_a"},
            {"name": "get_page", "input": {"part": 1, "page": 5}, "id": "tool_b"},
        ]
        results = execute_tools(calls, tb)
        assert len(results) == 2


# ── TOC formatting ─────────────────────────────────────────────────────────────


class TestTocFormatting:
    def test_toc_includes_topic_number(self):
        from src.tutor.common import execute_tools
        tb = dummy_textbook()
        calls = [{"name": "show_toc", "input": {}, "id": "toc_1"}]
        results = execute_tools(calls, tb)
        assert "§ 1" in results[0]["content"]

    def test_toc_includes_page_number(self):
        from src.tutor.common import execute_tools
        tb = dummy_textbook()
        calls = [{"name": "show_toc", "input": {}, "id": "toc_2"}]
        results = execute_tools(calls, tb)
        assert "стр. 5" in results[0]["content"]

    def test_toc_handles_empty_toc(self):
        from src.tutor.common import execute_tools
        tb = {"meta": {}, "toc": [], "_page_index": {}}
        calls = [{"name": "show_toc", "input": {}, "id": "toc_3"}]
        results = execute_tools(calls, tb)
        assert results[0]["content"] == ""

    def test_toc_formats_sections(self):
        from src.tutor.common import execute_tools
        tb = {
            "meta": {},
            "toc": [{"type": "section", "title": "Часть 1", "entries": []}],
            "_page_index": {},
        }
        calls = [{"name": "show_toc", "input": {}, "id": "toc_4"}]
        results = execute_tools(calls, tb)
        assert "[Часть 1]" in results[0]["content"]
