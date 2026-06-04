# Review #2: Инструментарий постраничной загрузки учебника

**Дата:** 2026-06-04
**Ревизуемый диапазон:** `39dcc62..e8875e2` (исправления M1, M2, m1)
**Ревизор:** deepseek-v4-pro
**Тесты:** 52/52 pass

## Резюме

Все три исправления корректны. Новых проблем не найдено. Косметические замечания из первого ревью остаются неустранёнными (не блокируют).

## Верификация исправлений

### M1: тест идемпотентности — исправлен

```python
mtime_before = os.path.getmtime(TEXTBOOK_JSON)
build()  # second run
mtime_after = os.path.getmtime(TEXTBOOK_JSON)
assert mtime_after == mtime_before, "Second run should not rewrite file"
```

Проверка правильная: второй `build()` без `--force` не меняет файл → `mtime` совпадают. Подтверждено тестом.

### M2: O(1) lookup — исправлен

```python
_data['_page_index'] = {
    (p['part'], p['pdf_page']): p for p in _data['pages']
}
```

Индекс строится один раз при первой загрузке. `get_page` делает `data['_page_index'].get((part, page))` — O(1). Ключ `_page_index` не попадает в `show_toc()` (та ходит только в `data['toc']`) и не записывается на диск (только в памяти). Корректно.

### m1: упрощение `_make_topic` — исправлен

```python
result = {
    'type': 'topic',
    'title': title,
    'part': part,
    'pdf_page': pdf_page,
    'number': number,   # всегда присутствует, None или str
}
```

Без if/else. JSON на выходе идентичен (ключ `number` и так был всегда). Подтверждено тестами.

## Нерешённое из первого ревью

| ID | Описание | Серьёзность |
|----|----------|-------------|
| c1 | `"""RED: Tests for ..."""` docstrings в 5 тестовых файлах | cosmetic |
| c2 | `_is_topic_start` docstring: «ALL CAPS with page number» не соответствует коду | cosmetic |
| c3 | Дублирование `_flatten` в test_toc_parser.py и test_build.py | cosmetic |
| c4 | Импорты внутри функций в test_build.py (10 повторов) | cosmetic |
| c5 | Импорты внутри функций в test_tools.py (10 повторов) | cosmetic |

## Новые находки

Нет. Код после исправлений чистый.

## Статистика

| Серьёзность | Кол-во |
|-------------|--------|
| critical | 0 |
| major | 0 |
| minor | 0 |
| cosmetic | 5 (переходящие из ревью #1) |
