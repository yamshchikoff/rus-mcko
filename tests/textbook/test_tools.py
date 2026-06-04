"""RED: Tests for src.textbook.tools."""

import pytest


def test_show_toc_returns_string():
    from src.textbook.tools import show_toc
    result = show_toc()
    assert isinstance(result, str)
    assert len(result) > 0


def test_show_toc_contains_sections():
    from src.textbook.tools import show_toc
    result = show_toc()
    assert 'ПОВТОРЕНИЕ ИЗУЧЕННОГО В 5—6 КЛАССАХ' in result
    assert 'МОРФОЛОГИЯ И ОРФОГРАФИЯ. КУЛЬТУРА РЕЧИ' in result


def test_show_toc_contains_topics():
    from src.textbook.tools import show_toc
    result = show_toc()
    assert '§ 12' in result
    assert 'Причастие как часть речи' in result


def test_show_toc_includes_pdf_pages():
    from src.textbook.tools import show_toc
    result = show_toc()
    assert 'стр. 7' in result or 'с. 7' in result or 'page 7' in result


def test_get_page_returns_text():
    from src.textbook.tools import get_page
    text = get_page(part=1, page=7)
    assert isinstance(text, str)
    assert len(text) > 0


def test_get_page_content_correct():
    from src.textbook.tools import get_page
    text = get_page(part=1, page=7)
    assert '§ 1' in text or 'Синтаксис' in text


def test_get_page_part2():
    from src.textbook.tools import get_page
    text = get_page(part=2, page=14)
    assert len(text) > 0
    assert '§ 49' in text or 'Категория состояния' in text


def test_get_page_invalid_part_raises():
    from src.textbook.tools import get_page
    with pytest.raises(ValueError):
        get_page(part=3, page=1)
    with pytest.raises(ValueError):
        get_page(part=0, page=1)


def test_get_page_invalid_page_raises():
    from src.textbook.tools import get_page
    with pytest.raises(ValueError):
        get_page(part=1, page=999)
    with pytest.raises(ValueError):
        get_page(part=1, page=0)


def test_lazy_loading():
    """Both functions work without explicit init call."""
    from src.textbook.tools import show_toc, get_page
    toc = show_toc()
    page = get_page(part=1, page=40)
    assert len(toc) > 0
    assert len(page) > 0
