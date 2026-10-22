import { useId, useEffect } from 'react';
import './PlanPreview.css';
import ScheduleTimeline from './ScheduleTimeline';
import type { ScheduleBlock } from './ScheduleTimeline';

export interface DiffItemKept {
  block_id?: string;
  title: string;
}

export interface DiffItemMoved extends DiffItemKept {
  old_start?: string;
  new_start?: string;
}

export interface DiffItemShortened extends DiffItemKept {
  old_duration_min?: number;
  new_duration_min?: number;
}

export interface DiffItemLengthened extends DiffItemKept {
  old_duration_min?: number;
  new_duration_min?: number;
}

export interface DiffItemDropped extends DiffItemKept {
  reason?: string;
}

export interface DiffItemAdded {
  title: string;
  start_time: string;
  end_time: string;
}

export interface DiffSummary {
  kept?: DiffItemKept[];
  moved?: DiffItemMoved[];
  shortened?: DiffItemShortened[];
  lengthened?: DiffItemLengthened[];
  dropped?: DiffItemDropped[];
  added?: DiffItemAdded[];
}

export interface PlanPreviewProps {
  planId?: string | null;
  explanation?: string | null;
  diff?: DiffSummary | null;
  visible?: boolean;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  className?: string;
  proposedBlocks?: ScheduleBlock[];
}

/** Preserve the supplied timezone's clock time, or an existing time label. */
function formatTime(value?: string): string {
  if (!value) return '—';
  return value.match(/(?:T|\s|^)(\d{2}:\d{2})(?::\d{2})?/)?.[1] ?? value;
}

/** Present a proposal for approval without fetching or mutating schedule data. */
export function PlanPreview({
  planId, explanation, diff, visible = true, loading = false,
  onConfirm, onCancel, className, proposedBlocks,
}: PlanPreviewProps) {
  const headingId = useId();

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape' && planId && !loading) {
        onCancel();
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [loading, onCancel, planId]);

  if (!visible || !planId || (!diff && !explanation)) return null;

  const sections = [
    { key: 'kept', label: 'Unchanged', icon: '✓', items: diff?.kept?.map(item => ({ ...item, detail: '' })) },
    { key: 'moved', label: 'Moved', icon: '→', items: diff?.moved?.map(item => ({
      ...item, detail: `(${formatTime(item.old_start)} → ${formatTime(item.new_start)})`,
    })) },
    { key: 'shortened', label: 'Shortened', icon: '↓', items: diff?.shortened?.map(item => ({
      ...item, detail: `(${item.old_duration_min ?? '—'} min → ${item.new_duration_min ?? '—'} min)`,
    })) },
    { key: 'lengthened', label: 'Lengthened', icon: '↑', items: diff?.lengthened?.map(item => ({
      ...item, detail: `(${item.old_duration_min ?? '—'} min → ${item.new_duration_min ?? '—'} min)`,
    })) },
    { key: 'dropped', label: 'Removed from calendar', icon: '✗', items: diff?.dropped?.map(item => ({
      ...item, detail: item.reason ?? '',
    })) },
    { key: 'added', label: 'Added', icon: '+', items: diff?.added?.map(item => ({
      ...item, block_id: undefined, detail: `(${formatTime(item.start_time)} – ${formatTime(item.end_time)})`,
    })) },
  ];

  return (
    <section className={['plan-preview', className].filter(Boolean).join(' ')} aria-labelledby={headingId} aria-busy={loading}>
      <header className="plan-preview__header">
        <h2 id={headingId}>Review your new plan</h2>
        <span className="plan-preview__status">Proposed</span>
      </header>
      {explanation && <blockquote className="plan-preview__explanation">{explanation}</blockquote>}
      <div className="plan-preview__diff">
        {sections.filter(section => section.items?.length).map(section => (
          <section className={`plan-preview__section plan-preview__section--${section.key}`} key={section.key}>
            <h3>{section.label}</h3>
            <ul>
              {section.items?.map((item, index) => (
                <li key={`${item.block_id ?? item.title}-${index}`}>
                  <span className="plan-preview__icon" aria-hidden="true">{section.icon}</span>
                  <span className="plan-preview__item">
                    <span className="plan-preview__title">{item.title}</span>
                    {item.detail && <span className="plan-preview__detail">{item.detail}</span>}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
      <p className="plan-preview__assurance">Your calendar is unchanged. Confirm to save exactly this proposal, or cancel to keep your current day.</p>
      {proposedBlocks && <details className="proposed-timeline"><summary>View the complete proposed timeline</summary><ScheduleTimeline blocks={proposedBlocks} /></details>}
      <div className="plan-preview__actions">
        <button type="button" id="confirm-plan-btn" className="plan-preview__confirm" disabled={loading} onClick={onConfirm}>Confirm plan</button>
        <button type="button" id="cancel-plan-btn" className="plan-preview__cancel" disabled={loading} onClick={onCancel}>Cancel</button>
      </div>
    </section>
  );
}

export default PlanPreview;
