import { useState } from 'react';
import type { FormEvent } from 'react';
import './UtteranceBar.css';
import VoiceInput from './VoiceInput';

export interface UtteranceBarProps {
  onSubmit: (utterance: string) => void;
  onVoiceStart?: () => void;
  reply?: string;
  loading?: boolean;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}

/** Collect a text instruction and submit it to the parent surface. */
export function UtteranceBar({ onSubmit, loading = false, placeholder = 'What would you like to plan?', disabled = false, className = '', onVoiceStart = () => {}, reply = '' }: UtteranceBarProps) {
  const [utterance, setUtterance] = useState('');
  const [listening, setListening] = useState(false);
  const unavailable = loading || disabled;

  /** Ignore blank or unavailable submissions and clear accepted instructions. */
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = utterance.trim();
    if (unavailable || listening || !message) return;
    onSubmit(message);
    setUtterance('');
  }

  return (
    <div className="utterance-bar-container">
      <form className={`utterance-bar ${loading ? 'utterance-bar--ambient' : ''} ${className}`} onSubmit={handleSubmit} aria-label="Send an instruction" aria-busy={loading}>
        <input id="utterance-input" type="text" maxLength={1000} aria-label="Your instruction" placeholder={placeholder} value={utterance} onChange={(event) => setUtterance(event.target.value)} disabled={unavailable || listening} />
        <button id="utterance-submit-btn" type="submit" disabled={unavailable || listening || !utterance.trim()}>
          {loading && <span className="utterance-bar__spinner" aria-hidden="true" />}
          {loading ? 'Thinking…' : 'Send'}
        </button>
      </form>
      <VoiceInput value={utterance} onChange={setUtterance} onSend={message => { onSubmit(message); setUtterance(''); }} onStart={onVoiceStart} onListeningChange={setListening} disabled={unavailable} reply={reply} />
    </div>
  );
}

export default UtteranceBar;
