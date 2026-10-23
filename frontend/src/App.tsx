import { useEffect, useRef, useState } from 'react';
import { getTaskDraft, getPendingTaskDraft, confirmTaskDraft, cancelTaskDraft, createWorkspace, openDay, getRoutines, saveRoutine, stopRoutine, sendMessage, getPlan, confirmPlan, cancelPlan, getSchedule, getMemory, getTasks, saveTask, deleteTask, proposeCommitment } from './api/client';
import type { MemoryResponse, TaskInput, Routine, RoutineInput, TaskDraft } from './api/client';
import ScheduleTimeline from './components/ScheduleTimeline';
import type { ScheduleBlock } from './components/ScheduleTimeline';
import TaskList from './components/TaskList';
import TaskEditor from './components/TaskEditor';
import CommitmentEditor from './components/CommitmentEditor';
import type { TaskItem } from './components/TaskList';
import PlanPreview from './components/PlanPreview';
import type { DiffSummary } from './components/PlanPreview';
import UtteranceBar from './components/UtteranceBar';
import ResponseLine from './components/ResponseLine';
import ModeBadge from './components/ModeBadge';
import MemoryIndicator from './components/MemoryIndicator';
import ToolTrace from './components/ToolTrace';
import { getSessionInfo, removePreference } from './api/client';
import type { ToolTraceItem } from './api/client';
import RoutineEditor from './components/RoutineEditor';
import TaskDraftPreview from './components/TaskDraftPreview';
import './App.css';
import PixelText from './components/PixelText';
import PixelSnow from './components/PixelSnow';
import DayLoad from './components/DayLoad';
import './PixelDashboard.css';

type ActivePlan = { planId: string; diff: DiffSummary | null; explanation: string; version: number; blocks: ScheduleBlock[] };

/** Validate the required timeline fields at the generic OpenAPI record boundary. */
function scheduleBlocks(records: Record<string, unknown>[]): ScheduleBlock[] {
  return records.map(record => {
    if (typeof record.title !== 'string' || typeof record.start_time !== 'string' || typeof record.end_time !== 'string') {
      throw new Error('The schedule contains an invalid block.');
    }
    return { ...record, title: record.title, start_time: record.start_time, end_time: record.end_time };
  });
}

function validateTasks(records: Record<string, unknown>[]): TaskItem[] {
  return records.map(record => ({
    id: String(record.id ?? ''),
    title: String(record.title ?? ''),
    duration_minutes: Number(record.duration_minutes ?? 0),
    deadline: typeof record.deadline === 'string' ? record.deadline : null,
    priority: typeof record.priority === 'string' ? record.priority : undefined,
    category: typeof record.category === 'string' ? record.category : undefined,
    status: typeof record.status === 'string' ? record.status : 'pending',
  }));
}

/** Present structured API failures and network failures as readable feedback. */
function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === 'object' && error !== null && 'error' in error) {
    const detail = error.error;
    if (typeof detail === 'object' && detail !== null && 'message' in detail && typeof detail.message === 'string') return detail.message;
  }
  return 'Unable to reach FlowPilot. Please try again.';
}

/** Use the browser's local date rather than UTC's possibly different day. */
function localDate(date = new Date()) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}
function shiftDay(day: string, delta: number) {
  const date = new Date(`${day}T12:00:00`); date.setDate(date.getDate() + delta); return localDate(date);
}

