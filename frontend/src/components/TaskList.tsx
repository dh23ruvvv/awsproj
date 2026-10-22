import { useState } from 'react';
import './TaskList.css';

export interface TaskItem {
  id: string;
  title: string;
  duration_minutes: number;
  deadline?: string | null;
  priority?: string;
  category?: string;
  status?: string;
}

export interface TaskListProps {
  tasks: TaskItem[];
  className?: string;
  disabled?: boolean;
  onEdit?: (task: TaskItem) => void;
  onDelete?: (task: TaskItem) => void;
}

function formatTime(isoString?: string | null): string | null {
  if (!isoString) return null;
  const match = isoString.match(/(?:T|\s|^)(\d{2}:\d{2})/);
  if (!match) return null;
  const [hourStr, minStr] = match[1].split(':');
  let hour = parseInt(hourStr, 10);
  const ampm = hour >= 12 ? 'PM' : 'AM';
  hour = hour % 12 || 12;
  return `${hour}:${minStr} ${ampm}`;
}

function getTaskIcon(title: string, category?: string): string {
  const t = title.toLowerCase();
  const c = category?.toLowerCase();
  if (t.includes('report') || t.includes('draft') || c === 'work') return '📄';
  if (t.includes('pr') || t.includes('review') || t.includes('code')) return '🔍';
  if (t.includes('standup') || t.includes('meeting') || t.includes('1-on-1') || c === 'meeting') return '👥';
  if (t.includes('grocery') || t.includes('shopping')) return '🛒';
  if (t.includes('gym') || t.includes('workout') || t.includes('exercise')) return '🏋️';
  if (t.includes('lunch') || t.includes('dinner')) return '🥗';
  return '📌';
}

export function TaskList({ tasks, onEdit, onDelete, disabled, className = '' }: TaskListProps) {
  const [filter, setFilter] = useState<'all' | 'pending' | 'scheduled'>('all');

  const pendingCount = tasks.filter(t => t.status === 'pending').length;
  const scheduledCount = tasks.filter(t => t.status === 'scheduled').length;

  const filteredTasks = tasks.filter(t => {
    if (filter === 'pending') return t.status === 'pending';
    if (filter === 'scheduled') return t.status === 'scheduled';
    return true;
  });

  return (
    <div className={`task-list-view ${className}`} role="region" aria-label="Tasks and remaining items">
      <header className="task-list-view__header">
        <div className="task-list-view__title-row">
          <h2>Your tasks</h2>
          <span className="task-list-view__badge">{pendingCount} pending</span>
        </div>
        <div className="task-list-view__filters" role="tablist" aria-label="Filter tasks">
          <button
            type="button"
            role="tab"
            aria-selected={filter === 'all'}
            className={`task-list-filter ${filter === 'all' ? 'task-list-filter--active' : ''}`}
            onClick={() => setFilter('all')}
          >
            All ({tasks.length})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={filter === 'pending'}
            className={`task-list-filter ${filter === 'pending' ? 'task-list-filter--active' : ''}`}
            onClick={() => setFilter('pending')}
          >
            Pending ({pendingCount})
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={filter === 'scheduled'}
            className={`task-list-filter ${filter === 'scheduled' ? 'task-list-filter--active' : ''}`}
            onClick={() => setFilter('scheduled')}
          >
            Scheduled ({scheduledCount})
          </button>
        </div>
      </header>

      {filteredTasks.length === 0 ? (
        <div className="task-list-view__empty">
          <p>No {filter === 'all' ? '' : filter} tasks found.</p>
        </div>
      ) : (
        <ul className="task-list-view__items">
          {filteredTasks.map(task => {
            const isPending = task.status === 'pending';
            const deadlineTime = formatTime(task.deadline);
            const icon = getTaskIcon(task.title, task.category);
            const priorityClass = task.priority ? `task-priority--${task.priority.toLowerCase()}` : '';

            return (
              <li
                key={task.id}
                className={`task-item ${isPending ? 'task-item--pending' : 'task-item--scheduled'}`}
              >
                <div className="task-item__main">
                  <span className="task-item__icon" aria-hidden="true">{icon}</span>
                  <div className="task-item__content">
                    <div className="task-item__header-line">
                      <span className="task-item__title">{task.title}</span>
                      {task.priority && (
                        <span className={`task-badge task-badge--priority ${priorityClass}`}>
                          {task.priority}
                        </span>
                      )}
                    </div>
                    <div className="task-item__meta">
                      <span className="task-badge task-badge--duration">⏱️ {task.duration_minutes}m</span>
                      {deadlineTime && (
                        <span className="task-badge task-badge--deadline">🏁 by {deadlineTime}</span>
                      )}
                      <span className={`task-badge task-badge--status ${isPending ? 'status-pending' : 'status-scheduled'}`}>
                        {isPending ? '⏳ Not Scheduled' : '✓ Scheduled'}
                      </span>
                    </div>
                  </div>
                </div>

                {isPending && <div className="task-item__controls">
                  {onEdit && <button type="button" disabled={disabled} onClick={() => onEdit(task)} aria-label={`Edit ${task.title}`}>Edit</button>}
                  {onDelete && <button type="button" disabled={disabled} onClick={() => onDelete(task)} aria-label={`Remove ${task.title}`}>Remove</button>}
                </div>}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export default TaskList;
