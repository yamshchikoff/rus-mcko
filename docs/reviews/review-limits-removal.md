# Ревью: снятие всех ограничений в review

**Коммиты:** `e28f8d8`, `e5f8551`, `15ebca3`
**Ветка:** `master`
**Дата:** 2026-06-06

## Общая оценка

✅ **ПРИНЯТО** — 1 замечание (исправлено в ходе ревью).

Суть правок: убрать все лимиты в review-пути, потому что ученик раз за разом
получал «Модель не смогла провести структурированную проверку» — модель не
успевала выполнить textbook-лукапы и 7 submit_review в отведённые 10 итераций.

## По файлам

### `src/tutor/common.py`

- `MAX_REVIEW_TOOL_ITERATIONS` удалён. ✅
- `MAX_REVIEW_TOKENS` удалён. ✅
- `MAX_TOOL_ITERATIONS = 5` остался для chat-лупа. ✅

### `src/tutor/review.py`

- `max_iterations` параметр удалён из сигнатуры `execute_review`. ✅
- Цикл `for` заменён на `while True` с единственным выходом по `end_turn`. ✅
- `max_tokens=32768` — аппаратный максимум API. ✅
- `_make_result(last_msg)` — хелпер, DRY-ит три точки возврата. ✅
- Diagnostic SSE-событие: при пустом reviews эмитится `step: "diagnostic"`
  с `stop_reason`, `content_types`, `text_sample`. Фронтенд игнорирует,
  видно только в Network-табе браузера. ✅
- Импорт `MAX_TOKENS` убран (не используется). ✅

**Замечание по безопасности цикла:** `while True` без счётчика — при баге
в коде или в API сервер зациклится навсегда и поток подвиснет. Однако:
- `compact_history` предотвращает переполнение контекста
- `requests.post(timeout=60)` предотвращает вечное ожидание ответа
- Каждая итерация отдаёт SSE-событие — фронтенд видит активность

Специального стоп-крана нет, но для MVP приемлемо. Если будут проблемы —
добавить safety cap на ~100 итераций (60×100 = 100 минут).

### `src/frontend/legacy/index.html`

- 7-минутный `setTimeout` (420000ms) убран. ✅
- Три вызова `clearTimeout(timeout)` убраны. ✅
- Обработка `AbortError` убрана — маловероятный сценарий
  (EventSource не использует AbortController). ✅

**Замечание:** без таймаута единственный способ прервать проверку для
пользователя — перезагрузить страницу. Кнопки «Отмена» нет. Не блокирует,
но стоит иметь в виду на будущее.

### Тесты

- `test_max_review_tokens_*` (2 теста) удалены. ✅
- `test_max_review_tool_iterations_exists` удалён. ✅
- `TestTimeoutConsistency` удалён. ✅
- `test_max_iterations_prevents_loop` → `test_loop_exits_on_end_turn` —
  проверяет выход по `end_turn` вместо счётчика. ✅
- `test_diagnostic_event_emitted_when_reviews_empty` — новый тест. ✅
- `test_max_tool_iterations_positive` — **был удалён по ошибке**, восстановлен
  в ходе ревью. Теперь 65 тестов (42 + 23). ✅

## Статистика

| Метрика | Было | Стало |
|---------|------|-------|
| MAX_REVIEW_TOOL_ITERATIONS | 30 (потом 10) | удалён |
| MAX_REVIEW_TOKENS | 8192 | удалён (32768 inline) |
| max_tokens в review | 4096 | 32768 |
| Фронтенд-таймаут | 420 с | безлимитный |
| Тестов | 68 | 65 |

## Верификация

```bash
python3 -m pytest tests/tutor/test_review.py tests/tutor/test_common.py -v
# 65 passed
```