/** Integrate the persistent session, proposal approval, and ambient schedule surface. */
export default function App() {
  const [linkedSession] = useState(() => new URLSearchParams(window.location.search).get('session'));
  const [snowEnabled, setSnowEnabled] = useState(() => localStorage.getItem('flowpilot_snow') !== 'off');
  const [search, setSearch] = useState('');
  const [sid, setSid] = useState('');
  const [stateVersion, setStateVersion] = useState(1);
  const [blocks, setBlocks] = useState<ScheduleBlock[]>([]);
  const [tasks, setTasks] = useState<TaskItem[]>([]);
  const [editingTask, setEditingTask] = useState<TaskItem | 'new' | null>(null);
  const [editingCommitment, setEditingCommitment] = useState(false);
  const [activeSidebarTab, setActiveSidebarTab] = useState<'timeline' | 'tasks'>('tasks');
  const [memory, setMemory] = useState<MemoryResponse['entries']>([]);
  const [toolTrace, setToolTrace] = useState<ToolTraceItem[]>([]);
  const [agentResponse, setAgentResponse] = useState('Choose a day, add your tasks and commitments, then review a plan.');
  const [providerUsed, setProviderUsed] = useState(() => localStorage.getItem('flowpilot_provider') || 'gemini');
  const [requestedProvider, setRequestedProvider] = useState<'gemini' | 'deterministic'>(() => {
    const saved = localStorage.getItem('flowpilot_provider');
    return (saved === 'deterministic' || saved === 'gemini') ? saved : 'gemini';
  });
  const [lastRequest, setLastRequest] = useState('');
  const [isDegraded, setIsDegraded] = useState(false);
  const [selectedDay, setSelectedDay] = useState(() => localStorage.getItem('flowpilot_day') || localDate());
  const [workspaceId, setWorkspaceId] = useState('');
  const [dayOffset, setDayOffset] = useState('+00:00');
  const [setupOpen, setSetupOpen] = useState(false);
  const [routinesOpen, setRoutinesOpen] = useState(false);
  const [routines, setRoutines] = useState<Routine[]>([]);
  const [taskDraft, setTaskDraft] = useState<TaskDraft | null>(null);
  const [activePlan, setActivePlan] = useState<ActivePlan | null>(null);
  const reviewPending = !!activePlan || !!taskDraft;
  const [loading, setLoading] = useState(false);
  const [initializing, setInitializing] = useState(true);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const busy = useRef(false);
  const startup = useRef<{key: string; promise: Promise<{
    sessionId: string;
    schedule: Awaited<ReturnType<typeof getSchedule>>;
    memories: MemoryResponse;
    tasks: Record<string, unknown>[];
    workspaceId: string; timestamp: string; routines: Routine[]; taskDraft: TaskDraft | null; pendingPlanId?: string | null;
  }> } | null>(null);

  useEffect(() => {
    let disposed = false;
    setInitializing(true);
    setError('');
    /** Reuse initialization across React StrictMode's effect replay. */
    async function initialize() {
      if (linkedSession) {
        const [info, schedule, memories, taskData, pendingTasks] = await Promise.all([
          getSessionInfo(linkedSession), getSchedule(linkedSession), getMemory(linkedSession), getTasks(linkedSession), getPendingTaskDraft(linkedSession),
        ]);
        return {sessionId: linkedSession, schedule, memories, tasks: taskData.tasks, workspaceId: '', timestamp: info.timestamp,
          routines: [], taskDraft: pendingTasks.draft, pendingPlanId: info.pending_plan_id};
      }
      let wid = localStorage.getItem('flowpilot_workspace');
      if (!wid) {
        wid = (await createWorkspace()).workspace_id;
        localStorage.setItem('flowpilot_workspace', wid);
        const previous = localStorage.getItem('flowpilot_sid');
        if (previous) localStorage.setItem('flowpilot_previous_demo_sid', previous);
      }
      let day;
      const offsetMinutes = -new Date(`${selectedDay}T12:00:00`).getTimezoneOffset();
      try {
        day = await openDay(wid, selectedDay, offsetMinutes);
      } catch (failure) {
        // A deliberately cleared database leaves a stale browser workspace ID.
        // Recover only a missing workspace; never hide network/server failures.
        if (typeof failure !== 'object' || failure === null || !('error' in failure) ||
            (failure as {error: {code: string}}).error.code !== 'HTTP_404') throw failure;
        wid = (await createWorkspace()).workspace_id;
        localStorage.setItem('flowpilot_workspace', wid);
        day = await openDay(wid, selectedDay, offsetMinutes);
      }
      const sessionId = day.session_id;
      const [schedule, memories, taskData, routineData, pendingTasks] = await Promise.all([
        getSchedule(sessionId), getMemory(sessionId), getTasks(sessionId), getRoutines(wid), getPendingTaskDraft(sessionId),
      ]);
      return {sessionId, schedule, memories, tasks: taskData.tasks, workspaceId: wid, timestamp: day.timestamp, routines: routineData.routines, taskDraft: pendingTasks.draft};
    }
    const key = `${selectedDay}/${retry}`;
    if (startup.current?.key !== key) startup.current = {key, promise: initialize()};
    startup.current.promise.then(async result => {
      if (disposed) return;
      setBlocks(scheduleBlocks(result.schedule.blocks));
      setSid(result.sessionId);
      if (!linkedSession) {
        localStorage.setItem('flowpilot_sid', result.sessionId);
        localStorage.setItem('flowpilot_day', selectedDay);
      } else {
        setSelectedDay(result.timestamp.slice(0, 10));
      }
      setWorkspaceId(result.workspaceId);
      setDayOffset(result.timestamp.slice(-6));
      setRoutines(result.routines);
      setTaskDraft(result.taskDraft);
      setActivePlan(null);
      setStateVersion(result.schedule.state_version);
      setMemory(result.memories.entries);
      if (result.tasks) setTasks(validateTasks(result.tasks));

      const pendingId = result.pendingPlanId || localStorage.getItem(`flowpilot_plan_${result.sessionId}`);
      if (pendingId) await getPlan(result.sessionId, pendingId).then(plan => {
        if (disposed) return;
        if (plan.status === 'PROPOSED') setActivePlan({ planId: pendingId, diff: plan.diff ?? null, explanation: plan.explanation || '', version: plan.state_version_at_proposal, blocks: scheduleBlocks(plan.proposed_blocks) });
        else localStorage.removeItem(`flowpilot_plan_${result.sessionId}`);
      }).catch(failure => { if (!disposed) setError(errorMessage(failure)); });
    }).catch(failure => {
      if (!disposed) setError(errorMessage(failure));
    }).finally(() => {
      if (!disposed) setInitializing(false);
    });
    return () => { disposed = true; };
  }, [retry, selectedDay, linkedSession]);

  /** Serialize mutations so proposal approval and reset cannot race. */
  async function runAction(action: () => Promise<void>) {
    if (!sid || initializing || busy.current) return;
    busy.current = true;
    setLoading(true);
    setError('');
    try { await action(); } catch (failure) { setError(errorMessage(failure)); }
    finally { busy.current = false; setLoading(false); }
  }

  function handleToggleProvider() {
    setRequestedProvider(prev => {
      const next = prev === 'gemini' ? 'deterministic' : 'gemini';
      localStorage.setItem('flowpilot_provider', next);
      setProviderUsed(next);
      return next;
    });
  }

  /** Send an utterance and retrieve the proposal selected by the agent. */
  async function handleSendMessage(utterance: string, fromSetup = false) {
    const hasPendingTasks = tasks.some(task => task.status === 'pending');
    if (!fromSetup && !hasPendingTasks && /^(plan( my)? day|plan today)[.!?]?$/i.test(utterance.trim())) { setSetupOpen(true); return; }
    if (!fromSetup && /^(add (an? )?interruption|interruption)[.!?]?$/i.test(utterance.trim())) { setEditingCommitment(true); return; }
    if (/\b(left|tasks|pending|status|remaining|show tasks)\b/i.test(utterance)) {
      setActiveSidebarTab('tasks');
    } else if (/\b(plan|replan|schedule|timeline|calendar)\b/i.test(utterance)) {
      setActiveSidebarTab('timeline');
    }
    if (reviewPending) return;
    await runAction(async () => {
      setLastRequest(utterance);
      setToolTrace([]);
      const res = await sendMessage(sid, utterance, stateVersion, requestedProvider);
      setToolTrace(res.tool_trace ?? []);
      setAgentResponse(res.response);
      setProviderUsed(res.provider_used);
      setIsDegraded(res.degraded);
      setStateVersion(res.state_version);

      setActivePlan(null);
      if (res.task_draft_id) setTaskDraft(await getTaskDraft(sid, res.task_draft_id));
      if (res.plan_id) {
        const plan = await getPlan(sid, res.plan_id);
        setActivePlan({ planId: res.plan_id, diff: plan.diff ?? null, explanation: plan.explanation || res.response, version: plan.state_version_at_proposal, blocks: scheduleBlocks(plan.proposed_blocks) });
        localStorage.setItem(`flowpilot_plan_${sid}`, res.plan_id);
      }
      try {
        setMemory((await getMemory(sid)).entries);
        const updatedTasks = await getTasks(sid);
        setTasks(validateTasks(updatedTasks.tasks));
      } catch { /* retain existing */ }
    });
  }

  /** Commit approval, then retrieve schedule blocks through the documented endpoint. */
  async function handleConfirmPlan() {
    if (!activePlan) return;
    await runAction(async () => {
      const result = await confirmPlan(sid, activePlan.planId, activePlan.version);
      setStateVersion(result.state_version);
      setActivePlan(null);
      localStorage.removeItem(`flowpilot_plan_${sid}`);
      setAgentResponse('Your plan is confirmed. Your schedule has been updated.');
      const schedule = await getSchedule(sid);
      setBlocks(scheduleBlocks(schedule.blocks));
      setStateVersion(schedule.state_version);
      const memories = await getMemory(sid);
      setMemory(memories.entries);
      try {
        const updatedTasks = await getTasks(sid);
        setTasks(validateTasks(updatedTasks.tasks));
      } catch { /* retain existing */ }
      setActiveSidebarTab('timeline');
    });
  }

  /** Discard a proposal only after the server acknowledges cancellation. */
  async function handleCancelPlan() {
    if (!activePlan) return;
    await runAction(async () => {
      const result = await cancelPlan(sid, activePlan.planId);
      setStateVersion(result.state_version);
      setActivePlan(null);
      localStorage.removeItem(`flowpilot_plan_${sid}`);
      setAgentResponse('Proposal cancelled. Ready for your next instruction.');
    });
  }

  /** Apply exactly the task draft that was reviewed, then refresh persisted tasks. */
  async function handleConfirmTasks() {
    if (!taskDraft) return;
    await runAction(async () => {
      await confirmTaskDraft(sid, taskDraft);
      setTaskDraft(null);
      const data = await getTasks(sid); setTasks(validateTasks(data.tasks)); setStateVersion(data.state_version);
      setAgentResponse('Task changes saved. Say "plan my day" or use the setup button to review a calendar plan.');
      setActiveSidebarTab('tasks');
    });
  }
  async function handleCancelTasks() {
    if (!taskDraft) return;
    await runAction(async () => {
      await cancelTaskDraft(sid, taskDraft.id); setTaskDraft(null);
      const data = await getTasks(sid); setTasks(validateTasks(data.tasks)); setStateVersion(data.state_version);
      setAgentResponse('Task changes cancelled. Nothing from that draft was saved.');
    });
  }

  async function handleSaveTask(input: TaskInput, taskId?: string): Promise<boolean> {
    let saved = false;
    await runAction(async () => {
      const result = await saveTask(sid, input, stateVersion, taskId);
      setStateVersion(result.state_version);
      const data = await getTasks(sid);
      setTasks(validateTasks(data.tasks));
      setStateVersion(data.state_version);
      setAgentResponse('Task saved for this day. Use Plan my day to review your tasks and create a schedule.');
      saved = true;
    });
    return saved;
  }

  async function handleDeleteTask(task: TaskItem) {
    if (!window.confirm(`Remove "${task.title}" from your task list?`)) return;
    await runAction(async () => {
      const result = await deleteTask(sid, task.id, stateVersion);
      setStateVersion(result.state_version);
      const data = await getTasks(sid);
      setTasks(validateTasks(data.tasks));
    });
  }

  function changeDay(day: string) {
    if (linkedSession || loading || initializing || reviewPending || day === selectedDay) return;
    setSelectedDay(day); setInitializing(true); setSid(''); setTasks([]); setBlocks([]);
    setToolTrace([]); setMemory([]);
    setEditingTask(null); setEditingCommitment(false); setSetupOpen(false); setSearch('');
    setLastRequest(''); setAgentResponse('Add tasks and events for this day, then preview your plan.');
  }

  async function handleSaveRoutine(input: RoutineInput): Promise<boolean> {
    let saved = false;
    await runAction(async () => {
      await saveRoutine(workspaceId, input);
      setRoutines((await getRoutines(workspaceId)).routines);
      await openDay(workspaceId, selectedDay, -new Date(`${selectedDay}T12:00:00`).getTimezoneOffset());
      const data = await getTasks(sid); setTasks(validateTasks(data.tasks)); setStateVersion(data.state_version);
      setAgentResponse('Routine saved. Its tasks appear once on each matching day when you open it. Review a plan to schedule them.');
      saved = true;
    });
    return saved;
  }

  async function handleStopRoutine(id: string) {
    await runAction(async () => { await stopRoutine(workspaceId, id); setRoutines((await getRoutines(workspaceId)).routines); });
  }

  const scheduleOffset = dayOffset;
  const scheduleDate = selectedDay;

  async function handleCommitment(event: { title: string; start_time: string; end_time: string }): Promise<boolean> {
    let proposed = false;
    await runAction(async () => {
      const plan = await proposeCommitment(sid, event, stateVersion);
      setActivePlan({ planId: plan.plan_id, diff: plan.diff ?? null, explanation: plan.explanation || '', version: plan.state_version_at_proposal, blocks: scheduleBlocks(plan.proposed_blocks) });
      localStorage.setItem(`flowpilot_plan_${sid}`, plan.plan_id);
      setAgentResponse('Review your fixed event below. Your calendar will change only after confirmation.');
      proposed = true;
    });
    return proposed;
  }

  const memorySummary = memory.map(entry => {
    if (entry.key === 'scheduling_preference' && typeof entry.value === 'string') return entry.value;
    if (typeof entry.summary === 'string') return entry.summary;
    if (typeof entry.key === 'string' && typeof entry.value === 'string') return `${entry.key}: ${entry.value}`;
    return JSON.stringify(entry);
  }).join('; ');

  const scheduledMinutes = Math.round(blocks.reduce((total, block) => total + (Date.parse(block.end_time) - Date.parse(block.start_time)) / 60000, 0));
  const filteredTasks = tasks.filter(task => task.title.toLowerCase().includes(search.toLowerCase()));
  const filteredBlocks = blocks.filter(block => block.title.toLowerCase().includes(search.toLowerCase()));

  /** Export the currently loaded committed workspace, never an unapproved draft. */
  function exportWorkspace() {
    const blob = new Blob([JSON.stringify({ tasks, calendar: blocks, state_version: stateVersion }, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url; link.download = `flowpilot-${scheduleDate ?? 'workspace'}.json`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return (
    <div className="ambient-app pixel-dashboard" id="overview">
      <PixelSnow enabled={snowEnabled} />
      <div className="pixel-main">
      <header className="app-header">
        <a className="pixel-brand" href="#overview"><PixelText>FLOWPILOT</PixelText></a>
        <div className="header-tools">
          <button className="snow-toggle" role="switch" aria-checked={snowEnabled} aria-label="Pixel snowfall" onClick={() => { const next = !snowEnabled; setSnowEnabled(next); localStorage.setItem('flowpilot_snow', next ? 'on' : 'off'); }}>Snow <span>{snowEnabled ? 'On' : 'Off'}</span></button>
          <button className="export-button" onClick={exportWorkspace} disabled={initializing || !sid}>Export data</button>
        </div>
      </header>
      <div className="dashboard-content">
      <div className="dashboard-heading"><div><h1><PixelText>YOUR DAY, AT A GLANCE.</PixelText></h1><p>Plan your time. Review changes. Stay in control.</p></div></div>
      <div className="dashboard-toolbar">
        <div className="app-header-actions">
          <ModeBadge provider={providerUsed} degraded={isDegraded} /><button className="reset-demo" onClick={handleToggleProvider} disabled={loading || reviewPending}>Use {requestedProvider === 'gemini' ? 'demo planner' : 'Gemini'}</button>
          <button className="reset-demo" onClick={() => setRoutinesOpen(value => !value)} disabled={!workspaceId || !sid || initializing || loading || reviewPending}>Fixed plan / routine</button>
        </div>
      </div>
      <div className="day-navigation">
        <button aria-label="Previous day" disabled={!!linkedSession || loading || initializing || reviewPending} onClick={() => changeDay(shiftDay(selectedDay, -1))}>&lt;</button>
        <label>Planning day<input aria-label="Planning day" type="date" value={selectedDay} disabled={!!linkedSession || loading || initializing || reviewPending} onChange={e => e.target.value && changeDay(e.target.value)} /></label>
        <strong>{new Date(`${selectedDay}T12:00:00`).toLocaleDateString(undefined, {weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'})}</strong>
        <button aria-label="Next day" disabled={!!linkedSession || loading || initializing || reviewPending} onClick={() => changeDay(shiftDay(selectedDay, 1))}>&gt;</button>
        <button disabled={!!linkedSession || loading || initializing || reviewPending} onClick={() => changeDay(localDate())}>Today</button>
      </div>
      {reviewPending && <p className="mode-help">Confirm or cancel your proposed changes before changing days.</p>}
      {routinesOpen && <RoutineEditor routines={routines} day={selectedDay} busy={loading || initializing || reviewPending} onSave={handleSaveRoutine} onStop={handleStopRoutine} onClose={() => setRoutinesOpen(false)} />}
      <section className="workspace-stats" aria-label="Workspace summary">{[
        ['PENDING TASKS', String(tasks.filter(task => task.status === 'pending').length).padStart(2, '0'), `${tasks.length} tasks in your workspace`],
        ['SCHEDULED TIME', `${Math.floor(scheduledMinutes / 60)}:${String(scheduledMinutes % 60).padStart(2, '0')}`, 'Hours / minutes committed'],
        ['FIXED COMMITMENTS', String(blocks.filter(block => block.immutable).length).padStart(2, '0'), 'Protected when replanning'],
        ['PLAN STATUS', initializing ? '...' : reviewPending ? 'REVIEW' : blocks.some(block => !block.immutable) ? 'SAVED' : 'READY', reviewPending ? 'Waiting for your approval' : 'No unapproved calendar changes'],
      ].map(([label, value, detail]) => <article className="stat-card" key={label}><span className="stat-label">{label}</span><strong><PixelText>{initializing ? '...' : value}</PixelText></strong><p>{detail}</p></article>)}</section>
      <main className="ambient-layout">
        <section className="interaction-zone" aria-labelledby="interaction-heading" aria-busy={initializing || loading}>
          <DayLoad blocks={blocks} />
          <div className="planner-panel" id="planner">
          <div className="surface-intro"><h2 id="interaction-heading"><PixelText>MAKE ROOM FOR WHAT MATTERS.</PixelText></h2><p>Tell me what needs to happen, or start with an example.</p></div>
          <div className="journey-steps" aria-label="Planning process"><span>01 Tell us</span><span>02 Review the changes</span><span>03 Approve your plan</span></div>
          <UtteranceBar key={selectedDay} reply={agentResponse} onVoiceStart={() => { setRequestedProvider('gemini'); localStorage.setItem('flowpilot_provider', 'gemini'); }} onSubmit={handleSendMessage} loading={loading} disabled={initializing || !sid || reviewPending} />
          <p className="mode-help">{requestedProvider === 'gemini' ? 'Next request: Gemini, with a clearly labeled fallback if unavailable.' : 'Plans prefer 09:00-17:00, with overflow up to 21:00 when needed. Review and approve before saving.'}</p>
          {reviewPending && <p className="proposal-notice">Confirm or cancel the proposed changes below before starting another request.</p>}
          <div className="demo-suggestions" aria-label="Demo prompt suggestions">
            <div className="demo-suggestions__header">
              <span>What would you like to do?</span>
              <span className="demo-suggestions__hint">Real proposals. No changes until approval.</span>
            </div>
            <div className="demo-suggestions__chips">
              <button
                type="button"
                className="demo-chip"
                disabled={loading || initializing || reviewPending}
                onClick={() => setSetupOpen(true)}
              >
                <span aria-hidden="true">🎯</span>
                <strong>Plan my day</strong>
              </button>
              <button
                type="button"
                className="demo-chip"
                disabled={loading || initializing || reviewPending}
                onClick={() => { setEditingCommitment(true); setActiveSidebarTab('timeline'); }}
              >
                <span aria-hidden="true">⚡</span>
                <strong>Add an interruption</strong>
              </button>
              <button
                type="button"
                className="demo-chip"
                disabled={loading || initializing || reviewPending}
                onClick={() => handleSendMessage("What's left for today?")}
              >
                <span aria-hidden="true">📋</span>
                <strong>What's left today?</strong>
              </button>
            </div>
          </div>
          {setupOpen && <section className="day-setup" aria-label="Plan your day">
            <h3>What do you want to do on this day?</h3>
            <p>Add your tasks with their durations, and any events with fixed times. Existing tasks for this day are included.</p>
            <div className="setup-actions">
              <button disabled={loading || reviewPending} onClick={() => { setActiveSidebarTab('tasks'); setEditingTask('new'); }}>Add a task</button>
              <button disabled={loading || reviewPending} onClick={() => setEditingCommitment(true)}>Add an event</button>
            </div>
            {editingTask && <TaskEditor key={editingTask === 'new' ? 'setup-new' : editingTask.id} task={editingTask === 'new' ? undefined : editingTask} offset={scheduleOffset} busy={loading || reviewPending} onSave={handleSaveTask} onClose={() => setEditingTask(null)} />}
            {tasks.length > 0 && <ul className="setup-task-list">{tasks.map(task => <li key={task.id}>{task.title} / {task.duration_minutes}m / {task.status}</li>)}</ul>}
            <p>{tasks.filter(t => t.status === 'pending').length} pending tasks / {blocks.length} saved calendar blocks. Preferred hours: 09:00-17:00; overflow up to 21:00 when deadlines allow.</p>
            <div className="setup-actions"><button disabled={loading || reviewPending || !tasks.some(t => t.status === 'pending')} onClick={() => { setSetupOpen(false); void handleSendMessage('Plan my day', true); }}>Preview my day</button><button onClick={() => setSetupOpen(false)}>Close setup</button></div>
          </section>}
          {editingCommitment && activeSidebarTab !== 'timeline' && <CommitmentEditor date={scheduleDate} offset={scheduleOffset} busy={loading || reviewPending} onPropose={handleCommitment} onClose={() => setEditingCommitment(false)} />}
          {lastRequest && <div className="request-bubble"><span>Your request</span><p>{lastRequest}</p></div>}
          <div aria-live="polite" aria-atomic="true">
            <ResponseLine text={initializing ? 'Connecting to your schedule…' : agentResponse} loading={loading} />
          </div>
          {error && <div className="app-error" role="alert"><p>{error}</p>{sid && <button onClick={() => window.location.reload()}>Reload saved state</button>}{!sid && <button onClick={() => { startup.current = null; setRetry(value => value + 1); }}>Retry connection</button>}</div>}
          {linkedSession && <p className="linked-session">Reviewing a linked planning session. <a href="/">Return to personal days</a></p>}
          <MemoryIndicator summary={memorySummary} entries={memory.flatMap(entry => typeof entry.id === 'string' && typeof entry.value === 'string' ? [{id: entry.id, value: entry.value}] : [])}
            disabled={loading || initializing || reviewPending} onRemove={id => runAction(async () => {
              const result = await removePreference(sid, id); setStateVersion(result.state_version);
              setMemory((await getMemory(sid)).entries);
            })} />
          {taskDraft && <TaskDraftPreview draft={taskDraft} busy={loading || initializing} onConfirm={handleConfirmTasks} onCancel={handleCancelTasks} />}
          <PlanPreview planId={activePlan?.planId} diff={activePlan?.diff} explanation={activePlan?.explanation} proposedBlocks={activePlan?.blocks} loading={loading || initializing} onConfirm={handleConfirmPlan} onCancel={handleCancelPlan} />
          <ToolTrace trace={toolTrace} />

          </div>
        </section>
        <aside className="schedule-zone" id="workspace-panel" aria-label="Committed schedule and tasks">
          <div className="day-heading"><p className="eyebrow">Your committed day</p><span>{scheduleDate || 'Your schedule'} · UTC{scheduleOffset === 'Z' ? '+00:00' : scheduleOffset}</span></div>
          <div className="zone-switcher" role="tablist" aria-label="View mode">
            <button
              type="button"
              role="tab"
              aria-selected={activeSidebarTab === 'tasks'}
              className={`zone-tab ${activeSidebarTab === 'tasks' ? 'zone-tab--active' : ''}`}
              onClick={() => setActiveSidebarTab('tasks')}
            >
              Tasks ({tasks.length})
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={activeSidebarTab === 'timeline'}
              className={`zone-tab ${activeSidebarTab === 'timeline' ? 'zone-tab--active' : ''}`}
              onClick={() => setActiveSidebarTab('timeline')}
            >
              Timeline ({blocks.length})
            </button>
          </div>
          <label className="workspace-search"><input type="search" aria-label="Search tasks and events" placeholder={activeSidebarTab === 'tasks' ? 'Find a task...' : 'Find an event...'} value={search} onChange={event => setSearch(event.target.value)} /></label>
          {activeSidebarTab === 'tasks' ? (
            <>
              <button className="add-task" disabled={loading || initializing || reviewPending} onClick={() => setEditingTask('new')}>+ Add a task</button>
              {editingTask && !setupOpen && <TaskEditor key={editingTask === 'new' ? 'new' : editingTask.id} task={editingTask === 'new' ? undefined : editingTask} offset={scheduleOffset} busy={loading || reviewPending} onSave={handleSaveTask} onClose={() => setEditingTask(null)} />}
              {search && <p className="search-result-count">{filteredTasks.length} matching tasks <button onClick={() => setSearch('')}>Clear search</button></p>}
              <TaskList tasks={filteredTasks} disabled={loading || initializing || reviewPending} onEdit={setEditingTask} onDelete={handleDeleteTask} />
            </>
          ) : (
            <>
              <button className="add-task" disabled={loading || initializing || reviewPending || !scheduleDate} onClick={() => { setEditingCommitment(true); setActiveSidebarTab('timeline'); }}>+ Add a fixed event</button>
              {editingCommitment && (
                <CommitmentEditor
                  date={scheduleDate}
                  offset={scheduleOffset}
                  busy={loading || reviewPending}
                  onPropose={handleCommitment}
                  onClose={() => setEditingCommitment(false)}
                />
              )}
              {activePlan && (
                <div className="timeline-proposal-notice">
                  <p>Proposed calendar changes ready for approval:</p>
                  <div className="timeline-proposal-actions">
                    <button type="button" className="timeline-confirm-btn" onClick={handleConfirmPlan} disabled={loading || initializing}>
                      Confirm proposal
                    </button>
                    <button type="button" className="timeline-cancel-btn" onClick={handleCancelPlan} disabled={loading || initializing}>
                      Cancel
                    </button>
                  </div>
                </div>
              )}
              {search && <p className="search-result-count">{filteredBlocks.length} matching events <button onClick={() => setSearch('')}>Clear search</button></p>}
              <ScheduleTimeline blocks={filteredBlocks} />
            </>
          )}
        </aside>
      </main>
      <footer className="app-footer"><span>Alexa+ simulation / Calendar changes require your approval.</span><span>{initializing ? 'Loading workspace...' : `Saved workspace / v${stateVersion}`}</span></footer>
      </div>
      </div>
    </div>
  );
}
