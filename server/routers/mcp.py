"""MCP 2025-11-25 Streamable HTTP with JSON responses and no COMMIT surface.

GET streams and DELETE termination are optional and return 405. Domain sessions
persist in SQLite; callers may bind an existing UI session or use an empty one.
"""
from copy import deepcopy
from datetime import datetime, timezone
import json
import sqlite3
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from jsonschema import ValidationError
from starlette.concurrency import run_in_threadpool

from server.config import settings
from server.database import get_connection
from server.tools.registry import default_registry

router = APIRouter()
PROTOCOL_VERSION = '2025-11-25'
EXPOSED_TIERS = {'READ', 'PROPOSE', 'PREFERENCE'}


def rpc_error(request_id, code, message, status=200):
    return JSONResponse({'jsonrpc': '2.0', 'id': request_id, 'error': {'code': code, 'message': message}}, status_code=status)


def _transport_error(request):
    allowed = {value.strip() for value in settings.flowpilot_cors_origins.split(',')}
    allowed.update({f'http://localhost:{settings.flowpilot_port}', f'http://127.0.0.1:{settings.flowpilot_port}'})
    origin = request.headers.get('origin')
    if origin is not None and origin not in allowed:
        return rpc_error(None, -32000, 'Origin not allowed', 403)
    version = request.headers.get('mcp-protocol-version')
    if version is not None and version != PROTOCOL_VERSION:
        return rpc_error(None, -32600, 'Unsupported MCP protocol version', 400)
    return None


