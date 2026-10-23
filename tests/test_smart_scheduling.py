"""Behavioral regressions for chunking, evening bounds and soft preferences."""
from copy import deepcopy
from datetime import datetime
import pytest
from server.engine.scheduler import compute_day_schedule, compute_replan
from server.providers.deterministic import _interruption

NOW = '2026-10-22T09:00:00+05:30'


def stamp(clock):
    return f'2026-10-22T{clock}:00+05:30'


def event(start, end, **extra):
    return dict(title='Fixed', start_time=stamp(start), end_time=stamp(end), immutable=True, **extra)


def task(minutes=120, **extra):
    return dict(id='task', title='Deep work', duration_minutes=minutes, priority='HIGH', category='work', **extra)


def durations(blocks):
    return [(datetime.fromisoformat(b['end_time']) - datetime.fromisoformat(b['start_time'])).total_seconds() / 60
            for b in blocks if b.get('task_id') == 'task']


def test_split_fills_primary_gaps_before_evening():
    busy = [event('10:00', '11:00'), event('12:00', '17:00')]
    before = deepcopy(busy)
    result = compute_day_schedule([task()], busy, NOW)
    assert durations(result) == [60, 60]
    assert busy == before
    assert [b['start_time'][11:16] for b in result if b.get('task_id')] == ['09:00', '11:00']


def test_contiguous_slot_wins_over_earlier_fragments():
    result = compute_day_schedule([task()], [event('10:00', '11:00')], NOW)
    assert durations(result) == [120]
    assert next(b for b in result if b.get('task_id'))['start_time'] == stamp('11:00')


@pytest.mark.parametrize('minutes,expected', [(61, [31, 30]), (75, [45, 30]), (90, [60, 30])])
def test_no_small_tail_chunk(minutes, expected):
    result = compute_day_schedule([task(minutes, deadline=stamp('12:00'))], [event('10:00', '11:00')], NOW)
    assert durations(result) == expected


def test_short_tasks_never_split():
    with pytest.raises(ValueError):
        compute_day_schedule([task(60, deadline=stamp('11:00'))], [event('09:30', '10:30')], NOW)


def test_overflow_uses_whole_evening_slot():
    result = compute_day_schedule([task(60)], [event('09:00', '16:30')], NOW)
    assert durations(result) == [60]
    assert next(b for b in result if b.get('task_id'))['end_time'] == stamp('17:30')


@pytest.mark.parametrize('deadline', [None, stamp('23:00')])
def test_maximum_bound_cannot_be_extended_by_deadline(deadline):
    with pytest.raises(ValueError, match='21:00'):
        compute_day_schedule([task(721, deadline=deadline)], [], NOW)


def test_explicit_deadline_blocks_overflow():
    with pytest.raises(ValueError):
        compute_day_schedule([task(60, deadline=stamp('17:00'))], [event('09:00', '16:30')], NOW)


def test_split_replan_retains_identity_once_and_duration():
    old = [dict(event('13:00', '15:00'), id='original', immutable=False, task_id='task'), event('16:00', '17:00')]
    result = compute_replan(old, event('14:00', '15:00'), NOW)
    assert durations(result) == [60, 60]
    assert sum(b.get('id') == 'original' for b in result) == 1
    assert [b['start_time'][11:16] for b in result if b.get('task_id')] == ['13:00', '15:00']


def test_replan_task_deadlines_from_saved_tasks():
    old = [dict(event('16:00', '17:00'), immutable=False, task_id='task')]
    with pytest.raises(ValueError):
        compute_replan(old, event('16:00', '17:00'), NOW, tasks=[task(60, deadline=stamp('17:00'))])
    result = compute_replan(old, event('16:00', '17:00'), NOW)
    assert next(b for b in result if b.get('task_id'))['end_time'] == stamp('18:00')


def test_preferences_are_soft_and_do_not_override_deadlines():
    preferences = [{'value': 'I prefer personal errands in the afternoon'}]
    personal = task(60, category_unused=True)
    personal['category'] = 'personal'
    result = compute_day_schedule([personal], [], NOW, preferences)
    assert result[0]['start_time'] == stamp('13:00')
    personal['deadline'] = stamp('12:00')
    assert compute_day_schedule([personal], [], NOW, preferences)[0]['start_time'] == stamp('09:00')
    preferences = [{'value': 'Keep after 4 PM for personal errands'}]
    personal['deadline'] = None
    assert compute_day_schedule([personal], [], NOW, preferences)[0]['start_time'] == stamp('16:00')


@pytest.mark.parametrize('utterance,title', [
    ('Replan around Client Demo from 2:00 to 2:45 PM', 'Client Demo'),
    ('Replan around Dentist at 2 PM for 30 minutes', 'Dentist'),
    ('Replan from 2:00 to 2:45 PM', 'Unexpected meeting'),
    ('My manager scheduled a 1-on-1 at 2 PM for 30 minutes', 'Manager 1-on-1'),
])
def test_interruption_titles(utterance, title):
    assert _interruption(utterance, datetime.fromisoformat(NOW))['title'] == title
