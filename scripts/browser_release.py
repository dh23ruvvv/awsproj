"""Exercise the real UI against an explicitly launched isolated test server.

Run: python scripts/browser_release.py --url http://127.0.0.1:8011
Requires Python Playwright and installed Chrome (or --channel msedge).
Creates a new demo session; never resets an existing browser session.
"""
import argparse
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8011')
    parser.add_argument('--channel', default='chrome')
    args = parser.parse_args()
    artifacts = Path('data/browser-release')
    artifacts.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=args.channel, headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 1050})
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(args.url)
        expect(page.get_by_role('button', name='+ Add a task')).to_be_enabled()
        expect(page.get_by_role('button', name='New demo workspace')).to_be_enabled()
        sid = page.evaluate("localStorage.getItem('flowpilot_sid')")
        endpoint = f'{args.url}/api/v1/sessions/{sid}'

        def schedule():
            response = context.request.get(f'{endpoint}/schedule')
            assert response.ok, response.text()
            return response.json()['blocks']

        original = schedule()
        page.screenshot(path=str(artifacts / 'desktop-home.png'), full_page=True)
        page.get_by_role('button', name='+ Add a task').click()
        page.get_by_label('Task name').fill('Browser regression task')
        page.get_by_label('Duration (minutes)').fill('20')
        page.get_by_role('button', name='Save task').click()
        expect(page.get_by_role('button', name='Edit Browser regression task')).to_be_visible()
        page.get_by_role('button', name='Edit Browser regression task').click()
        page.get_by_label('Duration (minutes)').fill('25')
        page.get_by_role('button', name='Save task').click()
        expect(page.get_by_role('form', name='Edit task')).to_have_count(0)
        tasks = context.request.get(f'{endpoint}/tasks').json()['tasks']
        assert next(t for t in tasks if t['title'] == 'Browser regression task')['duration_minutes'] == 25
        assert schedule() == original, 'Task editing changed the calendar'
        page.once('dialog', lambda dialog: dialog.accept())
        page.get_by_role('button', name='Remove Browser regression task').click()
        expect(page.get_by_role('button', name='Edit Browser regression task')).to_have_count(0)

        page.get_by_role('button', name='Plan my day', exact=True).click()
        expect(page.get_by_role('button', name='Confirm plan')).to_be_visible()
        assert schedule() == original, 'Proposal changed the calendar'
        page.screenshot(path=str(artifacts / 'desktop-proposal.png'), full_page=True)
        page.reload()
        expect(page.get_by_role('button', name='Confirm plan')).to_be_visible()
        page.get_by_role('button', name='Cancel', exact=True).click()
        expect(page.get_by_role('button', name='Confirm plan')).to_have_count(0)
        assert schedule() == original, 'Cancel changed the calendar'

        page.get_by_role('button', name='Plan my day', exact=True).click()
        expect(page.get_by_role('button', name='Confirm plan')).to_be_visible()
        pid = page.evaluate(f"localStorage.getItem('flowpilot_plan_{sid}')")
        proposed = context.request.get(f'{endpoint}/plans/{pid}').json()['proposed_blocks']
        page.get_by_role('button', name='Confirm plan').click()
        expect(page.get_by_role('button', name='Confirm plan')).to_have_count(0)
        expect(page.get_by_text('Your plan is confirmed.', exact=False)).to_be_visible()
        committed = schedule()
        assert {(b['title'], b['start_time'], b['end_time']) for b in committed} == {(b['title'], b['start_time'], b['end_time']) for b in proposed}
        page.reload()
        expect(page.get_by_role('button', name='+ Add a task')).to_be_enabled()
        assert schedule() == committed, 'Refresh lost committed state'

        page.get_by_role('button', name='Add an interruption', exact=True).click()
        expect(page.get_by_role('button', name='Confirm plan')).to_be_visible()
        assert schedule() == committed
        page.get_by_role('button', name='Confirm plan').click()
        expect(page.get_by_role('button', name='Confirm plan')).to_have_count(0)
        expect(page.get_by_text('Your plan is confirmed.', exact=False)).to_be_visible()
        after_interruption = schedule()
        protected = {(b['id'], b['start_time'], b['end_time']) for b in original if b['immutable']}
        assert protected <= {(b['id'], b['start_time'], b['end_time']) for b in after_interruption}
        # A new workspace preserves the previous session, while allowing a client-meeting story.
        expect(page.get_by_role('button', name='New demo workspace')).to_be_enabled()
        page.get_by_role('button', name='New demo workspace').click()
        expect(page.get_by_role('tab', name='Tasks (5)', exact=True)).to_be_visible()
        expect(page.get_by_role('button', name='Remove Grocery shopping')).to_be_enabled()
        assert context.request.get(f'{endpoint}/schedule').json()['blocks'] == after_interruption
        sid = page.evaluate("localStorage.getItem('flowpilot_sid')")
        endpoint = f'{args.url}/api/v1/sessions/{sid}'
        page.once('dialog', lambda dialog: dialog.accept())
        page.get_by_role('button', name='Remove Grocery shopping').click()
        expect(page.get_by_role('button', name='Edit Review PR #247')).to_be_enabled()
        page.get_by_role('button', name='Edit Review PR #247').click()
        page.get_by_label('Task name').fill('Prepare presentation')
        page.get_by_role('button', name='Save task').click()
        expect(page.get_by_role('button', name='Edit Prepare presentation')).to_be_visible()
        page.get_by_role('tab', name='Timeline (2)', exact=True).click()
        page.get_by_role('button', name='+ Add a fixed event').click()
        # Demonstrate a recoverable protected-event conflict in the actual UI.
        page.get_by_label('Start time', exact=True).fill('10:00')
        page.get_by_label('End time', exact=True).fill('10:15')
        page.get_by_role('button', name='Preview fixed event').click()
        expect(page.get_by_role('alert').filter(has_text='overlaps protected')).to_be_visible()
        page.get_by_label('Start time', exact=True).fill('15:30')
        page.get_by_label('End time', exact=True).fill('16:00')
        page.get_by_role('button', name='Preview fixed event').click()
        expect(page.get_by_role('button', name='Confirm plan')).to_be_visible()
        assert not any(b['title'] == 'Client meeting' for b in schedule())
        page.get_by_role('button', name='Confirm plan').click()
        expect(page.get_by_role('button', name='Confirm plan')).to_have_count(0)
        expect(page.get_by_role('button', name='Plan my day', exact=True)).to_be_enabled()
        client_meeting = next(b for b in schedule() if b['title'] == 'Client meeting')
        page.get_by_role('button', name='Plan my day', exact=True).click()
        expect(page.get_by_role('button', name='Confirm plan')).to_be_visible()
        page.get_by_role('button', name='Confirm plan').click()
        expect(page.get_by_role('button', name='Confirm plan')).to_have_count(0)
        expect(page.get_by_role('button', name='Add an interruption', exact=True)).to_be_enabled()
        day_before = schedule()
        page.get_by_role('button', name='Add an interruption', exact=True).click()
        expect(page.get_by_role('button', name='Confirm plan')).to_be_visible()
        page.get_by_role('button', name='Cancel', exact=True).click()
        expect(page.get_by_role('button', name='Confirm plan')).to_have_count(0)
        assert schedule() == day_before
        expect(page.get_by_role('button', name='Add an interruption', exact=True)).to_be_enabled()
        page.get_by_role('button', name='Add an interruption', exact=True).click()
        expect(page.get_by_role('button', name='Confirm plan')).to_be_visible()
        page.get_by_role('button', name='Confirm plan').click()
        expect(page.get_by_role('button', name='Confirm plan')).to_have_count(0)
        expect(page.get_by_role('button', name='New demo workspace')).to_be_enabled()
        final = schedule()
        fixed = next(b for b in final if b['id'] == client_meeting['id'])
        assert (fixed['start_time'], fixed['end_time'], fixed['immutable']) == (client_meeting['start_time'], client_meeting['end_time'], 1)
        page.reload()
        expect(page.get_by_role('button', name='+ Add a task')).to_be_enabled()
        assert schedule() == final
        page.get_by_role('tab', name=f'Timeline ({len(final)})', exact=True).click()
        page.screenshot(path=str(artifacts / 'desktop-client-confirmed.png'), full_page=True)
        page.set_viewport_size({'width': 390, 'height': 844})
        page.screenshot(path=str(artifacts / 'mobile-confirmed.png'), full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Mobile overflow'
        assert not errors, errors
        print('PASS: task CRUD; review/reload/cancel/confirm; refresh persistence; interruption; protected client meeting; recoverable conflict error; preserved previous workspace; 390px viewport; no browser exceptions')
        print(f'Screenshots: {artifacts.resolve()}')
        context.close()
        browser.close()


if __name__ == '__main__':
    main()
