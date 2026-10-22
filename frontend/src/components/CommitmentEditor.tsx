import { useState } from 'react';
import type { FormEvent } from 'react';

export default function CommitmentEditor({ date, offset, busy, onPropose, onClose }: {
  date: string; offset: string; busy: boolean;
  onPropose: (event: { title: string; start_time: string; end_time: string }) => Promise<boolean>;
  onClose: () => void;
}) {
  const [title, setTitle] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (await onPropose({ title: title.trim(), start_time: `${date}T${start}:00${offset}`, end_time: `${date}T${end}:00${offset}` })) onClose();
  }
  return <form className="task-editor" aria-label="Add fixed event" onSubmit={submit}>
    <h3>Add an event or interruption</h3>
    <label>Event name<input autoFocus required maxLength={200} value={title} onChange={e => setTitle(e.target.value)} /></label>
    <div className="task-editor__row">
      <label>Start time<input type="time" value={start} required onChange={e => setStart(e.target.value)} /></label>
      <label>End time<input type="time" value={end} required onChange={e => setEnd(e.target.value)} /></label>
    </div>
    <p>{date} · UTC{offset === 'Z' ? '+00:00' : offset}. Review and approve before this event is added. Future plans will keep it fixed.</p>
    {start && end && end <= start && <p role="alert">End time must be later than start time.</p>}
    <div className="task-editor__actions"><button disabled={busy || !title.trim() || (!start || !end || end <= start)} type="submit">Preview fixed event</button><button type="button" disabled={busy} onClick={onClose}>Cancel</button></div>
  </form>;
}
