import { useId, useState } from 'react';
import type { ToolTraceItem } from '../api/client';
import './ToolTrace.css';

export interface ToolTraceProps {
  trace?: ToolTraceItem[] | null;
  isOpen?: boolean;
  defaultOpen?: boolean;
  onToggle?: (open: boolean) => void;
  className?: string;
}

/** Display supplied tool executions in a controlled or local accordion. */
export function ToolTrace({ trace, isOpen, defaultOpen = false, onToggle, className = '' }: ToolTraceProps) {
  const [localOpen, setLocalOpen] = useState(defaultOpen);
  const panelId = useId();
  const triggerId = useId();
  const open = isOpen ?? localOpen;
  const items = trace ?? [];

  /** Notify the parent and update expansion only when uncontrolled. */
  function toggle() {
    if (isOpen === undefined) setLocalOpen(!open);
    onToggle?.(!open);
  }

  return (
    <section className={`tool-trace ${className}`} aria-label="Tool execution trace">
      <button className="tool-trace__toggle" id={triggerId} type="button" aria-expanded={open} aria-controls={panelId} onClick={toggle}>
        <span>Tool Execution Trace</span>
        <span className="tool-trace__count">{items.length} {items.length === 1 ? 'tool' : 'tools'}</span>
        <span className={`tool-trace__chevron ${open ? 'tool-trace__chevron--open' : ''}`} aria-hidden="true">⌄</span>
      </button>
      <div id={panelId} role="region" aria-labelledby={triggerId} hidden={!open} className="tool-trace__panel">
        {items.length === 0 ? <p className="tool-trace__empty">No tools executed in this turn</p> : (
          <ol className="tool-trace__list">
            {items.map((item, index) => (
              <li key={`${index}-${item.tool}`} className="tool-trace__item">
                <div className="tool-trace__item-header"><code>{item.tool}</code><span>{item.duration_ms}ms</span></div>
                <dl>
                  <dt>Arguments</dt>
                  <dd><pre>{JSON.stringify(item.args, null, 2)}</pre></dd>
                  <dt>Result</dt>
                  <dd className="tool-trace__result">{item.result_summary || 'No result summary provided.'}</dd>
                </dl>
              </li>
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}

export default ToolTrace;
