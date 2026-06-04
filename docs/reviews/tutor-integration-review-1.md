# Review #1: интеграция ИИ-репетитора

**Дата:** 2026-06-05
**Объект:** `src/tutor/`, `tests/tutor/`, `src/frontend/legacy/index.html` и `sdamgia.css`
**Всего тестов:** 130 (68 старых + 45 tutor), все зелёные

## Находки

### M1. `run_tool_use_loop` игнорирует контекст прогресса и задания

**Файл:** `src/tutor/server.py:187`
**Серьёзность:** major (репетитор не видит прогресс ученика и задание)

Внутри цикла tool-use системный промпт формируется вызовом `get_system_prompt()` без аргументов:

```python
body = {
    "model": MODEL,
    "system": get_system_prompt(),  # ← без progress_context и current_task
    ...
}
```

Прогресс и задание, переданные фронтендом в `POST /api/chat`, теряются. Репетитор не знает, над каким вариантом работает ученик и какой у него прогресс.

**Вариант исправления:** добавить параметры `progress_context` и `current_task` в сигнатуру `run_tool_use_loop` и прокидывать в `get_system_prompt()`.

### M2. Мёртвый код: `system` вычисляется но не используется

**Файл:** `src/tutor/server.py:283-291`
**Серьёзность:** major (мёртвый код + symptom M1)

```python
if progress_context or current_task:
    _, _, body = build_chat_request(
        api_key, messages,
        progress_context=progress_context,
        current_task=current_task,
    )
    system = body["system"]
else:
    system = get_system_prompt()
```

Переменная `system` присваивается, но нигде в `_handle_chat` не читается. Результат вызова `build_chat_request` (три значения) — два из трёх (`url`, `headers`) тоже не используются. Всё это — следствие M1.

### M3. `_handle_chat` не обрабатывает ошибку парсинга JSON

**Файл:** `src/tutor/server.py:266-268`
**Серьёзность:** minor (падение хендлера при кривом запросе)

```python
raw = self.rfile.read(length)
payload = json.loads(raw)
```

Если клиент пришлёт невалидный JSON, `json.loads` выбросит `JSONDecodeError` — хендлер упадёт с 500, но без внятного сообщения. Стоит обернуть в `try/except`.

### m1. `buildTutorContext` парсит HTML заново на каждое сообщение

**Файл:** `src/frontend/legacy/index.html:185-189`
**Серьёзность:** minor (лишняя работа DOM)

```javascript
v.tasks.forEach(t => {
    const div = document.createElement('div');
    div.innerHTML = t.content_html;
    const text = div.textContent.trim().substring(0, 300);
    ...
});
```

На каждое сообщение чата — 7 проходов по `innerHTML → textContent`. При 100 сообщениях в истории — 700 парсингов. Можно распарсить один раз при `showVariant` и сохранить в `cachedTaskTexts`.

### m2. `simpleMarkdown` оборачивает элементы `<ol>` в `<ul>`

**Файл:** `src/frontend/legacy/index.html:225-228`
**Серьёзность:** minor (функциональный баг в рендеринге)

```javascript
// Line 225: - items → <li>
html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, '<ul>$1</ul>');  // все <li> → <ul>
// Line 228: 1. items → <li> (без <ol> обёртки!)
html = html.replace(/^\d+\.\s+(.+)$/gm, '<li>$1</li>');
```

Строка 226 оборачивает любые `<li>` в `<ul>`, включая элементы упорядоченных списков (из строки 228). Результат: `1. Пункт` рендерится с маркером, а не с номером.

### m3. `renderProgressTable` хардкодит 15 вариантов

**Файл:** `src/frontend/legacy/index.html:697`
**Серьёзность:** minor (хрупкость, аналог ранее исправленного M3)

```javascript
for (let vNum = 1; vNum <= 15; vNum++) {
```

Ранее та же проблема была исправлена в `exportProgress` (M3 из `progress-tooling-review-1.md`). Здесь осталась копия.

### m4. `chat-input` textarea сбрасывает высоту в `auto` вместо `''`

**Файл:** `src/frontend/legacy/index.html:298`
**Серьёзность:** minor (прыгающая высота после отправки)

```javascript
input.style.height = 'auto';
```

`auto` — валидное значение CSS, но оно переопределяет инлайн-стиль. Если пользователь растянул textarea мышкой (resize: vertical), после отправки высота сбросится в браузерный дефолт, а не в CSS-заданный `min-height: 40px`. Правильнее: `input.style.height = ''` (удалить инлайн-стиль, вернуть CSS).

### m5. Нет `Connection: close` в ответах хендлера

**Файл:** `src/tutor/server.py:258, 306`
**Серьёзность:** minor (потенциальные проблемы с keep-alive)

`BaseHTTPRequestHandler` использует HTTP/1.1 с keep-alive. Без `Connection: close` браузер может ждать следующего запроса на том же соединении. Для текущей нестриминговой реализации не критично, но станет проблемой при переходе на SSE.

### c1. `import time` — мёртвый импорт

**Файл:** `tests/tutor/test_server.py:5`
**Серьёзность:** cosmetic

### c2. `from pathlib import Path` — мёртвый импорт

**Файл:** `tests/tutor/test_server.py:9`
**Серьёзность:** cosmetic

### c3. `_PROJECT_ROOT` и `PROJECT_ROOT` — дублирование

**Файл:** `src/tutor/server.py:18, 35`
**Серьёзность:** cosmetic

Обе переменные вычисляются одинаково: `Path(__file__).resolve().parent.parent.parent`. Можно определить один раз и переиспользовать.

### c4. `max_tokens: float` в сигнатуре `compact_history`

**Файл:** `src/tutor/compaction.py:22`
**Серьёзность:** cosmetic

Тип `float` для счётчика токенов нелогичен — токены дискретны. Константа `170_000` — `int`. Лучше `max_tokens: int`.

### c5. `estimate_tokens` возвращает `float`

**Файл:** `src/tutor/compaction.py:10`
**Серьёзность:** cosmetic

Возврат `float` при делении на 3.5 — результат почти всегда дробный. Логично возвращать `int` (округление вверх или до ближайшего), чтобы `max_tokens` могло быть `int`.

## Итог

| Серьёзность | Количество |
|-------------|-----------|
| major       | 2 |
| minor       | 5 |
| cosmetic    | 5 |

**Вердикт:** к мержу не готов. M1 и M2 должны быть исправлены до первого реального использования — без них репетитор работает вслепую, не видя ни прогресса ученика, ни текущего задания. Minors можно поправить следом.
