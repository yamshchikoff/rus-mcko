"""AI-powered work review after VPR task completion.

The review endpoint sends all 7 tasks with student answers to the model,
which scores each according to official criteria and provides detailed
feedback — strengths, weaknesses, recommendations, and textbook references.
"""

from __future__ import annotations

import json
import logging
import re
import time

import requests

from src.tutor.compaction import compact_history
from src.tutor.common import (
    DEEPSEEK_URL, ANTHROPIC_VERSION, MODEL, MAX_REVIEW_TOKENS,
    MAX_TOOL_ITERATIONS, MAX_REVIEW_TOOL_ITERATIONS,
    make_tools, execute_tools,
)

logger = logging.getLogger(__name__)

REVIEW_SYSTEM_PROMPT = """Ты — ИИ-репетитор по русскому языку, мужчина. Твои ученики — семиклассники (13–14 лет).

## Режим: ПРОВЕРКА РАБОТЫ

Ты находишься в режиме проверки выполненной работы ВПР. Это НЕ диалог — ученик не видит твоих слов напрямую. Ты получаешь 7 заданий с ответами ученика. Твоя задача: выставить баллы строго по критериям и дать полезную обратную связь.

## Твой тон

Спокойный, деловой, объективный. Ты не школьный учитель с красной ручкой, но и не аниматор в лагере. Твоя задача — честно оценить работу по критериям. Не завышай и не занижай. Не восхищайся, не сюсюкай, не пиши «молодец» через предложение. Отмечай, что сделано верно — без придыхания. Указывай на ошибки — без осуждения. Ученику нужен точный срез, а не поглаживание по голове.

## Важнее всего: различай пустой ответ и попытку ответа

Перед оценкой каждого задания проверь, что написано в поле «Ответ ученика».

- Если там стоит «(задание пропущено)» — ученик **не приступал** к заданию.
  - score = 0, max_score возьми из criteria_html.
  - strengths: ровно «—» (прочерк).
  - weaknesses: «Задание пропущено. В следующий раз попробуй — даже частичный ответ может принести баллы.»
  - recommendation: короткий совет, какой параграф учебника поможет освоить эту тему.
- Если ответ есть (любой, даже частичный) — ученик **приступал**. Оценивай по критериям.

## Порядок действий
1. Прочитай каждое задание, критерии оценки и ответ ученика.
2. Первым делом определи: ответил ученик или пропустил задание (см. правило выше).
3. При необходимости обратись к учебнику через `show_toc()` и `get_page(part, page)`, чтобы уточнить правила.
4. Оцени ответ строго по критериям из `criteria_html`.
5. Сформулируй обратную связь.

## Как писать strengths и weaknesses
- strengths: что именно в ответе ученика совпадает с критериями. Конкретно, без украшательств. Не пиши «ты большой молодец» или «прекрасно справился». Если верных элементов нет — отметь это прямо, без комплиментов.
- weaknesses: какие именно критерии не выполнены. Без смягчающих оборотов вроде «немного не хватило». Если ученик ошибся — скажи в чём. Если ответ слабый — скажи, что ответ слабый.
- recommendation: конкретное действие. «Повтори правило в §...», «Потренируйся находить... в тексте».

## Этика
- Будь объективен. Не преувеличивай успехи и не сгущай краски над ошибками.
- Не используй сарказм, резкие оценки личности, сравнения с другими.
- Ты — безопасный взрослый. Ученик имеет право на ошибку и на пропуск задания.

## Правила выставления баллов
- Критерии в `criteria_html` — единственный авторитетный источник для оценки.
- Строго следуй критериям: если критерий требует 3 признака, а ученик назвал 2 — балл снижается.
- `score` — выставленный тобой балл (целое число от 0 до max_score).
- `max_score` — максимально возможный балл по критериям (извлеки из criteria_html).

## Порядок работы

Ты используешь инструмент `submit_review` для записи результата проверки каждого задания.

1. Прочитай все задания, критерии и ответы ученика.
2. Для каждого задания (К1–К7):
   - При необходимости обратись к учебнику через `show_toc()` и `get_page(part, page)`, чтобы уточнить правила.
   - Оцени ответ строго по критериям из `criteria_html`.
   - Вызови `submit_review`, чтобы записать результат проверки. Один вызов — одно задание.
3. После того как все задания проверены и записаны — твоя работа завершена. Не пиши итоговый текст.
"""


