/**
 * Typed FlowPilot API client consuming OpenAPI generated schemas.
 */

import type { components } from "./types";

export type SessionCreateRequest = components["schemas"]["SessionCreateRequest"];
export type SessionResponse = components["schemas"]["SessionResponse"];
export type SessionResetResponse = components["schemas"]["SessionResetResponse"];
export type AgentMessageRequest = components["schemas"]["AgentMessageRequest"];
export type AgentMessageResponse = components["schemas"]["AgentMessageResponse"];
export type PlanResponse = components["schemas"]["PlanResponse"];
export type ConfirmRequest = components["schemas"]["ConfirmRequest"];
export type ConfirmResponse = components["schemas"]["ConfirmResponse"];
export type CancelResponse = components["schemas"]["CancelResponse"];
export type ScheduleResponse = components["schemas"]["ScheduleResponse"];
export type TasksResponse = components["schemas"]["TasksResponse"];
export type MemoryResponse = components["schemas"]["MemoryResponse"];
export type ExecutionLogResponse = components["schemas"]["ExecutionLogResponse"];
export type ToolTraceItem = components["schemas"]["ToolTraceItem"];

export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

const BASE_URL = "/api/v1";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  let response: Response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch (err) {
    const error: ApiError = {
      error: {
        code: "NETWORK_ERROR",
        message: "Unable to reach FlowPilot server. Please ensure the backend is running.",
        details: { original: err instanceof Error ? err.message : String(err) },
      },
    };
    throw error;
  }

  let data: any = null;
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    try {
      data = await response.json();
    } catch {
      data = null;
    }
  } else {
    try {
      const text = await response.text();
      data = text ? { raw: text } : null;
    } catch {
      data = null;
    }
  }

  if (!response.ok) {
    if (data?.error?.message) {
      throw data as ApiError;
    }
    const fallbackMessage =
      typeof data?.raw === "string" && data.raw.trim().length > 0 && data.raw.length < 150
        ? data.raw.trim()
        : response.statusText || `Request failed with status ${response.status}`;
    const error: ApiError = {
      error: {
        code: `HTTP_${response.status}`,
        message: fallbackMessage,
        details: data,
      },
    };
    throw error;
  }

  return (data ?? {}) as T;
}

