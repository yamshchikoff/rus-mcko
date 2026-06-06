"""Shared constants, tool definitions, and tool execution for tutor server.

Used by both chat endpoint (server.py) and review endpoint (review.py).
"""

from __future__ import annotations

# ── DeepSeek API constants ────────────────────────────────────────────────────

DEEPSEEK_URL = "https://api.deepseek.com/anthropic/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MODEL = "deepseek-v4-pro"
MAX_TOKENS = 4096
MAX_TOOL_ITERATIONS = 5
MAX_REVIEW_TOOL_ITERATIONS = 15

# ── Tool definitions ──────────────────────────────────────────────────────────


def make_tools(review_mode: bool = False) -> list[dict]:
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

    if review_mode:
        tools.append({
            "name": "submit_review",
            "description": "Записать результат проверки одного задания. "
                           "Вызывай этот инструмент для каждого задания (К1–К7) после оценки. "
                           "Один вызов — одно задание.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "issue": {
                        "type": "integer",
                        "description": "Номер задания (1–7)",
                    },
                    "score": {
                        "type": "integer",
                        "description": "Выставленный балл (0 до max_score)",
                    },
                    "max_score": {
                        "type": "integer",
                        "description": "Максимально возможный балл по критериям задания",
                    },
                    "strengths": {
                        "type": "string",
                        "description": "Что в ответе ученика верно и соответствует критериям",
                    },
                    "weaknesses": {
                        "type": "string",
                        "description": "Какие критерии не выполнены, какие ошибки допущены",
                    },
                    "recommendation": {
                        "type": "string",
                        "description": "Конкретный совет: какой параграф повторить, на что обратить внимание",
                    },
                    "textbook_refs": {
                        "type": "array",
                        "description": "Ссылки на параграфы учебника, относящиеся к теме задания",
                        "items": {
                            "type": "object",
                            "properties": {
                                "paragraph": {"type": "string", "description": "Номер параграфа, например § 12"},
                                "part": {"type": "integer", "description": "Номер части учебника (1 или 2)"},
                                "page": {"type": "integer", "description": "Номер PDF-страницы"},
                                "description": {"type": "string", "description": "О чём параграф"},
                            },
                            "required": ["paragraph", "part", "page", "description"],
                        },
                    },
                },
                "required": ["issue", "score", "max_score", "strengths", "weaknesses", "recommendation"],
            },
        })

    return tools


# ── Tool execution ────────────────────────────────────────────────────────────


def execute_tools(tool_calls: list[dict], textbook: dict) -> list[dict]:
    """Execute a batch of tool calls against the in-memory textbook.

    Returns a list of tool_result dicts ready to append to the conversation.
    """
    results = []

    def _toc() -> str:
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
