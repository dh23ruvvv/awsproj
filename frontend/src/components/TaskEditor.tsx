import { useState } from 'react';
import type { FormEvent } from 'react';
import type { TaskInput } from '../api/client';
import type { TaskItem } from './TaskList';

export default function TaskEditor({ task, offset, busy, onSave, onClose }: {
  task?: TaskItem; offset: string; busy: boolean;
  onSave: (input: TaskInput, id?: string) => Promise<boolean>; onClose: () => void;
}) {
  const [title, setTitle] = useState(task?.title ?? '');
  const [duration, setDuration] = useState(task?.duration_minutes ?? 45);
  const [priority, setPriority] = useState(task?.priority?.toUpperCase() ?? 'MEDIUM');
  const [category, setCategory] = useState(task?.category ?? 'work');
  const [deadline, setDeadline] = useState(task?.deadline?.slice(0, 16) ?? '');
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (await onSave({ title: title.trim(), duration_minutes: duration, priority, category, deadline: deadline ? `${deadline}:00${offset}` : null }, task?.id)) onClose();
  }
  return <form className="task-editor" onSubmit={submit} aria-label={task ? 'Edit task' : 'Add task'}>
    <h3>{task ? 'Edit your task' : 'Make room for something new'}</h3>
    <label>Task name<input autoFocus required maxLength={200} value={title} onChange={e => setTitle(e.target.value)} placeholder="Finish the project report" /></label>
    <div className="task-editor__row">
      <label>Duration (minutes)<input type="number" min={1} max={480} required value={duration} onChange={e => setDuration(Number(e.target.value))} /></label>
      <label>Priority<select value={priority} onChange={e => setPriority(e.target.value)}><option value="HIGH">High</option><option value="MEDIUM">Medium</option><option value="LOW">Low</option></select></label>
    </div>
    <div className="task-editor__row">
      <label>Category<select value={category} onChange={e => setCategory(e.target.value)}><option value="work">Work</option><option value="personal">Personal</option></select></label>
      <label>Deadline (optional)<input type="datetime-local" value={deadline} onChange={e => setDeadline(e.target.value)} /></label>
    </div>
    <p>Times use the schedule's UTC{offset === 'Z' ? '+00:00' : offset} timezone. Saving a task does not change your calendar.</p>
    <div className="task-editor__actions"><button type="submit" disabled={busy || !title.trim()}>{busy ? 'Saving…' : 'Save task'}</button><button type="button" disabled={busy} onClick={onClose}>Cancel</button></div>
  </form>;
}
