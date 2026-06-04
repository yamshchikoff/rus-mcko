"""RED: Tests for src.textbook.constants."""

import os
from pathlib import Path


def test_pdf_path_part1_exists():
    from src.textbook.constants import PDF_PATH_PART1
    assert os.path.exists(PDF_PATH_PART1), f"PDF not found: {PDF_PATH_PART1}"


def test_pdf_path_part2_exists():
    from src.textbook.constants import PDF_PATH_PART2
    assert os.path.exists(PDF_PATH_PART2), f"PDF not found: {PDF_PATH_PART2}"


def test_pdf_paths_are_absolute():
    from src.textbook.constants import PDF_PATH_PART1, PDF_PATH_PART2
    assert Path(PDF_PATH_PART1).is_absolute()
    assert Path(PDF_PATH_PART2).is_absolute()


def test_content_page_range_part1():
    from src.textbook.constants import CONTENT_PAGE_RANGE_PART1
    assert CONTENT_PAGE_RANGE_PART1 == (4, 177)


def test_content_page_range_part2():
    from src.textbook.constants import CONTENT_PAGE_RANGE_PART2
    assert CONTENT_PAGE_RANGE_PART2 == (4, 144)


def test_toc_page_range_part1():
    from src.textbook.constants import TOC_PAGE_RANGE_PART1
    assert TOC_PAGE_RANGE_PART1 == (173, 175)


def test_toc_page_range_part2():
    from src.textbook.constants import TOC_PAGE_RANGE_PART2
    assert TOC_PAGE_RANGE_PART2 == (142, 143)


def test_data_dir():
    from src.textbook.constants import DATA_DIR
    assert os.path.isabs(DATA_DIR)
    assert DATA_DIR.endswith('data/textbook')


def test_textbook_json_path():
    from src.textbook.constants import TEXTBOOK_JSON
    assert TEXTBOOK_JSON.endswith('textbook.json')
    assert os.path.isabs(TEXTBOOK_JSON)


def test_min_content_chars():
    from src.textbook.constants import MIN_CONTENT_CHARS
    assert MIN_CONTENT_CHARS == 30
