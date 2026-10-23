import { useEffect, useRef, useState } from 'react';

interface RecognitionResult { isFinal: boolean; 0: { transcript: string } }
interface Recognition {
  lang: string; continuous: boolean; interimResults: boolean;
  onresult: ((event: { results: ArrayLike<RecognitionResult> }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void; stop(): void; abort(): void;
}
type SpeechWindow = Window & { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition };

/** Push-to-talk with an editable transcript; microphone input cannot approve drafts. */
export default function VoiceInput({ value, onChange, onSend, onStart, disabled, reply, onListeningChange }: {
  value: string; onChange: (value: string) => void; onSend: (value: string) => void;
  onStart: () => void; disabled: boolean; reply: string; onListeningChange: (listening: boolean) => void;
}) {
  const [listening, setListening] = useState(false);
  const [notice, setNotice] = useState('');
  const [language, setLanguage] = useState('en-IN');
  const [autoSend, setAutoSend] = useState(false);
  const [readAloud, setReadAloud] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const lastSpoken = useRef(reply);
  useEffect(() => { onListeningChange(listening); }, [listening, onListeningChange]);
  const recognition = useRef<Recognition | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const aborted = useRef(false);
  const callbacks = useRef({onChange, onSend, autoSend, disabled});
  callbacks.current = {onChange, onSend, autoSend, disabled};
  const Speech = (window as SpeechWindow).SpeechRecognition ?? (window as SpeechWindow).webkitSpeechRecognition;
  const supported = !!Speech && window.isSecureContext;

  useEffect(() => () => {
    aborted.current = true;
    if (recognition.current) { recognition.current.onend = null; recognition.current.onresult = null; recognition.current.onerror = null; recognition.current.abort(); }
    clearTimeout(timer.current);
    window.speechSynthesis?.cancel();
  }, []);

  useEffect(() => {
    if (disabled && recognition.current) { aborted.current = true; recognition.current.abort(); setListening(false); clearTimeout(timer.current); }
  }, [disabled]);

  useEffect(() => {
    if (!reply) return;
    if (!readAloud) { lastSpoken.current = reply; return; }
    if (listening || !window.speechSynthesis || lastSpoken.current === reply) return;
    lastSpoken.current = reply;
    window.speechSynthesis.cancel();
    const speech = new SpeechSynthesisUtterance(reply.slice(0, 1500));
    speech.lang = language;
    speech.onstart = () => setSpeaking(true);
    speech.onend = speech.onerror = () => setSpeaking(false);
    window.speechSynthesis.speak(speech);
  }, [reply, readAloud, language, listening]);

  function start() {
    if (!Speech || disabled || recognition.current) return;
    window.speechSynthesis?.cancel();
    const engine = new Speech();
    recognition.current = engine;
    aborted.current = false;
    engine.lang = language; engine.continuous = false; engine.interimResults = true;
    let finalText = '';
    let latestHeard = '';
    const prefix = value.trim();
    engine.onresult = event => {
      if (aborted.current) return;
      const results = Array.from(event.results);
      const heard = results.map(result => result[0].transcript).join(' ').trim();
      latestHeard = heard;
      finalText = results.filter(result => result.isFinal).map(result => result[0].transcript).join(' ').trim();
      const text = [prefix, heard].filter(Boolean).join(' ');
      if (text.length > 1000) {
        aborted.current = true; engine.abort();
        setNotice('The instruction is too long. Shorten it to 1,000 characters before sending.');
      }
      callbacks.current.onChange(text.slice(0, 1000));
    };
    engine.onerror = event => {
      aborted.current = true;
      const messages: Record<string, string> = {
        'not-allowed': 'Microphone permission was denied. Allow it in browser settings, or type your request.',
        'service-not-allowed': 'Speech recognition is blocked by this browser. You can still type.',
        'audio-capture': 'No microphone is available. Check your input device, or type instead.',
        'no-speech': 'No speech was detected. Try again, or type your request.',
        'network': 'The speech service could not connect. Check your connection, or type instead.',
        'language-not-supported': 'This speech language is unavailable. Choose another language or type.',
      };
      setNotice(messages[event.error] ?? 'Voice input stopped. Your transcript remains editable.');
    };
    engine.onend = () => {
      recognition.current = null; clearTimeout(timer.current); setListening(false);
      if (aborted.current) return;
      const transcript = finalText || latestHeard;
      if (!transcript) { setNotice('No transcript received. Try again or type your request.'); return; }
      const text = [prefix, transcript].filter(Boolean).join(' ');
      callbacks.current.onChange(text);
      if (callbacks.current.autoSend && !callbacks.current.disabled) {
        setNotice('Transcript sent to Gemini. Any proposed changes still need your approval.');
        callbacks.current.onSend(text);
      } else setNotice('Review or edit the transcript above, then press Send.');
    };
    try {
      engine.start(); onStart(); setListening(true); setNotice('Listening. Speak your request, then press Stop.');
      timer.current = setTimeout(() => engine.stop(), 45000);
    } catch {
      recognition.current = null; setListening(false); setNotice('Voice input could not start. Try again or type your request.');
    }
  }

  return <div className="voice-controls">
    <div className="voice-actions">
      <button type="button" onClick={() => listening ? recognition.current?.stop() : start()} disabled={disabled || !supported} aria-pressed={listening}>{listening ? 'Stop listening' : 'Speak to Gemini'}</button>
      <label>Speech language<select aria-label="Speech language" value={language} disabled={listening || disabled} onChange={e => setLanguage(e.target.value)}><option value="en-IN">English (India)</option><option value="en-US">English (US)</option><option value="hi-IN">Hindi</option></select></label>
    </div>
    <div className="voice-options">
      <label><input type="checkbox" checked={autoSend} disabled={listening || disabled} onChange={e => setAutoSend(e.target.checked)} />Send after speaking</label>
      <label><input type="checkbox" checked={readAloud} disabled={!window.speechSynthesis} onChange={e => setReadAloud(e.target.checked)} />Read replies aloud</label>
      {speaking && <button type="button" onClick={() => { setReadAloud(false); window.speechSynthesis.cancel(); }}>Stop reading</button>}
    </div>
    <p>Voice switches to Gemini. Your browser's speech service may process audio; FlowPilot sends the transcript to the planner. Listening stops after 45 seconds.</p>
    {!supported && <p>Voice recognition is unavailable here. Use a supported browser on HTTPS or localhost, or type above.</p>}
    <p role="status" aria-live="polite">{notice}</p>
  </div>;
}
