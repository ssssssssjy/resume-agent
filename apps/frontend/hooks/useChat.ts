"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import type { Message, FileData, PendingEdit, ThreadState, ReferenceFiles } from "@/types";
import {
  createThread,
  streamResumeEnhancement,
  getThreadState,
  getPendingEdit,
  resumeWithDecision,
} from "@/api/langgraph";
import { parseStateMessages, extractReferenceFiles } from "@/lib/message-parser";
import { findMatchingString } from "@/lib/string-match";
import { buildApiUrl, API_ENDPOINTS } from "@/api/config";

interface UseChatOptions {
  onSessionUpdate?: (threadId: string, content: string) => void;
}

interface UseChatReturn {
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  isLoading: boolean;
  threadId: string | null;
  setThreadId: (id: string | null) => void;
  pendingEdit: PendingEdit | null;
  setPendingEdit: (edit: PendingEdit | null) => void;
  referenceFiles: ReferenceFiles;
  scrollRef: React.RefObject<HTMLDivElement | null>;
  sendMessage: (message: string) => Promise<void>;
  handleFileUpload: (file: File, onParsed: (text: string) => void) => Promise<string | null>;
  handleApproveEdit: (pdfText: string, pdfFilename: string) => Promise<string | null>;
  handleRejectEdit: () => Promise<void>;
  checkForPendingEdit: (tid: string) => Promise<void>;
  restoreSession: (threadId: string, content: string) => Promise<{
    messages: Message[];
    referenceFiles: ReferenceFiles;
    pendingEdit: PendingEdit | null;
    latestContent: string | null;
  }>;
  resetChat: () => void;
}

/**
 * 聊天逻辑 Hook
 */