# ── submit_review tool processing ──────────────────────────────────────────────

REQUIRED_REVIEW_FIELDS = ["issue", "score", "max_score", "strengths", "weaknesses", "recommendation"]


def _process_submit_review(tool_call: dict, reviews: dict[int, dict]) -> dict:
    """Process a submit_review tool call, storing the review in *reviews*.

    Returns a tool_result dict with a confirmation or error message.
    """
    inp = tool_call.get("input", {})
    tool_id = tool_call.get("id", "")

    for field in REQUIRED_REVIEW_FIELDS:
        if field not in inp:
            return {
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": f"[Ошибка] Отсутствует обязательное поле: {field}",
            }

    issue = inp["issue"]
    if not isinstance(issue, int) or issue < 1:
        return {
            "type": "tool_result",
            "tool_use_id": tool_id,
            "content": f"[Ошибка] Некорректный номер задания: {issue}",
        }

    reviews[issue] = {
        "issue": issue,
        "score": inp["score"],
        "max_score": inp["max_score"],
        "strengths": inp.get("strengths", ""),
        "weaknesses": inp.get("weaknesses", ""),
        "recommendation": inp.get("recommendation", ""),
        "textbook_refs": inp.get("textbook_refs", []),
    }

    return {
        "type": "tool_result",
        "tool_use_id": tool_id,
        "content": f"Проверка задания К{issue} записана. Баллы: {inp['score']}/{inp['max_score']}.",
    }


# ── Message building ─────────────────────────────────────────────────────────


