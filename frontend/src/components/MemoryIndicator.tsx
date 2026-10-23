import './MemoryIndicator.css';

export interface MemoryIndicatorProps {
  summary?: string | null;
  memories?: Array<{ key: string; value: string }> | null;
  visible?: boolean;
  className?: string;
  entries?: Array<{id: string; value: string}>;
  onRemove?: (id: string) => void;
  disabled?: boolean;
}

/** Show remembered context only when supplied by the parent. */
export function MemoryIndicator({ summary, memories, entries, onRemove, disabled, visible = true, className = '' }: MemoryIndicatorProps) {
  const context = summary?.trim() || memories?.map(({ key, value }) => `${key}: ${value}`).join('; ');
  if (!visible || !context) return null;
  if (entries?.length) return <section className={`memory-indicator ${className}`} aria-label="Saved preferences">
    <div><strong>Preferences for this day</strong><ul>{entries.map(entry => <li key={entry.id}>{entry.value}
      {onRemove && <button type="button" disabled={disabled} aria-label={`Forget preference: ${entry.value}`} onClick={() => onRemove(entry.id)}>Forget</button>}
    </li>)}</ul></div>
  </section>;
  return (
    <span className={`memory-indicator ${className}`}>
      <span aria-hidden="true">✦</span>
      <span>Remembered: {context}</span>
    </span>
  );
}

export default MemoryIndicator;
