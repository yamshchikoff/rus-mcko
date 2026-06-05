"""Tests for src.tutor.review."""

import json
import re
import threading
import urllib.request
import urllib.error
from http.server import HTTPServer
from unittest.mock import patch, MagicMock

import pytest
import requests as real_requests

from src.tutor.review import (
    REVIEW_SYSTEM_PROMPT,
    build_review_messages,
    parse_review_response,
    execute_review,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def make_task(issue, **overrides):
    """Return a minimal valid task dict."""
    t = {
        "issue": issue,
        "category": f"К{issue}. Тестовая категория",
        "content_html": f"<p>Формулировка задания {issue}</p>",
        "criteria_html": "<table><tr><td>K1</td><td>Орфография</td><td>4</td></tr></table>",
        "solution_html": f"<p>Правильный ответ {issue}</p>",
        "student_answer": f"Ответ ученика на задание {issue}",
    }
    t.update(overrides)
    return t


def dummy_textbook():
    return {
        "meta": {"title": "Тестовый учебник", "authors": "Тест", "year": 2025, "publisher": "Тест"},
        "toc": [{"type": "topic", "title": "Тема 1", "part": 1, "pdf_page": 5, "number": "§ 1"}],
        "pages": [
            {"part": 1, "pdf_page": 5, "printed_page": 4, "text": "Текст страницы 5"},
            {"part": 1, "pdf_page": 6, "printed_page": 5, "text": "Текст страницы 6"},
        ],
    }


def dummy_textbook_with_index():
    d = dummy_textbook()
    d["_page_index"] = {(p["part"], p["pdf_page"]): p for p in d["pages"]}
    return d


def sample_tasks(n=7):
    return [make_task(i) for i in range(1, n + 1)]


# ── Review system prompt ─────────────────────────────────────────────────────


class TestReviewSystemPrompt:
    def test_contains_teacher_identity(self):
        prompt = REVIEW_SYSTEM_PROMPT.lower()
        assert "репетитор" in prompt or "учитель" in prompt
        assert "русск" in prompt
        assert "мужчин" in prompt

    def test_contains_target_audience(self):
        prompt = REVIEW_SYSTEM_PROMPT.lower()
        assert "13" in prompt and "14" in prompt
        assert "семиклассник" in prompt or "7 класс" in prompt or "седьм" in prompt

    def test_contains_output_format(self):
        prompt = REVIEW_SYSTEM_PROMPT.lower()
        assert "json" in prompt
        assert "issue" in prompt
        assert "score" in prompt
        assert "strengths" in prompt

    def test_contains_scoring_instructions(self):
        prompt = REVIEW_SYSTEM_PROMPT.lower()
        assert "критери" in prompt
        assert "балл" in prompt

    def test_contains_textbook_usage(self):
        prompt = REVIEW_SYSTEM_PROMPT
        assert "show_toc" in prompt
        assert "get_page" in prompt

    def test_contains_ethics_guidelines(self):
        prompt = REVIEW_SYSTEM_PROMPT.lower()
        assert "не высмеивай" in prompt or "не используй сарказм" in prompt or "безопасный" in prompt


# ── build_review_messages ────────────────────────────────────────────────────


class TestBuildReviewMessages:
    def test_returns_list_with_one_message(self):
        tasks = sample_tasks(3)
        msgs = build_review_messages(tasks, 1)
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"

    def test_formats_all_seven_tasks(self):
        tasks = sample_tasks(7)
        msgs = build_review_messages(tasks, 5)
        content = msgs[0]["content"]
        for i in range(1, 8):
            assert f"К{i}" in content

    def test_includes_variant_number(self):
        msgs = build_review_messages(sample_tasks(1), 12)
        assert "Вариант 12" in msgs[0]["content"] or "12" in msgs[0]["content"]

    def test_includes_criteria(self):
        tasks = [make_task(1, criteria_html="<table><tr><td>K1</td><td>Грамотность</td><td>5</td></tr></table>")]
        msgs = build_review_messages(tasks, 1)
        assert "Грамотность" in msgs[0]["content"]

    def test_includes_solution(self):
        tasks = [make_task(1, solution_html="<p>Эталон: правильно написанный текст</p>")]
        msgs = build_review_messages(tasks, 1)
        assert "правильно написанный текст" in msgs[0]["content"]

    def test_includes_student_answer(self):
        tasks = [make_task(1, student_answer="Мой ответ")]
        msgs = build_review_messages(tasks, 1)
        assert "Мой ответ" in msgs[0]["content"]

    def test_handles_empty_answer(self):
        tasks = [make_task(1, student_answer="")]
        msgs = build_review_messages(tasks, 1)
        content = msgs[0]["content"].lower()
        assert "пусто" in content or "отсутствует" in content or "нет ответа" in content

    def test_strips_html_tags(self):
        tasks = [make_task(1, content_html="<p><b>Спишите</b> текст, <i>раскрывая</i> скобки.</p>")]
        msgs = build_review_messages(tasks, 1)
        content = msgs[0]["content"]
        assert "<p>" not in content
        assert "<b>" not in content
        # Should contain the text without tags
        assert "Спишите" in content
        assert "раскрывая" in content


# ── parse_review_response ───────────────────────────────────────────────────


class TestParseReviewResponse:
    def test_parses_valid_json(self):
        valid = json.dumps({"reviews": [{"issue": 1, "score": 3, "max_score": 4, "strengths": "ok", "weaknesses": "", "recommendation": ""}]})
        result = parse_review_response(valid)
        assert not result.get("parse_error")
        assert len(result["reviews"]) == 1
        assert result["reviews"][0]["score"] == 3

    def test_parses_json_in_code_fence(self):
        wrapped = 'Вот результаты проверки:\n```json\n{"reviews": [{"issue": 1, "score": 2, "max_score": 4, "strengths": "Молодец", "weaknesses": "Ошибки", "recommendation": "Повтори §5"}]}\n```\nНадеюсь, понятно.'
        result = parse_review_response(wrapped)
        assert not result.get("parse_error")
        assert len(result["reviews"]) == 1
        assert result["reviews"][0]["issue"] == 1

    def test_parses_json_amidst_text(self):
        text = 'Разбор задания:\n{"reviews": [{"issue": 1, "score": 1, "max_score": 3, "strengths": "", "weaknesses": "", "recommendation": ""}]}\nВот так.'
        result = parse_review_response(text)
        assert not result.get("parse_error")
        assert len(result["reviews"]) == 1

    def test_handles_invalid_json(self):
        result = parse_review_response("Это не JSON, просто текст ответа модели.")
        assert result.get("parse_error")

    def test_handles_missing_reviews_key(self):
        result = parse_review_response('{"something": "else"}')
        assert result.get("parse_error")

    def test_fills_defaults_for_missing_fields(self):
        minimal = '{"reviews": [{"issue": 1, "score": 2, "max_score": 5}]}'
        result = parse_review_response(minimal)
        r = result["reviews"][0]
        assert r["strengths"] == ""
        assert r["weaknesses"] == ""
        assert r["recommendation"] == ""
        assert r["textbook_refs"] == []

    def test_validates_and_clamps_scores(self):
        data = '{"reviews": [{"issue": 1, "score": 10, "max_score": 4, "strengths": "", "weaknesses": "", "recommendation": ""}]}'
        result = parse_review_response(data)
        r = result["reviews"][0]
        assert r["max_score"] >= r["score"]

    def test_clamping_skipped_when_max_score_missing(self):
        data = '{"reviews": [{"issue": 1, "score": 3, "strengths": "", "weaknesses": "", "recommendation": ""}]}'
        result = parse_review_response(data)
        r = result["reviews"][0]
        assert r["score"] == 3

    def test_handles_partial_reviews(self):
        data = json.dumps({"reviews": [
            {"issue": 1, "score": 3, "max_score": 4, "strengths": "", "weaknesses": "", "recommendation": ""},
            {"issue": 3, "score": 2, "max_score": 5, "strengths": "", "weaknesses": "", "recommendation": ""},
        ]})
        result = parse_review_response(data)
        assert len(result["reviews"]) == 2
        issues = {r["issue"] for r in result["reviews"]}
        assert issues == {1, 3}

    def test_handles_empty_text(self):
        result = parse_review_response("")
        assert result.get("parse_error")

    def test_preserves_textbook_refs(self):
        data = json.dumps({"reviews": [{
            "issue": 1, "score": 3, "max_score": 4,
            "strengths": "ok", "weaknesses": "", "recommendation": "",
            "textbook_refs": [
                {"paragraph": "§ 12", "part": 1, "page": 34, "description": "Чередование гласных"},
                {"paragraph": "§ 24", "part": 1, "page": 61, "description": "Причастный оборот"},
            ]
        }]})
        result = parse_review_response(data)
        refs = result["reviews"][0]["textbook_refs"]
        assert len(refs) == 2
        assert refs[0]["paragraph"] == "§ 12"


# ── execute_review ───────────────────────────────────────────────────────────


class TestExecuteReview:
    def test_direct_json_response(self):
        tb = dummy_textbook_with_index()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": json.dumps({"reviews": [
                {"issue": 1, "score": 3, "max_score": 4, "strengths": "ok", "weaknesses": "", "recommendation": ""}
            ]})}],
            "stop_reason": "end_turn",
        }

        with patch("src.tutor.review.requests.post", return_value=mock_resp):
            result = execute_review("sk-test", sample_tasks(1), 1, tb)

        assert not result.get("parse_error")
        assert len(result["reviews"]) == 1
        assert result["reviews"][0]["issue"] == 1

    def test_with_tool_use(self):
        tb = dummy_textbook_with_index()

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
            "content": [{"type": "text", "text": json.dumps({"reviews": [
                {"issue": 1, "score": 2, "max_score": 3, "strengths": "ok", "weaknesses": "", "recommendation": ""}
            ]})}],
            "stop_reason": "end_turn",
        }

        with patch("src.tutor.review.requests.post", side_effect=[call1, call2]):
            result = execute_review("sk-test", sample_tasks(1), 1, tb)

        assert not result.get("parse_error")
        assert len(result["reviews"]) == 1

    def test_max_iterations_prevents_loop(self):
        tb = dummy_textbook_with_index()

        always_tool = MagicMock()
        always_tool.json.return_value = {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "tool_use", "name": "show_toc", "input": {}}],
            "stop_reason": "tool_use",
        }

        with patch("src.tutor.review.requests.post", return_value=always_tool):
            result = execute_review("sk-test", sample_tasks(1), 1, tb, max_iterations=2)

        # Should return parse_error after max iterations (no text to parse)
        assert result is not None

    def test_compaction_in_loop(self):
        tb = dummy_textbook_with_index()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": json.dumps({"reviews": [
                {"issue": 1, "score": 3, "max_score": 4, "strengths": "ok", "weaknesses": "", "recommendation": ""}
            ]})}],
            "stop_reason": "end_turn",
        }

        with patch("src.tutor.review.compact_history") as mock_compact:
            mock_compact.return_value = [{"role": "user", "content": "..."}]
            with patch("src.tutor.review.requests.post", return_value=mock_resp):
                execute_review("sk-test", sample_tasks(1), 1, tb)

        assert mock_compact.called

    def test_api_error_propagated(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.raise_for_status.side_effect = real_requests.HTTPError("401", response=mock_resp)

        with patch("src.tutor.review.requests.post", return_value=mock_resp):
            with pytest.raises(real_requests.HTTPError):
                execute_review("sk-bad", sample_tasks(1), 1, dummy_textbook_with_index())

    def test_network_error_propagated(self):
        with patch("src.tutor.review.requests.post", side_effect=ConnectionError("Network down")):
            with pytest.raises(ConnectionError):
                execute_review("sk-test", sample_tasks(1), 1, dummy_textbook_with_index())

    def test_includes_progress_context_in_system_prompt(self):
        tb = dummy_textbook_with_index()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "id": "msg_1",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": json.dumps({"reviews": [
                {"issue": 1, "score": 3, "max_score": 4, "strengths": "", "weaknesses": "", "recommendation": ""}
            ]})}],
            "stop_reason": "end_turn",
        }

        with patch("src.tutor.review.requests.post", return_value=mock_resp) as mock_post:
            execute_review("sk-test", sample_tasks(1), 1, tb, progress_context="Завершено: 3 из 15")

        call_body = mock_post.call_args.kwargs["json"]
        assert "Завершено: 3 из 15" in call_body["system"]


