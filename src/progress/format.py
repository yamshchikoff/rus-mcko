"""Format student progress data as an LLM-readable summary.

The output is a self-contained markdown document describing the student's
real learning status, observed through their completed training works.
Designed for consumption by an AI tutor (deepseek-v4-pro) operating on the
«Алмазный фундамент» pattern — the textbook is the authoritative source,
the progress matrix tells the model where the student currently stands.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from src.vpr.constants import VARIANTS_JSON


def load_variants(path: str = VARIANTS_JSON) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_progress(path: str) -> dict:
    """Load progress JSON exported from the frontend (localStorage dump)."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_topics(variants: dict) -> List[dict]:
    """Extract topic list from variants data: [{issue, title}, ...]."""
    return [
        {'issue': c['issue'], 'title': c['title']}
        for c in variants['constructor']
    ]


def fmt_dt(iso: str) -> str:
    """Format ISO datetime to human-readable form."""
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime('%d.%m.%Y %H:%M')
    except (ValueError, TypeError):
        return iso


def format_progress(
    progress: dict,
    variants: Optional[dict] = None,
    answers: Optional[dict] = None,
) -> str:
    """Produce an LLM-optimised markdown summary of student progress.

    Args:
        progress: dict like {"1": {"completed": "ISO", "scores": {"1": 0, ...}}, ...}
        variants: loaded variants.json (loaded from VARIANTS_JSON if None)
        answers: dict like {"1-1": "answer text", ...} or None

    Returns:
        Markdown string.
    """
    if variants is None:
        variants = load_variants()

    meta = variants['meta']
    topics = get_topics(variants)
    total_variants = meta['total_variants']
    tasks_per_variant = meta['tasks_per_variant']
    total_tasks = total_variants * tasks_per_variant

    completed_variants = {int(k): v for k, v in progress.items()}
    completed_nums = sorted(completed_variants.keys())

    lines: List[str] = []

    # ── Header ──────────────────────────────────────────────────────
    lines.append(
        f"# Прогресс ученика — ВПР {meta['subject']} {meta['grade']} класс"
    )
    lines.append('')
    lines.append(
        'Это **реальный статус обучения ученика**, наблюдаемый через решаемые '
        'им тренировочные работы. Данные собраны с тренажёра ВПР. '
        'Ниже — матрица завершённости: какие варианты пройдены, '
        'с каким баллом по каждой теме, когда. '
        'Баллы на данный момент — стаб-заглушка '
        '(пустой ответ → младший балл, непустой → следующий за младшим), '
        'проверка ответов ИИ-репетитором пока не подключена.'
    )
    lines.append('')

    # ── Summary ─────────────────────────────────────────────────────
    lines.append('## Сводка')
    lines.append('')
    n_completed = len(completed_variants)
    n_tasks_done = n_completed * tasks_per_variant
    lines.append(f'- Завершено вариантов: **{n_completed}** из {total_variants}')
    lines.append(f'- Пройдено заданий: **{n_tasks_done}** из {total_tasks}')
    total_score = sum(
        sum(v.get('scores', {}).values())
        for v in completed_variants.values()
    )
    lines.append(f'- Суммарный балл (стаб): **{total_score}**')
    if completed_variants:
        last_dt = max(v['completed'] for v in completed_variants.values())
        lines.append(f'- Последняя активность: **{fmt_dt(last_dt)}**')
    else:
        lines.append('- Последняя активность: **нет данных**')
    lines.append('')

    # ── Topics legend ───────────────────────────────────────────────
    lines.append('## Темы заданий (К1–К{})'.format(tasks_per_variant))
    lines.append('')
    lines.append('| Код | Тема |')
    lines.append('|-----|------|')
    for t in topics:
        lines.append(f'| К{t["issue"]} | {t["title"]} |')
    lines.append('')

    # ── Progress matrix ─────────────────────────────────────────────
    lines.append('## Матрица прогресса')
    lines.append('')
    header = '| Вариант | ' + ' | '.join(
        f'К{t["issue"]}' for t in topics
    ) + ' | Завершён |'
    lines.append(header)
    sep = '|---------|' + '|'.join(['----' for _ in topics]) + '|----------|'
    lines.append(sep)

    for vnum in range(1, total_variants + 1):
        p = completed_variants.get(vnum)
        cells = [str(vnum)]
        for t in topics:
            if p and str(t['issue']) in p.get('scores', {}):
                cells.append(str(p['scores'][str(t['issue'])]))
            else:
                cells.append('—')
        cells.append(fmt_dt(p['completed']) if p else '—')
        lines.append('| ' + ' | '.join(cells) + ' |')
    lines.append('')

    # ── Detail per completed variant ────────────────────────────────
    if completed_variants:
        lines.append('## Детали по завершённым вариантам')
        lines.append('')
        for vnum in completed_nums:
            v = completed_variants[vnum]
            lines.append(f'### Вариант {vnum} — завершён {fmt_dt(v["completed"])}')
            lines.append('')
            scores = v.get('scores', {})
            for t in topics:
                issue_str = str(t['issue'])
                sc = scores.get(issue_str, '—')
                lines.append(f'- **К{t["issue"]}** {t["title"]}: балл **{sc}**')
                # Include answer text if available
                if answers:
                    ans_key = f'{vnum}-{t["issue"]}'
                    ans = answers.get(ans_key, '')
                    if ans and ans.strip():
                        lines.append(f'  > Ответ: «{ans}»')
            lines.append('')

    # ── Weak areas ──────────────────────────────────────────────────
    if completed_variants:
        lines.append('## Темы, требующие внимания')
        lines.append('')
        # Per-topic: count how many times score was the minimum possible
        topic_zeros: Dict[int, int] = {}
        topic_total: Dict[int, int] = {}
        for v in completed_variants.values():
            scores = v.get('scores', {})
            for t in topics:
                iss = t['issue']
                iss_str = str(iss)
                topic_total[iss] = topic_total.get(iss, 0) + 1
                if scores.get(iss_str, 1) == 0:
                    topic_zeros[iss] = topic_zeros.get(iss, 0) + 1

        if topic_zeros:
            lines.append('Темы, по которым ученик получил 0 баллов:')
            lines.append('')
            for t in topics:
                iss = t['issue']
                zeros = topic_zeros.get(iss, 0)
                total = topic_total.get(iss, 0)
                if total > 0 and zeros > 0:
                    lines.append(
                        f'- **К{iss}** {t["title"]}: '
                        f'{zeros} из {total} попыток с нулевым баллом'
                    )
            lines.append('')
        else:
            lines.append('Все пройденные задания имеют ненулевой балл.')
            lines.append('')

    # ── Interpretation guide for LLM ────────────────────────────────
    lines.append('## Интерпретация для ИИ-репетитора')
    lines.append('')
    lines.append(
        'Это срез прогресса ученика на основе **наблюдаемого поведения** '
        '(решаемые варианты ВПР). Данные отражают реальную картину тренировки. '
        'Баллы — стаб-заглушка: 0 за пустой ответ, 1 за непустой; '
        'содержательная проверка ответов будет подключена позже. '
        'Используй эту матрицу, чтобы понять:'
    )
    lines.append('')
    lines.append(
        '1. Какие темы ученик уже тренировал (ячейки с числом) '
        'а какие ещё нет (прочерк).'
    )
    lines.append(
        '2. По каким темам баллы низкие — возможно, нужен разбор '
        'соответствующих параграфов учебника.'
    )
    lines.append(
        '3. Какова интенсивность занятий: даты завершённых вариантов '
        'показывают частоту и регулярность тренировок.'
    )
    lines.append(
        '4. Какие варианты ученик начал но не завершил (есть ответы '
        'в localStorage но нет записи о завершении).'
    )
    lines.append('')

    return '\n'.join(lines)


def progress_as_context(
    progress: dict,
    variants: Optional[dict] = None,
    answers: Optional[dict] = None,
) -> str:
    """Return a compact one-liner + progress matrix suitable for injection
    into the LLM system prompt alongside the textbook.

    More concise than format_progress() — designed for context windows.
    """
    if variants is None:
        variants = load_variants()

    topics = get_topics(variants)
    completed_variants = {int(k): v for k, v in progress.items()}
    completed_nums = sorted(completed_variants.keys())

    lines = []
    lines.append(
        'Прогресс ученика (ВПР Русский язык 7 класс): '
        f'завершено {len(completed_variants)} из {variants["meta"]["total_variants"]} вариантов.'
    )

    if completed_variants:
        # Matrix
        header = 'Вариант ' + ' '.join(f'К{t["issue"]}' for t in topics) + ' Завершён'
        lines.append(header)
        for vnum in completed_nums:
            v = completed_variants[vnum]
            scores = v.get('scores', {})
            cells = [str(vnum)]
            for t in topics:
                cells.append(str(scores.get(str(t['issue']), '—')))
            cells.append(fmt_dt(v['completed']))
            lines.append(' '.join(cells))

    return '\n'.join(lines)
