"""RED: Tests for src.textbook.build."""

import json
import os
import pytest
from src.textbook.constants import TEXTBOOK_JSON, CONTENT_PAGE_RANGE_PART1, CONTENT_PAGE_RANGE_PART2


def test_build_creates_json_file():
    from src.textbook.build import build
    build()
    assert os.path.exists(TEXTBOOK_JSON)


def test_build_json_is_valid():
    from src.textbook.build import build
    build()
    with open(TEXTBOOK_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    assert isinstance(data, dict)


def test_build_json_has_top_level_keys():
    from src.textbook.build import build
    build()
    with open(TEXTBOOK_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for key in ('meta', 'toc', 'pages'):
        assert key in data, f"Missing top-level key: {key}"


def test_build_meta_has_required_fields():
    from src.textbook.build import build
    build()
    with open(TEXTBOOK_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    meta = data['meta']
    assert 'title' in meta
    assert 'authors' in meta
    assert 'year' in meta
    assert 'publisher' in meta


def test_build_pages_count():
    from src.textbook.build import build
    build()
    with open(TEXTBOOK_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    pages = data['pages']
    expected_count = (
        (CONTENT_PAGE_RANGE_PART1[1] - CONTENT_PAGE_RANGE_PART1[0] + 1)
        + (CONTENT_PAGE_RANGE_PART2[1] - CONTENT_PAGE_RANGE_PART2[0] + 1)
    )
    assert len(pages) == expected_count


def test_build_pages_have_required_fields():
    from src.textbook.build import build
    build()
    with open(TEXTBOOK_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for page in data['pages']:
        assert 'part' in page
        assert 'pdf_page' in page
        assert 'printed_page' in page
        assert 'text' in page
        assert isinstance(page['text'], str)
        assert len(page['text']) > 0
        assert page['part'] in (1, 2)


def test_build_pages_pdf_page_matches_index():
    from src.textbook.build import build
    build()
    with open(TEXTBOOK_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # PDF pages should match CONTENT_PAGE_RANGE ranges
    part1_pages = [p for p in data['pages'] if p['part'] == 1]
    part2_pages = [p for p in data['pages'] if p['part'] == 2]
    assert part1_pages[0]['pdf_page'] == CONTENT_PAGE_RANGE_PART1[0]
    assert part1_pages[-1]['pdf_page'] == CONTENT_PAGE_RANGE_PART1[1]
    assert part2_pages[0]['pdf_page'] == CONTENT_PAGE_RANGE_PART2[0]
    assert part2_pages[-1]['pdf_page'] == CONTENT_PAGE_RANGE_PART2[1]


def test_build_toc_non_empty():
    from src.textbook.build import build
    build()
    with open(TEXTBOOK_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    assert len(data['toc']) > 0


def test_build_toc_topics_have_valid_pages():
    from src.textbook.build import build
    build()
    with open(TEXTBOOK_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    topics = _flatten_toc(data['toc'])
    valid_pages = {(p['part'], p['pdf_page']) for p in data['pages']}
    for topic in topics:
        if topic['type'] == 'topic' and topic.get('pdf_page') is not None:
            key = (topic['part'], topic['pdf_page'])
            assert key in valid_pages, f"TOC topic '{topic['title']}' references missing page {key}"


def test_build_second_run_idempotent():
    from src.textbook.build import build
    build()  # first run
    mtime_before = os.path.getmtime(TEXTBOOK_JSON)
    build()  # second run
    mtime_after = os.path.getmtime(TEXTBOOK_JSON)
    assert mtime_after == mtime_before, "Second run should not rewrite file"


def _flatten_toc(entries):
    result = []
    for e in entries:
        result.append(e)
        if 'entries' in e:
            result.extend(_flatten_toc(e['entries']))
    return result
