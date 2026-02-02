import { getAuthHeaders } from "./auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface Session {
  thread_id: string;
  filename: string;
  created_at: string;
  updated_at: string;
}

export interface SessionDetail extends Session {
  resume_content: string;
}

export async function createSession(data: {
  thread_id: string;
  filename: string;
  resume_content: string;
}): Promise<SessionDetail> {
  const response = await fetch(`${API_BASE}/api/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(data),
  });
  return response.json();
}

export async function listSessions(limit = 50): Promise<Session[]> {
  const response = await fetch(`${API_BASE}/api/sessions?limit=${limit}`, {
    headers: getAuthHeaders(),
  });
  return response.json();
}

export async function getSession(threadId: string): Promise<SessionDetail> {
  const response = await fetch(`${API_BASE}/api/sessions/${threadId}`, {
    headers: getAuthHeaders(),
  });
  if (!response.ok) {
    throw new Error("Session not found");
  }
  return response.json();
}

export async function deleteSession(threadId: string): Promise<void> {
  await fetch(`${API_BASE}/api/sessions/${threadId}`, {
    method: "DELETE",
    headers: getAuthHeaders(),
  });
}

export async function updateSession(data: {
  thread_id: string;
  filename: string;
  resume_content: string;
}): Promise<SessionDetail> {
  // 使用 createSession 的 UPSERT 功能来更新
  const response = await fetch(`${API_BASE}/api/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(data),
  });
  return response.json();
}
