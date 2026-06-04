"""Constants for the textbook tools package."""

import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PDF_PATH_PART1 = os.path.join(ROOT_DIR, 'docs', 'textbook', 'rus7-2022-part1.pdf')
PDF_PATH_PART2 = os.path.join(ROOT_DIR, 'docs', 'textbook', 'rus7-2022-part2.pdf')

DATA_DIR = os.path.join(ROOT_DIR, 'data', 'textbook')
TEXTBOOK_JSON = os.path.join(DATA_DIR, 'textbook.json')

CONTENT_PAGE_RANGE_PART1 = (4, 177)
CONTENT_PAGE_RANGE_PART2 = (4, 144)

TOC_PAGE_RANGE_PART1 = (173, 175)
TOC_PAGE_RANGE_PART2 = (142, 143)

MIN_CONTENT_CHARS = 30
