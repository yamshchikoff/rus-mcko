"""Tests for src.tutor.system_prompt."""

import pytest
from src.tutor.system_prompt import get_system_prompt


class TestGetSystemPrompt:
    """Core identity and rules."""

    def test_contains_tutor_identity(self):
        prompt = get_system_prompt()
        assert 'репетитор' in prompt.lower()
        assert 'русск' in prompt.lower()

    def test_contains_target_audience(self):
        prompt = get_system_prompt()
        assert '7 класс' in prompt or 'седьм' in prompt.lower()
        assert '13' in prompt and '14' in prompt

    def test_contains_anti_provocation_rule(self):
        prompt = get_system_prompt()
        assert 'провокац' in prompt.lower()
        assert 'мягко' in prompt.lower() and 'профессионально' in prompt.lower()

    def test_contains_textbook_reference(self):
        prompt = get_system_prompt()
        assert 'учебник' in prompt.lower()
        assert 'Баранов' in prompt or 'Ладыженская' in prompt

    def test_contains_tool_references(self):
        prompt = get_system_prompt()
        assert 'show_toc' in prompt
        assert 'get_page' in prompt

    def test_contains_vpr_context(self):
        prompt = get_system_prompt()
        assert 'ВПР' in prompt


class TestContextInjection:
    """Progress and task context is injected into the prompt."""

    def test_progress_context_appears(self):
        progress = "Завершено вариантов: 3 из 15"
        prompt = get_system_prompt(progress_context=progress)
        assert progress in prompt

    def test_current_task_appears(self):
        task = "К1. Осложненное списывание"
        prompt = get_system_prompt(current_task=task)
        assert task in prompt

    def test_no_context_is_clean(self):
        prompt = get_system_prompt()
        assert 'None' not in prompt


class TestPromptLength:
    """Prompt size is bounded."""

    def test_base_prompt_under_limit(self):
        prompt = get_system_prompt()
        assert len(prompt) < 4000, f'Base prompt is {len(prompt)} chars'

    def test_with_large_context_still_reasonable(self):
        prompt = get_system_prompt(
            progress_context='x' * 5000,
            current_task='y' * 5000,
        )
        # Should not exceed base + injected contexts
        assert len(prompt) < 15000
