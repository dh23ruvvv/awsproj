import { useState } from 'react';
import type { ScheduleBlock } from './ScheduleTimeline';
import PixelText from './PixelText';

export type ScaleMode = '0-90' | 'fit';
export type ViewMode = 'blocks' | 'timeline';

function parseClockMinutes(value: string): number {
  if (!value) return 0;
  const timeStr = value.includes('T') ? value.slice(value.indexOf('T') + 1) : value;
  const match = timeStr.match(/^(\d{1,2}):(\d{2})/);
  if (match) {
    return Number(match[1]) * 60 + Number(match[2]);
  }
  return 0;
}

function formatSlotTime(minutesFromMidnight: number): string {
  const h = Math.floor(minutesFromMidnight / 60);
  const m = minutesFromMidnight % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

function getTicksForScale(scaleMax: number): number[] {
  if (scaleMax <= 30) return [30, 15, 0];
  if (scaleMax <= 60) return [60, 30, 0];
  if (scaleMax <= 90) return [90, 60, 30, 0];
  if (scaleMax <= 120) return [120, 90, 60, 30, 0];
  const step = scaleMax > 180 ? 60 : 30;
  const ticks: number[] = [];
  for (let val = scaleMax; val >= 0; val -= step) {
    ticks.push(val);
  }
  if (ticks[ticks.length - 1] !== 0) {
    ticks.push(0);
  }
  return ticks;
}

/**
 * Visualize your day in blocks:
 * - Blocks view (default): each bar represents an actual scheduled block; height = duration.
 * - Timeline view: hourly calendar load across the active day (from morning through night).
 */
export default function DayLoad({ blocks }: { blocks: ScheduleBlock[] }) {
  const [viewMode, setViewMode] = useState<ViewMode>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('flowpilot_dayload_view');
      if (saved === 'blocks' || saved === 'timeline') return saved;
    }
    return 'blocks';
  });

  const [scaleMode, setScaleMode] = useState<ScaleMode>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('flowpilot_dayload_scale');
      if (saved === '0-90' || saved === 'fit') return saved;
    }
    return '0-90';
  });

  // Sort blocks chronologically
  const sortedBlocks = [...blocks].map((block) => {
    const start = parseClockMinutes(block.start_time);
    const end = parseClockMinutes(block.end_time);
    const duration = Math.max(0, end - start);
    return {
      ...block,
      startMinutes: start,
      endMinutes: end,
      duration,
      timeLabel: `${formatSlotTime(start)}–${formatSlotTime(end)}`,
    };
  }).sort((a, b) => a.startMinutes - b.startMinutes);

  const totalMinutes = sortedBlocks.reduce((acc, b) => acc + b.duration, 0);

  // Dynamic hourly timeline spanning from the earliest event (or 9:00) to latest event (or 17:00 / 24:00)
  const earliestHour = sortedBlocks.length > 0
    ? Math.min(9, Math.floor(Math.min(...sortedBlocks.map((b) => b.startMinutes)) / 60))
    : 9;
  const latestHour = sortedBlocks.length > 0
    ? Math.max(17, Math.ceil(Math.max(...sortedBlocks.map((b) => b.endMinutes)) / 60))
    : 17;
  const totalHours = Math.max(8, latestHour - earliestHour);

  const hourlySlots = Array.from({ length: totalHours }, (_, i) => {
    const start = (earliestHour + i) * 60;
    const end = start + 60;
    const minutes = blocks.reduce((sum, block) => {
      const bStart = parseClockMinutes(block.start_time);
      const bEnd = parseClockMinutes(block.end_time);
      return sum + Math.max(0, Math.min(bEnd, end) - Math.max(bStart, start));
    }, 0);
    return { start, minutes };
  });

  // Calculate max value based on active view mode
  const maxVal = viewMode === 'blocks'
    ? Math.max(0, ...sortedBlocks.map((b) => b.duration))
    : Math.max(0, ...hourlySlots.map((s) => s.minutes));

  let scaleMax = 90;
  if (scaleMode === '0-90') {
    // 0-90m baseline scale; dynamically auto-adjusts higher if any bar exceeds 90m
    scaleMax = Math.max(90, Math.ceil(maxVal / 30) * 30);
  } else {
    // Tight auto-fit to longest bar
    scaleMax = Math.max(30, Math.ceil(maxVal / 30) * 30);
  }

  const ticks = getTicksForScale(scaleMax);
  const intermediateTicks = ticks.filter((t) => t > 0 && t < scaleMax);

  const toggleViewMode = () => {
    setViewMode((prev) => {
      const next: ViewMode = prev === 'blocks' ? 'timeline' : 'blocks';
      try { localStorage.setItem('flowpilot_dayload_view', next); } catch { /* ignore */ }
      return next;
    });
  };

  const cycleScaleMode = () => {
    setScaleMode((prev) => {
      const next: ScaleMode = prev === '0-90' ? 'fit' : '0-90';
      try { localStorage.setItem('flowpilot_dayload_scale', next); } catch { /* ignore */ }
      return next;
    });
  };

  const scaleModeLabel = scaleMode === '0-90'
    ? scaleMax > 90 ? `0–90m (Auto ${scaleMax}m)` : '0–90m'
    : `Auto (${scaleMax}m)`;

  return (
    <section className="day-load" aria-label="Committed calendar occupancy">
      <div className="panel-title">
        <div>
          <h2><PixelText>YOUR DAY, IN BLOCKS</PixelText></h2>
          <p>
            {sortedBlocks.length > 0
              ? `${sortedBlocks.length} block${sortedBlocks.length === 1 ? '' : 's'} · ${Math.floor(totalMinutes / 60)}h ${totalMinutes % 60}m committed`
              : 'No commitments scheduled yet'}
          </p>
        </div>
        <div className="day-load-actions">
          <button
            type="button"
            className="outline-tag outline-tag--interactive"
            onClick={toggleViewMode}
            title="Switch between Blocks (duration of each event) and Timeline (hourly distribution)"
            aria-label={`Current view: ${viewMode}. Click to switch view.`}
          >
            View: {viewMode === 'blocks' ? 'Blocks' : 'Timeline'}
          </button>
          <button
            type="button"
            className="outline-tag outline-tag--interactive"
            onClick={cycleScaleMode}
            title="Cycle scale: 0–90m (auto-expanding) or Auto-Fit"
            aria-label={`Y-axis scale mode: ${scaleModeLabel}. Click to cycle.`}
          >
            Scale: {scaleModeLabel}
          </button>
          <span className="outline-tag">■ Saved</span>
        </div>
      </div>

      {sortedBlocks.length === 0 ? (
        <div className="day-load-empty" role="status">
          <p><PixelText>NO SCHEDULED BLOCKS YET</PixelText></p>
          <span>Add your tasks or click "+ Add a fixed event" to build your day.</span>
        </div>
      ) : viewMode === 'blocks' ? (
        /* BLOCKS VIEW: Each bar is a block, height is duration in minutes */
        <>
          <div className="occupancy-chart">
            <div
              className="chart-scale"
              role="presentation"
              title={`Scale: 0–${scaleMax}m (click to cycle scale)`}
              onClick={cycleScaleMode}
            >
              {ticks.map((tick) => (
                <span key={tick}>{tick === 0 ? '0' : `${tick}m`}</span>
              ))}
            </div>
            <div className="chart-bars chart-bars--blocks">
              {intermediateTicks.map((tick) => (
                <div
                  key={tick}
                  className="chart-gridline"
                  style={{ bottom: `${(tick / scaleMax) * 100}%` }}
                  aria-hidden="true"
                />
              ))}
              {sortedBlocks.map((block, index) => {
                const heightPercent = scaleMax > 0 ? Math.min(100, (block.duration / scaleMax) * 100) : 0;
                const isProtected = Boolean(block.immutable);
                const categoryClass = block.category ? `day-load-block--${block.category}` : '';
                const protectedClass = isProtected ? 'day-load-block--protected' : '';

                return (
                  <div
                    className={`chart-slot day-load-block ${categoryClass} ${protectedClass}`}
                    key={block.id ?? `${block.start_time}-${index}`}
                    tabIndex={0}
                    aria-label={`${block.title}: ${block.timeLabel}, duration ${block.duration} minutes${isProtected ? ', protected' : ''}`}
                    title={`${block.title}\n${block.timeLabel} · ${block.duration}m${isProtected ? ' (Protected)' : ''}`}
                  >
                    <span style={{ height: `${heightPercent}%` }}>
                      <span className="day-load-block__duration-badge">{block.duration}m</span>
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
          <div className="day-load-block-labels">
            {sortedBlocks.map((block, index) => (
              <div
                className="day-load-block-label"
                key={block.id ?? `${block.start_time}-lbl-${index}`}
                title={`${block.timeLabel} · ${block.title}`}
              >
                <span className="day-load-block-label__time">{formatSlotTime(block.startMinutes)}</span>
                <span className="day-load-block-label__title">{block.title}</span>
              </div>
            ))}
          </div>
        </>
      ) : (
        /* TIMELINE VIEW: Hourly calendar load across the active day */
        <>
          <div className="occupancy-chart">
            <div
              className="chart-scale"
              role="presentation"
              title={`Scale: 0–${scaleMax}m`}
              onClick={cycleScaleMode}
            >
              {ticks.map((tick) => (
                <span key={tick}>{tick === 0 ? '0' : `${tick}m`}</span>
              ))}
            </div>
            <div className="chart-bars">
              {intermediateTicks.map((tick) => (
                <div
                  key={tick}
                  className="chart-gridline"
                  style={{ bottom: `${(tick / scaleMax) * 100}%` }}
                  aria-hidden="true"
                />
              ))}
              {hourlySlots.map((slot) => {
                const heightPercent = scaleMax > 0 ? Math.min(100, (slot.minutes / scaleMax) * 100) : 0;
                const timeLabel = `${formatSlotTime(slot.start)}–${formatSlotTime(slot.start + 60)}`;
                return (
                  <div
                    className="chart-slot"
                    key={slot.start}
                    tabIndex={0}
                    aria-label={`${timeLabel}: ${slot.minutes} minutes scheduled`}
                    title={`${timeLabel} · ${slot.minutes}m scheduled`}
                  >
                    <span style={{ height: `${heightPercent}%` }} />
                  </div>
                );
              })}
            </div>
          </div>
          <div className="chart-labels">
            {Array.from({ length: Math.min(6, totalHours) }, (_, i) => {
              const hourIndex = Math.round((i / (Math.min(6, totalHours) - 1)) * (totalHours - 1));
              const hour = earliestHour + hourIndex;
              return <span key={hour}>{formatSlotTime(hour * 60)}</span>;
            })}
          </div>
        </>
      )}
    </section>
  );
}
