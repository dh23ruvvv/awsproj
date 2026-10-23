"""Explicit preference lifecycle, session isolation and scheduler integration."""
import pytest
from fastapi.testclient import TestClient
from server.config import settings
from server.main import app


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'flowpilot_db_path', str(tmp_path / 'memory.db'))
    monkeypatch.setattr(settings, 'flowpilot_default_provider', 'deterministic')
    with TestClient(app) as client:
        sid = client.post('/api/v1/sessions', json={'seed': False, 'demo_timestamp': '2026-10-22T09:00:00+05:30'}).json()['session_id']
        yield client, f'/api/v1/sessions/{sid}'


def test_preference_lifecycle_is_explicit_and_isolated(workspace):
    client, base = workspace
    assert client.get(base + '/memory').json()['entries'] == []
    before_tasks = client.get(base + '/tasks').json()['tasks']
    before_calendar = client.get(base + '/schedule').json()['blocks']
    body = {'preference': 'I prefer deep work in the morning'}
    first = client.post(base + '/memory', json=body)
    assert first.status_code == 201
    assert client.post(base + '/memory', json=body).json() == first.json()
    mid = first.json()['entry']['id']
    other = client.post('/api/v1/sessions', json={'seed': False}).json()['session_id']
    assert client.delete(f'/api/v1/sessions/{other}/memory/{mid}').status_code == 404
    assert client.get(f'/api/v1/sessions/{other}/memory').json()['entries'] == []
    assert client.get(base + '/tasks').json()['tasks'] == before_tasks
    assert client.get(base + '/schedule').json()['blocks'] == before_calendar
    assert client.delete(base + '/memory/' + mid).json() == {'deleted': True, 'state_version': 3}
    assert client.get(base + '/memory').json()['entries'] == []


@pytest.mark.parametrize('preference', ['', '   ', 'x' * 501])
def test_invalid_preference_rejected(workspace, preference):
    client, base = workspace
    assert client.post(base + '/memory', json={'preference': preference}).status_code == 422


def test_remember_turn_and_preference_scheduling(workspace):
    client, base = workspace
    response = client.post(base + '/agent/message', json={'message': 'Remember: I prefer personal tasks in the afternoon'})
    assert response.status_code == 200
    assert not response.json()['has_proposal'] and response.json()['state_version'] == 2
    assert response.json()['tool_trace'][0]['tool'] == 'remember_preference'
    assert len(client.get(base + '/memory').json()['entries']) == 1
    task = client.post(base + '/tasks', json={'state_version': 2, 'title': 'Errands', 'duration_minutes': 60, 'category': 'personal'})
    assert task.status_code == 201
    plan = client.post(base + '/agent/message', json={'message': 'Plan my day'}).json()
    proposal = client.get(base + '/plans/' + plan['plan_id']).json()
    assert proposal['proposed_blocks'][0]['start_time'][11:16] == '13:00'
    assert client.get(base + '/schedule').json()['blocks'] == []
    assert client.post(base + '/plans/' + plan['plan_id'] + '/confirm', json={'state_version': 3}).status_code == 200
    assert len(client.get(base + '/memory').json()['entries']) == 1


def test_preference_change_invalidates_earlier_calendar_review(workspace):
    client, base = workspace
    client.post(base + '/tasks', json={'state_version': 1, 'title': 'Work', 'duration_minutes': 60})
    plan = client.post(base + '/agent/message', json={'message': 'Plan my day'}).json()
    assert plan['state_version'] == 2
    saved = client.post(base + '/memory', json={'preference': 'I prefer work in the morning'})
    assert saved.json()['state_version'] == 3
    assert client.post(base + '/plans/' + plan['plan_id'] + '/confirm', json={'state_version': 2}).status_code == 409
    assert client.get(base + '/schedule').json()['blocks'] == []
