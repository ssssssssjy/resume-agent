import { getAuthHeaders } from "./auth";
import { buildApiUrl, API_ENDPOINTS } from "./config";
import type { Session, SessionDetail } from "@/types";

export async function createSession(data: {
  thread_id: string;
  filename: string;
  resume_content: string;
}): Promise<SessionDetail> {
  const response = await fetch(buildApiUrl(API_ENDPOINTS.SESSIONS.BASE), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(data),
  });
  return response.json();
}

export async function listSessions(limit = 50): Promise<Session[]> {
  const response = await fetch(buildApiUrl(`${API_ENDPOINTS.SESSIONS.BASE}?limit=${limit}`), {
    headers: getAuthHeaders(),
  });
  return response.json();
}

export async function getSession(threadId: string): Promise<SessionDetail> {
  const response = await fetch(buildApiUrl(API_ENDPOINTS.SESSIONS.DETAIL(threadId)), {
    headers: getAuthHeaders(),
  });
  if (!response.ok) {
    throw new Error("Session not found");
  }
  return response.json();
}

export async function deleteSession(threadId: string): Promise<void> {
  await fetch(buildApiUrl(API_ENDPOINTS.SESSIONS.DETAIL(threadId)), {
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
  const response = await fetch(buildApiUrl(API_ENDPOINTS.SESSIONS.BASE), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeaders() },
    body: JSON.stringify(data),
  });
  return response.json();
}

// Re-export types for convenience
export type { Session, SessionDetail } from "@/types";
