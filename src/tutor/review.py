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

logger = logging.getLogger(__name__)

DEEPSEEK_URL = "https://api.deepseek.com/anthropic/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MODEL = "deepseek-v4-pro"
MAX_TOKENS = 4096
MAX_TOOL_ITERATIONS = 5

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


# ── Review execution ─────────────────────────────────────────────────────────


def execute_tools(tool_calls: list[dict], textbook: dict) -> list[dict]:
    """Execute a batch of tool calls against the in-memory textbook."""
    results = []

    def _toc():
        lines = []
        for entry in textbook["toc"]:
            _fmt_entry(entry, lines, 0)
        return "\n".join(lines)

    def _fmt_entry(entry: dict, lines: list[str], indent: int) -> None:
        prefix = "  " * indent
        if entry["type"] == "section":
            lines.append(f'{prefix}[{entry["title"]}]')
        elif entry["type"] == "subsection":
            lines.append(f'{prefix}{entry["title"]}')
        elif entry["type"] == "topic":
            num = entry.get("number") or ""
            page = entry.get("pdf_page", "?")
            lines.append(f'{prefix}{num} {entry["title"]} — стр. {page}')
        for child in entry.get("entries", []):
            _fmt_entry(child, lines, indent + 1)

    for tc in tool_calls:
        name = tc.get("name", "")
        inp = tc.get("input", {})
        tool_id = tc.get("id", "")

        try:
            if name == "show_toc":
                content = _toc()
            elif name == "get_page":
                part = int(inp.get("part", 1))
                page = int(inp.get("page", 1))
                entry = textbook["_page_index"].get((part, page))
                if entry is None:
                    content = f"[Ошибка] Страница не найдена: часть {part}, стр. {page}"
                else:
                    content = entry["text"]
            else:
                content = f"[Ошибка] Неизвестный инструмент: {name}"
        except Exception as exc:
            content = f"[Ошибка] {exc}"

        results.append({"type": "tool_result", "tool_use_id": tool_id, "content": content})

    return results


def execute_review(
    api_key: str,
    tasks: list[dict],
    variant_num: int,
    textbook: dict,
    progress_context: str = "",
    max_iterations: int = MAX_TOOL_ITERATIONS,
) -> dict:
    """Send tasks to DeepSeek, handling tool-use callbacks, return parsed review.

    Returns a dict with ``reviews`` array and optional ``parse_error`` flag.
    """
    url = DEEPSEEK_URL
    headers = {
        "x-api-key": api_key,
        "content-type": "application/json",
        "anthropic-version": ANTHROPIC_VERSION,
    }

    tools = [
        {
            "name": "show_toc",
            "description": "Получить полное оглавление учебника «Русский язык. 7 класс» "
                           "(Баранов, Ладыженская, 2022) с номерами параграфов и страниц.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "get_page",
            "description": "Получить текст конкретной страницы учебника по номеру PDF-страницы. "
                           "Часть (part): 1 или 2.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "part": {"type": "integer", "description": "Номер части учебника: 1 или 2"},
                    "page": {"type": "integer", "description": "Номер PDF-страницы"},
                },
                "required": ["part", "page"],
            },
        },
    ]

    system_prompt = REVIEW_SYSTEM_PROMPT
    if progress_context:
        system_prompt += f"\n\n## Прогресс ученика\n{progress_context}"

    messages = build_review_messages(tasks, variant_num)

    for _ in range(max_iterations):
        compacted = compact_history(messages)

        body = {
            "model": MODEL,
            "system": system_prompt,
            "messages": compacted,
            "tools": tools,
            "stream": False,
            "max_tokens": MAX_TOKENS,
        }

        resp = requests.post(url, headers=headers, json=body, timeout=60)
        resp.raise_for_status()
        msg = resp.json()

        if msg.get("stop_reason") != "tool_use":
            # Extract text content
            text_blocks = []
            for c in msg.get("content", []):
                if c.get("type") == "text":
                    text_blocks.append(c.get("text", ""))
            text = "\n".join(text_blocks)
            return parse_review_response(text)

        # Extract tool_use blocks and execute
        tool_calls = [c for c in msg.get("content", []) if c.get("type") == "tool_use"]
        if not tool_calls:
            text_blocks = []
            for c in msg.get("content", []):
                if c.get("type") == "text":
                    text_blocks.append(c.get("text", ""))
            return parse_review_response("\n".join(text_blocks))

        tool_results = execute_tools(tool_calls, textbook)
        messages.append({"role": "assistant", "content": msg.get("content", [])})
        messages.append({"role": "user", "content": tool_results})

    # Ran out of iterations — try to parse whatever we got
    text_blocks = []
    for c in msg.get("content", []):
        if c.get("type") == "text":
            text_blocks.append(c.get("text", ""))
    return parse_review_response("\n".join(text_blocks))
