# Review #1: progress tooling (`src/progress/`, `tests/progress/`, фронтенд-экспорт)

**Дата:** 2026-06-04
**Объект:** `src/progress/format.py`, `tests/progress/test_format.py`, `src/frontend/legacy/index.html` (функция `exportProgress`)
**Всего тестов:** 85 (52 textbook + 15 VPR + 18 progress), все зелёные

## Находки

### M1. `os` импортирован но не используется

**Файл:** `src/progress/format.py:11`
**Серьёзность:** major (мёртвый импорт)

Строка `import os` — модуль нигде в файле не используется. Удалить.

### M2. `Tuple` импортирован но не используется

**Файл:** `src/progress/format.py:13`
**Серьёзность:** major (мёртвый импорт)

`from typing import Dict, List, Optional, Tuple` — `Tuple` нигде не применяется.

### M3. `exportProgress()` жёстко задаёт 15×7 ✅ ИСПРАВЛЕНО

**Файл:** `src/frontend/legacy/index.html:376-377`
**Серьёзность:** major (хрупкость)

~~~javascript
// Было:
for (let v = 1; v <= 15; v++) {
  for (let i = 1; i <= 7; i++) {

// Стало:
const nV = variants.length || 15;
const nT = (variants.length > 0 && variants[0].tasks) ? variants[0].tasks.length : 7;
for (let v = 1; v <= nV; v++) {
  for (let i = 1; i <= nT; i++) {
~~~

Если количество вариантов или заданий изменится (новые данные с источника), экспорт молча потеряет ответы за пределами 15×7. Должно итерироваться по `variants.length` и фактическому числу заданий из данных.

### m1. `progress_as_context` принимает `answers`, но не использует

**Файл:** `src/progress/format.py:230`
**Серьёзность:** minor (обманчивый интерфейс)

Сигнатура `progress_as_context(progress, variants, answers)` — параметр `answers` объявлен, но нигде в теле функции не читается. Вызыватель может передать ответы, ожидая их увидеть в выводе — не увидит. Либо удалить параметр, либо добавить вывод ответов.

### m2. `progress_as_context` хардкодит предмет и класс

**Файл:** `src/progress/format.py:246-247`
**Серьёзность:** minor (дублирование)

```python
'Прогресс ученика (ВПР Русский язык 7 класс): '
```

В отличие от `format_progress`, которая берёт `meta['subject']` и `meta['grade']`, здесь значения зашиты строкой. При переходе на другой предмет/класс — рассыплется.

### m3. `json` импортирован но не используется в тестах

**Файл:** `tests/progress/test_format.py:3`
**Серьёзность:** minor (мёртвый импорт)

`import json` — нигде в тестовом файле не применяется.

### m4. Нет обработки отказа `localStorage` в `exportProgress()`

**Файл:** `src/frontend/legacy/index.html:373-392`
**Серьёзность:** minor (отказоустойчивость)

В режиме инкогнито некоторых браузеров, или при переполненном localStorage, вызов `getItem`/`setItem` может выбросить исключение. Функция `exportProgress` не обёрнута в try/catch — при ошибке кнопка молча не сработает.

### m5. Разделитель матрицы в `format_progress` не совпадает по ширине с заголовком

**Файл:** `src/progress/format.py:126`
**Серьёзность:** minor (не влияет на рендеринг, но сбивает при чтении сырого markdown)

```python
sep = '|---------|' + '|'.join(['----' for _ in topics]) + '|----------|'
```

Колонка «Вариант»: 9 дефисов. Колонки тем: 4 дефиса. Колонка «Завершён»: 10 дефисов. Markdown-парсеру безразлично, но при взгляде на сырой текст — неопрятно.

### c1. Смешанный стиль форматирования строк

**Файл:** `src/progress/format.py:111`
**Серьёзность:** cosmetic

```python
lines.append('## Темы заданий (К1–К{})'.format(tasks_per_variant))
```

Весь остальной файл использует f-строки. Эта единственная строка — `.format()`. Привести к единообразию.

### c2. `load_variants` без docstring

**Файл:** `src/progress/format.py:18-20`
**Серьёзность:** cosmetic

`load_progress` имеет docstring, `load_variants` — нет. Для симметрии либо добавить обоим, либо убрать у обоих (функции тривиальные).

### c3. Имя теста `test_llm_context_preamble` вводит в заблуждение

**Файл:** `tests/progress/test_format.py:132-135`
**Серьёзность:** cosmetic

Тест называется `test_llm_context_preamble` («преамбула контекста для LLM»), но проверяет `format_progress`, а не `progress_as_context` (которая именно для контекста и предназначена). Переименовать, например, в `test_format_progress_preamble`.

### c4. Слабое условие в `test_empty_progress`

**Файл:** `tests/progress/test_format.py:93`
**Серьёзность:** cosmetic

```python
assert 'нет данных' in output.lower() or '0 из 15' in output
```

Два независимых утверждения склеены через `or`. Лучше разбить на два `assert` — при падении будет ясно, что именно сломалось.

## Итог

| Серьёзность | Количество |
|-------------|-----------|
| major       | 2 (было 3, M3 исправлен) |
| minor       | 5         |
| cosmetic    | 4         |

**Вердикт:** к мержу готов. Оставшиеся 2 major (M1, M2) — мёртвые импорты, не влияют на работу. Minors рекомендуется поправить при рефакторинге.
