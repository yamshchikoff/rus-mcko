"""Extract VPR variants from rus7-vpr.sdamgia.ru into a structured JSON file."""

import json
import os
import re
import sys
import time
import urllib.request
from urllib.error import URLError

from src.vpr.constants import BASE_URL, DATA_DIR, VARIANTS_JSON


def fetch_json(url: str) -> dict:
    """Fetch a URL and parse the response as JSON."""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode('utf-8'))


def fetch_html(url: str) -> str:
    """Fetch a URL and return the response as a string."""
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode('utf-8')


def extract_solution(html: str) -> str:
    """Extract solution HTML from a problem page."""
    m = re.search(
        r'<div[^>]*class="[^"]*solution[^"]*"[^>]*>(.*?)<!--rule_info-->',
        html, re.DOTALL,
    )
    if m:
        content = m.group(1).strip()
        if content:
            return content
    return ''


def extract_criteria(html: str) -> str:
    """Extract grading criteria HTML from a problem page."""
    m = re.search(
        r'<div[^>]*class="[^"]*prob_crits[^"]*"[^>]*>(.*?)</div>\s*</div>',
        html, re.DOTALL,
    )
    if m:
        content = m.group(1).strip()
        if content:
            return content
    return ''


def extract(force: bool = False) -> str:
    """Fetch all 15 VPR variants and save to variants.json.

    Returns the path to the generated JSON file.
    """
    if os.path.exists(VARIANTS_JSON) and not force:
        return VARIANTS_JSON

    print('Fetching general config...', file=sys.stderr)
    general = fetch_json(f'{BASE_URL}/newapi/general')

    variant_ids = general['ourVariants']
    constructor = general['constructor']
    subject = general['subject']

    category_by_index = {}
    for i, cat in enumerate(constructor):
        category_by_index[i] = cat['title']

    # Collect all unique problem IDs across all variants
    all_tasks = []
    seen_problem_ids = set()

    for idx, test_id in enumerate(variant_ids):
        num = idx + 1
        print(f'Fetching variant {num}/15 (test_id={test_id})...', file=sys.stderr)
        test_data = fetch_json(f'{BASE_URL}/newapi/test?id={test_id}')

        tasks = []
        for task_data in test_data['tasks']:
            problem_id = task_data['id']
            issue = int(task_data['issue'])
            task = {
                'issue': issue,
                'problem_id': problem_id,
                'category': category_by_index.get(issue - 1, ''),
                'content_html': task_data['content'],
                'text_html': task_data.get('text', ''),
                'solution_html': '',
                'criteria_html': '',
            }
            tasks.append(task)
            seen_problem_ids.add(problem_id)

        all_tasks.append({
            'num': num,
            'test_id': test_id,
            'tasks': tasks,
        })
        time.sleep(0.3)

    # Fetch solutions and criteria for each unique problem
    print(f'Fetching solutions for {len(seen_problem_ids)} unique problems...', file=sys.stderr)
    problem_data = {}
    for i, pid in enumerate(sorted(seen_problem_ids)):
        if (i + 1) % 20 == 0:
            print(f'  {i + 1}/{len(seen_problem_ids)} problems...', file=sys.stderr)
        try:
            html = fetch_html(f'{BASE_URL}/problem?id={pid}&ajax=1')
            problem_data[pid] = {
                'solution_html': extract_solution(html),
                'criteria_html': extract_criteria(html),
            }
        except URLError as e:
            print(f'  WARNING: Failed to fetch problem {pid}: {e}', file=sys.stderr)
            problem_data[pid] = {'solution_html': '', 'criteria_html': ''}
        time.sleep(0.2)

    # Attach solutions/criteria to tasks
    for variant in all_tasks:
        for task in variant['tasks']:
            pid = task['problem_id']
            if pid in problem_data:
                task['solution_html'] = problem_data[pid]['solution_html']
                task['criteria_html'] = problem_data[pid]['criteria_html']

    data = {
        'meta': {
            'subject': 'Русский язык',
            'grade': 7,
            'year': '2025-2026',
            'type': 'ВПР',
            'total_variants': len(all_tasks),
            'tasks_per_variant': subject['c_num'],
        },
        'constructor': [
            {'title': c['title'], 'issue': i + 1}
            for i, c in enumerate(constructor[:subject['c_num']])
        ],
        'variants': all_tasks,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(VARIANTS_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f'Saved to {VARIANTS_JSON}', file=sys.stderr)
    return VARIANTS_JSON


if __name__ == '__main__':
    force = '--force' in sys.argv
    path = extract(force=force)
    print(f'Done: {path}')