# ── Review endpoint (HTTP integration) ───────────────────────────────────────


class TestReviewEndpoint:
    @pytest.fixture
    def server_url(self, tmp_path):
        """Start a test server with a patched review handler."""
        from src.tutor.server import TutorHandler

        tb_path = tmp_path / "textbook.json"
        tb_path.write_text(json.dumps(dummy_textbook()), encoding="utf-8")

        with patch.object(TutorHandler, "textbook_path", str(tb_path)):
            server = HTTPServer(("127.0.0.1", 0), TutorHandler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            host, port = server.server_address
            yield f"http://{host}:{port}"
            server.shutdown()

    def test_review_missing_api_key(self, server_url):
        req = urllib.request.Request(
            f"{server_url}/api/review",
            data=json.dumps({"tasks": []}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                assert resp.status == 400
        except urllib.error.HTTPError as e:
            assert e.code == 400

    def test_review_missing_tasks(self, server_url):
        req = urllib.request.Request(
            f"{server_url}/api/review",
            data=json.dumps({"apiKey": "sk-test"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                assert resp.status == 400
        except urllib.error.HTTPError as e:
            assert e.code == 400

    def test_review_returns_200_with_mocked_execute(self, server_url):
        with patch("src.tutor.server.execute_review", return_value={"reviews": [], "parse_error": False}):
            req = urllib.request.Request(
                f"{server_url}/api/review",
                data=json.dumps({
                    "apiKey": "sk-test",
                    "variantNum": 1,
                    "tasks": [make_task(1)],
                    "progressContext": "",
                }).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req) as resp:
                assert resp.status == 202
                data = json.loads(resp.read().decode())
                assert "request_id" in data
                request_id = data["request_id"]

            # Poll until done (mock returns immediately, so thread finishes fast)
            import time
            for _ in range(20):
                time.sleep(0.1)
                status_req = urllib.request.Request(f"{server_url}/api/review/status/{request_id}")
                with urllib.request.urlopen(status_req) as sresp:
                    sdata = json.loads(sresp.read().decode())
                if sdata.get("step") == "done":
                    assert "reviews" in sdata
                    break
            else:
                raise AssertionError("Review did not complete within polling window")


# ── Pluralization (Russian) ───────────────────────────────────────────────────


def pluralize_score_py(n: int) -> str:
    """Python version of the JS pluralizeScore for testing algorithm."""
    mod10 = n % 10
    mod100 = n % 100
    if mod10 == 1 and mod100 != 11:
        return ""
    if mod10 >= 2 and mod10 <= 4 and not (mod100 >= 12 and mod100 <= 14):
        return "а"
    return "ов"


class TestPluralizeScore:
    """Verify the Russian pluralization algorithm for балл/балла/баллов."""

    def test_singular(self):
        assert pluralize_score_py(1) == ""
        assert pluralize_score_py(21) == ""
        assert pluralize_score_py(31) == ""
        assert pluralize_score_py(101) == ""

    def test_few(self):
        assert pluralize_score_py(2) == "а"
        assert pluralize_score_py(3) == "а"
        assert pluralize_score_py(4) == "а"
        assert pluralize_score_py(22) == "а"
        assert pluralize_score_py(24) == "а"
        assert pluralize_score_py(34) == "а"

    def test_many(self):
        assert pluralize_score_py(5) == "ов"
        assert pluralize_score_py(0) == "ов"
        assert pluralize_score_py(6) == "ов"
        assert pluralize_score_py(10) == "ов"
        assert pluralize_score_py(20) == "ов"
        assert pluralize_score_py(25) == "ов"

    def test_teens_are_many(self):
        """11-14 always use 'ов' form."""
        assert pluralize_score_py(11) == "ов"
        assert pluralize_score_py(12) == "ов"
        assert pluralize_score_py(13) == "ов"
        assert pluralize_score_py(14) == "ов"

    def test_hundreds_with_teens(self):
        """111-114 always use 'ов' form."""
        assert pluralize_score_py(111) == "ов"
        assert pluralize_score_py(112) == "ов"
        assert pluralize_score_py(113) == "ов"
        assert pluralize_score_py(114) == "ов"


# ── Timeout consistency ──────────────────────────────────────────────────────


class TestTimeoutConsistency:
    def test_backend_timeout_within_bounds(self):
        """Backend worst-case: MAX_TOOL_ITERATIONS * 60s timeout should be < 600s."""
        from src.tutor.review import MAX_TOOL_ITERATIONS
        per_request_timeout = 60  # hardcoded in execute_review requests.post(..., timeout=60)
        worst_case = MAX_TOOL_ITERATIONS * per_request_timeout
        assert worst_case <= 600, (
            f"Backend worst-case timeout {worst_case}s exceeds 600s"
        )
