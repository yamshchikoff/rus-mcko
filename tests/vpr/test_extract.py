"""Tests for src.vpr.extract."""

import json
import os
import pytest
from src.vpr.constants import VARIANTS_JSON


def test_variants_json_exists():
    assert os.path.exists(VARIANTS_JSON), f"Variants JSON not found: {VARIANTS_JSON}"


def test_variants_json_is_valid():
    with open(VARIANTS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    assert isinstance(data, dict)


def test_variants_json_has_top_level_keys():
    with open(VARIANTS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for key in ('meta', 'constructor', 'variants'):
        assert key in data, f"Missing top-level key: {key}"


def test_meta_has_required_fields():
    with open(VARIANTS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    meta = data['meta']
    assert meta['subject'] == 'Русский язык'
    assert meta['grade'] == 7
    assert meta['type'] == 'ВПР'
    assert 'year' in meta
    assert meta['total_variants'] == 15
    assert meta['tasks_per_variant'] == 7


def test_variants_count():
    with open(VARIANTS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    assert len(data['variants']) == 15


def test_variants_numbered_1_to_15():
    with open(VARIANTS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    nums = [v['num'] for v in data['variants']]
    assert nums == list(range(1, 16)), f"Expected 1..15, got {nums}"


def test_each_variant_has_test_id():
    with open(VARIANTS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for v in data['variants']:
        assert 'test_id' in v
        assert isinstance(v['test_id'], int)
        assert v['test_id'] > 0


def test_each_variant_has_7_tasks():
    with open(VARIANTS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for v in data['variants']:
        assert len(v['tasks']) == 7, f"Variant {v['num']} has {len(v['tasks'])} tasks"


def test_tasks_have_required_fields():
    with open(VARIANTS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for v in data['variants']:
        for task in v['tasks']:
            assert 'issue' in task
            assert 'problem_id' in task
            assert 'category' in task
            assert 'content_html' in task
            assert 'solution_html' in task
            assert 'criteria_html' in task
            assert isinstance(task['issue'], int)
            assert 1 <= task['issue'] <= 7
            assert isinstance(task['problem_id'], int)
            assert task['problem_id'] > 0
            assert isinstance(task['content_html'], str)
            assert len(task['content_html']) > 0


def test_tasks_1_to_4_have_text():
    with open(VARIANTS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for v in data['variants']:
        for task in v['tasks']:
            if task['issue'] in (1, 2, 3, 4):
                assert 'text_html' in task, (
                    f"Variant {v['num']} task {task['issue']} missing text_html"
                )
                assert len(task['text_html']) > 0


def test_tasks_1_and_4_share_same_text():
    with open(VARIANTS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for v in data['variants']:
        t1 = [t for t in v['tasks'] if t['issue'] == 1]
        t4 = [t for t in v['tasks'] if t['issue'] == 4]
        if t1 and t4:
            text1 = t1[0].get('text_html', '')
            text4 = t4[0].get('text_html', '')
            if text1 and text4:
                assert text1 == text4, (
                    f"Variant {v['num']}: tasks 1 and 4 should share same text"
                )


def test_constructor_has_7_categories():
    with open(VARIANTS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    constructor = data['constructor']
    assert len(constructor) >= 7
    titles = [c['title'] for c in constructor]
    assert 'Осложненное списывание' in titles


def test_no_duplicate_variant_nums():
    with open(VARIANTS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    nums = [v['num'] for v in data['variants']]
    assert len(nums) == len(set(nums))


def test_all_solution_html_non_empty():
    with open(VARIANTS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    empty_solutions = []
    for v in data['variants']:
        for task in v['tasks']:
            if not task['solution_html'].strip():
                empty_solutions.append(f"V{v['num']}T{task['issue']}")
    assert len(empty_solutions) == 0, f"Empty solutions: {empty_solutions}"


def test_all_criteria_html_non_empty():
    with open(VARIANTS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    empty_criteria = []
    for v in data['variants']:
        for task in v['tasks']:
            if not task['criteria_html'].strip():
                empty_criteria.append(f"V{v['num']}T{task['issue']}")
    assert len(empty_criteria) == 0, f"Empty criteria: {empty_criteria}"
