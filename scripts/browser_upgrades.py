"""Verify MCP-to-UI reviews, live tool traces and preference controls in Chrome."""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

parser = argparse.ArgumentParser()
parser.add_argument('--url', default='http://127.0.0.1:8017')
args = parser.parse_args()

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("localStorage.setItem('flowpilot_provider', 'deterministic')")
    def call(name, arguments):
        response = page.request.post(args.url + '/mcp', headers={'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2025-11-25'},
            data={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {'name': name, 'arguments': arguments}})
        assert response.ok, response.text()
        result = response.json()['result']
        assert not result['isError'], result
        return result['structuredContent']
    sid = page.request.post(args.url + '/api/v1/sessions', data={'seed': False, 'demo_timestamp': '2026-10-22T09:00:00+05:30'}).json()['session_id']
    base = args.url + '/api/v1/sessions/' + sid
    draft = call('propose_task_changes', {'session_id': sid, 'changes': [{'action': 'add', 'title': 'Client research', 'duration_minutes': 120}], 'explanation': 'Review research task'})
    assert page.request.get(base + '/tasks').json()['tasks'] == []
    page.goto(args.url + draft['review_path'])
    expect(page.get_by_role('button', name='Confirm task changes')).to_be_enabled()
    expect(page.get_by_label('Planning day', exact=True)).to_have_value('2026-10-22')
    page.reload()
    page.get_by_role('button', name='Confirm task changes').click()
    expect(page.get_by_role('tab', name='Tasks (1)', exact=True)).to_be_visible()
    assert page.request.get(base + '/schedule').json()['blocks'] == []
    proposal = call('propose_schedule', {'session_id': sid, 'blocks': [], 'explanation': 'Review the calendar'})
    page.goto(args.url + proposal['review_path'])
    expect(page.get_by_role('button', name='Confirm plan', exact=True)).to_be_enabled()
    page.get_by_role('button', name='Cancel', exact=True).click()
    expect(page.get_by_role('button', name='Confirm plan', exact=True)).to_have_count(0)
    assert page.request.get(base + '/schedule').json()['blocks'] == []
    # Typed planning must reach the deterministic provider with a pending task.
    page.get_by_label('Your instruction').fill('Plan my day')
    page.get_by_role('button', name='Send', exact=True).click()
    expect(page.get_by_role('button', name='Confirm plan', exact=True)).to_be_enabled()
    expect(page.get_by_role('button', name='Preview my day')).to_have_count(0)
    page.get_by_role('button', name='Tool Execution Trace', exact=False).click()
    trace = page.get_by_role('region', name='Tool Execution Trace', exact=False)
    expect(trace.get_by_text('propose_schedule', exact=True)).to_be_visible()
    expect(trace.get_by_text('get_memory', exact=True)).to_be_visible()
    Path('data/upgrades').mkdir(parents=True, exist_ok=True)
    for width in (320, 390, 768, 1440):
        page.set_viewport_size({'width': width, 'height': 1000})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), width
    page.screenshot(path='data/upgrades/review-trace.png', full_page=True)
    page.get_by_role('button', name='Confirm plan', exact=True).click()
    expect(page.get_by_role('tab', name='Timeline (1)', exact=True)).to_be_visible()
    page.get_by_label('Your instruction').fill('Remember: I prefer deep work in the morning')
    page.get_by_role('button', name='Send', exact=True).click()
    preferences = page.get_by_role('region', name='Saved preferences')
    expect(preferences).to_contain_text('I prefer deep work in the morning')
    expect(trace.get_by_text('remember_preference', exact=True)).to_be_visible()
    page.reload()
    expect(preferences).to_contain_text('I prefer deep work in the morning')
    page.get_by_role('button', name='Forget preference:', exact=False).click()
    expect(preferences).to_have_count(0)
    page.get_by_role('link', name='Return to personal days').click()
    expect(page.get_by_role('button', name='+ Add a task')).to_be_enabled()
    page.get_by_label('Your instruction').fill("What's left today?")
    page.get_by_role('button', name='Send', exact=True).click()
    expect(page.locator('.tool-trace__count')).to_have_text('3 tools')
    page.get_by_role('button', name='Next day').click()
    expect(page.locator('.tool-trace__count')).to_have_text('0 tools')
    for width in (320, 390, 768, 1440):
        page.set_viewport_size({'width': width, 'height': 1000})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), width
    Path('data/upgrades').mkdir(parents=True, exist_ok=True)
    page.screenshot(path='data/upgrades/desktop.png', full_page=True)
    assert not errors, errors
    browser.close()
print('PASS: MCP task/calendar UI review, typed provider dispatch, tool trace, preference save/forget/reload, day clearing, 320-1440px layouts.')
