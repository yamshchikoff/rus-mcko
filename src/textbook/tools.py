"""Runtime tools for LLM function calling: show_toc() and get_page(part, page)."""

import json

from src.textbook.constants import TEXTBOOK_JSON

_data = None


def _load() -> dict:
    global _data
    if _data is None:
        with open(TEXTBOOK_JSON, 'r', encoding='utf-8') as f:
            _data = json.load(f)
    return _data


def show_toc() -> str:
    """Return formatted table of contents with PDF page numbers.

    Sections are in [brackets], subsections are indented, topics
    include § numbers and PDF page references.
    """
    data = _load()
    lines = []
    for entry in data['toc']:
        _format_entry(entry, lines, indent=0)
    return '\n'.join(lines)


def _format_entry(entry: dict, lines: list[str], indent: int) -> None:
    prefix = '  ' * indent
    if entry['type'] == 'section':
        lines.append(f'{prefix}[{entry["title"]}]')
    elif entry['type'] == 'subsection':
        lines.append(f'{prefix}{entry["title"]}')
    elif entry['type'] == 'topic':
        num = entry.get('number') or ''
        page = entry.get('pdf_page', '?')
        lines.append(f'{prefix}{num} {entry["title"]} — стр. {page}')
    if 'entries' in entry:
        for child in entry['entries']:
            _format_entry(child, lines, indent + 1)


def get_page(part: int, page: int) -> str:
    """Return raw text of a PDF page.

    Args:
        part: 1 or 2
        page: PDF page number (from show_toc output)

    Raises:
        ValueError: if part is not 1 or 2, or page not found
    """
    if part not in (1, 2):
        raise ValueError(f'part must be 1 or 2, got {part}')

    data = _load()
    for p in data['pages']:
        if p['part'] == part and p['pdf_page'] == page:
            return p['text']

    raise ValueError(f'Page not found: part={part}, page={page}')
