"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Loader2, Sparkles, FileText, X, Plus, History, Trash2, LogOut, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import ReactMarkdown from "react-markdown";
import { MarkdownViewer } from "@/components/resume/markdown-viewer";
import { PDFUpload } from "@/components/resume/pdf-upload";
import { LoginForm } from "@/components/auth/login-form";
import {
  createThread,
  streamResumeEnhancement,
  getThreadState,
  getPendingEdit,
  resumeWithDecision,
  updateThreadState,
  type PendingEdit,
  type ThreadState,
  type FileData,
} from "@/api/langgraph";
import { createSession, listSessions, getSession, deleteSession, updateSession, type Session } from "@/api/sessions";
import { getStoredUser, logout, getCurrentUser, type UserInfo } from "@/api/auth";

interface ToolCall {
  name: string;
  args: Record<string, unknown>;
  status?: "running" | "success" | "error";
  result?: string;
}

interface Message {
  role: "user" | "assistant" | "tool";
  content: string;
  toolCalls?: ToolCall[];
}

export default function HomePage() {
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [pdfFilename, setPdfFilename] = useState<string>("");
  const [pdfText, setPdfText] = useState<string>("");
  const [isParsing, setIsParsing] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [pendingEdit, setPendingEdit] = useState<PendingEdit | null>(null);
  const [user, setUser] = useState<UserInfo | null>(null);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Check auth on mount
  useEffect(() => {
    const checkAuth = async () => {
      const storedUser = getStoredUser();
      if (storedUser) {
        setUser(storedUser);
        // 后台验证 token 有效性
        const validUser = await getCurrentUser();
        if (!validUser) {
          setUser(null);
        }
      }
      setIsCheckingAuth(false);
    };
    checkAuth();
  }, []);

  // Load sessions on mount and restore last session
  useEffect(() => {
    if (!user) return; // 只有登录后才加载 sessions

    const init = async () => {
      await loadSessions();

      // Try to restore last session from localStorage
      const lastThreadId = localStorage.getItem("lastThreadId");
      if (lastThreadId) {
        try {
          const detail = await getSession(lastThreadId);
          // Session exists, restore it
          setPdfFilename(detail.filename);
          setThreadId(lastThreadId);
          setPdfFile({ name: detail.filename } as File);

          // Get thread state to restore messages and content
          const state = await getThreadState(lastThreadId) as ThreadState;

          // 优先使用 LangGraph state 中的 files 内容（这是最新的）
          let currentContent = detail.resume_content;
          if (state?.values?.files?.["/resume.md"]) {
            const stateContent = state.values.files["/resume.md"].content.join("\n");
            console.log("Using content from LangGraph state, length:", stateContent.length);
            currentContent = stateContent;
            // 同步到 Session DB
            await updateSession({
              thread_id: lastThreadId,
              filename: detail.filename,
              resume_content: stateContent,
            });
          }
          setPdfText(currentContent);

          if (state?.values?.messages) {
            const restoredMessages: Message[] = state.values.messages
              .filter((msg: { type: string }) => msg.type === "human" || msg.type === "ai" || msg.type === "HumanMessage" || msg.type === "AIMessage")
              .map((msg: { type: string; content: string }) => ({
                role: (msg.type === "human" || msg.type === "HumanMessage") ? "user" : "assistant",
                content: msg.content,
              }));
            setMessages(restoredMessages);
          }

          // Check for pending edits - 使用同步后的 currentContent
          const edit = getPendingEdit(state);
          if (edit && currentContent.includes(edit.oldString)) {
            setPendingEdit(edit);
          }
        } catch {
          // Session not found (可能是切换用户后的旧 session)，静默清理
          localStorage.removeItem("lastThreadId");
        }
      }
    };
    init();
  }, [user]);

  const loadSessions = async () => {
    try {
      const data = await listSessions();
      setSessions(data);
    } catch (error) {
      console.error("Failed to load sessions:", error);
    }
  };

  // Save current threadId to localStorage when it changes
  useEffect(() => {
    if (threadId) {
      localStorage.setItem("lastThreadId", threadId);
    }
  }, [threadId]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // Parse PDF via backend API
  const parsePDF = async (file: File): Promise<string> => {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch("http://localhost:8000/api/parse-pdf", {
      method: "POST",
      body: formData,
    });

    const result = await response.json();

    if (result.error) {
      throw new Error(result.error);
    }

    return result.markdown;
  };

  // Check for pending edits after stream completes
  const checkForPendingEdit = async (tid: string) => {
    try {
      const state = await getThreadState(tid) as ThreadState;
      console.log("Thread state tasks:", state.tasks);
      const edit = getPendingEdit(state);
      console.log("Pending edit:", edit);

      if (edit) {
        // 必须从 LangGraph state 获取最新内容（不能依赖 pdfText 闭包）
        let currentContent = "";
        if (state?.values?.files?.["/resume.md"]) {
          currentContent = state.values.files["/resume.md"].content.join("\n");
          console.log("Got content from LangGraph state, length:", currentContent.length);
          // 同步到前端状态
          setPdfText(currentContent);
        }

        // 检查 oldString 是否存在于当前内容中
        if (currentContent && currentContent.includes(edit.oldString)) {
          console.log("oldString found in content, setting pendingEdit");
          setPendingEdit(edit);
          // 不再单独添加消息，左侧预览区会显示 diff 和操作按钮
        } else {
          console.warn("oldString not found in current content, skipping pendingEdit");
          console.log("oldString (first 100 chars):", edit.oldString.substring(0, 100));
          console.log("currentContent (first 200 chars):", currentContent.substring(0, 200));
        }
      }
    } catch (error) {
      console.error("Failed to check pending edit:", error);
    }
  };

  // Handle approve edit - 使用乐观更新，立即显示修改结果
  const handleApproveEdit = async () => {
    if (!pendingEdit || !threadId) return;

    const currentPendingEdit = pendingEdit;
    const previousContent = pdfText;

    // 调试：检查 oldString 是否存在于 pdfText 中
    const oldStringExists = pdfText.includes(currentPendingEdit.oldString);
    console.log("handleApproveEdit called");
    console.log("oldString exists in pdfText:", oldStringExists);
    console.log("oldString length:", currentPendingEdit.oldString.length);
    console.log("pdfText length:", pdfText.length);
    if (!oldStringExists) {
      console.warn("oldString not found in pdfText!");
      console.log("oldString (first 200 chars):", currentPendingEdit.oldString.substring(0, 200));
      console.log("pdfText (first 500 chars):", pdfText.substring(0, 500));
    }

    // 乐观更新：立即应用修改并清除 pending edit
    const optimisticContent = pdfText.replace(currentPendingEdit.oldString, currentPendingEdit.newString);
    const contentChanged = optimisticContent !== pdfText;
    console.log("Content changed after replace:", contentChanged);

    setPdfText(optimisticContent);
    setPendingEdit(null);
    // 只在出错时显示消息，成功时左侧预览区已经显示了变化
    if (!contentChanged) {
      setMessages((prev) => [...prev, { role: "assistant", content: "修改未生效（内容未找到）" }]);
    }

    // 后台同步到 Session DB
    if (pdfFilename) {
      updateSession({
        thread_id: threadId,
        filename: pdfFilename,
        resume_content: optimisticContent,
      }).catch(console.error);
    }

    // 后台发送 resume 到 backend，不阻塞 UI
    setIsLoading(true);
    let latestBackendContent: string | null = null;
    try {
      const stream = resumeWithDecision(threadId, currentPendingEdit, "approve");
      let assistantMessage = "";

      for await (const event of stream) {
        console.log("Stream event:", event.type);
        if (event.type === "state") {
          const state = event.data as {
            messages?: Array<{ content: string; type: string }>;
            files?: Record<string, { content: string[] }>;
          };
          console.log("State files keys:", state.files ? Object.keys(state.files) : "no files");
          // 检查 backend 返回的内容
          if (state.files && state.files["/resume.md"]) {
            const backendContent = state.files["/resume.md"].content.join("\n");
            latestBackendContent = backendContent;
            console.log("Backend content length:", backendContent.length);
            console.log("Backend content changed from optimistic:", backendContent !== optimisticContent);
            // 始终使用 backend 返回的最新内容
            setPdfText(backendContent);
            if (pdfFilename) {
              updateSession({
                thread_id: threadId,
                filename: pdfFilename,
                resume_content: backendContent,
              }).catch(console.error);
            }
          }
          if (state.messages && state.messages.length > 0) {
            const lastMsg = state.messages[state.messages.length - 1];
            if (lastMsg.type === "ai" || lastMsg.type === "AIMessage") {
              if (lastMsg.content) {
                assistantMessage = lastMsg.content;
              }
            }
          }
        }
      }

      console.log("Stream completed. Latest backend content received:", !!latestBackendContent);

      // 如果 backend 返回了额外的有意义的消息，追加显示
      if (assistantMessage && !["已完成修改。", "已完成修改", "修改已完成"].includes(assistantMessage.trim())) {
        setMessages((prev) => [...prev, { role: "assistant", content: assistantMessage }]);
      }

      // Check for more pending edits
      try {
        const state = await getThreadState(threadId) as ThreadState;
        const newEdit = getPendingEdit(state);
        // 只有当新的 edit 与刚处理的不同，且 old_string 存在于当前内容中时才设置
        if (newEdit && newEdit.interruptId !== currentPendingEdit.interruptId) {
          if (optimisticContent.includes(newEdit.oldString)) {
            setPendingEdit(newEdit);
            // 不再单独添加消息，左侧预览区会显示 diff 和操作按钮
          }
        }
      } catch (error) {
        console.error("Failed to check for more pending edits:", error);
      }
    } catch (error) {
      console.error("Failed to approve edit:", error);
      // 乐观更新失败时回滚
      setPdfText(previousContent);
      setPendingEdit(currentPendingEdit);
      setMessages((prev) => [...prev, { role: "assistant", content: "修改过程中出现错误，请重试。" }]);
      // 回滚 Session DB
      if (pdfFilename) {
        updateSession({
          thread_id: threadId,
          filename: pdfFilename,
          resume_content: previousContent,
        }).catch(console.error);
      }
    } finally {
      setIsLoading(false);
    }
  };

  // Handle reject edit
  const handleRejectEdit = async () => {
    if (!pendingEdit || !threadId) return;

    setIsLoading(true);
    try {
      // Clear pending edit first
      const currentPendingEdit = pendingEdit;
      setPendingEdit(null);

      // Resume the agent with rejection and stream the response
      const stream = resumeWithDecision(threadId, currentPendingEdit, "reject");
      let assistantMessage = "";

      for await (const event of stream) {
        console.log("Resume stream event:", event.type, event.data);
        if (event.type === "state") {
          const state = event.data as { messages?: Array<{ content: string; type: string }> };
          if (state.messages && state.messages.length > 0) {
            const lastMsg = state.messages[state.messages.length - 1];
            if (lastMsg.type === "ai" || lastMsg.type === "AIMessage") {
              if (lastMsg.content) {
                assistantMessage = lastMsg.content;
              }
            }
          }
        }
      }

      if (assistantMessage) {
        setMessages((prev) => [...prev, { role: "assistant", content: assistantMessage }]);
      } else {
        setMessages((prev) => [...prev, { role: "assistant", content: "已取消修改。" }]);
      }

      // Check for more pending edits (different from the one we just rejected)
      try {
        const state = await getThreadState(threadId) as ThreadState;
        const newEdit = getPendingEdit(state);
        // 只有当新的 edit 与刚处理的不同时才设置
        if (newEdit && newEdit.interruptId !== currentPendingEdit.interruptId) {
          setPendingEdit(newEdit);
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content: "我建议对简历进行以下修改，请在左侧预览并确认是否接受。",
            },
          ]);
        }
      } catch (error) {
        console.error("Failed to check for more pending edits:", error);
      }
    } catch (error) {
      console.error("Failed to reject edit:", error);
      setMessages((prev) => [...prev, { role: "assistant", content: "操作过程中出现错误，请重试。" }]);
    } finally {
      setIsLoading(false);
    }
  };

  // Handle PDF file selection
  const handleFileSelect = async (file: File) => {
    setPdfFile(file);
    setPdfFilename(file.name);
    setIsParsing(true);
    setPendingEdit(null);

    try {
      // Parse PDF to extract text
      const text = await parsePDF(file);
      setPdfText(text);

      // Initialize thread
      const { thread_id } = await createThread();
      setThreadId(thread_id);

      // Save session to backend
      await createSession({
        thread_id,
        filename: file.name,
        resume_content: text,
      });

      // Refresh sessions list
      await loadSessions();

      // Send initial message with resume content and file
      const initialMessage = `我上传了我的简历，文件路径是 /resume.md，请帮我分析并优化这份简历。`;

      // 创建初始文件数据，将简历内容写入 agent 的 files state
      const now = new Date().toISOString();
      const initialFiles: Record<string, FileData> = {
        "/resume.md": {
          content: text.split("\n"),
          created_at: now,
          modified_at: now,
        },
      };

      setMessages([{ role: "user", content: "我上传了我的简历，请帮我分析并优化。" }]);
      setIsLoading(true);

      const stream = streamResumeEnhancement(thread_id, initialMessage, initialFiles);
      let assistantMessage = "";
      let currentToolCalls: ToolCall[] = [];
      let toolMessageIndex: number | null = null;

      for await (const event of stream) {
        if (event.type === "state") {
          const state = event.data as {
            messages?: Array<{
              content: string;
              type: string;
              name?: string;
              tool_calls?: Array<{ name: string; args: Record<string, unknown> }>;
            }>
          };
          if (state.messages && state.messages.length > 0) {
            for (let i = state.messages.length - 1; i >= 0; i--) {
              const msg = state.messages[i];

              // 处理工具调用
              if ((msg.type === "ai" || msg.type === "AIMessage") && msg.tool_calls && msg.tool_calls.length > 0) {
                const newToolCalls = msg.tool_calls.map(tc => ({
                  name: tc.name,
                  args: tc.args,
                  status: "running" as const,
                }));

                if (JSON.stringify(newToolCalls.map(t => t.name)) !== JSON.stringify(currentToolCalls.map(t => t.name))) {
                  currentToolCalls = newToolCalls;
                  setMessages((prev) => {
                    if (toolMessageIndex !== null) {
                      const updated = [...prev];
                      updated[toolMessageIndex] = { role: "tool", content: "", toolCalls: currentToolCalls };
                      return updated;
                    } else {
                      toolMessageIndex = prev.length;
                      return [...prev, { role: "tool", content: "", toolCalls: currentToolCalls }];
                    }
                  });
                }
                break;
              }

              // 处理工具结果
              if (msg.type === "tool" && msg.name) {
                setMessages((prev) => {
                  if (toolMessageIndex !== null && prev[toolMessageIndex]?.toolCalls) {
                    const updated = [...prev];
                    const toolCalls = updated[toolMessageIndex].toolCalls!.map(tc =>
                      tc.name === msg.name ? { ...tc, status: "success" as const } : tc
                    );
                    updated[toolMessageIndex] = { ...updated[toolMessageIndex], toolCalls };
                    return updated;
                  }
                  return prev;
                });
              }

              // 处理最终回复
              if ((msg.type === "ai" || msg.type === "AIMessage") && msg.content && !msg.tool_calls) {
                assistantMessage = msg.content;
                break;
              }
            }
          }
        }
      }

      // 标记所有工具为完成
      if (toolMessageIndex !== null) {
        setMessages((prev) => {
          const updated = [...prev];
          if (updated[toolMessageIndex!]?.toolCalls) {
            const toolCalls = updated[toolMessageIndex!].toolCalls!.map(tc => ({
              ...tc,
              status: tc.status === "running" ? "success" as const : tc.status,
            }));
            updated[toolMessageIndex!] = { ...updated[toolMessageIndex!], toolCalls };
          }
          return updated;
        });
      }

      if (assistantMessage) {
        setMessages((prev) => [...prev, { role: "assistant", content: assistantMessage }]);
      }

      // Check for pending edits
      await checkForPendingEdit(thread_id);
    } catch (error) {
      console.error("Failed to parse PDF:", error);
      setMessages([
        {
          role: "assistant",
          content: "抱歉，解析 PDF 时出现错误。请确保文件是有效的 PDF 格式后重试。",
        },
      ]);
    } finally {
      setIsParsing(false);
      setIsLoading(false);
    }
  };

  // Handle selecting a history session
  const handleSelectSession = async (session: Session) => {
    try {
      setIsParsing(true);
      setPendingEdit(null);

      // Get session details (including resume content)
      const detail = await getSession(session.thread_id);
      setPdfFilename(detail.filename);
      setThreadId(session.thread_id);
      setPdfFile({ name: detail.filename } as File); // Mock file object for UI

      // Get thread state to restore messages and get latest content
      const state = await getThreadState(session.thread_id) as ThreadState;

      // 优先使用 LangGraph state 中的 files 内容（这是最新的）
      let currentContent = detail.resume_content;
      if (state?.values?.files?.["/resume.md"]) {
        const stateContent = state.values.files["/resume.md"].content.join("\n");
        console.log("Using content from LangGraph state, length:", stateContent.length);
        currentContent = stateContent;
        // 同步到 Session DB
        await updateSession({
          thread_id: session.thread_id,
          filename: detail.filename,
          resume_content: stateContent,
        });
      }
      setPdfText(currentContent);

      if (state?.values?.messages) {
        const restoredMessages: Message[] = state.values.messages
          .filter((msg: { type: string }) => msg.type === "human" || msg.type === "ai" || msg.type === "HumanMessage" || msg.type === "AIMessage")
          .map((msg: { type: string; content: string }) => ({
            role: (msg.type === "human" || msg.type === "HumanMessage") ? "user" : "assistant",
            content: msg.content,
          }));
        setMessages(restoredMessages);
      }

      // Check for pending edits - 使用同步后的 currentContent
      const edit = getPendingEdit(state);
      if (edit && currentContent.includes(edit.oldString)) {
        setPendingEdit(edit);
      }
      // If there's a stale interrupt (old_string not in content), we ignore it
      // The user can continue chatting normally
    } catch (error) {
      console.error("Failed to restore session:", error);
    } finally {
      setIsParsing(false);
    }
  };

  // Handle deleting a session
  const handleDeleteSession = async (e: React.MouseEvent, threadId: string) => {
    e.stopPropagation();
    try {
      await deleteSession(threadId);
      await loadSessions();
    } catch (error) {
      console.error("Failed to delete session:", error);
    }
  };

  // Handle clearing the PDF / starting new
  const handleNewChat = () => {
    setPdfFile(null);
    setPdfFilename("");
    setPdfText("");
    setMessages([]);
    setThreadId(null);
    setInput("");
    setPendingEdit(null);
    // Clear localStorage so refresh won't restore the old session
    localStorage.removeItem("lastThreadId");
  };

  // Handle sending a message
  const handleSend = async () => {
    if (!input.trim() || isLoading || !threadId || pendingEdit) return;

    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setIsLoading(true);

    try {
      const stream = streamResumeEnhancement(threadId, userMessage);
      let assistantMessage = "";
      let currentToolCalls: ToolCall[] = [];
      let toolMessageIndex: number | null = null;

      for await (const event of stream) {
        console.log("Stream event:", event.type, event.data);
        if (event.type === "state") {
          const state = event.data as {
            messages?: Array<{
              content: string;
              type: string;
              name?: string;
              tool_call_id?: string;
              tool_calls?: Array<{ name: string; args: Record<string, unknown>; id?: string }>;
            }>
          };
          if (state.messages && state.messages.length > 0) {
            // 遍历所有消息，找到工具调用和工具结果
            for (let i = state.messages.length - 1; i >= 0; i--) {
              const msg = state.messages[i];

              // 处理工具调用
              if ((msg.type === "ai" || msg.type === "AIMessage") && msg.tool_calls && msg.tool_calls.length > 0) {
                const newToolCalls = msg.tool_calls.map(tc => ({
                  name: tc.name,
                  args: tc.args,
                  status: "running" as const,
                }));

                // 只有当有新的工具调用时才更新
                if (JSON.stringify(newToolCalls.map(t => t.name)) !== JSON.stringify(currentToolCalls.map(t => t.name))) {
                  currentToolCalls = newToolCalls;

                  // 添加或更新工具调用消息
                  setMessages((prev) => {
                    if (toolMessageIndex !== null) {
                      // 更新现有的工具消息
                      const updated = [...prev];
                      updated[toolMessageIndex] = { role: "tool", content: "", toolCalls: currentToolCalls };
                      return updated;
                    } else {
                      // 添加新的工具消息
                      toolMessageIndex = prev.length;
                      return [...prev, { role: "tool", content: "", toolCalls: currentToolCalls }];
                    }
                  });
                }
                break;
              }

              // 处理工具结果
              if (msg.type === "tool" && msg.name && msg.content) {
                // 更新对应工具的状态为成功
                setMessages((prev) => {
                  if (toolMessageIndex !== null && prev[toolMessageIndex]?.toolCalls) {
                    const updated = [...prev];
                    const toolCalls = updated[toolMessageIndex].toolCalls!.map(tc =>
                      tc.name === msg.name
                        ? { ...tc, status: "success" as const, result: msg.content.substring(0, 100) }
                        : tc
                    );
                    updated[toolMessageIndex] = { ...updated[toolMessageIndex], toolCalls };
                    return updated;
                  }
                  return prev;
                });
              }

              // 处理最终的 AI 回复
              if ((msg.type === "ai" || msg.type === "AIMessage") && msg.content && !msg.tool_calls) {
                assistantMessage = msg.content;
                break;
              }
            }
          }
        } else if (event.type === "error") {
          const errorMsg = typeof event.data === "string" ? event.data : "未知错误";
          console.error("Stream error:", errorMsg);
          assistantMessage = `抱歉，处理请求时出错：${errorMsg}`;
        }
      }

      // 标记所有工具调用为完成
      if (toolMessageIndex !== null) {
        setMessages((prev) => {
          const updated = [...prev];
          if (updated[toolMessageIndex!]?.toolCalls) {
            const toolCalls = updated[toolMessageIndex!].toolCalls!.map(tc => ({
              ...tc,
              status: tc.status === "running" ? "success" as const : tc.status,
            }));
            updated[toolMessageIndex!] = { ...updated[toolMessageIndex!], toolCalls };
          }
          return updated;
        });
      }

      // 如果有文本消息则显示
      if (assistantMessage) {
        setMessages((prev) => [...prev, { role: "assistant", content: assistantMessage }]);
      }

      // Check for pending edits
      await checkForPendingEdit(threadId);
    } catch (error) {
      console.error("Failed to send message:", error);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "抱歉，发送消息失败。请检查网络连接后重试。" },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // 检测是否正在使用输入法（IME），如果是则不处理 Enter
    // isComposing 为 true 表示正在输入法组合状态（如中文拼音输入中）
    if (e.nativeEvent.isComposing || e.keyCode === 229) {
      return;
    }

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return "今天";
    if (diffDays === 1) return "昨天";
    if (diffDays < 7) return `${diffDays}天前`;
    return date.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
  };

  // Handle logout
  const handleLogout = async () => {
    await logout();
    setUser(null);
    // 清空所有状态
    handleNewChat();
    setSessions([]);
  };

  // Handle login success
  const handleLoginSuccess = () => {
    const storedUser = getStoredUser();
    setUser(storedUser);
  };

  // 检查认证状态时显示加载
  if (isCheckingAuth) {
    return (
      <div className="h-screen flex items-center justify-center bg-background">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  // 未登录时显示登录页面
  if (!user) {
    return <LoginForm onSuccess={handleLoginSuccess} />;
  }

  return (
    <div className="h-screen bg-background flex overflow-hidden">
      {/* Sidebar */}
      {sidebarOpen && (
        <aside className="w-64 bg-card flex flex-col">
          {/* App Title */}
          <div className="p-4 pb-2">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                <Sparkles className="w-4 h-4 text-primary" />
              </div>
              <span className="font-semibold text-base">AI 简历优化</span>
            </div>
          </div>

          {/* New Chat Button */}
          <div className="px-4 pb-2">
            <Button
              onClick={handleNewChat}
              className="w-full justify-start gap-2 bg-secondary hover:bg-accent text-foreground"
            >
              <Plus className="w-4 h-4" />
              新建对话
            </Button>
          </div>

          {/* Sessions List */}
          <div className="flex-1 overflow-y-auto px-2">
            <div className="flex items-center gap-2 px-2 py-2 text-xs text-muted-foreground">
              <History className="w-3 h-3" />
              历史记录
            </div>
            <div className="space-y-1">
              {sessions.map((session) => (
                <div
                  key={session.thread_id}
                  onClick={() => handleSelectSession(session)}
                  className={`group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors ${
                    threadId === session.thread_id
                      ? "bg-accent"
                      : "hover:bg-accent/50"
                  }`}
                >
                  <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm truncate">{session.filename}</p>
                    <p className="text-xs text-muted-foreground">{formatDate(session.updated_at)}</p>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
                    onClick={(e) => handleDeleteSession(e, session.thread_id)}
                  >
                    <Trash2 className="w-3 h-3 text-muted-foreground" />
                  </Button>
                </div>
              ))}
              {sessions.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-8">
                  暂无历史记录
                </p>
              )}
            </div>
          </div>

          {/* User Info & Logout */}
          <div className="p-4 border-t border-border">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                  <User className="w-4 h-4 text-primary" />
                </div>
                <span className="text-sm font-medium truncate max-w-[120px]">{user.username}</span>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={handleLogout}
                title="退出登录"
              >
                <LogOut className="w-4 h-4 text-muted-foreground" />
              </Button>
            </div>
          </div>
        </aside>
      )}

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Main Content Area */}
        <main className="flex-1 flex overflow-hidden">
          {!pdfFile ? (
            /* Upload State */
            <div className="flex-1 flex items-center justify-center p-8">
              <div className="w-full max-w-xl">
                <PDFUpload onFileSelect={handleFileSelect} disabled={isParsing} />
              </div>
            </div>
          ) : (
            /* Split View - PDF on left, Chat on right */
            <div className="flex-1 flex min-h-0">
              {/* Left Panel - Markdown Viewer with Diff */}
              <div className="w-1/2 bg-card overflow-hidden">
                <MarkdownViewer
                  content={pdfText}
                  isLoading={isParsing}
                  className="h-full"
                  pendingEdit={pendingEdit}
                  onApprove={handleApproveEdit}
                  onReject={handleRejectEdit}
                />
              </div>

              {/* Right Panel - Chat */}
              <div className="w-1/2 flex flex-col min-h-0 bg-background overflow-hidden">

                {/* Messages Area - Scrollable */}
                <div className="flex-1 overflow-y-auto p-5" ref={scrollRef}>
                  <div className="space-y-5">
                    {messages.map((msg, idx) => (
                      <div
                        key={idx}
                        className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                      >
                        {msg.role === "tool" && msg.toolCalls ? (
                          /* 工具调用状态 - 简洁的内联样式 */
                          <div className="flex items-center gap-2 text-sm text-muted-foreground py-1">
                            {msg.toolCalls.some(t => t.status === "running") ? (
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            ) : (
                              <svg className="w-3.5 h-3.5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                              </svg>
                            )}
                            <span>
                              {msg.toolCalls.map((tool, i) => {
                                const toolNames: Record<string, string> = {
                                  read_file: "读取文件",
                                  edit_file: "编辑文件",
                                  write_file: "写入文件",
                                  search: "搜索",
                                };
                                const name = toolNames[tool.name] || tool.name;
                                const path = tool.args?.file_path ? ` ${String(tool.args.file_path)}` : "";
                                return (
                                  <span key={i}>
                                    {i > 0 && "、"}
                                    {name}
                                    {path && <code className="text-xs bg-muted px-1 py-0.5 rounded ml-1">{path}</code>}
                                  </span>
                                );
                              })}
                              {msg.toolCalls.some(t => t.status === "running") && "..."}
                            </span>
                          </div>
                        ) : (
                          <div
                            className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                              msg.role === "user"
                                ? "bg-primary text-primary-foreground"
                                : "bg-secondary"
                            }`}
                          >
                            {msg.role === "assistant" ? (
                              <div className="prose prose-sm max-w-none dark:prose-invert prose-p:leading-relaxed prose-headings:font-semibold">
                                <ReactMarkdown>{msg.content}</ReactMarkdown>
                              </div>
                            ) : (
                              <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                            )}
                          </div>
                        )}
                      </div>
                    ))}

                    {(isLoading || isParsing) && (
                      <div className="flex justify-start">
                        <div className="bg-secondary rounded-2xl px-4 py-3">
                          <div className="flex items-center gap-2">
                            <Loader2 className="w-4 h-4 animate-spin text-primary" />
                            <span className="text-sm text-muted-foreground">
                              {isParsing ? "正在解析简历..." : "思考中..."}
                            </span>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Input Area - Fixed at bottom */}
                <div className="flex-shrink-0 p-4">
                  <div className="flex gap-3 items-center">
                    <textarea
                      value={input}
                      onChange={(e) => setInput(e.target.value)}
                      onKeyDown={handleKeyDown}
                      placeholder={pendingEdit ? "请先处理待确认的修改..." : "输入您的问题或需求..."}
                      disabled={isLoading || isParsing || !threadId || !!pendingEdit}
                      className="flex-1 h-[48px] px-4 py-3 text-sm bg-secondary border-0 rounded-2xl resize-none focus:outline-none focus:ring-2 focus:ring-primary/50 disabled:opacity-50 placeholder:text-muted-foreground"
                      rows={1}
                    />
                    <Button
                      onClick={handleSend}
                      disabled={!input.trim() || isLoading || isParsing || !threadId || !!pendingEdit}
                      size="icon"
                      className="h-[48px] w-[48px] rounded-xl bg-primary hover:bg-primary/90 transition-colors"
                    >
                      {isLoading ? (
                        <Loader2 className="w-5 h-5 animate-spin" />
                      ) : (
                        <Send className="w-5 h-5" />
                      )}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
