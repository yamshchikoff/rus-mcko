"""Parse table of contents text into hierarchical structure."""

import re


def parse_toc(text: str, part: int) -> list[dict]:
    """Parse raw TOC text into a hierarchical list of entries.

    Returns a list where each element is a dict with:
      - type: 'section', 'subsection', or 'topic'
      - title: str
      - entries: list of child entries (for section/subsection)
      - pdf_page: int (for topic only)
      - part: int (for topic only)
      - number: str or None (for topic only, e.g. '§ 12')
    """
    if not text.strip():
        raise ValueError('TOC text is empty')

    lines = text.split('\n')
    entries = []
    current_section = entries
    current_subsection = None

    pending_topic_lines = []
    in_topic = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if 'СОДЕРЖАНИЕ' in stripped:
            continue
        if re.match(r'^\d{1,3}$', stripped):
            continue

        # Check if we're in a topic and this line completes it
        if in_topic:
            page_num = _extract_trailing_page(stripped)
            if page_num is not None:
                # Topic complete
                full_title = ' '.join(pending_topic_lines + [stripped])
                full_title = _strip_page_number(full_title)
                full_title = _clean_title(full_title)
                topic = _make_topic(full_title, page_num, part)
                current_subsection.append(topic) if current_subsection is not None else current_section.append(topic)
                pending_topic_lines = []
                in_topic = False
                continue
            elif _is_new_entry_start(stripped):
                # If pending topic starts with §, treat as continuation
                if pending_topic_lines and re.match(r'^§', pending_topic_lines[0]):
                    pending_topic_lines.append(stripped)
                    continue
                # Otherwise flush topic without page number and fall through
                full_title = ' '.join(pending_topic_lines)
                full_title = _clean_title(full_title)
                topic = _make_topic(full_title, None, part)
                current_subsection.append(topic) if current_subsection is not None else current_section.append(topic)
                pending_topic_lines = []
                in_topic = False
                # Fall through to process this line normally
            else:
                pending_topic_lines.append(stripped)
                continue

        # Not in topic — classify the line
        if _is_section_header(stripped):
            section = {'type': 'section', 'title': stripped, 'entries': []}
            current_section.append(section)
            current_subsection = section['entries']
            continue

        if _is_subsection_header(stripped):
            subsection = {'type': 'subsection', 'title': stripped, 'entries': []}
            current_section.append(subsection)
            current_subsection = subsection['entries']
            continue

        if _is_topic_start(stripped):
            page_num = _extract_trailing_page(stripped)
            if page_num is not None:
                title = _strip_page_number(stripped)
                title = _clean_title(title)
                topic = _make_topic(title, page_num, part)
                current_subsection.append(topic) if current_subsection is not None else current_section.append(topic)
            else:
                pending_topic_lines = [stripped]
                in_topic = True
            continue

        # Catch topic-like lines without § or Повторение marker
        page_num = _extract_trailing_page(stripped)
        if page_num is not None:
            title = _strip_page_number(stripped)
            title = _clean_title(title)
            topic = _make_topic(title, page_num, part)
            current_subsection.append(topic) if current_subsection is not None else current_section.append(topic)
            continue

    return entries


def _is_section_header(line: str) -> bool:
    """ALL CAPS line with no § marker and no trailing page number."""
    if re.match(r'^§', line):
        return False
    stripped_upper = line.upper()
    if stripped_upper != line:
        return False
    # Must not have a trailing page number
    if _extract_trailing_page(line) is not None:
        return False
    # Must contain Cyrillic
    if not re.search(r'[А-ЯЁ]', line):
        return False
    return True


def _is_subsection_header(line: str) -> bool:
    """Title Case (not ALL CAPS) line that names a grammar topic area."""
    if re.match(r'^§', line):
        return False
    if line.upper() == line:
        return False
    if _extract_trailing_page(line) is not None:
        return False
    if not re.search(r'[А-ЯЁ]', line):
        return False
    # First char must be uppercase Cyrillic and it's NOT a topic start
    if not re.match(r'^[А-ЯЁ]', line):
        return False
    if re.match(r'^Повторение', line):
        return False
    return True


def _is_topic_start(line: str) -> bool:
    """Line starts a topic: § marker, Повторение, or ALL CAPS with page number."""
    if re.match(r'^§\s*\d+\.', line):
        return True
    if re.match(r'^Повторение', line):
        return True
    return False


def _is_new_entry_start(line: str) -> bool:
    return _is_section_header(line) or _is_subsection_header(line) or _is_topic_start(line)


def _extract_trailing_page(line: str) -> int | None:
    """Extract the trailing page number from a line, if present."""
    m = re.search(r'(\d{1,3})\s*$', line)
    if m:
        num = int(m.group(1))
        if 1 <= num <= 200:
            return num
    return None


def _strip_page_number(line: str) -> str:
    """Remove trailing page number and leader dots from a line."""
    line = re.sub(r'[\s.]*\d{1,3}\s*$', '', line)
    return line.rstrip('.').rstrip()


def _clean_title(title: str) -> str:
    """Clean up a topic title: collapse spaces, remove stray artifacts."""
    title = re.sub(r'\s+', ' ', title)
    return title.strip()


def _make_topic(title: str, printed_page: int | None, part: int) -> dict:
    """Create a topic entry dict."""
    number = None
    m = re.match(r'(§\s*\d+)\.?\s*', title)
    if m:
        number = m.group(1)
        title = title[m.end():].strip()

    if printed_page is not None:
        pdf_page = printed_page + 1
    else:
        pdf_page = None

    result = {
        'type': 'topic',
        'title': title,
        'part': part,
        'pdf_page': pdf_page,
        'number': number,
    }
    return result
