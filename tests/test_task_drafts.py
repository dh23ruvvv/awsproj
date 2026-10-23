"""Regression coverage for task reviews, concurrency and Gemini clarification."""
import asyncio
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from google.genai import types

from server.config import settings
from server.database import get_connection
from server.main import app
from server.providers.base import AgentContext, AgentTurnResult
from server.providers.gemini import GeminiProvider
from server.providers.fallback import FallbackProvider
from server.routers import agent
from server.tools.task_drafts import propose_task_changes


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Use isolated SQLite and a deterministic default without network calls."""
    monkeypatch.setattr(settings, 'flowpilot_db_path', str(tmp_path / 'task_drafts.db'))
    monkeypatch.setattr(settings, 'flowpilot_default_provider', 'deterministic')
    monkeypatch.setattr(agent, '_message_times', {})
    with TestClient(app) as client:
        res = client.post('/api/v1/sessions', json={'seed': True, 'demo_timestamp': '2026-10-22T09:00:00+05:30'})
        assert res.status_code == 201
        sid = res.json()['session_id']
        yield client, sid, f'/api/v1/sessions/{sid}'


def draft(sid, changes):
    """Persist an actual tool proposal independently of the HTTP confirm route."""
    db = get_connection()
    try:
        result = propose_task_changes(sid, {'explanation': 'Review task changes.', 'changes': changes}, db)
        db.commit()
        return result['task_draft_id']
    finally:
        db.close()


def addition():
    """A fully specified new task."""
    return {'action': 'add', 'title': 'Read paper', 'duration_minutes': 45, 'priority': 'HIGH', 'category': 'work'}


def test_task_draft_lifecycle_atomic_confirm_and_repeat_idempotency(workspace):
    """A three-operation review changes no task before approval and commits once."""
    client, sid, base = workspace
    assert client.get(base + '/task-drafts/pending').json() == {'draft': None}
    before = client.get(base + '/tasks').json()['tasks']
    grocery = next(t for t in before if t['title'] == 'Grocery shopping')
    gym = next(t for t in before if t['title'] == 'Gym session')
    did = draft(sid, [addition(), {'action': 'update', 'task_id': grocery['id'], 'title': 'Grocery & market', 'duration_minutes': 40, 'priority': 'LOW', 'category': 'personal'}, {'action': 'remove', 'task_id': gym['id']}])
    pending = client.get(base + '/task-drafts/pending').json()['draft']
    assert pending['id'] == did and pending['status'] == 'PROPOSED' and len(pending['changes']) == 3
    blocked = client.post(base + '/agent/message', json={'message': 'Plan my day', 'state_version': 1})
    assert blocked.status_code == 409 and blocked.json()['error']['code'] == 'REVIEW_PENDING'
    assert client.get(base + '/tasks').json()['tasks'] == before
    res = client.post(f'{base}/task-drafts/{did}/confirm', json={'state_version': 1})
    assert res.status_code == 200 and res.json() == {'state_version': 2, 'already_confirmed': False}
    after = client.get(base + '/tasks').json()
    titles = {t['title']: t for t in after['tasks']}
    assert titles['Read paper']['duration_minutes'] == 45
    assert titles['Grocery & market']['duration_minutes'] == 40 and 'Gym session' not in titles
    repeat = client.post(f'{base}/task-drafts/{did}/confirm', json={'state_version': 2})
    assert repeat.status_code == 200 and repeat.json() == {'state_version': 2, 'already_confirmed': True}
    assert client.get(base + '/tasks').json() == after
    assert client.get(base + '/task-drafts/pending').json() == {'draft': None}
    assert client.post(f'{base}/task-drafts/{did}/cancel').status_code == 409
    # A subsequent writer can acquire the database after repeat-confirm.
    db = get_connection()
    try:
        db.execute('BEGIN IMMEDIATE')
        db.rollback()
    finally:
        db.close()


def test_task_draft_partial_update_preserves_omitted_fields(workspace):
    """Omitted values survive both normalization passes; explicit null clears deadline."""
    client, sid, base = workspace
    deadline = '2026-10-22T15:00:00+05:30'
    res = client.post(base + '/tasks', json={'state_version': 1, 'title': 'Call accountant', 'duration_minutes': 20, 'priority': 'HIGH', 'category': 'personal', 'deadline': deadline})
    assert res.status_code == 201
    task_id = res.json()['task']['id']
    did = draft(sid, [{'action': 'update', 'task_id': task_id, 'duration_minutes': 35}])
    assert client.post(f'{base}/task-drafts/{did}/confirm', json={'state_version': 2}).status_code == 200
    updated = next(t for t in client.get(base + '/tasks').json()['tasks'] if t['id'] == task_id)
    assert (updated['title'], updated['duration_minutes'], updated['priority'], updated['category'], updated['deadline']) == ('Call accountant', 35, 'HIGH', 'personal', deadline)
    did = draft(sid, [{'action': 'update', 'task_id': task_id, 'deadline': None}])
    assert client.post(f'{base}/task-drafts/{did}/confirm', json={'state_version': 3}).status_code == 200
    updated = next(t for t in client.get(base + '/tasks').json()['tasks'] if t['id'] == task_id)
    assert updated['deadline'] is None and updated['duration_minutes'] == 35


def test_partial_null_fields_preserve_values_and_add_defaults(workspace):
    client, sid, base = workspace
    task = next(t for t in client.get(base + '/tasks').json()['tasks'] if t['title'] == 'Grocery shopping')
    did = draft(sid, [
        {'action': 'update', 'task_id': task['id'], 'duration_minutes': 45, 'title': None, 'priority': None, 'category': None},
        {'action': 'add', 'title': 'Read', 'duration_minutes': 30, 'priority': None, 'category': None},
    ])
    assert client.post(f'{base}/task-drafts/{did}/confirm', json={'state_version': 1}).status_code == 200
    tasks = client.get(base + '/tasks').json()['tasks']
    updated = next(t for t in tasks if t['id'] == task['id'])
    for field in ('title', 'priority', 'category', 'deadline'):
        assert updated[field] == task[field]
    assert updated['duration_minutes'] == 45
    added = next(t for t in tasks if t['title'] == 'Read')
    assert added['priority'] == 'MEDIUM' and added['category'] == 'work'


def test_task_draft_cancel_and_version_conflict(workspace):
    """Wrong versions, repeated cancellation and confirmation after cancel conflict."""
    client, sid, base = workspace
    before = client.get(base + '/tasks').json()
    did = draft(sid, [addition()])
    assert client.post(f'{base}/task-drafts/{did}/confirm', json={'state_version': 99}).status_code == 409
    assert client.post(f'{base}/task-drafts/{did}/cancel').json() == {'cancelled': True}
    assert client.post(f'{base}/task-drafts/{did}/cancel').status_code == 409
    assert client.get(base + '/task-drafts/pending').json()['draft'] is None
    assert client.post(f'{base}/task-drafts/{did}/confirm', json={'state_version': 1}).status_code == 409
    assert client.get(base + '/tasks').json() == before


def test_task_draft_session_ownership_and_protected_scheduled_tasks(workspace):
    """Cross-session IDs and scheduled tasks cannot be changed through task drafts."""
    client, sid, base = workspace
    other = client.post('/api/v1/sessions', json={'seed': True}).json()['session_id']
    standup = next(t for t in client.get(base + '/tasks').json()['tasks'] if t['title'] == 'Team standup')
    with pytest.raises(ValueError, match='Scheduled or completed tasks are protected'):
        draft(sid, [{'action': 'remove', 'task_id': standup['id']}])
    with pytest.raises(ValueError, match='does not belong'):
        draft(other, [{'action': 'remove', 'task_id': standup['id']}])
    did = draft(sid, [addition()])
    assert client.get(f'/api/v1/sessions/{other}/task-drafts/pending').json() == {'draft': None}
    other_base = f'/api/v1/sessions/{other}/task-drafts/{did}'
    assert client.get(other_base).status_code == 404
    assert client.post(other_base + '/confirm', json={'state_version': 1}).status_code == 404
    assert client.post(other_base + '/cancel').status_code == 404


def test_stale_draft_after_another_writer_never_commits(workspace):
    """Changing the session after drafting rejects the entire batch."""
    client, sid, base = workspace
    did = draft(sid, [addition()])
    client.post(base + '/tasks', json={'state_version': 1, 'title': 'Other tab', 'duration_minutes': 10})
    before = client.get(base + '/tasks').json()
    assert client.post(f'{base}/task-drafts/{did}/confirm', json={'state_version': 1}).status_code == 409
    assert client.get(base + '/tasks').json() == before


def test_confirm_failure_rolls_back_entire_batch(workspace):
    """A database failure on the second write also removes the first write."""
    client, sid, base = workspace
    did = draft(sid, [addition(), {**addition(), 'title': 'Reject this'}])
    db = get_connection()
    try:
        db.execute("CREATE TRIGGER reject_task BEFORE INSERT ON tasks WHEN NEW.title='Reject this' BEGIN SELECT RAISE(ABORT,'test constraint'); END")
        db.commit()
    finally:
        db.close()
    before = client.get(base + '/tasks').json()
    with pytest.raises(sqlite3.IntegrityError):
        client.post(f'{base}/task-drafts/{did}/confirm', json={'state_version': 1})
    assert client.get(base + '/tasks').json() == before
    assert client.get(base + '/task-drafts/pending').json()['draft']['id'] == did


def test_cancel_races_confirm_with_one_winner(workspace):
    """Two concurrent lifecycle mutations serialize and cannot both report success."""
    client, sid, base = workspace
    did = draft(sid, [addition()])
    with ThreadPoolExecutor(max_workers=2) as pool:
        confirm = pool.submit(client.post, f'{base}/task-drafts/{did}/confirm', json={'state_version': 1})
        cancel = pool.submit(client.post, f'{base}/task-drafts/{did}/cancel')
        assert sorted([confirm.result().status_code, cancel.result().status_code]) == [200, 409]


def test_plan_cancel_rejects_already_cancelled_or_executed(workspace):
    """Calendar cancellation reports real state transitions only."""
    client, _, base = workspace
    pid = client.post(base + '/agent/message', json={'message': 'Plan my day'}).json()['plan_id']
    assert client.post(f'{base}/plans/{pid}/cancel').status_code == 200
    assert client.post(f'{base}/plans/{pid}/cancel').status_code == 409
    pid = client.post(base + '/agent/message', json={'message': 'Plan my day'}).json()['plan_id']
    assert client.post(f'{base}/plans/{pid}/confirm', json={'state_version': 1}).status_code == 200
    assert client.post(f'{base}/plans/{pid}/cancel').status_code == 409


def test_post_turn_wal_conflict_returns_409(workspace, monkeypatch):
    """A writer during the awaited turn causes a recoverable conflict on history insert."""
    client, sid, base = workspace
    async def concurrent_write(message, context):
        db = get_connection()
        try:
            with db:
                db.execute('UPDATE sessions SET state_version=state_version+1 WHERE id=?', (sid,))
        finally:
            db.close()
        return AgentTurnResult(response='Read-only reply')
    monkeypatch.setattr(settings, 'gemini_api_key', 'mock-key')
    monkeypatch.setattr(agent, '_live_provider', lambda key: SimpleNamespace(run_agent_turn=concurrent_write))
    res = client.post(base + '/agent/message?provider=gemini', json={'message': 'Status'})
    assert res.status_code == 409 and res.json()['error']['code'] == 'STATE_CONFLICT'
    db = get_connection()
    try:
        assert db.execute('SELECT COUNT(*) FROM agent_messages WHERE session_id=?', (sid,)).fetchone()[0] == 0
    finally:
        db.close()


def test_domain_refusal_does_not_trigger_fallback(workspace):
    """Validation refusal keeps the outage counter unchanged and never reroutes intent."""
    _, sid, _ = workspace
    primary, fallback = AsyncMock(), AsyncMock()
    primary.run_agent_turn.side_effect = ValueError('Not enough room in the selected day')
    provider = FallbackProvider(primary, fallback)
    db = get_connection()
    try:
        with pytest.raises(ValueError, match='Not enough room'):
            asyncio.run(provider.run_agent_turn('Plan', AgentContext(sid, db)))
        assert provider.failure_count == 0
        fallback.run_agent_turn.assert_not_awaited()
        assert not db.in_transaction
    finally:
        db.close()


@pytest.mark.parametrize('personal', [False, True])
def test_unseeded_reset_stays_empty(workspace, personal):
    """Both unseeded API sessions and personal date sessions reset without demo data."""
    client, _, _ = workspace
    if personal:
        wid = client.post('/api/v1/workspaces').json()['workspace_id']
        sid = client.post(f'/api/v1/workspaces/{wid}/days', json={'day': '2026-10-22', 'offset_minutes': 330}).json()['session_id']
    else:
        sid = client.post('/api/v1/sessions', json={'seed': False}).json()['session_id']
    base = f'/api/v1/sessions/{sid}'
    assert client.delete(base).status_code == 200
    assert client.get(base + '/tasks').json()['tasks'] == []
    assert client.get(base + '/schedule').json()['blocks'] == []


def test_gemini_clarification_history_and_task_draft_tool_call(workspace, monkeypatch):
    """A follow-up duration uses the prior question and creates only a task draft."""
    client, _, base = workspace
    monkeypatch.setattr(settings, 'gemini_api_key', 'mock-key')
    from server.providers import gemini
    def response(name=None, args=None, text=''):
        part = types.Part(function_call=types.FunctionCall(name=name, args=args)) if name else types.Part.from_text(text=text)
        return types.GenerateContentResponse(candidates=[types.Candidate(content=types.Content(role='model', parts=[part]))])
    generate = AsyncMock()
    manager = AsyncMock()
    manager.__aenter__.return_value = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    monkeypatch.setattr(gemini.genai, 'Client', lambda **kwargs: SimpleNamespace(aio=manager))
    agent._live_provider.cache_clear()
    try:
        before = client.get(base + '/tasks').json()
        generate.side_effect = [response('get_tasks', {}), response(text="How many minutes should I set for 'Prepare slides'?")]
        first = client.post(base + '/agent/message?provider=gemini', json={'message': 'Add a task to Prepare slides'})
        assert first.status_code == 200 and not first.json()['has_proposal'] and 'minutes' in first.json()['response']
        generate.side_effect = [response('propose_task_changes', {'explanation': 'Prepare slides for 45 minutes.', 'changes': [{**addition(), 'title': 'Prepare slides'}]}), response(text='Please review and confirm.')]
        second = client.post(base + '/agent/message?provider=gemini', json={'message': '45 minutes'})
        assert second.status_code == 200, second.text
        assert second.json()['has_proposal'] and second.json()['task_draft_id']
        did = second.json()['task_draft_id']
        pending = client.get(base + '/task-drafts/pending').json()['draft']
        assert pending['id'] == did and pending['status'] == 'PROPOSED'
        assert pending['changes'][0]['after']['title'] == 'Prepare slides'
        assert pending['changes'][0]['after']['duration_minutes'] == 45
        assert second.json().get('plan_id') is None
        sent = generate.call_args.kwargs['contents'][0].parts[0].text
        assert 'Prepare slides' in sent and 'How many minutes' in sent
        assert 'combine the user' in generate.call_args.kwargs['config'].system_instruction
        assert client.get(base + '/tasks').json() == before
    finally:
        agent._live_provider.cache_clear()


@pytest.mark.skipif(os.getenv('FLOWPILOT_RUN_LIVE_TESTS') != '1' or not (settings.gemini_api_key or os.getenv('GEMINI_API_KEY')), reason='Live calls require FLOWPILOT_RUN_LIVE_TESTS=1 and a key')
def test_live_gemini_task_draft(workspace):
    """Authorized live inference creates a real draft without mutating saved tasks."""
    _, sid, _ = workspace
    db = get_connection()
    try:
        before = [dict(r) for r in db.execute('SELECT * FROM tasks WHERE session_id=? ORDER BY id', (sid,))]
        result = asyncio.run(GeminiProvider().run_agent_turn("Add a new pending work task called 'Write unit tests' for 30 minutes with HIGH priority.", AgentContext(sid, db, '2026-10-22T09:00:00+05:30')))
        assert result.provider_used == 'gemini' and not result.degraded
        assert result.has_proposal and result.task_draft_id
        assert any(t['tool'] == 'propose_task_changes' for t in result.tool_trace)
        assert [dict(r) for r in db.execute('SELECT * FROM tasks WHERE session_id=? ORDER BY id', (sid,))] == before
    finally:
        db.close()
