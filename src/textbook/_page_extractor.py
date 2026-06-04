"""PDF text extraction via pdftotext."""

import os
import subprocess


def _check_pdftotext() -> None:
    """Verify pdftotext is available."""
    try:
        subprocess.run(
            ['pdftotext', '-v'],
            capture_output=True,
            timeout=5,
        )
    except FileNotFoundError:
        raise RuntimeError(
            'pdftotext is not installed. '
            'Install poppler-utils: apt install poppler-utils'
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError('pdftotext check timed out')


def extract_all_pages(pdf_path: str) -> list[str]:
    """Extract all pages from a PDF file as a list of strings.

    Uses pdftotext to extract text, then splits on form-feed characters.
    Each element corresponds to one PDF page (1-indexed: index 0 = page 1).
    """
    _check_pdftotext()

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    result = subprocess.run(
        ['pdftotext', '-layout', pdf_path, '-'],
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f'pdftotext failed with code {result.returncode}: {result.stderr}'
        )

    text = result.stdout
    pages = text.split('\x0c')
    pages = [p.rstrip() for p in pages]

    while pages and len(pages[-1].strip()) == 0:
        pages.pop()

    return pages
