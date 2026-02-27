"use client";

import { useState, useCallback } from "react";
import type { Session, SessionDetail } from "@/types";
import {
  listSessions,
  getSession,
  createSession,
  updateSession,
  deleteSession,
} from "@/api/sessions";

interface UseSessionsReturn {
  sessions: Session[];
  isLoading: boolean;
  loadSessions: () => Promise<void>;
  getSessionDetail: (threadId: string) => Promise<SessionDetail>;
  saveSession: (data: { thread_id: string; filename: string; resume_content: string }) => Promise<SessionDetail>;
  updateSessionContent: (data: { thread_id: string; filename: string; resume_content: string }) => Promise<void>;
  removeSession: (threadId: string) => Promise<void>;
}

/**
 * 会话管理 Hook
 */
export function useSessions(): UseSessionsReturn {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // 加载会话列表
  const loadSessions = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await listSessions();
      setSessions(data);
    } catch (error) {
      console.error("Failed to load sessions:", error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // 获取会话详情
  const getSessionDetail = useCallback(async (threadId: string): Promise<SessionDetail> => {
    return getSession(threadId);
  }, []);

  // 保存新会话
  const saveSession = useCallback(async (data: {
    thread_id: string;
    filename: string;
    resume_content: string;
  }): Promise<SessionDetail> => {
    const result = await createSession(data);
    // 刷新会话列表
    await loadSessions();
    return result;
  }, [loadSessions]);

  // 更新会话内容
  const updateSessionContent = useCallback(async (data: {
    thread_id: string;
    filename: string;
    resume_content: string;
  }): Promise<void> => {
    await updateSession(data);
  }, []);

  // 删除会话
  const removeSession = useCallback(async (threadId: string): Promise<void> => {
    await deleteSession(threadId);
    await loadSessions();
  }, [loadSessions]);

  return {
    sessions,
    isLoading,
    loadSessions,
    getSessionDetail,
    saveSession,
    updateSessionContent,
    removeSession,
  };
}
