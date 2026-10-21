import './ModeBadge.css';

export interface ModeBadgeProps {
  provider?: string | null;
  degraded?: boolean;
  className?: string;
  onToggle?: () => void;
}

/** Keep the effective provider visible, with fallback taking precedence and optional interactive toggle. */
export function ModeBadge({ provider, degraded = false, className = '', onToggle }: ModeBadgeProps) {
  const mode = degraded ? 'fallback' : provider === 'gemini' ? 'live' : 'demo';
  const label = mode === 'fallback' ? 'Deterministic fallback' : mode === 'live' ? 'Live model (Gemini)' : 'Deterministic demo mode';

  if (onToggle) {
    return (
      <button
        type="button"
        className={`mode-badge mode-badge--${mode} mode-badge--clickable ${className}`}
        onClick={onToggle}
        title="Click to switch provider mode"
      >
        <span className="mode-badge__dot" aria-hidden="true" />
        {label}
        <span className="mode-badge__toggle-hint">⇄</span>
      </button>
    );
  }

  return (
    <span className={`mode-badge mode-badge--${mode} ${className}`}>
      <span className="mode-badge__dot" aria-hidden="true" />
      {label}
    </span>
  );
}

export default ModeBadge;
