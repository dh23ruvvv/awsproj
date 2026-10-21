import { useEffect, useRef, useState } from 'react';
import { createSession, resetSession, sendMessage, getPlan, confirmPlan, cancelPlan, getSchedule, getMemory } from './api/client';
import type { MemoryResponse, ToolTraceItem } from './api/client';
import ScheduleTimeline from './components/ScheduleTimeline';
import type { ScheduleBlock } from './components/ScheduleTimeline';
import PlanPreview from './components/PlanPreview';
import type { DiffSummary } from './components/PlanPreview';
import UtteranceBar from './components/UtteranceBar';
import ResponseLine from './components/ResponseLine';
import ModeBadge from './components/ModeBadge';
import MemoryIndicator from './components/MemoryIndicator';
import ToolTrace from './components/ToolTrace';
import './App.css';

type ActivePlan = { planId: string; diff: DiffSummary | null; explanation: string };

/** Validate the required timeline fields at the generic OpenAPI record boundary. */
function scheduleBlocks(records: Record<string, unknown>[]): ScheduleBlock[] {
  return records.map(record => {
    if (typeof record.title !== 'string' || typeof record.start_time !== 'string' || typeof record.end_time !== 'string') {
      throw new Error('The schedule contains an invalid block.');
    }
    return { ...record, title: record.title, start_time: record.start_time, end_time: record.end_time };
  });
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

/** Integrate the persistent session, proposal approval, and ambient schedule surface. */
export default function App() {
  const [sid, setSid] = useState('');
  const [stateVersion, setStateVersion] = useState(1);
  const [blocks, setBlocks] = useState<ScheduleBlock[]>([]);
  const [memory, setMemory] = useState<MemoryResponse['entries']>([]);
  const [agentResponse, setAgentResponse] = useState('Tell me what needs to happen. We will make room for it.');
  const [providerUsed, setProviderUsed] = useState('deterministic');
  const [isDegraded, setIsDegraded] = useState(false);
  const [toolTrace, setToolTrace] = useState<ToolTraceItem[]>([]);
  const [activePlan, setActivePlan] = useState<ActivePlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [initializing, setInitializing] = useState(true);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);
  const busy = useRef(false);
  const startup = useRef<Promise<{ sessionId: string; schedule: Awaited<ReturnType<typeof getSchedule>>; memories: MemoryResponse; provider?: string }> | null>(null);

  useEffect(() => {
    let disposed = false;
    setInitializing(true);
    setError('');
    /** Reuse initialization across React StrictMode's effect replay. */
    async function initialize() {
      let sessionId = localStorage.getItem('flowpilot_sid');
      if (sessionId) {
        try {
          const [schedule, memories] = await Promise.all([getSchedule(sessionId), getMemory(sessionId)]);
          return { sessionId, schedule, memories };
        } catch { /* The handoff requires a fresh session when restoration fails. */ }
      }
      const session = await createSession(true);
      sessionId = session.session_id;
      localStorage.setItem('flowpilot_sid', sessionId);
      const [schedule, memories] = await Promise.all([getSchedule(sessionId), getMemory(sessionId)]);
      return { sessionId, schedule, memories, provider: session.provider };
    }
    startup.current ??= initialize();
    startup.current.then(result => {
      if (disposed) return;
      setBlocks(scheduleBlocks(result.schedule.blocks));
      setSid(result.sessionId);
      setStateVersion(result.schedule.state_version);
      setMemory(result.memories.entries);
      if (result.provider) setProviderUsed(result.provider);
    }).catch(failure => {
      if (!disposed) setError(errorMessage(failure));
    }).finally(() => {
      if (!disposed) setInitializing(false);
    });
    return () => { disposed = true; };
  }, [retry]);

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
    setProviderUsed(prev => prev === 'gemini' ? 'deterministic' : 'gemini');
    setIsDegraded(false);
  }

  /** Send an utterance and retrieve the proposal selected by the agent. */
  async function handleSendMessage(utterance: string) {
    await runAction(async () => {
      const res = await sendMessage(sid, utterance, stateVersion, providerUsed);
      setAgentResponse(res.response);
      setProviderUsed(res.provider_used);
      setIsDegraded(res.degraded);
      setStateVersion(res.state_version);
      setToolTrace(res.tool_trace ?? []);
      setActivePlan(null);
      if (res.plan_id) {
        const plan = await getPlan(sid, res.plan_id);
        setActivePlan({ planId: res.plan_id, diff: plan.diff ?? null, explanation: plan.explanation || res.response });
      }
    });
  }

  /** Commit approval, then retrieve schedule blocks through the documented endpoint. */
  async function handleConfirmPlan() {
    if (!activePlan) return;
    await runAction(async () => {
      const result = await confirmPlan(sid, activePlan.planId, stateVersion);
      setStateVersion(result.state_version);
      setActivePlan(null);
      setAgentResponse('Your plan is confirmed. Your schedule has been updated.');
      const schedule = await getSchedule(sid);
      setBlocks(scheduleBlocks(schedule.blocks));
      setStateVersion(schedule.state_version);
      const memories = await getMemory(sid);
      setMemory(memories.entries);
    });
  }

  /** Discard a proposal only after the server acknowledges cancellation. */
  async function handleCancelPlan() {
    if (!activePlan) return;
    await runAction(async () => {
      const result = await cancelPlan(sid, activePlan.planId);
      setStateVersion(result.state_version);
      setActivePlan(null);
      setAgentResponse('Proposal cancelled. Ready for your next instruction.');
    });
  }

  /** Restore the seeded demo and clear transient interaction state. */
  async function handleReset() {
    await runAction(async () => {
      const result = await resetSession(sid);
      setStateVersion(result.state_version);
      setMemory([]);
      setToolTrace([]);
      setActivePlan(null);
      setAgentResponse('Session reset to initial demo state.');
      const schedule = await getSchedule(sid);
      setBlocks(scheduleBlocks(schedule.blocks));
      setStateVersion(schedule.state_version);
    });
  }

  const memorySummary = memory.map(entry => {
    if (typeof entry.summary === 'string') return entry.summary;
    if (typeof entry.key === 'string' && typeof entry.value === 'string') return `${entry.key}: ${entry.value}`;
    return JSON.stringify(entry);
  }).join('; ');

  return (
    <div className="ambient-app">
      <header className="app-header">
        <div className="app-brand"><span className="app-orb" aria-hidden="true">✦</span><div><h1>FlowPilot</h1><p>Ambient AI Scheduling Assistant</p></div></div>
        <div className="app-header-actions">
          <ModeBadge provider={providerUsed} degraded={isDegraded} onToggle={handleToggleProvider} />
          <button className="reset-demo" onClick={handleReset} disabled={!sid || initializing || loading}>Reset Demo</button>
        </div>
      </header>
      <main className="ambient-layout">
        <section className="interaction-zone" aria-labelledby="interaction-heading" aria-busy={initializing || loading}>
          <div className="surface-intro"><p className="eyebrow">A little clarity for your day</p><h2 id="interaction-heading">Make space for<br /><span>what matters.</span></h2><p>Plan your day. Adjust when life happens.</p></div>
          <UtteranceBar onSubmit={handleSendMessage} loading={loading} disabled={initializing || !sid} />
          <div className="demo-suggestions" aria-label="Demo prompt suggestions">
            <div className="demo-suggestions__header">
              <span>Quick demo actions</span>
              <span className="demo-suggestions__hint">Click any prompt to run:</span>
            </div>
            <div className="demo-suggestions__chips">
              <button
                type="button"
                className="demo-chip"
                disabled={loading || initializing}
                onClick={() => handleSendMessage("Plan my day — finish the quarterly report by 5 PM and review the PR before the 2 PM meeting.")}
              >
                <span aria-hidden="true">🎯</span>
                <strong>Plan my day</strong>
              </button>
              <button
                type="button"
                className="demo-chip"
                disabled={loading || initializing}
                onClick={() => handleSendMessage("My manager scheduled a 1-on-1 at 2 PM for 30 minutes — replan around it.")}
              >
                <span aria-hidden="true">⚡</span>
                <strong>Replan: 2 PM 1-on-1</strong>
              </button>
              <button
                type="button"
                className="demo-chip"
                disabled={loading || initializing}
                onClick={() => handleSendMessage("What's left for today?")}
              >
                <span aria-hidden="true">📋</span>
                <strong>What's left today?</strong>
              </button>
            </div>
          </div>
          <ResponseLine text={initializing ? 'Connecting to your schedule…' : agentResponse} loading={loading} />
          {error && <div className="app-error" role="alert"><p>{error}</p>{!sid && <button onClick={() => { startup.current = null; setRetry(value => value + 1); }}>Retry connection</button>}</div>}
          <MemoryIndicator summary={memorySummary} />
          <PlanPreview planId={activePlan?.planId} diff={activePlan?.diff} explanation={activePlan?.explanation} loading={loading || initializing} onConfirm={handleConfirmPlan} onCancel={handleCancelPlan} />
          <ToolTrace trace={toolTrace} />
        </section>
        <aside className="schedule-zone" aria-label="Committed schedule"><p className="eyebrow">Your day, in focus</p><ScheduleTimeline blocks={blocks} /></aside>
      </main>
      <footer className="app-footer">A calmer day starts with a clear plan.</footer>
    </div>
  );
}
