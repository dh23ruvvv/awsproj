"""Exercise MCP wire transport, session binding and the approval boundary."""
from concurrent.futures import ThreadPoolExecutor
import json
import pytest
from fastapi.testclient import TestClient
from server.config import settings
from server.database import get_connection
from server.main import app

HEADERS = {'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2025-11-25'}
INIT = {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'test-inspector', 'version': '1'}}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'flowpilot_db_path', str(tmp_path / 'mcp.db'))
    monkeypatch.setattr(settings, 'flowpilot_demo_timestamp', '2026-10-22T09:00:00+05:30')
    with TestClient(app) as client:
        yield client


def rpc(client, method, params=None, path='/mcp', headers=None, rid=1):
    return client.post(path, headers={**HEADERS, **(headers or {})}, json={'jsonrpc': '2.0', 'id': rid, 'method': method, 'params': params or {}})


def call(client, name, args=None, **kwargs):
    return rpc(client, 'tools/call', {'name': name, 'arguments': args or {}}, **kwargs)


@pytest.mark.parametrize('path', ['/mcp', '/api/v1/mcp'])
def test_initialize_list_and_read(client, path):
    initialized = rpc(client, 'initialize', INIT, path)
    assert initialized.status_code == 200 and initialized.headers['content-type'] == 'application/json'
    result = initialized.json()['result']
    assert result['protocolVersion'] == '2025-11-25'
    assert result['capabilities']['tools'] == {'listChanged': False}
    sid = initialized.headers['Mcp-Session-Id']
    headers = {'Mcp-Session-Id': sid}
    ready = client.post(path, json={'jsonrpc': '2.0', 'method': 'notifications/initialized'}, headers={**HEADERS, **headers})
    assert ready.status_code == 202 and not ready.content
    tools = rpc(client, 'tools/list', path=path, headers=headers).json()['result']['tools']
    assert len(tools) == 9 and 'commit_schedule' not in {tool['name'] for tool in tools}
    assert all('session_id' in tool['inputSchema']['properties'] for tool in tools)
    for name, key in [('get_tasks', 'tasks'), ('get_calendar', 'blocks'), ('get_schedule', 'blocks'), ('get_memory', 'entries'), ('get_current_time', 'current_time')]:
        res = call(client, name, path=path, headers=headers).json()['result']
        assert res['isError'] is False and key in res['structuredContent']
        assert json.loads(res['content'][0]['text']) == res['structuredContent']
        assert res['structuredContent']['session_id'] == sid
    assert rpc(client, 'ping', headers=headers).json()['result'] == {}


def test_default_session_is_stable_and_initializations_isolated(client):
    a = call(client, 'get_tasks').json()['result']['structuredContent']['session_id']
    b = call(client, 'get_tasks').json()['result']['structuredContent']['session_id']
    c = rpc(client, 'initialize', INIT).headers['Mcp-Session-Id']
    d = rpc(client, 'initialize', INIT).headers['Mcp-Session-Id']
    assert a == b and len({a, c, d}) == 3


@pytest.mark.parametrize('selector', ['argument', 'X-FlowPilot-Session-Id', 'Mcp-Session-Id'])
def test_proposal_waits_for_ui_confirmation(client, selector):
    sid = client.post('/api/v1/sessions', json={'seed': True}).json()['session_id']
    base = f'/api/v1/sessions/{sid}'
    before = client.get(base + '/schedule').json()
    args = {'blocks': [], 'explanation': 'Review this plan'}
    headers = {}
    if selector == 'argument':
        args['session_id'] = sid
    else:
        headers[selector] = sid
    result = call(client, 'propose_schedule', args, headers=headers).json()['result']
    assert not result['isError']
    out = result['structuredContent']
    assert out['approval_required'] and out['review_path'].startswith(f'/?session={sid}')
    assert client.get(base + '/schedule').json() == before
    pid = out['plan_id']
    assert client.get(base + '/context').json()['pending_plan_id'] == pid
    assert client.get(base + '/plans/' + pid).json()['status'] == 'PROPOSED'
    assert client.post(base + '/plans/' + pid + '/confirm', json={'state_version': 1}).status_code == 200
    after = client.get(base + '/schedule').json()
    assert after['state_version'] == 2 and len(after['blocks']) > len(before['blocks'])
    # Replanning also produces only a reviewable draft.
    result = call(client, 'propose_replan', {'session_id': sid, 'new_blocks': after['blocks'], 'explanation': 'Keep saved work'}).json()['result']
    assert not result['isError'] and result['structuredContent']['plan_id']
    assert client.get(base + '/schedule').json() == after