export function useChat(options: UseChatOptions = {}): UseChatReturn {
  const { onSessionUpdate } = options;

  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [pendingEdit, setPendingEdit] = useState<PendingEdit | null>(null);
  const [referenceFiles, setReferenceFiles] = useState<ReferenceFiles>({});
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // Save threadId to localStorage
  useEffect(() => {
    if (threadId) {
      localStorage.setItem("lastThreadId", threadId);
    }
  }, [threadId]);

  // Parse PDF via backend API
  const parsePDF = useCallback(async (file: File): Promise<string> => {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(buildApiUrl(API_ENDPOINTS.PARSE_PDF), {
      method: "POST",
      body: formData,
    });

    const result = await response.json();

    if (result.error) {
      throw new Error(result.error);
    }

    return result.markdown;
  }, []);

  // Check for pending edits
  const checkForPendingEdit = useCallback(async (tid: string) => {
    try {
      const state = await getThreadState(tid) as ThreadState;
      const edit = getPendingEdit(state);

      if (edit) {
        // 从 LangGraph state 获取最新内容
        let currentContent = "";
        if (state?.values?.files?.["/resume.md"]) {
          currentContent = state.values.files["/resume.md"].content.join("\n");
        }

        // 使用三层匹配策略
        const match = findMatchingString(edit.oldString, currentContent);
        if (match.found) {
          setPendingEdit({ ...edit, oldString: match.matchedString });
        }
      }
    } catch (error) {
      console.error("Failed to check pending edit:", error);
    }
  }, []);

  // Send message
  const sendMessage = useCallback(async (userMessage: string) => {
    if (!userMessage.trim() || isLoading || !threadId || pendingEdit) return;

    setMessages(prev => [...prev, { role: "user", content: userMessage }]);
    setIsLoading(true);

    try {
      const stream = streamResumeEnhancement(threadId, userMessage);

      for await (const event of stream) {
        if (event.type === "state_update") {
          const state = event.data as {
            messages?: Message[];
            files?: Record<string, FileData>;
          };

          if (state.messages) {
            const parsedMessages = parseStateMessages(state.messages as never[]);
            setMessages(parsedMessages);
          }

          if (state.files) {
            const refs = extractReferenceFiles(state.files);
            setReferenceFiles(refs);
          }
        }

        if (event.type === "error") {
          const errorMsg = typeof event.data === "string" ? event.data : "未知错误";
          setMessages(prev => [
            ...prev,
            { role: "assistant", content: `抱歉，处理请求时出错：${errorMsg}` },
          ]);
        }
      }

      await checkForPendingEdit(threadId);
    } catch (error) {
      console.error("Failed to send message:", error);
      setMessages(prev => [
        ...prev,
        { role: "assistant", content: "抱歉，发送消息失败。请检查网络连接后重试。" },
      ]);
    } finally {
      setIsLoading(false);
    }
  }, [threadId, isLoading, pendingEdit, checkForPendingEdit]);

  // Handle file upload
  const handleFileUpload = useCallback(async (
    file: File,
    onParsed: (text: string) => void
  ): Promise<string | null> => {
    setIsLoading(true);
    setPendingEdit(null);

    try {
      // Parse PDF
      const text = await parsePDF(file);
      onParsed(text);

      // Create thread
      const { thread_id } = await createThread();
      setThreadId(thread_id);

      // Send initial message
      const initialMessage = `我上传了我的简历，文件路径是 /resume.md，请帮我分析并优化这份简历。`;
      const now = new Date().toISOString();
      const initialFiles: Record<string, FileData> = {
        "/resume.md": {
          content: text.split("\n"),
          created_at: now,
          modified_at: now,
        },
      };

      setMessages([{ role: "user", content: "我上传了我的简历，请帮我分析并优化。" }]);

      const stream = streamResumeEnhancement(thread_id, initialMessage, initialFiles);

      for await (const event of stream) {
        if (event.type === "state_update") {
          const state = event.data as {
            messages?: Message[];
            files?: Record<string, FileData>;
          };

          if (state.messages) {
            const parsedMessages = parseStateMessages(state.messages as never[]);
            setMessages(parsedMessages);
          }

          if (state.files) {
            const refs = extractReferenceFiles(state.files);
            setReferenceFiles(refs);
          }
        }

        if (event.type === "error") {
          const errorMsg = typeof event.data === "string" ? event.data : "未知错误";
          setMessages(prev => [
            ...prev,
            { role: "assistant", content: `抱歉，处理请求时出错：${errorMsg}` },
          ]);
        }
      }

      await checkForPendingEdit(thread_id);
      return thread_id;
    } catch (error) {
      console.error("Failed to parse PDF:", error);
      setMessages([{
        role: "assistant",
        content: "抱歉，解析 PDF 时出现错误。请确保文件是有效的 PDF 格式后重试。",
      }]);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [parsePDF, checkForPendingEdit]);

  // Handle approve edit
  const handleApproveEdit = useCallback(async (
    pdfText: string,
    pdfFilename: string
  ): Promise<string | null> => {
    if (!pendingEdit || !threadId) return null;

    const currentPendingEdit = pendingEdit;

    // 使用三层匹配策略找到实际的 oldString
    const match = findMatchingString(currentPendingEdit.oldString, pdfText);

    // 乐观更新 - 立即计算新内容
    const optimisticContent = pdfText.replace(match.matchedString, currentPendingEdit.newString);
    const contentChanged = optimisticContent !== pdfText;

    // 立即清除 pending 状态
    setPendingEdit(null);

    if (!contentChanged) {
      setMessages(prev => [...prev, { role: "assistant", content: "修改未生效（内容未找到）" }]);
      return null;
    }

    // 后台同步到 Session DB
    if (pdfFilename && onSessionUpdate) {
      onSessionUpdate(threadId, optimisticContent);
    }

    // 后台异步发送 resume，不阻塞 UI 更新
    setIsLoading(true);
    (async () => {
      try {
        const stream = resumeWithDecision(threadId, currentPendingEdit, "approve");

        for await (const event of stream) {
          if (event.type === "state_update") {
            const state = event.data as { messages?: Message[] };
            if (state.messages) {
              const parsedMessages = parseStateMessages(state.messages as never[]);
              setMessages(parsedMessages);
            }
          }
        }

        // Check for more pending edits
        const state = await getThreadState(threadId) as ThreadState;
        const newEdit = getPendingEdit(state);
        if (newEdit && newEdit.interruptId !== currentPendingEdit.interruptId) {
          if (optimisticContent.includes(newEdit.oldString)) {
            setPendingEdit(newEdit);
          }
        }
      } catch (error) {
        console.error("Failed to approve edit:", error);
        setMessages(prev => [...prev, { role: "assistant", content: "后台同步失败，但修改已应用。" }]);
      } finally {
        setIsLoading(false);
      }
    })();

    // 立即返回乐观更新的内容，不等待后台完成
    return optimisticContent;
  }, [pendingEdit, threadId, onSessionUpdate]);

  // Handle reject edit
  const handleRejectEdit = useCallback(async () => {
    if (!pendingEdit || !threadId) return;

    setIsLoading(true);
    try {
      const currentPendingEdit = pendingEdit;
      setPendingEdit(null);

      const stream = resumeWithDecision(threadId, currentPendingEdit, "reject");

      for await (const event of stream) {
        if (event.type === "state_update") {
          const state = event.data as { messages?: Message[] };
          if (state.messages) {
            const parsedMessages = parseStateMessages(state.messages as never[]);
            setMessages(parsedMessages);
          }
        }
      }

      setMessages(prev => [...prev, { role: "assistant", content: "已取消修改。" }]);

      // Check for more pending edits
      const state = await getThreadState(threadId) as ThreadState;
      const newEdit = getPendingEdit(state);
      if (newEdit && newEdit.interruptId !== currentPendingEdit.interruptId) {
        setPendingEdit(newEdit);
        setMessages(prev => [
          ...prev,
          { role: "assistant", content: "我建议对简历进行以下修改，请在左侧预览并确认是否接受。" },
        ]);
      }
    } catch (error) {
      console.error("Failed to reject edit:", error);
      setMessages(prev => [...prev, { role: "assistant", content: "操作过程中出现错误，请重试。" }]);
    } finally {
      setIsLoading(false);
    }
  }, [pendingEdit, threadId]);

  // Restore session
  const restoreSession = useCallback(async (tid: string, savedContent: string) => {
    const state = await getThreadState(tid) as ThreadState;

    // 优先使用 LangGraph state 中的内容
    let latestContent: string | null = null;
    if (state?.values?.files?.["/resume.md"]) {
      latestContent = state.values.files["/resume.md"].content.join("\n");
    }

    // Parse messages
    let restoredMessages: Message[] = [];
    if (state?.values?.messages) {
      restoredMessages = parseStateMessages(state.values.messages);
    }

    // Extract reference files
    const refs = extractReferenceFiles(state?.values?.files);

    // Check for pending edits
    let edit: PendingEdit | null = null;
    const pendingEditFromState = getPendingEdit(state);
    if (pendingEditFromState) {
      const content = latestContent || savedContent;
      const match = findMatchingString(pendingEditFromState.oldString, content);
      if (match.found) {
        edit = { ...pendingEditFromState, oldString: match.matchedString };
      }
    }

    // Update local state
    setMessages(restoredMessages);
    setReferenceFiles(refs);
    setPendingEdit(edit);
    setThreadId(tid);

    return {
      messages: restoredMessages,
      referenceFiles: refs,
      pendingEdit: edit,
      latestContent,
    };
  }, []);

  // Reset chat
  const resetChat = useCallback(() => {
    setMessages([]);
    setThreadId(null);
    setPendingEdit(null);
    setReferenceFiles({});
    localStorage.removeItem("lastThreadId");
  }, []);

  return {
    messages,
    setMessages,
    isLoading,
    threadId,
    setThreadId,
    pendingEdit,
    setPendingEdit,
    referenceFiles,
    scrollRef,
    sendMessage,
    handleFileUpload,
    handleApproveEdit,
    handleRejectEdit,
    checkForPendingEdit,
    restoreSession,
    resetChat,
  };
}
