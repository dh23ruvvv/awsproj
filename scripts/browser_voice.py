"""Exercise voice UI with simulated speech events and an intercepted Gemini turn."""
import argparse
from playwright.sync_api import sync_playwright, expect

parser = argparse.ArgumentParser()
parser.add_argument('--url', default='http://127.0.0.1:8016')
args = parser.parse_args()
speech_mock = """
if (!sessionStorage.getItem('voice_test_initialized')) { localStorage.setItem('flowpilot_workspace', 'deleted-workspace'); localStorage.setItem('flowpilot_provider', 'deterministic'); sessionStorage.setItem('voice_test_initialized', 'yes'); }
window.__spoken = []; window.__cancelled = 0;
window.SpeechRecognition = class {
  start() { window.__recognition = this; }
  stop() { this.onend?.(); }
  abort() { this.onend?.(); }
};
window.SpeechSynthesisUtterance = class { constructor(text) { this.text = text; } };
Object.defineProperty(window, 'speechSynthesis', {value: {
  speak(speech) { window.__spoken.push(speech.text); speech.onstart?.(); },
  cancel() { window.__cancelled++; }
}});
"""
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    page.add_init_script(speech_mock)
    errors, requests = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    def answer(route):
        """Intercept inference only; preserve the real day/task APIs."""
        requests.append((route.request.url, route.request.post_data_json))
        route.fulfill(json={'response': f'Reply {len(requests)}: ready for review.', 'state_version': 2, 'provider_used': 'gemini', 'degraded': False, 'has_proposal': False, 'tool_trace': [{'tool': 'get_tasks', 'args': {}, 'result_summary': 'Read saved tasks', 'duration_ms': 7}]})
    page.route('**/agent/message*', answer)
    page.goto(args.url)
    expect(page.get_by_role('button', name='+ Add a task')).to_be_enabled()
    page.get_by_label('Read replies aloud', exact=True).check()
    assert page.evaluate('window.__spoken.length') == 0, 'Static placeholder was spoken'
    # Gemini on an empty personal day must still open setup.
    page.get_by_role('button', name='Use Gemini', exact=True).click()
    page.get_by_label('Your instruction').fill('Plan my day')
    page.get_by_role('button', name='Send', exact=True).click()
    expect(page.get_by_role('button', name='Preview my day')).to_be_disabled()
    assert not requests
    page.get_by_role('button', name='Add a task', exact=True).click()
    page.get_by_label('Task name').fill('Voice regression task')
    page.get_by_role('button', name='Save task', exact=True).click()
    expect(page.get_by_role('button', name='Preview my day')).to_be_enabled()
    page.get_by_role('button', name='Close setup').click()
    page.get_by_label('Send after speaking', exact=True).check()
    page.get_by_role('button', name='Speak to Gemini', exact=True).click()
    expect(page.get_by_role('button', name='Stop listening')).to_be_visible()
    page.evaluate("window.__recognition.onresult({results:[{isFinal:true,0:{transcript:'Plan my day'}}]})")
    page.get_by_role('button', name='Stop listening').click()
    expect(page.get_by_text('Reply 1: ready for review.', exact=True)).to_be_visible()
    assert requests[0][1]['message'] == 'Plan my day' and 'provider=gemini' in requests[0][0]
    expect(page.get_by_role('button', name='Preview my day')).to_have_count(0)
    page.get_by_role('button', name='Tool Execution Trace', exact=False).click()
    expect(page.locator('.tool-trace').get_by_text('get_tasks', exact=True)).to_be_visible()
    expect(page.locator('.tool-trace').get_by_text('7ms', exact=True)).to_be_visible()
    count, cancels = page.evaluate('[window.__spoken.length, window.__cancelled]')
    page.get_by_label('Speech language', exact=True).select_option('en-US')
    assert page.evaluate('[window.__spoken.length, window.__cancelled]') == [count, cancels], 'Language change interrupted TTS'
    # Final and interim words both survive Stop; no duplicate request is sent.
    page.get_by_role('button', name='Speak to Gemini', exact=True).click()
    page.evaluate("window.__recognition.onresult({results:[{isFinal:true,0:{transcript:'Add reading'}},{isFinal:false,0:{transcript:'for 30 minutes'}}]})")
    page.get_by_role('button', name='Stop listening').click()
    expect(page.get_by_text('Reply 2: ready for review.', exact=True)).to_be_visible()
    assert requests[1][1]['message'] == 'Add reading for 30 minutes'
    # Permission errors never submit partial speech.
    page.get_by_role('button', name='Speak to Gemini', exact=True).click()
    page.evaluate("window.__recognition.onerror({error:'not-allowed'}); window.__recognition.onend()")
    expect(page.get_by_text('Microphone permission was denied.', exact=False)).to_be_visible()
    assert len(requests) == 2
    page.get_by_label('Read replies aloud', exact=True).uncheck()
    page.get_by_label('Your instruction').fill('Status')
    page.get_by_role('button', name='Send', exact=True).click()
    expect(page.get_by_text('Reply 3: ready for review.', exact=True)).to_be_visible()
    count = page.evaluate('window.__spoken.length')
    page.get_by_label('Read replies aloud', exact=True).check()
    assert page.evaluate('window.__spoken.length') == count, 'Enabling TTS replayed a muted reply'
    for width in [320, 390, 768, 1440]:
        page.set_viewport_size({'width': width, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
    assert not errors, errors
    browser.close()
print('PASS: deleted-workspace recovery; empty-day setup; Gemini voice planning; no placeholder TTS; no language-change cutoff; trailing interim words retained; permission errors; muted reply tracking; 320-1440px; no browser exceptions.')
