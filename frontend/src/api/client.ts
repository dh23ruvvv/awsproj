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
  const response = await fetch(url, { ...options, headers });
  const data = await response.json();
  if (!response.ok) {
    const error: ApiError = data?.error
      ? data
      : { error: { code: `HTTP_${response.status}`, message: response.statusText, details: data } };
    throw error;
  }
  return data as T;
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
  stateVersion?: number | null
): Promise<AgentMessageResponse> {
  const body: AgentMessageRequest = {
    message,
    state_version: stateVersion,
  };
  return request<AgentMessageResponse>(`/sessions/${encodeURIComponent(sid)}/agent/message`, {
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

export async function getMemory(sid: string): Promise<MemoryResponse> {
  return request<MemoryResponse>(`/sessions/${encodeURIComponent(sid)}/memory`);
}

export async function getExecutionLog(sid: string): Promise<ExecutionLogResponse> {
  return request<ExecutionLogResponse>(`/sessions/${encodeURIComponent(sid)}/execution-log`);
}
