import { useState } from 'react';
import type { FormEvent } from 'react';
import './UtteranceBar.css';

export interface UtteranceBarProps {
  onSubmit: (utterance: string) => void;
  loading?: boolean;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
}

/** Collect a text instruction and submit it to the parent surface. */
export function UtteranceBar({ onSubmit, loading = false, placeholder = 'What would you like to plan?', disabled = false, className = '' }: UtteranceBarProps) {
  const [utterance, setUtterance] = useState('');
  const unavailable = loading || disabled;

  /** Ignore blank or unavailable submissions and clear accepted instructions. */
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = utterance.trim();
    if (unavailable || !message) return;
    onSubmit(message);
    setUtterance('');
  }

  return (
    <form className={`utterance-bar ${className}`} onSubmit={handleSubmit} aria-label="Send an instruction" aria-busy={loading}>
      <input id="utterance-input" type="text" aria-label="Your instruction" placeholder={placeholder} value={utterance} onChange={(event) => setUtterance(event.target.value)} disabled={unavailable} />
      <button id="utterance-submit-btn" type="submit" disabled={unavailable || !utterance.trim()}>
        {loading && <span className="utterance-bar__spinner" aria-hidden="true" />}
        {loading ? 'Thinking…' : 'Send'}
      </button>
    </form>
  );
}

export default UtteranceBar;
