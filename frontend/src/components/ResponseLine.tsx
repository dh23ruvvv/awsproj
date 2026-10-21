import './ResponseLine.css';

export interface ResponseLineProps {
  text?: string | null;
  loading?: boolean;
  className?: string;
}

/** Announce the current response without accumulating a chat transcript. */
export function ResponseLine({ text, loading = false, className = '' }: ResponseLineProps) {
  return (
    <p className={`response-line ${loading ? 'response-line--loading' : ''} ${className}`} role="status" aria-live="polite" aria-atomic="true">
      {loading && <span className="response-line__pulse" aria-hidden="true" />}
      {loading ? 'FlowPilot is thinking…' : text?.trim() || 'Ready for your instructions.'}
    </p>
  );
}

export default ResponseLine;
