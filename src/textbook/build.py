"""Build textbook.json from PDF sources."""

import json
import os
import sys

from src.textbook._page_extractor import extract_all_pages
from src.textbook._toc_parser import parse_toc
from src.textbook.constants import (
    PDF_PATH_PART1, PDF_PATH_PART2,
    CONTENT_PAGE_RANGE_PART1, CONTENT_PAGE_RANGE_PART2,
    TOC_PAGE_RANGE_PART1, TOC_PAGE_RANGE_PART2,
    DATA_DIR, TEXTBOOK_JSON,
)


def build(force: bool = False) -> str:
    if os.path.exists(TEXTBOOK_JSON) and not force:
        return TEXTBOOK_JSON

    pages_part1 = extract_all_pages(PDF_PATH_PART1)
    pages_part2 = extract_all_pages(PDF_PATH_PART2)

    content_pages = _collect_content_pages(pages_part1, 1, CONTENT_PAGE_RANGE_PART1)
    content_pages += _collect_content_pages(pages_part2, 2, CONTENT_PAGE_RANGE_PART2)

    toc_text_1 = _prepare_toc_text('\n'.join(
        pages_part1[TOC_PAGE_RANGE_PART1[0] - 1 : TOC_PAGE_RANGE_PART1[1]]
    ))
    toc_text_2 = _prepare_toc_text('\n'.join(
        pages_part2[TOC_PAGE_RANGE_PART2[0] - 1 : TOC_PAGE_RANGE_PART2[1]]
    ))
    all_toc = parse_toc(toc_text_1, part=1) + parse_toc(toc_text_2, part=2)

    data = {
        'meta': {
            'title': 'Русский язык. 7 класс',
            'authors': 'М.Т. Баранов, Т.А. Ладыженская и др.',
            'year': 2022,
            'publisher': 'Просвещение',
        },
        'toc': all_toc,
        'pages': content_pages,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(TEXTBOOK_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return TEXTBOOK_JSON


def _collect_content_pages(pages: list[str], part: int, page_range: tuple[int, int]) -> list[dict]:
    start, end = page_range
    result = []
    for i in range(start - 1, end):
        result.append({
            'part': part,
            'pdf_page': i + 1,
            'printed_page': i,
            'text': pages[i],
        })
    return result


def _prepare_toc_text(text: str) -> str:
    """Strip content before the СОДЕРЖАНИЕ marker."""
    idx = text.find('СОДЕРЖАНИЕ')
    if idx != -1:
        return text[idx:]
    return text


if __name__ == '__main__':
    force = '--force' in sys.argv
    path = build(force=force)
    print(f'Built: {path}')
