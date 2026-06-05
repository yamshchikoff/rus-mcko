"""AI-powered work review after VPR task completion.

The review endpoint sends all 7 tasks with student answers to the model,
which scores each according to official criteria and provides detailed
feedback — strengths, weaknesses, recommendations, and textbook references.
"""

from __future__ import annotations

import json
import logging
import re

import requests

from src.tutor.compaction import compact_history
from src.tutor.common import (
    DEEPSEEK_URL, ANTHROPIC_VERSION, MODEL, MAX_TOKENS, MAX_TOOL_ITERATIONS,
    make_tools, execute_tools,
)

logger = logging.getLogger(__name__)

REVIEW_SYSTEM_PROMPT = """Ты — ИИ-репетитор по русскому языку, мужчина. Твои ученики — семиклассники (13–14 лет).

## Режим: ПРОВЕРКА РАБОТЫ

Ты находишься в режиме проверки выполненной работы ВПР. Это НЕ диалог — ученик не видит твоих слов напрямую. Ты получаешь 7 заданий с ответами ученика. Твоя задача: выставить баллы строго по критериям и дать полезную обратную связь.

## Порядок действий
1. Прочитай каждое задание, критерии оценки и ответ ученика.
2. При необходимости обратись к учебнику через `show_toc()` и `get_page(part, page)`, чтобы уточнить правила.
3. Оцени ответ строго по критериям из `criteria_html`.
4. Сформулируй обратную связь: что правильно, над чем поработать, конкретный совет со ссылкой на параграф учебника.

## Этика
- Начинай с того, что ученик сделал правильно. Хвали за усилия.
- Не используй сарказм, резкие оценки личности, сравнения с другими.
- Формулируй weaknesses как «над чем поработать», а не как «что плохо».
- Если ответ отсутствует — мягко предложи попробовать в следующий раз.
- Ты — безопасный взрослый. Ученик имеет право на ошибку.

## Правила выставления баллов
- Критерии в `criteria_html` — единственный авторитетный источник для оценки.
- Строго следуй критериям: если критерий требует 3 признака, а ученик назвал 2 — балл снижается.
- `score` — выставленный тобой балл (целое число от 0 до max_score).
- `max_score` — максимально возможный балл по критериям (извлеки из criteria_html).
- Если ответ отсутствует (пустая строка) — score = 0, soft weaknesses.

## Формат ответа

Ты должен вернуть **строго JSON** без текста до или после:

```json
{
  "reviews": [
    {
      "issue": 1,
      "score": 3,
      "max_score": 4,
      "strengths": "Ты правильно расставил знаки препинания...",
      "weaknesses": "В первом предложении пропущена запятая...",
      "recommendation": "Повтори правило в параграфе 12 учебника...",
      "textbook_refs": [
        {"paragraph": "§ 12", "part": 1, "page": 34, "description": "Чередование гласных"}
      ]
    }
  ]
}
```

Проверь, что в твоём ответе нет текста вне JSON-блока.
"""


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
            lines.append("\n**Ответ ученика:**\n(ответ отсутствует)")

        lines.append("")

    return [{"role": "user", "content": "\n".join(lines)}]


# ── Response parsing ─────────────────────────────────────────────────────────


