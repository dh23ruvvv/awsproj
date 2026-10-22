import './ResponseLine.css';

export interface ResponseLineProps {
  text?: string | null;
  loading?: boolean;
  className?: string;
}

/** Preserve every part of the agent response, including warnings and tradeoffs. */
export function ResponseLine({ text, loading = false, className = '' }: ResponseLineProps) {
  return <div className={`response-line ${loading ? 'response-line--loading' : ''} ${className}`} role="status" aria-live="polite" aria-atomic="true">
    {loading ? <><span className="response-line__pulse" aria-hidden="true" /><span>Working on your request?</span></> : <p className="response-line__intro" style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{text || 'Ready for your instructions.'}</p>}
  </div>;
}

export default ResponseLine;
