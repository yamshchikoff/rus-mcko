"""Tests for src.progress.format."""

import json
import pytest
from src.progress.format import (
    format_progress,
    progress_as_context,
    load_variants,
    get_topics,
    fmt_dt,
)


@pytest.fixture
def variants():
    return load_variants()


@pytest.fixture
def empty_progress():
    return {}


@pytest.fixture
def sample_progress():
    return {
        "1": {
            "completed": "2026-06-04T15:30:00",
            "scores": {"1": 0, "2": 1, "3": 0, "4": 1, "5": 0, "6": 1, "7": 0},
        },
        "3": {
            "completed": "2026-06-03T12:00:00",
            "scores": {"1": 1, "2": 1, "3": 0, "4": 0, "5": 1, "6": 0, "7": 1},
        },
    }


@pytest.fixture
def sample_answers():
    return {
        "1-1": "Толя смотрел в озеро...",
        "1-2": "",
        "3-1": "Ответ на задание 1 варианта 3",
    }


class TestLoadVariants:
    def test_returns_dict_with_variants(self, variants):
        assert isinstance(variants, dict)
        assert 'variants' in variants
        assert len(variants['variants']) == 15

    def test_meta_fields(self, variants):
        meta = variants['meta']
        assert meta['subject'] == 'Русский язык'
        assert meta['grade'] == 7
        assert meta['total_variants'] == 15
        assert meta['tasks_per_variant'] == 7


class TestGetTopics:
    def test_returns_7_topics(self, variants):
        topics = get_topics(variants)
        assert len(topics) == 7

    def test_each_topic_has_issue_and_title(self, variants):
        topics = get_topics(variants)
        for t in topics:
            assert 'issue' in t
            assert 'title' in t
            assert isinstance(t['issue'], int)
            assert 1 <= t['issue'] <= 7
            assert len(t['title']) > 0

    def test_first_topic_is_spisivanie(self, variants):
        topics = get_topics(variants)
        assert 'списывание' in topics[0]['title'].lower()


class TestFmtDt:
    def test_formats_iso(self):
        assert fmt_dt('2026-06-04T15:30:00') == '04.06.2026 15:30'

    def test_handles_z_suffix(self):
        result = fmt_dt('2026-06-04T15:30:00+00:00')
        assert '04.06.2026' in result


class TestFormatProgress:
    def test_empty_progress(self, empty_progress, variants):
        output = format_progress(empty_progress, variants)
        assert '0' in output  # 0 completed
        assert 'нет данных' in output.lower() or '0 из 15' in output

    def test_sample_progress_structure(self, sample_progress, variants):
        output = format_progress(sample_progress, variants)
        # Sections present
        assert '# Прогресс ученика' in output
        assert '## Сводка' in output
        assert '## Темы заданий' in output
        assert '## Матрица прогресса' in output
        assert '## Детали по завершённым вариантам' in output
        assert '## Темы, требующие внимания' in output
        assert '## Интерпретация для ИИ-репетитора' in output

    def test_sample_progress_counts(self, sample_progress, variants):
        output = format_progress(sample_progress, variants)
        assert '**2** из 15' in output  # completed variants
        assert '**14** из 105' in output  # completed tasks (2 × 7)

    def test_sample_progress_dates(self, sample_progress, variants):
        output = format_progress(sample_progress, variants)
        assert '04.06.2026 15:30' in output
        assert '03.06.2026 12:00' in output

    def test_sample_progress_topics(self, sample_progress, variants):
        output = format_progress(sample_progress, variants)
        # Topic names from constructor appear
        assert 'Осложненное списывание' in output
        assert 'Морфологический разбор' in output

    def test_sample_progress_weak_areas(self, sample_progress, variants):
        output = format_progress(sample_progress, variants)
        # Variant 1 has many zeros and should be flagged
        assert '0 баллов' in output or 'нулевым баллом' in output

    def test_with_answers(self, sample_progress, variants, sample_answers):
        output = format_progress(sample_progress, variants, sample_answers)
        # Answer text from variant 1, task 1
        assert 'Толя смотрел в озеро' in output

    def test_llm_context_preamble(self, sample_progress, variants):
        output = format_progress(sample_progress, variants)
        assert 'реальный статус обучения' in output.lower()
        assert 'наблюдаемый через решаемые' in output.lower()

    def test_interpretation_section(self, sample_progress, variants):
        output = format_progress(sample_progress, variants)
        assert 'наблюдаемого поведения' in output.lower()
        assert 'стаб-заглушка' in output.lower()


class TestProgressAsContext:
    def test_compact_output(self, sample_progress, variants):
        output = progress_as_context(sample_progress, variants)
        assert 'завершено 2 из 15' in output
        assert 'К1' in output

    def test_empty_is_concise(self, empty_progress, variants):
        output = progress_as_context(empty_progress, variants)
        lines = output.strip().split('\n')
        assert len(lines) == 1  # single line summary
