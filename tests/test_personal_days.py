"""Personal day isolation and persistent, idempotent weekday routines."""
import pytest
from fastapi.testclient import TestClient
from server.config import settings
from server.main import app

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'flowpilot_db_path', str(tmp_path / 'days.db'))
    monkeypatch.setattr(settings, 'flowpilot_default_provider', 'deterministic')
    with TestClient(app) as c:
        yield c

def workspace(c):
    return '/api/v1/workspaces/' + c.post('/api/v1/workspaces').json()['workspace_id']

def day(c, w, d):
    response = c.post(w + '/days', json={'day': d, 'offset_minutes': 330})
    assert response.status_code == 200, response.text
    return '/api/v1/sessions/' + response.json()['session_id']

def routine():
    return {'name':'Study week', 'weekdays':[1,5,6], 'starts_on':'2026-10-20', 'tasks':[{'title':'Read book','duration_minutes':30}]}

def test_day_isolation_routine_weekdays_reload_and_stop(client):
    c=client; w=workspace(c)
    thu=day(c,w,'2026-10-22')
    assert c.get(thu+'/tasks').json()['tasks']==[]
    assert c.get(thu+'/schedule').json()['blocks']==[]
    r=c.post(w+'/routines',json=routine()).json()['id']
    assert day(c,w,'2026-10-22')==thu
    assert c.get(thu+'/tasks').json()['tasks']==[]
    sat=day(c,w,'2026-10-24')
    assert sat != thu
    original=c.get(sat+'/tasks').json()
    assert [t['title'] for t in original['tasks']]==['Read book']
    assert day(c,w,'2026-10-24')==sat
    assert c.get(sat+'/tasks').json()==original
    # Removal is a per-day override, not recreated on reload.
    task=original['tasks'][0]
    c.request('DELETE',sat+'/tasks/'+task['id'],json={'state_version':original['state_version']})
    day(c,w,'2026-10-24')
    assert c.get(sat+'/tasks').json()['tasks']==[]
    sun=day(c,w,'2026-10-25')
    assert len(c.get(sun+'/tasks').json()['tasks'])==1
    assert c.delete(w+'/routines/'+r).status_code==200
    tue=day(c,w,'2026-10-27')
    assert c.get(tue+'/tasks').json()['tasks']==[]
    assert len(c.get(sun+'/tasks').json()['tasks'])==1

def test_routine_keeps_review_valid_and_never_commits(client):
    c=client; w=workspace(c); url=day(c,w,'2026-10-24')
    c.post(url+'/tasks',json={'title':'Write','duration_minutes':60,'state_version':1})
    proposal=c.post(url+'/agent/message',json={'message':'Plan my day','state_version':2}).json()
    assert proposal['has_proposal']
    c.post(w+'/routines',json=routine())
    day(c,w,'2026-10-24')
    assert len(c.get(url+'/tasks').json()['tasks'])==1
    assert c.get(url+'/schedule').json()['blocks']==[]
    assert c.get(url+'/plans/'+proposal['plan_id']).json()['status']=='PROPOSED'
    c.post(url+'/plans/'+proposal['plan_id']+'/cancel')
    day(c,w,'2026-10-24')
    assert len(c.get(url+'/tasks').json()['tasks'])==2
    assert c.get(url+'/schedule').json()['blocks']==[]

def test_routine_validation_scope_and_start_date(client):
    c=client; w=workspace(c); other=workspace(c)
    for change in [{'weekdays':[]},{'weekdays':[7]},{'weekdays':[1,1]},{'name':' '},{'tasks':[{'title':' ','duration_minutes':30}]},{'tasks':[{'title':'Test','duration_minutes':0}]}]:
        assert c.post(w+'/routines',json={**routine(),**change}).status_code==422
    r=c.post(w+'/routines',json=routine()).json()['id']
    assert c.delete(other+'/routines/'+r).status_code==404
    early=day(c,w,'2026-10-18')
    assert c.get(early+'/tasks').json()['tasks']==[]
    assert c.post(w+'/days',json={'day':'2026-02-30','offset_minutes':330}).status_code==422
