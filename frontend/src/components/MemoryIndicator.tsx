import './MemoryIndicator.css';

export interface MemoryIndicatorProps {
  summary?: string | null;
  memories?: Array<{ key: string; value: string }> | null;
  visible?: boolean;
  className?: string;
}

/** Show remembered context only when supplied by the parent. */
export function MemoryIndicator({ summary, memories, visible = true, className = '' }: MemoryIndicatorProps) {
  const context = summary?.trim() || memories?.map(({ key, value }) => `${key}: ${value}`).join('; ');
  if (!visible || !context) return null;
  return (
    <span className={`memory-indicator ${className}`}>
      <span aria-hidden="true">✦</span>
      <span>Remembered: {context}</span>
    </span>
  );
}

export default MemoryIndicator;