export async function createSession(
  seed = true,
  demoTimestamp?: string
): Promise<SessionResponse> {
  const body: SessionCreateRequest = {
    seed,
    demo_timestamp: demoTimestamp,
  };
  return request<SessionResponse>("/sessions", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function resetSession(sid: string): Promise<SessionResetResponse> {
  return request<SessionResetResponse>(`/sessions/${encodeURIComponent(sid)}`, {
    method: "DELETE",
  });
}

export async function sendMessage(
  sid: string,
  message: string,
  stateVersion?: number | null,
  provider?: string | null
): Promise<AgentMessageResponse> {
  const body: AgentMessageRequest = {
    message,
    state_version: stateVersion,
  };
  const query = provider ? `?provider=${encodeURIComponent(provider)}` : "";
  return request<AgentMessageResponse>(`/sessions/${encodeURIComponent(sid)}/agent/message${query}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getPlan(sid: string, pid: string): Promise<PlanResponse> {
  return request<PlanResponse>(
    `/sessions/${encodeURIComponent(sid)}/plans/${encodeURIComponent(pid)}`
  );
}

export async function confirmPlan(
  sid: string,
  pid: string,
  stateVersion?: number | null
): Promise<ConfirmResponse> {
  const body: ConfirmRequest = {
    state_version: stateVersion,
  };
  return request<ConfirmResponse>(
    `/sessions/${encodeURIComponent(sid)}/plans/${encodeURIComponent(pid)}/confirm`,
    {
      method: "POST",
      body: JSON.stringify(body),
    }
  );
}

export async function cancelPlan(sid: string, pid: string): Promise<CancelResponse> {
  return request<CancelResponse>(
    `/sessions/${encodeURIComponent(sid)}/plans/${encodeURIComponent(pid)}/cancel`,
    {
      method: "POST",
    }
  );
}

export async function getSchedule(sid: string): Promise<ScheduleResponse> {
  return request<ScheduleResponse>(`/sessions/${encodeURIComponent(sid)}/schedule`);
}

export async function getTasks(sid: string): Promise<TasksResponse> {
  return request<TasksResponse>(`/sessions/${encodeURIComponent(sid)}/tasks`);
}

export interface TaskInput {
  title: string;
  duration_minutes: number;
  priority: string;
  category: string;
  deadline: string | null;
}

export async function saveTask(sid: string, task: TaskInput, stateVersion: number, taskId?: string): Promise<{ state_version: number }> {
  const path = `/sessions/${encodeURIComponent(sid)}/tasks${taskId ? `/${encodeURIComponent(taskId)}` : ''}`;
  return request(path, { method: taskId ? 'PATCH' : 'POST', body: JSON.stringify({ ...task, state_version: stateVersion }) });
}

export async function deleteTask(sid: string, taskId: string, stateVersion: number): Promise<{ state_version: number }> {
  return request(`/sessions/${encodeURIComponent(sid)}/tasks/${encodeURIComponent(taskId)}`, {
    method: 'DELETE', body: JSON.stringify({ state_version: stateVersion }),
  });
}

export async function proposeCommitment(sid: string, event: { title: string; start_time: string; end_time: string }, stateVersion: number): Promise<PlanResponse> {
  return request(`/sessions/${encodeURIComponent(sid)}/commitments`, {
    method: 'POST', body: JSON.stringify({ ...event, state_version: stateVersion }),
  });
}

export async function getMemory(sid: string): Promise<MemoryResponse> {
  return request<MemoryResponse>(`/sessions/${encodeURIComponent(sid)}/memory`);
}

export async function getExecutionLog(sid: string): Promise<ExecutionLogResponse> {
  return request<ExecutionLogResponse>(`/sessions/${encodeURIComponent(sid)}/execution-log`);
}

/** Personal days keep tasks isolated; routines are persisted in SQLite. */
export interface RoutineInput {
  name: string; weekdays: number[]; starts_on: string;
  tasks: { title: string; duration_minutes: number; priority: 'HIGH' | 'MEDIUM' | 'LOW'; category: 'work' | 'personal' }[];
}
export interface Routine extends RoutineInput { id: string }
export const createWorkspace = () => request<{workspace_id: string}>('/workspaces', {method: 'POST'});
export const openDay = (wid: string, day: string, offsetMinutes: number) => request<{session_id: string; timestamp: string; routine_tasks_added: number}>(`/workspaces/${encodeURIComponent(wid)}/days`, {method: 'POST', body: JSON.stringify({day, offset_minutes: offsetMinutes})});
export const getRoutines = (wid: string) => request<{routines: Routine[]}>(`/workspaces/${encodeURIComponent(wid)}/routines`);
export const saveRoutine = (wid: string, routine: RoutineInput) => request(`/workspaces/${encodeURIComponent(wid)}/routines`, {method: 'POST', body: JSON.stringify(routine)});
export const stopRoutine = (wid: string, rid: string) => request(`/workspaces/${encodeURIComponent(wid)}/routines/${encodeURIComponent(rid)}`, {method: 'DELETE'});

export interface TaskDraft {
  id: string; status: string; state_version: number; explanation: string;
  changes: {action: 'add' | 'update' | 'remove'; task_id: string | null; before: TaskInput | null; after: TaskInput | null}[];
}
export const getTaskDraft = (sid: string, did: string) => request<TaskDraft>(`/sessions/${encodeURIComponent(sid)}/task-drafts/${encodeURIComponent(did)}`);
export const getPendingTaskDraft = (sid: string) => request<{draft: TaskDraft | null}>(`/sessions/${encodeURIComponent(sid)}/task-drafts/pending`);
export const confirmTaskDraft = (sid: string, draft: TaskDraft) => request<{state_version: number}>(`/sessions/${encodeURIComponent(sid)}/task-drafts/${encodeURIComponent(draft.id)}/confirm`, {method: 'POST', body: JSON.stringify({state_version: draft.state_version})});
export const cancelTaskDraft = (sid: string, did: string) => request(`/sessions/${encodeURIComponent(sid)}/task-drafts/${encodeURIComponent(did)}/cancel`, {method: 'POST'});