def test_task_draft_and_explicit_preference(client):
    sid = rpc(client, 'initialize', INIT).headers['Mcp-Session-Id']
    base = f'/api/v1/sessions/{sid}'
    headers = {'Mcp-Session-Id': sid}
    memory = call(client, 'remember_preference', {'preference': 'I prefer deep work in the morning'}, headers=headers).json()['result']
    assert not memory['isError'] and client.get(base + '/memory').json()['entries']
    args = {'changes': [{'action': 'add', 'title': 'Write report', 'duration_minutes': 90}], 'explanation': 'Review the task'}
    result = call(client, 'propose_task_changes', args, headers=headers).json()['result']
    assert not result['isError']
    assert client.get(base + '/tasks').json()['tasks'] == []
    assert client.get(base + '/schedule').json()['blocks'] == []
    out = result['structuredContent']
    assert out['review_path'] == f'/?session={sid}'
    did = out['task_draft_id']
    assert client.post(f'{base}/task-drafts/{did}/confirm', json={'state_version': 2}).status_code == 200
    assert client.get(base + '/tasks').json()['tasks'][0]['title'] == 'Write report'


@pytest.mark.parametrize('name', ['commit_schedule', 'confirm_task_draft', 'delete_everything'])
def test_commit_is_unavailable(client, name):
    sid = client.post('/api/v1/sessions', json={'seed': True}).json()['session_id']
    base = f'/api/v1/sessions/{sid}'
    before = client.get(base + '/schedule').json()
    result = call(client, name, {'session_id': sid, 'plan_id': 'anything'})
    assert result.json()['error']['code'] == -32602
    assert client.get(base + '/schedule').json() == before


def test_transport_errors_and_notifications(client):
    assert client.get('/mcp').status_code == 405
    assert client.delete('/mcp').status_code == 405
    for method in ('get', 'delete', 'post'):
        assert getattr(client, method)('/mcp', headers={'Origin': 'https://evil.example'}).status_code == 403
    assert rpc(client, 'ping', headers={'MCP-Protocol-Version': '2099-01-01'}).status_code == 400
    assert rpc(client, 'ping', headers={'Accept': 'application/json'}).status_code == 406
    assert client.post('/mcp', content='{}', headers=HEADERS).status_code == 415
    assert client.post('/mcp', content='{', headers={**HEADERS, 'Content-Type': 'application/json'}).json()['error']['code'] == -32700
    for payload in ([], {}, {'jsonrpc': '2.0', 'id': None, 'method': 'ping'}, {'jsonrpc': '2.0', 'method': 'tools/call'}):
        assert client.post('/mcp', json=payload, headers=HEADERS).status_code == 400
    assert rpc(client, 'initialize', {}).json()['error']['code'] == -32602
    assert rpc(client, 'unknown').json()['error']['code'] == -32601
    assert call(client, 'get_tasks', {'session_id': 'missing'}).status_code == 404
    assert call(client, 'get_tasks', {'unknown': True}).json()['result']['isError']
    assert call(client, 'get_tasks', {'session_id': 'one'}, headers={'Mcp-Session-Id': 'two'}).json()['error']['code'] == -32602


def test_concurrent_task_drafts_do_not_bypass_review(client):
    sid = rpc(client, 'initialize', INIT).headers['Mcp-Session-Id']
    args = {'session_id': sid, 'changes': [{'action': 'add', 'title': 'Read', 'duration_minutes': 30}], 'explanation': 'Review'}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: call(client, 'propose_task_changes', args).json()['result'], range(2)))
    assert sorted(result['isError'] for result in results) == [False, True]
    assert client.get(f'/api/v1/sessions/{sid}/tasks').json()['tasks'] == []


def test_split_proposal_commits_all_chunks_once(client):
    sid = client.post('/api/v1/sessions', json={'seed': False}).json()['session_id']
    base = f'/api/v1/sessions/{sid}'
    task = client.post(base + '/tasks', json={'state_version': 1, 'title': 'Deep work', 'duration_minutes': 120}).json()['task']
    db = get_connection()
    try:
        with db:
            for bid, start, end in [('a', '10:00', '11:00'), ('b', '12:00', '17:00')]:
                db.execute('INSERT INTO calendar_blocks (id,session_id,title,start_time,end_time,immutable,created_at) VALUES (?,?,?,?,?,1,?)', (bid, sid, bid, f'2026-10-22T{start}:00+05:30', f'2026-10-22T{end}:00+05:30', '2026-10-22T09:00:00+05:30'))
    finally:
        db.close()
    out = call(client, 'propose_schedule', {'session_id': sid, 'blocks': [], 'explanation': 'Split around meetings'}).json()['result']['structuredContent']
    pid = out['plan_id']
    assert client.post(f'{base}/plans/{pid}/confirm', json={'state_version': 2}).status_code == 200
    saved = client.get(base + '/schedule').json()
    chunks = [b for b in saved['blocks'] if b.get('task_id') == task['id']]
    assert len(chunks) == 2 and len({b['id'] for b in chunks}) == 2
    assert client.post(f'{base}/plans/{pid}/confirm', json={'state_version': 3}).status_code == 200
    assert client.get(base + '/schedule').json() == saved