def parse_review_response(text: str) -> dict:
    """Extract and validate the JSON review from model output.

    Strategies, tried in order:
    1. Find ```json ... ``` code fence, parse content.
    2. Find outermost {...} in text, parse it.
    3. Parse entire text as JSON.

    Returns ``{"reviews": [...], "parse_error": False}`` on success,
    or ``{"reviews": [], "parse_error": True, "raw_text": "..."}`` on failure.
    """
    if not text or not text.strip():
        return {"reviews": [], "parse_error": True, "raw_text": text}

    candidates = []

    # Strategy 1: code fence
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence_match:
        candidates.append(fence_match.group(1).strip())

    # Strategy 2: outermost braces
    brace_match = re.search(r"\{[\s\S]*\}", text)
    if brace_match:
        candidates.append(brace_match.group(0).strip())

    # Strategy 3: entire text
    candidates.append(text.strip())

    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if isinstance(data, dict) and "reviews" in data:
                for r in data["reviews"]:
                    r.setdefault("strengths", "")
                    r.setdefault("weaknesses", "")
                    r.setdefault("recommendation", "")
                    r.setdefault("textbook_refs", [])
                    # Clamp score to valid range
                    max_s = r.get("max_score", 0)
                    if max_s > 0 and r.get("score", 0) > max_s:
                        r["score"] = max_s
                    if r.get("score", 0) < 0:
                        r["score"] = 0
                return {"reviews": data["reviews"], "parse_error": False}
        except (json.JSONDecodeError, TypeError):
            continue

    return {"reviews": [], "parse_error": True, "raw_text": text}


def execute_review(
    api_key: str,
    tasks: list[dict],
    variant_num: int,
    textbook: dict,
    progress_context: str = "",
    max_iterations: int = MAX_TOOL_ITERATIONS,
    on_status: callable = None,
) -> dict:
    """Send tasks to DeepSeek, handling tool-use callbacks, return parsed review.

    Args:
        on_status: Optional callback receiving ``{"step": "...", ...}`` dicts.
                   Steps: ``submitted``, ``processing``, ``tool``, ``parsing``,
                   ``done``, ``error``.

    Returns a dict with ``reviews`` array and optional ``parse_error`` flag.
    """
    def _emit(step, **kwargs):
        if on_status:
            payload = {"step": step}
            payload.update(kwargs)
            on_status(payload)

    url = DEEPSEEK_URL
    headers = {
        "x-api-key": api_key,
        "content-type": "application/json",
        "anthropic-version": ANTHROPIC_VERSION,
    }

    tools = make_tools()

    system_prompt = REVIEW_SYSTEM_PROMPT
    if progress_context:
        system_prompt += f"\n\n## Прогресс ученика\n{progress_context}"

    messages = build_review_messages(tasks, variant_num)
    _emit("submitted", task_count=len(tasks))

    for iteration in range(max_iterations):
        _emit("processing", iteration=iteration + 1)

        compacted = compact_history(messages)

        body = {
            "model": MODEL,
            "system": system_prompt,
            "messages": compacted,
            "tools": tools,
            "stream": False,
            "max_tokens": MAX_TOKENS,
        }

        try:
            resp = requests.post(url, headers=headers, json=body, timeout=60)
            resp.raise_for_status()
        except Exception as e:
            _emit("error", message=str(e))
            raise

        msg = resp.json()

        if msg.get("stop_reason") != "tool_use":
            _emit("parsing")
            text_blocks = []
            for c in msg.get("content", []):
                if c.get("type") == "text":
                    text_blocks.append(c.get("text", ""))
            result = parse_review_response("\n".join(text_blocks))
            _emit("done")
            return result

        # Extract tool_use blocks and execute
        tool_calls = [c for c in msg.get("content", []) if c.get("type") == "tool_use"]
        if not tool_calls:
            _emit("parsing")
            text_blocks = []
            for c in msg.get("content", []):
                if c.get("type") == "text":
                    text_blocks.append(c.get("text", ""))
            result = parse_review_response("\n".join(text_blocks))
            _emit("done")
            return result

        for tc in tool_calls:
            _emit("tool", name=tc.get("name", "?"), input=tc.get("input", {}))

        tool_results = execute_tools(tool_calls, textbook)
        messages.append({"role": "assistant", "content": msg.get("content", [])})
        messages.append({"role": "user", "content": tool_results})

    # Ran out of iterations — try to parse whatever we got
    _emit("parsing")
    text_blocks = []
    for c in msg.get("content", []):
        if c.get("type") == "text":
            text_blocks.append(c.get("text", ""))
    result = parse_review_response("\n".join(text_blocks))
    _emit("done")
    return result
