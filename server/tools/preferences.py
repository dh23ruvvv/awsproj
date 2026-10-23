"""Explicit user preferences, stored separately from tasks and calendar mutations."""
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator
from server.clock import now


class PreferenceInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    preference: str = Field(min_length=1, max_length=500)

    @field_validator('preference')
    @classmethod
    def clean(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('Preference cannot be blank')
        return value


def remember_preference(session_id, args, db_conn):
    """Save only an explicitly requested preference; caller owns the transaction."""
    preference = PreferenceInput.model_validate(args).preference
    session = db_conn.execute('SELECT * FROM sessions WHERE id=?', (session_id,)).fetchone()
    if session is None:
        raise ValueError('Session does not exist')
    existing = db_conn.execute("SELECT * FROM memory WHERE session_id=? AND key='scheduling_preference' AND value=?", (session_id, preference)).fetchone()
    if existing:
        return {'entry': dict(existing), 'state_version': session['state_version'], 'saved': True}
    entry = dict(id=str(uuid4()), session_id=session_id, key='scheduling_preference', value=preference, created_at=now(session['demo_timestamp']))
    db_conn.execute('INSERT INTO memory (id,session_id,key,value,created_at) VALUES (?,?,?,?,?)', tuple(entry.values()))
    db_conn.execute('UPDATE sessions SET state_version=state_version+1 WHERE id=?', (session_id,))
    return {'entry': entry, 'state_version': session['state_version'] + 1, 'saved': True}
