# Ревью: удаление JSON-фолбека из execute_review

**Коммит:** `52b4150`
**Ветка:** `master`
**Дата:** 2026-06-06

## Общая оценка

✅ **ПРИНЯТО** — 1 замечание (косметическое).

Удаление чистое, все 66 тестов проходят. `parse_review_response` и три точки фолбека убраны
без остатка. Фронтенд переведён на проверку пустоты массива `reviews`. Промпт очищен от
упоминаний JSON.

## По файлам

### `src/tutor/review.py`

- `parse_review_response` (50 строк) удалена полностью. ✅
- 3 точки фолбека в `execute_review` заменены на одинаковый return — DRY. ✅
- `REVIEW_SYSTEM_PROMPT`: убрана последняя строка про «не возвращай JSON». ✅
- Docstring `execute_review`: убран шаг `parsing`, описание скорректировано. ✅
- Импорты `json` и `re` — нужны (`json.dumps` в _emit, `re` в `_strip_html`). ✅

### `src/tutor/server.py`

- SSE `done` event: убран `parse_error` из payload (строка 368). ✅
- Фронтенд больше не зависит от этого поля — смотрит на `reviews.length`. ✅

### `src/frontend/legacy/index.html`

- `requestAIReview`: проверка `reviews.length === 0` вместо `data.parse_error`. ✅
- При пустом reviews: `saveReviews(vNum, [])` — чистит localStorage от старого ревью. ✅
- Успешный путь: `renderReviewBlocks` + `notifyModelOfReview` внутри else — корректно. ✅
- `renderReviewBlocks`: убран fallback `issue === 0`, ранний return на пустом массиве. ✅
- `showReviewError` существует и вызывается корректно. ✅

### `tests/tutor/test_review.py`

- `TestParseReviewResponse` (11 тестов) удалён. ✅
- `parse_review_response` из импортов убран. ✅
- `test_direct_json_response` → `test_text_response_without_submit_tool_yields_empty_reviews`. ✅
- `test_with_tool_use` → `test_textbook_tool_without_submit_review_yields_empty`. ✅
- `test_fallback_json_parsing_when_no_submit_tool_used` → `test_no_submit_tool_returns_empty_reviews`. ✅
- `test_max_iterations_prevents_loop`: добавлены ассерты `parse_error is True` + `len(reviews) == 0`. ✅
- `test_no_json_format_instructions`: теперь `"json" not in prompt.lower()` — строже. ✅
- Моки в `test_compaction_in_loop` и `test_includes_progress_context` всё ещё содержат JSON-текст
  в ответе модели — но не влияют на ассерты (тесты проверяют побочные эффекты, а не результат). Допустимо. ✅

## Замечания

### 1. Мёртвый импорт `re` в `tests/tutor/test_review.py` (строка 4)

```python
import re
```

Ни одного вызова `re.*` в тестовом файле не осталось — импорт был нужен только
для `TestParseReviewResponse`. Подлежит удалению.

**Требуется:** да.

## Статистика

| Метрика | Было | Стало |
|---------|------|-------|
| Строк в review.py (тело) | 300 | 299 |
| Тестов в test_review.py | 77 | 66 |
| Точек фолбека в execute_review | 3 | 0 (унифицировано) |
| parse_error в SSE done | был | убран |

## Верификация

```bash
python3 -m pytest tests/tutor/test_review.py tests/tutor/test_common.py -v
# 66 passed
```