def _session(db, sid=None, fresh=False):
    if sid is not None:
        if not isinstance(sid, str) or not sid or len(sid) > 200:
            raise ValueError('Invalid session_id')
        if db.execute('SELECT 1 FROM sessions WHERE id=?', (sid,)).fetchone() is None:
            raise LookupError('Session not found')
        return sid
    if not fresh:
        row = db.execute("SELECT session_id FROM mcp_defaults WHERE name='inspector' ").fetchone()
        if row:
            return row['session_id']
    sid = str(uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    db.execute('INSERT INTO sessions (id,created_at,demo_timestamp) VALUES (?,?,?)', (sid, timestamp, settings.flowpilot_demo_timestamp))
    if not fresh:
        db.execute("INSERT INTO mcp_defaults (name,session_id) VALUES ('inspector',?)", (sid,))
    return sid


def _tool_list():
    tools = []
    for tool in default_registry.list_tools():
        if tool.tier not in EXPOSED_TIERS:
            continue
        schema = deepcopy(tool.input_schema)
        schema.setdefault('properties', {})['session_id'] = {'type': 'string', 'description': 'Optional FlowPilot UI session ID; otherwise use the session header.'}
        tools.append(dict(name=tool.name, description=tool.description, inputSchema=schema,
                          annotations={'readOnlyHint': tool.tier == 'READ', 'destructiveHint': False, 'openWorldHint': False}))
    return tools


def _dispatch(message, headers):
    """Run short SQLite transactions in a worker; no network or model execution."""
    rid, method, params = message['id'], message['method'], message.get('params', {})
    if method not in {'initialize', 'ping', 'tools/list', 'tools/call'}:
        return rpc_error(rid, -32601, 'Method not found')
    if method == 'initialize':
        info = params.get('clientInfo')
        if (not isinstance(params.get('protocolVersion'), str) or not isinstance(params.get('capabilities'), dict)
                or not isinstance(info, dict) or not isinstance(info.get('name'), str) or not isinstance(info.get('version'), str)):
            return rpc_error(rid, -32602, 'initialize requires protocolVersion, capabilities and clientInfo')
    if method == 'tools/call':
        name, args = params.get('name'), params.get('arguments', {})
        if not isinstance(name, str) or not isinstance(args, dict):
            return rpc_error(rid, -32602, 'tools/call requires a tool name and object arguments')
        try:
            tool = default_registry.get(name)
        except KeyError:
            return rpc_error(rid, -32602, 'Unknown or unavailable tool')
        if tool.tier not in EXPOSED_TIERS:
            return rpc_error(rid, -32602, 'COMMIT tools are unavailable. Review and confirm in the FlowPilot UI.')
        args = dict(args)
        argument_sid = args.pop('session_id', None)
    else:
        argument_sid = None
    selectors = [value for value in (argument_sid, headers.get('x-flowpilot-session-id'), headers.get('mcp-session-id')) if value is not None]
    if any(value != selectors[0] for value in selectors):
        return rpc_error(rid, -32602, 'Conflicting session selectors')
    db = get_connection()
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            sid = _session(db, selectors[0] if selectors else None, fresh=method == 'initialize')
            response_headers = {'X-FlowPilot-Session-Id': sid}
            if method == 'initialize':
                response_headers['Mcp-Session-Id'] = sid
                result = {'protocolVersion': PROTOCOL_VERSION, 'capabilities': {'tools': {'listChanged': False}},
                          'serverInfo': {'name': 'flowpilot', 'version': '1.0.0'},
                          'instructions': 'READ then PROPOSE. Present review_path to the human. Only the FlowPilot UI may confirm task/calendar changes. Keep the returned session header on subsequent calls.'}
            elif method == 'ping':
                result = {}
            elif method == 'tools/list':
                if params.get('cursor'):
                    return rpc_error(rid, -32602, 'Invalid cursor; all tools fit on one page')
                result = {'tools': _tool_list()}
            else:
                db.execute('SAVEPOINT mcp_tool')
                try:
                    default_registry.validate_args(name, args)
                    output = tool.handler(sid, args, db)
                except (ValidationError, ValueError, TypeError, KeyError) as exc:
                    db.execute('ROLLBACK TO SAVEPOINT mcp_tool')
                    result = {'content': [{'type': 'text', 'text': str(exc)}], 'isError': True}
                else:
                    output = {**output, 'session_id': sid}
                    if tool.tier == 'PROPOSE':
                        output['review_path'] = f'/?session={sid}'
                        if output.get('plan_id'):
                            output['review_path'] += f"&plan={output['plan_id']}"
                        output['approval_required'] = True
                    result = {'content': [{'type': 'text', 'text': json.dumps(output, ensure_ascii=False)}],
                              'structuredContent': output, 'isError': False}
                db.execute('RELEASE SAVEPOINT mcp_tool')
            return JSONResponse({'jsonrpc': '2.0', 'id': rid, 'result': result}, headers=response_headers)
    except LookupError:
        return rpc_error(rid, -32001, 'Session not found', 404)
    except ValueError as exc:
        return rpc_error(rid, -32602, str(exc))
    except sqlite3.OperationalError:
        return rpc_error(rid, -32000, 'Workspace changed or is busy; retry the request', 409)
    finally:
        db.close()


@router.post('/mcp')
async def post_mcp(request: Request):
    error = _transport_error(request)
    if error:
        return error
    if request.headers.get('content-type', '').split(';')[0].strip() != 'application/json':
        return rpc_error(None, -32600, 'Content-Type must be application/json', 415)
    accept = request.headers.get('accept', '')
    if 'application/json' not in accept or 'text/event-stream' not in accept:
        return rpc_error(None, -32600, 'Accept must include application/json and text/event-stream', 406)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 262144:
            return rpc_error(None, -32600, 'Request too large', 413)
    try:
        message = json.loads(body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return rpc_error(None, -32700, 'Parse error', 400)
    if not isinstance(message, dict) or message.get('jsonrpc') != '2.0' or not isinstance(message.get('method'), str):
        return rpc_error(None, -32600, 'Expected one JSON-RPC 2.0 request or notification', 400)
    if not isinstance(message.get('params', {}), dict):
        return rpc_error(message.get('id'), -32602, 'params must be an object', 400)
    if 'id' not in message:
        if not message['method'].startswith('notifications/'):
            return rpc_error(None, -32600, 'Tool requests require an id', 400)
        return Response(status_code=202)
    if isinstance(message['id'], bool) or not isinstance(message['id'], (str, int)):
        return rpc_error(None, -32600, 'id must be a string or integer', 400)
    return await run_in_threadpool(_dispatch, message, dict(request.headers))


@router.get('/mcp')
@router.delete('/mcp')
async def unsupported_stream(request: Request):
    return _transport_error(request) or Response(status_code=405, headers={'Allow': 'POST'})
