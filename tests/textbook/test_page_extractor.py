"""RED: Tests for src.textbook._page_extractor."""

import pytest
from src.textbook.constants import PDF_PATH_PART1, PDF_PATH_PART2, MIN_CONTENT_CHARS


def test_extract_all_pages_returns_list():
    from src.textbook._page_extractor import extract_all_pages
    pages = extract_all_pages(PDF_PATH_PART1)
    assert isinstance(pages, list)
    assert len(pages) > 0


def test_extract_all_pages_part1_count():
    from src.textbook._page_extractor import extract_all_pages
    pages = extract_all_pages(PDF_PATH_PART1)
    assert len(pages) == 185


def test_extract_all_pages_part2_count():
    from src.textbook._page_extractor import extract_all_pages
    pages = extract_all_pages(PDF_PATH_PART2)
    assert len(pages) == 149


def test_all_pages_are_strings():
    from src.textbook._page_extractor import extract_all_pages
    pages = extract_all_pages(PDF_PATH_PART1)
    for page in pages:
        assert isinstance(page, str)


def test_pages_are_valid_utf8():
    from src.textbook._page_extractor import extract_all_pages
    pages = extract_all_pages(PDF_PATH_PART1)
    for i, page in enumerate(pages):
        page.encode('utf-8')


def test_content_pages_have_cyrillic():
    from src.textbook._page_extractor import extract_all_pages
    pages = extract_all_pages(PDF_PATH_PART1)
    import re
    content_pages_found = 0
    for i, page in enumerate(pages):
        if len(page.strip()) >= MIN_CONTENT_CHARS:
            content_pages_found += 1
            assert re.search(r'[а-яА-ЯёЁ]', page), f"Page {i+1} has no Cyrillic"
    assert content_pages_found > 100


def test_cover_page_has_minimal_text():
    from src.textbook._page_extractor import extract_all_pages
    pages = extract_all_pages(PDF_PATH_PART1)
    assert len(pages[0].strip()) < MIN_CONTENT_CHARS


def test_content_pages_range_part1():
    from src.textbook._page_extractor import extract_all_pages
    from src.textbook.constants import CONTENT_PAGE_RANGE_PART1
    pages = extract_all_pages(PDF_PATH_PART1)
    start, end = CONTENT_PAGE_RANGE_PART1
    for i in range(start - 1, end):
        assert len(pages[i].strip()) >= MIN_CONTENT_CHARS, f"Page {i+1} too short"


def test_raises_on_nonexistent_pdf():
    from src.textbook._page_extractor import extract_all_pages
    with pytest.raises(FileNotFoundError):
        extract_all_pages('/nonexistent/path.pdf')
