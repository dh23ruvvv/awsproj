import { useState } from 'react';
import type { FormEvent } from 'react';
import type { Routine, RoutineInput } from '../api/client';

const weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

/** Explicit weekday recurrence creates tasks, never silently commits a calendar. */
export default function RoutineEditor({ routines, day, busy, onSave, onStop, onClose }: {
  routines: Routine[]; day: string; busy: boolean;
  onSave: (input: RoutineInput) => Promise<boolean>;
  onStop: (id: string) => Promise<void>; onClose: () => void;
}) {
  const [name, setName] = useState('');
  const [days, setDays] = useState<number[]>([]);
  const [tasks, setTasks] = useState<RoutineInput['tasks']>([{title: '', duration_minutes: 30, priority: 'MEDIUM', category: 'personal'}]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (await onSave({name: name.trim(), weekdays: days, starts_on: day, tasks: tasks.map(t => ({...t, title: t.title.trim()}))})) {
      setName(''); setDays([]); setTasks([{title: '', duration_minutes: 30, priority: 'MEDIUM', category: 'personal'}]);
    }
  }
  return <section className="routine-panel" aria-label="Fixed plans and routines">
    <div className="panel-title"><h2>Fixed plan / routine</h2><button onClick={onClose}>Close routines</button></div>
    <p>Choose weekdays and tasks. Starting {day}, matching days receive these tasks automatically when opened. Calendar scheduling still needs your approval.</p>
    {routines.length > 0 && <ul className="routine-list">{routines.map(r => <li key={r.id}><div><strong>{r.name}</strong><p>{r.weekdays.map(d => weekdays[d]).join(', ')} / {r.tasks.length} tasks / from {r.starts_on}</p><p>{r.tasks.map(t => `${t.title} (${t.duration_minutes}m)`).join(' / ')}</p></div><button disabled={busy} onClick={() => { if (window.confirm('Stop this routine? Existing day tasks will remain.')) void onStop(r.id); }}>Stop routine</button></li>)}</ul>}
    <form className="task-editor" aria-label="Create routine" onSubmit={submit}>
      <label>Routine name<input required maxLength={120} value={name} onChange={e => setName(e.target.value)} placeholder="My study routine" /></label>
      <fieldset><legend>Repeat on</legend><div className="weekday-options">{weekdays.map((label, index) => <label key={label}><input type="checkbox" checked={days.includes(index)} onChange={e => setDays(e.target.checked ? [...days, index] : days.filter(d => d !== index))} />{label}</label>)}</div></fieldset>
      {tasks.map((task, index) => <div className="routine-task" key={index}>
        <label>Task {index + 1}<input required maxLength={200} value={task.title} onChange={e => setTasks(tasks.map((t, i) => i === index ? {...t, title: e.target.value} : t))} /></label>
        <label>Minutes<input type="number" required min={1} max={480} value={task.duration_minutes} onChange={e => setTasks(tasks.map((t, i) => i === index ? {...t, duration_minutes: Number(e.target.value)} : t))} /></label>
        <button type="button" disabled={tasks.length === 1 || busy} aria-label={`Remove routine task ${index + 1}`} onClick={() => setTasks(tasks.filter((_, i) => i !== index))}>Remove</button>
      </div>)}
      <div className="setup-actions"><button type="button" disabled={busy || tasks.length >= 30} onClick={() => setTasks([...tasks, {title: '', duration_minutes: 30, priority: 'MEDIUM', category: 'personal'}])}>Add another routine task</button><button type="submit" disabled={busy || !days.length || !name.trim() || tasks.some(t => !t.title.trim())}>Save routine</button></div>
      <p>Stopping a routine prevents new occurrences. Tasks already added to a day remain editable in that day's task list.</p>
    </form>
  </section>;
}
