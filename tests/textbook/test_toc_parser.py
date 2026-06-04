"""RED: Tests for src.textbook._toc_parser."""

import pytest
from src.textbook._toc_parser import parse_toc


SAMPLE_TOC_PART1 = """
СОДЕРЖАНИЕ

Русский язык как развивающееся явление ...................                     4
ПОВТОРЕНИЕ ИЗУЧЕННОГО В 5—6 КЛАССАХ
§ 1. Синтаксис. Синтаксический разбор предложения 6
§ 2. Пунктуация. Пунктуационный разбор предложе-
ния ......................................................................... 7
ТЕКСТ И СТИЛИ РЕЧИ
§ 7. Текст ................................................................   24
МОРФОЛОГИЯ И ОРФОГРАФИЯ. КУЛЬТУРА РЕЧИ
Причастие
§ 12. Причастие как часть речи ................................               39
§ 13. Склонение причастий и правописание гласных
в падежных окончаниях причастий .............................                 43
Деепричастие
§ 28. Деепричастие как часть речи .............................. 97
Повторение .............................................................. 116
Наречие
§ 34. Наречие как часть речи ................................... 119
"""


def test_parse_toc_returns_list():
    entries = parse_toc(SAMPLE_TOC_PART1, part=1)
    assert isinstance(entries, list)
    assert len(entries) > 0


def test_parse_toc_detects_sections():
    entries = parse_toc(SAMPLE_TOC_PART1, part=1)
    sections = [e for e in entries if e['type'] == 'section']
    assert len(sections) >= 2
    titles = [s['title'] for s in sections]
    assert 'ПОВТОРЕНИЕ ИЗУЧЕННОГО В 5—6 КЛАССАХ' in titles
    assert 'ТЕКСТ И СТИЛИ РЕЧИ' in titles


def test_parse_toc_detects_subsections():
    entries = parse_toc(SAMPLE_TOC_PART1, part=1)
    all_entries = _flatten(entries)
    subsections = [e for e in all_entries if e['type'] == 'subsection']
    titles = [s['title'] for s in subsections]
    assert 'Причастие' in titles
    assert 'Деепричастие' in titles
    assert 'Наречие' in titles


def test_parse_toc_detects_topics():
    entries = parse_toc(SAMPLE_TOC_PART1, part=1)
    all_entries = _flatten(entries)
    topics = [e for e in all_entries if e['type'] == 'topic']
    assert len(topics) >= 8
    numbers = [t.get('number') for t in topics]
    assert '§ 1' in numbers
    assert '§ 12' in numbers


def test_parse_toc_converts_printed_page_to_pdf():
    entries = parse_toc(SAMPLE_TOC_PART1, part=1)
    all_entries = _flatten(entries)
    topics = [e for e in all_entries if e['type'] == 'topic']
    # § 1: printed page 6 → PDF page 7
    t = next(t for t in topics if t.get('number') == '§ 1')
    assert t['pdf_page'] == 7
    assert t['part'] == 1


def test_parse_toc_extracts_topic_without_paragraph_sign():
    entries = parse_toc(SAMPLE_TOC_PART1, part=1)
    all_entries = _flatten(entries)
    povtorenie = [e for e in all_entries
                  if e['type'] == 'topic' and 'Повторение' in e['title']]
    assert len(povtorenie) >= 1
    # Повторение after Деепричастие: printed page 116 → PDF page 117
    assert povtorenie[0]['pdf_page'] == 117


def test_parse_toc_multi_line_topic():
    entries = parse_toc(SAMPLE_TOC_PART1, part=1)
    all_entries = _flatten(entries)
    # § 2 has a multi-line title: "Пунктуация. Пунктуационный разбор предложения"
    topics = [e for e in all_entries if e.get('number') == '§ 2']
    assert len(topics) == 1
    assert 'Пунктуационный разбор' in topics[0]['title']


def test_parse_toc_ignores_soderzhanie():
    entries = parse_toc(SAMPLE_TOC_PART1, part=1)
    all_entries = _flatten(entries)
    for e in all_entries:
        assert 'СОДЕРЖАНИЕ' not in e.get('title', '')


def test_parse_toc_empty_text_raises():
    with pytest.raises(ValueError):
        parse_toc('', part=1)


def test_parse_toc_entries_have_required_fields():
    entries = parse_toc(SAMPLE_TOC_PART1, part=1)
    all_entries = _flatten(entries)
    for e in all_entries:
        assert 'type' in e
        assert 'title' in e
        assert e['type'] in ('section', 'subsection', 'topic')
        if e['type'] == 'topic':
            assert 'pdf_page' in e, f"Topic '{e['title']}' missing pdf_page"
            assert 'part' in e


def test_parse_toc_part2_structure():
    sample_p2 = """
СОДЕРЖАНИЕ
Текст и стили речи
Научный стиль
§ 47. Учебно-научная речь. Отзыв ...............................                 4
Морфология и орфография. Культура речи
Категория состояния
§ 49. Категория состояния как часть речи ................... 14
Служебные части речи
§ 51. Самостоятельные и служебные части речи ........... 26
Предлог
§ 52. Предлог как часть речи......................................              27
"""
    entries = parse_toc(sample_p2, part=2)
    all_entries = _flatten(entries)
    subsections = [e for e in all_entries if e['type'] == 'subsection']
    titles = [s['title'] for s in subsections]
    assert 'Научный стиль' in titles
    assert 'Категория состояния' in titles
    assert 'Предлог' in titles

    topics = [e for e in all_entries if e['type'] == 'topic']
    assert len(topics) >= 3


def test_parse_toc_unmarked_topic():
    """Topic without § — e.g. 'Русский язык как развивающееся явление ... 4'."""
    text = """
СОДЕРЖАНИЕ

Русский язык как развивающееся явление ...................                     4
ПОВТОРЕНИЕ ИЗУЧЕННОГО В 5—6 КЛАССАХ
§ 1. Синтаксис. Синтаксический разбор предложения 6
"""
    entries = parse_toc(text, part=1)
    all_entries = _flatten(entries)
    topics = [e for e in all_entries if e['type'] == 'topic']
    titles = [t['title'] for t in topics]
    assert any('Русский язык как развивающееся явление' in t for t in titles), \
        f"Missing unmarked topic, got: {titles}"


def test_parse_toc_section_topic_with_subsection_like_continuation():
    """§ topic where continuation line looks like a subsection header."""
    text = """
СОДЕРЖАНИЕ

МОРФОЛОГИЯ И ОРФОГРАФИЯ. КУЛЬТУРА РЕЧИ
Причастие
§ 18. Действительные причастия настоящего времени.
Гласные в суффиксах действительных причастий на-
стоящего времени ....................................................           58
§ 19. Действительные причастия прошедшего времени                               61
"""
    entries = parse_toc(text, part=1)
    all_entries = _flatten(entries)
    topics = [e for e in all_entries if e['type'] == 'topic']
    t18 = next((t for t in topics if t.get('number') == '§ 18'), None)
    assert t18 is not None, '§ 18 not found'
    assert 'Гласные в суффиксах' in t18['title'], f"Continuation missing: {t18['title']}"
    assert t18['pdf_page'] == 59, f"Expected PDF page 59, got {t18['pdf_page']}"


def _flatten(entries):
    result = []
    for e in entries:
        result.append(e)
        if 'entries' in e:
            result.extend(_flatten(e['entries']))
    return result
