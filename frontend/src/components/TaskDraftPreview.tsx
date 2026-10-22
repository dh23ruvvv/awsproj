import type { TaskDraft, TaskInput } from '../api/client';

/** Show all proposed values, including removals, before a single atomic approval. */
export default function TaskDraftPreview({ draft, busy, onConfirm, onCancel }: {
  draft: TaskDraft; busy: boolean; onConfirm: () => void; onCancel: () => void;
}) {
  const describe = (task: TaskInput) => `${task.title} / ${task.duration_minutes} min / ${task.priority} / ${task.category} / ${task.deadline ? `deadline ${task.deadline}` : 'no deadline'}`;
  return <section className="task-draft-preview" aria-label="Review task changes">
    <h2>Review task changes</h2>
    <p>{draft.explanation}</p>
    <ul>{draft.changes.map((change, index) => <li key={index}>
      <strong>{change.action === 'add' ? 'Add task' : change.action === 'update' ? 'Update task' : 'Remove task'}</strong>
      {change.before && <p>Before: {describe(change.before)}</p>}
      {change.after && <p>{change.before ? 'After' : 'New'}: {describe(change.after)}</p>}
    </li>)}</ul>
    <p>Nothing in this draft is saved yet. Confirming changes your task list only; calendar scheduling is a separate review.</p>
    <div className="setup-actions"><button disabled={busy} onClick={onConfirm}>Confirm task changes</button><button disabled={busy} onClick={onCancel}>Cancel task changes</button></div>
  </section>;
}
