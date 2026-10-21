import './ModeBadge.css';

export interface ModeBadgeProps {
  provider?: string | null;
  degraded?: boolean;
  className?: string;
}

/** Keep the effective provider visible, with fallback taking precedence. */
export function ModeBadge({ provider, degraded = false, className = '' }: ModeBadgeProps) {
  const mode = degraded ? 'fallback' : provider === 'gemini' ? 'live' : 'demo';
  const label = mode === 'fallback' ? 'Deterministic fallback' : mode === 'live' ? 'Live model (Gemini)' : 'Deterministic demo mode';
  return (
    <span className={`mode-badge mode-badge--${mode} ${className}`}>
      <span className="mode-badge__dot" aria-hidden="true" />
      {label}
    </span>
  );
}

export default ModeBadge;
