import './ResponseLine.css';

export interface ResponseLineProps {
  text?: string | null;
  loading?: boolean;
  className?: string;
}

interface ParsedItem {
  id: string;
  title: string;
  tag?: string;
  category?: 'work' | 'meeting' | 'personal' | 'general';
}

interface ParsedResponse {
  intro: string;
  items: ParsedItem[];
}

function getItemCategory(title: string): 'work' | 'meeting' | 'personal' | 'general' {
  const t = title.toLowerCase();
  if (t.includes('report') || t.includes('pr review') || t.includes('code') || t.includes('review') || t.includes('draft')) {
    return 'work';
  }
  if (t.includes('standup') || t.includes('1-on-1') || t.includes('sync') || t.includes('meeting')) {
    return 'meeting';
  }
  if (t.includes('grocery') || t.includes('gym') || t.includes('lunch') || t.includes('workout')) {
    return 'personal';
  }
  return 'general';
}

function getItemIcon(title: string, category: string): string {
  const t = title.toLowerCase();
  if (t.includes('report') || t.includes('draft')) return '📄';
  if (t.includes('pr') || t.includes('review')) return '🔍';
  if (t.includes('standup') || t.includes('sync')) return '👥';
  if (t.includes('1-on-1')) return '🤝';
  if (t.includes('grocery') || t.includes('shopping')) return '🛒';
  if (t.includes('gym') || t.includes('workout')) return '🏋️';
  if (t.includes('lunch')) return '🥗';
  if (category === 'work') return '💼';
  return '📌';
}

function parseItemContent(raw: string, idx: number): ParsedItem {
  let cleaned = raw.trim();
  let tag: string | undefined;

  // Extract parenthetical info e.g. (Deadline: 5:00 PM) or (at 2:30 PM)
  const parenMatch = cleaned.match(/\(([^)]+)\)$/);
  if (parenMatch) {
    tag = parenMatch[1].trim();
    cleaned = cleaned.replace(/\s*\([^)]+\)$/, '').trim();
  } else {
    // Extract "at 2:30 PM" or "by 5:00 PM"
    const atMatch = cleaned.match(/\s+(at\s+\d{1,2}(?::\d{2})?\s*(?:AM|PM)?|by\s+\d{1,2}(?::\d{2})?\s*(?:AM|PM)?)$/i);
    if (atMatch) {
      tag = atMatch[1].trim();
      cleaned = cleaned.replace(atMatch[0], '').trim();
    }
  }

  const category = getItemCategory(cleaned);
  return {
    id: `item-${idx}-${cleaned.slice(0, 10)}`,
    title: cleaned,
    tag,
    category,
  };
}

function parseResponse(rawText?: string | null): ParsedResponse {
  const text = rawText?.trim() || '';
  if (!text) {
    return { intro: 'Ready for your instructions.', items: [] };
  }

  // 1. Check for multiline with bullet points / dashes / numbers
  const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
  const bulletLines = lines.filter(l => /^[-*•\d+\.]\s+/.test(l));

  if (bulletLines.length > 0) {
    const firstBulletIdx = lines.findIndex(l => /^[-*•\d+\.]\s+/.test(l));
    const intro = firstBulletIdx > 0 ? lines.slice(0, firstBulletIdx).join(' ') : 'Remaining schedule & tasks:';
    const items = bulletLines.map((line, idx) => {
      const clean = line.replace(/^[-*•\d+\.]\s+/, '').trim();
      return parseItemContent(clean, idx);
    });
    return { intro, items };
  }

  // 2. Check for colon-separated list of items e.g. "You have five pending tasks for today: Task 1, Task 2..."
  const colonMatch = text.match(/^([^:]+):\s*(.+)$/s);
  if (colonMatch) {
    const potentialIntro = colonMatch[1].trim();
    const rest = colonMatch[2].trim();
    const isListPhrase = /\b(pending|tasks|remaining|left|schedule|items|to-do|todo|following|list)\b/i.test(potentialIntro);

    const parts = rest
      .replace(/\.\s*$/, '')
      .split(/(?:;\s*|,\s*(?:and\s+)?|\s+and\s+)/i)
      .map(s => s.trim())
      .filter(s => s.length > 1);

    if (parts.length >= 2 || (isListPhrase && parts.length >= 1)) {
      const items = parts.map((part, idx) => parseItemContent(part, idx));
      return { intro: `${potentialIntro}:`, items };
    }
  }

  return { intro: text, items: [] };
}

/** Announce the current response with structured list views for task/schedule queries. */
export function ResponseLine({ text, loading = false, className = '' }: ResponseLineProps) {
  if (loading) {
    return (
      <div className={`response-line response-line--loading ${className}`} role="status" aria-live="polite">
        <span className="response-line__pulse" aria-hidden="true" />
        <span>FlowPilot is thinking…</span>
      </div>
    );
  }

  const { intro, items } = parseResponse(text);

  return (
    <div
      className={`response-line ${items.length > 0 ? 'response-line--has-list' : ''} ${className}`}
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      <p className="response-line__intro">{intro}</p>

      {items.length > 0 && (
        <div className="response-list-container">
          <div className="response-list-header">
            <span className="response-list-badge">{items.length} {items.length === 1 ? 'task' : 'tasks'}</span>
            <span className="response-list-tag">Active View</span>
          </div>
          <ul className="response-task-cards">
            {items.map(item => {
              const icon = getItemIcon(item.title, item.category || 'general');
              return (
                <li key={item.id} className={`response-task-card response-task-card--${item.category}`}>
                  <span className="response-task-card__icon" aria-hidden="true">{icon}</span>
                  <div className="response-task-card__body">
                    <span className="response-task-card__title">{item.title}</span>
                    {item.tag && (
                      <span className="response-task-card__tag">
                        {item.tag.startsWith('at ') || item.tag.startsWith('by ') ? '🕒 ' : '⏱️ '}
                        {item.tag}
                      </span>
                    )}
                  </div>
                  <span className="response-task-card__status">To Do</span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}

export default ResponseLine;
