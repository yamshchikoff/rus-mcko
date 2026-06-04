# Review: Инструментарий постраничной загрузки учебника

**Дата:** 2026-06-04
**Ревизуемые фазы:** 1–6 (полный цикл)
**Ревизор:** deepseek-v4-pro
**Файлы:** 6 source + 5 test + 1 spec = 12 файлов
**Тесты:** 52/52 pass

## Резюме

Инструментарий работает, тесты проходят, сборка воспроизводима. Найдено 3 существенных замечания (2 major, 1 minor) и 5 косметических. Ни одного блокирующего.

## Статистика находок

| Серьёзность | Кол-во | Суть |
|-------------|--------|------|
| critical | 0 | — |
| major | 2 | Невалидный тест идемпотентности; неверное описание алгоритма в коммите |
| minor | 1 | Линейный поиск вместо O(1)-lookup в get_page |
| cosmetic | 5 | Устаревшие docstrings, дублирование _flatten, стиль импортов |

---

## Находки

### M1. `test_build_second_run_idempotent` не проверяет идемпотентность

**Файл:** `tests/textbook/test_build.py:107`
**Серьёзность:** major

```python
def test_build_second_run_idempotent():
    from src.textbook.build import build
    build()  # first run
    mtime_before = os.path.getmtime(TEXTBOOK_JSON)  # ← сохраняется, но...
    build()  # second run — should succeed
    assert os.path.exists(TEXTBOOK_JSON)  # ← ...не используется
```

Переменная `mtime_before` присваивается, но никогда не проверяется. Тест лишь убеждается, что файл существует после второго запуска — это проверяет не идемпотентность, а всего лишь что второй запуск не удалил файл. Настоящий тест идемпотентности должен проверять, что `mtime_after == mtime_before` (файл не был перезаписан).

**Рекомендация:**
```python
build()
mtime_before = os.path.getmtime(TEXTBOOK_JSON)
build()
mtime_after = os.path.getmtime(TEXTBOOK_JSON)
assert mtime_after == mtime_before, "Idempotent build should not rewrite file"
```

### M2. Описание `get_page` в коммите и спеке говорит «бинарный поиск», но реализация — линейный

**Файлы:** commit `543f59c`, `src/textbook/tools.py:60`
**Серьёзность:** major (несоответствие документации и кода)

Сообщение коммита:
```
get_page(part, page) — бинарный поиск по (part, page).
```

Реализация:
```python
for p in data['pages']:          # O(n) линейный обход
    if p['part'] == part and p['pdf_page'] == page:
        return p['text']
```

315 страниц — O(n) приемлемо, но документация вводит в заблуждение.

**Рекомендация:** либо перестроить `pages` в `dict` ключом `(part, pdf_page)` при загрузке (O(1) lookup), либо исправить описание. Учитывая, что это function calling и модель может делать несколько вызовов подряд, O(1) предпочтительнее:

```python
def _load() -> dict:
    global _data
    if _data is None:
        with open(TEXTBOOK_JSON, 'r', encoding='utf-8') as f:
            _data = json.load(f)
        _data['_page_index'] = {
            (p['part'], p['pdf_page']): p for p in _data['pages']
        }
    return _data

def get_page(part: int, page: int) -> str:
    ...
    p = data['_page_index'].get((part, page))
    if p is None:
        raise ValueError(...)
    return p['text']
```

### m1. `_make_topic` всегда записывает `number`, даже когда он None

**Файл:** `src/textbook/_toc_parser.py:192-195`
**Серьёзность:** minor

```python
if number:
    result['number'] = number
else:
    result['number'] = None
```

Обе ветки записывают ключ `number`. Можно сократить до `result['number'] = number` (тогда `None`-темы получат `number: null` вместо `number: null`, разницы нет — в JSON оба варианта дают `"number": null`). Это не баг, но усложнение без причины.

### c1. Устаревшие docstrings в тестовых файлах

**Файлы:** `test_constants.py:1`, `test_page_extractor.py:1`, `test_toc_parser.py:1`, `test_build.py:1`, `test_tools.py:1`
**Серьёзность:** cosmetic

Все пять файлов начинаются с `"""RED: Tests for ..."""`. Фаза RED пройдена, тесты зелёные — заголовки устарели.

### c2. `_is_topic_start` docstring расходится с реализацией

**Файл:** `src/textbook/_toc_parser.py:138-139`
**Серьёзность:** cosmetic

```python
def _is_topic_start(line: str) -> bool:
    """Line starts a topic: § marker, Повторение, or ALL CAPS with page number."""
```

Фраза «or ALL CAPS with page number» — остаток от ранней версии. Функция проверяет только `§\d+.` и `Повторение`. ALL CAPS с номерами страниц («Русский язык как развивающееся явление ... 4») обрабатываются catch-all блоком ниже (строка 92-99), а не этой функцией.

### c3. Дублирование `_flatten`

**Файлы:** `test_toc_parser.py:182`, `test_build.py:115`
**Серьёзность:** cosmetic

Обе версии `_flatten` идентичны. Стоит вынести в `tests/textbook/conftest.py` или в общий хелпер.

### c4. Импорты внутри функций

**Файлы:** `test_build.py`, `test_tools.py`, `test_constants.py`
**Серьёзность:** cosmetic

В RED-фазе импорты внутри функций оправданы (модуля ещё нет). Сейчас все модули существуют — импорты можно поднять на уровень модуля. Например, `test_build.py` делает `from src.textbook.build import build` в каждом тесте — 10 раз для одного и того же импорта.

### c5. `test_tools.py` использует `from src.textbook.tools import` в каждом тесте

**Файл:** `tests/textbook/test_tools.py`
**Серьёзность:** cosmetic

Аналогично c4: 10 тестов, 10 импортов. Достаточно одного модульного импорта.

---

## Что сделано хорошо

1. **Парсер TOC** — уверенно обрабатывает реальный хаос PDF-оглавления: ALL CAPS секции, Title Case подсекции, §-темы, Повторение без §, многострочные названия, строки-продолжения похожие на подсекции. Тесты на реальных данных, а не синтетических.

2. **Сборка идемпотентна** — повторный `build()` без `--force` не перезаписывает файл.

3. **Фильтрация словарных статей** — `_prepare_toc_text` отсекает толковый словарь, который физически находится на тех же PDF-страницах, что и оглавление. Неочевидная проблема, найденная и исправленная при тестировании.

4. **Конвертация страниц** — `printed_page + 1 = pdf_page`, учтено на всех слоях (парсер, сборка, tools).

5. **Спецификация** — честно перечисляет ограничения v1, включая что Part 2 не имеет ALL CAPS секций и словарь не индексирован.

6. **TDD** — каждая фаза прошла RED→GREEN→REFACTOR, 15 атомарных коммитов.

---

## Рекомендации к следующей итерации

| Приоритет | Что сделать |
|-----------|-------------|
| P0 | Исправить тест идемпотентности (M1) |
| P1 | Реализовать O(1) lookup в `get_page` (m1) |
| P2 | Поднять импорты на уровень модуля в тестах (c4, c5) |
| P3 | Вынести `_flatten` в общий хелпер (c3) |
| P3 | Актуализировать docstrings (c1, c2) |