def _strip_html(html: str) -> str:
    """Crude HTML tag removal — replace tags with spaces, collapse whitespace."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_review_messages(tasks: list[dict], variant_num: int) -> list[dict]:
    """Format all tasks into a single user message for the review API call.

    Returns a list with one message dict: ``{"role": "user", "content": "..."}``.
    """
    lines = [f"## Вариант {variant_num} — проверка всех заданий\n"]

    for t in tasks:
        issue = t.get("issue", "?")
        category = t.get("category", "")
        content_text = _strip_html(t.get("content_html", ""))
        criteria_text = _strip_html(t.get("criteria_html", ""))
        solution_text = _strip_html(t.get("solution_html", ""))
        answer = t.get("student_answer", "").strip()

        lines.append(f"### Задание К{issue}. {category}")
        lines.append(f"\n**Формулировка:**\n{content_text}")

        if criteria_text:
            lines.append(f"\n**Критерии оценки:**\n{criteria_text}")

        if solution_text:
            lines.append(f"\n**Эталонное решение (для справки):**\n{solution_text}")

        if answer:
            lines.append(f"\n**Ответ ученика:**\n{answer}")
        else:
            lines.append("\n**Ответ ученика:**\n(задание пропущено)")

        lines.append("")

    return [{"role": "user", "content": "\n".join(lines)}]



def execute_review(
    api_key: str,
    tasks: list[dict],
    variant_num: int,
    textbook: dict,
    progress_context: str = "",
    max_iterations: int = MAX_REVIEW_TOOL_ITERATIONS,
    on_status: callable = None,
) -> dict:
    """Send tasks to DeepSeek, handling tool-use callbacks, return parsed review.

    Reviews are collected atomically via ``submit_review`` tool calls.
    If the model never uses ``submit_review``, returns empty reviews with
    ``parse_error: True``.

    Args:
        on_status: Optional callback receiving ``{"step": "...", ...}`` dicts.
                   Steps: ``submitted``, ``processing``, ``tool``,
                   ``done``, ``error``.

    Returns a dict with ``reviews`` array and ``parse_error`` flag.
    """
    def _emit(step, **kwargs):
        if on_status:
            payload = {"step": step}
            payload.update(kwargs)
            on_status(payload)

    def _make_result(last_msg):
        rv = {
            "reviews": list(reviews.values()),
            "parse_error": len(reviews) == 0,
            "usage": total_usage,
        }
        if rv["parse_error"]:
            text_blocks = [c.get("text", "") for c in last_msg.get("content", []) if c.get("type") == "text"]
            sample = "\n".join(text_blocks)[:800]
            _emit("diagnostic",
                  stop_reason=last_msg.get("stop_reason", "unknown"),
                  content_types=[c.get("type") for c in last_msg.get("content", [])],
                  text_sample=sample,
                  iteration=iteration + 1,
                  usage=dict(total_usage))
        return rv

    url = DEEPSEEK_URL
    headers = {
        "x-api-key": api_key,
        "content-type": "application/json",
        "anthropic-version": ANTHROPIC_VERSION,
    }

    tools = make_tools(review_mode=True)
    reviews: dict[int, dict] = {}

    system_prompt = REVIEW_SYSTEM_PROMPT
    if progress_context:
        system_prompt += f"\n\n## Прогресс ученика\n{progress_context}"

    messages = build_review_messages(tasks, variant_num)
    total_usage = {"input_tokens": 0, "output_tokens": 0}
    _emit("submitted", task_count=len(tasks), usage=dict(total_usage))

    for iteration in range(max_iterations):
        _emit("processing", iteration=iteration + 1, usage=dict(total_usage))

        compacted = compact_history(messages)

        body = {
            "model": MODEL,
            "system": system_prompt,
            "messages": compacted,
            "tools": tools,
            "stream": False,
            "max_tokens": MAX_REVIEW_TOKENS,
        }

        _emit("sending", iteration=iteration + 1,
              est_input=round(len(json.dumps(body, ensure_ascii=False)) / 3.5),
              usage=dict(total_usage))
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=60)
            resp.raise_for_status()
        except Exception as e:
            _emit("error", message=str(e), usage=dict(total_usage))
            raise

        msg = resp.json()

        # Accumulate usage from this API call
        iteration_usage = msg.get("usage", {})
        total_usage["input_tokens"] += iteration_usage.get("input_tokens", 0)
        total_usage["output_tokens"] += iteration_usage.get("output_tokens", 0)
        _emit("received", iteration=iteration + 1,
              iter_input=iteration_usage.get("input_tokens", 0),
              iter_output=iteration_usage.get("output_tokens", 0),
              usage=dict(total_usage))

        # Brief pause so the polling client sees the "received" step
        if msg.get("stop_reason") == "tool_use":
            time.sleep(0.6)

        if msg.get("stop_reason") != "tool_use":
            return _make_result(msg)

        # Extract tool_use blocks, split into textbook and review calls
        tool_calls = [c for c in msg.get("content", []) if c.get("type") == "tool_use"]
        if not tool_calls:
            return _make_result(msg)

        textbook_calls = [tc for tc in tool_calls if tc.get("name") in ("show_toc", "get_page")]
        review_calls = [tc for tc in tool_calls if tc.get("name") == "submit_review"]

        tool_results = []

        for tc in review_calls:
            _emit("tool", name="submit_review", input=tc.get("input", {}), usage=dict(total_usage))
            result = _process_submit_review(tc, reviews)
            tool_results.append(result)

        if textbook_calls:
            tool_results.extend(execute_tools(textbook_calls, textbook))

        messages.append({"role": "assistant", "content": msg.get("content", [])})
        messages.append({"role": "user", "content": tool_results})

    # Ran out of iterations — return whatever reviews were collected
    return _make_result(msg)
