import './ScheduleTimeline.css';

/** A committed calendar block supplied by the parent application. */
export interface ScheduleBlock {
  id?: string;
  title: string;
  start_time: string;
  end_time: string;
  immutable?: boolean | number;
  task_id?: string | null;
  status?: string;
  category?: 'work' | 'personal' | 'meeting' | string;
}

/** Timeline data and optional externally controlled clock. */
export interface ScheduleTimelineProps {
  blocks: ScheduleBlock[];
  currentTime?: string;
  className?: string;
}

const categories = ['work', 'meeting', 'personal', 'buffer'] as const;
type Category = (typeof categories)[number];

/** Respect explicit categories, otherwise apply title rules in priority order. */
function categoryFor(block: ScheduleBlock): Category {
  if (block.category) {
    return categories.find((category) => category === block.category) ?? 'work';
  }
  const title = block.title.toLowerCase();
  const keywords: Record<Category, string[]> = {
    work: ['report', 'pr review', 'work', 'planning'],
    meeting: ['standup', 'sync', '1-on-1', 'meeting', 'review'],
    personal: ['gym', 'grocery', 'lunch', 'personal', 'errand'],
    buffer: ['buffer', 'overflow'],
  };
  return categories.find((category) => keywords[category].some((word) => title.includes(word))) ?? 'work';
}

/** Parse ISO timestamps or time-only strings without consulting the real clock. */
function timestamp(value: string): number {
  return /^\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/.test(value)
    ? Date.parse(`1970-01-01T${value}Z`)
    : Date.parse(value);
}

/** Keep the supplied schedule's wall-clock labels independent of browser timezone. */
function timeLabel(value: string): string {
  return value.match(/(?:T|\s|^)(\d{2}:\d{2})/)?.[1] ?? '—';
}

/** Render a responsive, read-only view of the committed schedule. */
export function ScheduleTimeline({ blocks, currentTime, className }: ScheduleTimelineProps) {
  const now = currentTime ? timestamp(currentTime) : Number.NaN;
  const orderedBlocks = [...blocks].sort((a, b) => timestamp(a.start_time) - timestamp(b.start_time));

  return (
    <section className={['schedule-timeline', className].filter(Boolean).join(' ')} role="region" aria-label="Today's Schedule">
      <header className="schedule-timeline__header">
        <h2>Today's Schedule</h2>
        {Number.isFinite(now) && currentTime && (
          <span className="schedule-timeline__clock">
            <span className="schedule-timeline__clock-dot" aria-hidden="true" />
            Now <time dateTime={currentTime}>{timeLabel(currentTime)}</time>
          </span>
        )}
      </header>
      {blocks.length === 0 ? (
        <p className="schedule-timeline__empty">No scheduled events for today.</p>
      ) : (
        <ol className="schedule-timeline__list">
          {orderedBlocks.map((block, index) => {
            const start = timestamp(block.start_time);
            const end = timestamp(block.end_time);
            const completed = block.status === 'completed' || end <= now;
            const active = !completed && start <= now && now < end;
            const category = categoryFor(block);
            const duration = Math.round((end - start) / 60000);
            return (
              <li key={block.id ?? `${block.start_time}-${block.title}-${index}`} className={`schedule-timeline__item${completed ? ' schedule-timeline__item--completed' : ''}`}>
                <div className="schedule-timeline__time">
                  <span><time dateTime={block.start_time}>{timeLabel(block.start_time)}</time> – <time dateTime={block.end_time}>{timeLabel(block.end_time)}</time></span>
                  {Number.isFinite(duration) && duration >= 0 && <span className="schedule-timeline__duration">{duration}m</span>}
                </div>
                <article className={`schedule-timeline__card schedule-timeline__card--${category}${active ? ' schedule-timeline__card--active' : ''}`} aria-current={active ? 'time' : undefined}>
                  <h3>{block.title}</h3>
                  <div className="schedule-timeline__badges">
                    <span className="schedule-timeline__category">{category.charAt(0).toUpperCase() + category.slice(1)}</span>
                    {completed && <span>✓ Completed</span>}
                    {Boolean(block.immutable) && <span>Protected</span>}
                    {active && <span>In progress</span>}
                  </div>
                </article>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

export default ScheduleTimeline;
