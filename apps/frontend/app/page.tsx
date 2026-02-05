"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Loader2, Sparkles, FileText, X, Plus, History, Trash2, LogOut, User, ChevronDown, ChevronRight, FileCode } from "lucide-react";
import { Button } from "@/components/ui/button";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
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

// LangGraph state message 类型
interface StateMessage {
  type: string;
  content: string | Array<{ type: string; text?: string }>;
  tool_calls?: Array<{ name: string; args: Record<string, unknown>; id?: string }>;
  name?: string;
  tool_call_id?: string;
}

// Levenshtein 距离计算（用于模糊匹配）
function levenshteinDistance(a: string, b: string): number {
  const matrix: number[][] = [];
  for (let i = 0; i <= b.length; i++) {
    matrix[i] = [i];
  }
  for (let j = 0; j <= a.length; j++) {
    matrix[0][j] = j;
  }
  for (let i = 1; i <= b.length; i++) {
    for (let j = 1; j <= a.length; j++) {
      if (b.charAt(i - 1) === a.charAt(j - 1)) {
        matrix[i][j] = matrix[i - 1][j - 1];
      } else {
        matrix[i][j] = Math.min(
          matrix[i - 1][j - 1] + 1, // 替换
          matrix[i][j - 1] + 1,     // 插入
          matrix[i - 1][j] + 1      // 删除
        );
      }
    }
  }
  return matrix[b.length][a.length];
}

// 计算字符串相似度 (0-1, 1 为完全匹配)
function stringSimilarity(a: string, b: string): number {
  if (a === b) return 1;
  if (a.length === 0 || b.length === 0) return 0;
  const distance = levenshteinDistance(a, b);
  const maxLen = Math.max(a.length, b.length);
  return 1 - distance / maxLen;
}

// 三层匹配策略：精确匹配 → trim 匹配 → 模糊匹配
// 返回 { found: boolean, matchedString: string }
function findMatchingString(
  targetString: string,
  content: string,
  similarityThreshold = 0.85
): { found: boolean; matchedString: string } {
  // 第一层：精确匹配
  if (content.includes(targetString)) {
    return { found: true, matchedString: targetString };
  }

  const trimmedTarget = targetString.trim();
  const lines = content.split("\n");

  // 第二层：trim 匹配
  for (const line of lines) {
    if (line.trim() === trimmedTarget || line.includes(trimmedTarget)) {
      return { found: true, matchedString: line };
    }
  }

  // 第三层：模糊匹配
  let bestMatch = { line: "", similarity: 0 };
  for (const line of lines) {
    const similarity = stringSimilarity(line.trim(), trimmedTarget);
    if (similarity > bestMatch.similarity && similarity >= similarityThreshold) {
      bestMatch = { line, similarity };
    }
  }

  if (bestMatch.similarity >= similarityThreshold) {
    return { found: true, matchedString: bestMatch.line };
  }

  return { found: false, matchedString: targetString };
}

// 从 LangGraph state 的 files 中提取 /references/ 目录下的参考文档
function extractReferenceFiles(files: Record<string, { content: string[]; modified_at?: string }> | undefined): Record<string, { content: string[]; modified_at?: string }> {
  if (!files) return {};
  const refs: Record<string, { content: string[]; modified_at?: string }> = {};
  for (const [path, data] of Object.entries(files)) {
    if (path.startsWith("/references/")) {
      refs[path] = data;
    }
  }
  return refs;
}

// 从 LangGraph state 的 messages 数组解析为前端 Message 格式
function parseStateMessages(stateMessages: StateMessage[]): Message[] {
  const result: Message[] = [];
  // 用于追踪哪些工具调用已经有结果了
  const completedToolCallIds = new Set<string>();

  // 先收集所有 ToolMessage 的 tool_call_id
  for (const msg of stateMessages) {
    if ((msg.type === "tool" || msg.type === "ToolMessage") && msg.tool_call_id) {
      completedToolCallIds.add(msg.tool_call_id);
    }
  }

  for (const msg of stateMessages) {
    // Human message
    if (msg.type === "human" || msg.type === "HumanMessage") {
      const content = typeof msg.content === "string"
        ? msg.content
        : msg.content.filter(b => b.type === "text").map(b => b.text || "").join("\n");
      result.push({ role: "user", content });
    }
    // AI message with tool_calls - 显示工具调用状态
    else if ((msg.type === "ai" || msg.type === "AIMessage") && msg.tool_calls && msg.tool_calls.length > 0) {
      const toolCalls: ToolCall[] = msg.tool_calls.map(tc => ({
        name: tc.name,
        args: tc.args,
        // 如果这个工具调用的结果已经存在，状态就是 success，否则是 running
        status: tc.id && completedToolCallIds.has(tc.id) ? "success" as const : "running" as const,
      }));
      result.push({ role: "tool", content: "", toolCalls });
    }
    // AI message without tool_calls - 显示文本回复
    else if (msg.type === "ai" || msg.type === "AIMessage") {
      const content = typeof msg.content === "string"
        ? msg.content
        : msg.content.filter(b => b.type === "text").map(b => b.text || "").join("\n");
      if (content) {
        result.push({ role: "assistant", content });
      }
    }
    // ToolMessage - 工具结果（不单独显示，已经在上面的 tool_calls 中标记状态了）
  }

  return result;
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
  const [referenceFiles, setReferenceFiles] = useState<Record<string, { content: string[]; modified_at?: string }>>({});
  const [activeFile, setActiveFile] = useState<string | null>(null); // null = 显示简历, 其他 = 参考文档路径
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
            // 使用统一的解析函数，包含工具调用状态
            const restoredMessages = parseStateMessages(state.values.messages as StateMessage[]);
            setMessages(restoredMessages);
          }

          // 提取参考文档
          const refs = extractReferenceFiles(state?.values?.files);
          setReferenceFiles(refs);

          // Check for pending edits - 使用三层匹配策略
          const edit = getPendingEdit(state);
          if (edit) {
            const match = findMatchingString(edit.oldString, currentContent);
            if (match.found) {
              setPendingEdit({ ...edit, oldString: match.matchedString });
            }
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

    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const response = await fetch(`${apiBase}/api/parse-pdf`, {
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
      console.log("=== checkForPendingEdit ===");
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

        // 使用三层匹配策略
        const match = findMatchingString(edit.oldString, currentContent);
        if (match.found) {
          console.log("oldString found in content, setting pendingEdit");
          if (match.matchedString !== edit.oldString) {
            console.log("Corrected oldString from:", edit.oldString.substring(0, 50));
            console.log("To:", match.matchedString.substring(0, 50));
          }
          setPendingEdit({ ...edit, oldString: match.matchedString });
        } else {
          console.warn("oldString not found (all 3 layers failed), skipping pendingEdit");
          console.log("oldString (first 100):", edit.oldString.substring(0, 100));
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

    // 使用三层匹配策略找到实际的 oldString
    const match = findMatchingString(currentPendingEdit.oldString, pdfText);
    if (!match.found) {
      console.warn("handleApproveEdit: oldString not found (all 3 layers failed)!");
    }

    // 乐观更新：立即应用修改并清除 pending edit
    const optimisticContent = pdfText.replace(match.matchedString, currentPendingEdit.newString);
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
    try {
      const stream = resumeWithDecision(threadId, currentPendingEdit, "approve");

      for await (const event of stream) {
        console.log("Approve stream event:", event.type, event.data);

        // values 模式返回完整的 state
        if (event.type === "state_update") {
          const state = event.data as {
            messages?: Array<{
              type: string;
              content: string | Array<{ type: string; text?: string }>;
              tool_calls?: Array<{ name: string; args: Record<string, unknown>; id?: string }>;
              name?: string;
              tool_call_id?: string;
            }>;
          };

          if (state.messages) {
            const parsedMessages = parseStateMessages(state.messages);
            setMessages(parsedMessages);
          }
        }
      }

      console.log("Approve stream completed.");

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

      for await (const event of stream) {
        console.log("Reject stream event:", event.type, event.data);

        // values 模式返回完整的 state
        if (event.type === "state_update") {
          const state = event.data as {
            messages?: Array<{
              type: string;
              content: string | Array<{ type: string; text?: string }>;
              tool_calls?: Array<{ name: string; args: Record<string, unknown>; id?: string }>;
              name?: string;
              tool_call_id?: string;
            }>;
          };

          if (state.messages) {
            const parsedMessages = parseStateMessages(state.messages);
            setMessages(parsedMessages);
          }
        }
      }

      // 添加取消消息提示
      setMessages((prev) => [...prev, { role: "assistant", content: "已取消修改。" }]);

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

      for await (const event of stream) {
        console.log("Initial stream event:", event.type, event.data);

        // values 模式返回完整的 state
        if (event.type === "state_update") {
          const state = event.data as {
            messages?: Array<{
              type: string;
              content: string | Array<{ type: string; text?: string }>;
              tool_calls?: Array<{ name: string; args: Record<string, unknown>; id?: string }>;
              name?: string;
              tool_call_id?: string;
            }>;
            files?: Record<string, { content: string[]; modified_at?: string }>;
          };

          if (state.messages) {
            const parsedMessages = parseStateMessages(state.messages);
            setMessages(parsedMessages);
          }

          // 更新参考文档
          if (state.files) {
            const refs = extractReferenceFiles(state.files);
            setReferenceFiles(refs);
          }
        }

        // 错误处理
        if (event.type === "error") {
          const errorMsg = typeof event.data === "string" ? event.data : "未知错误";
          console.error("Initial stream error:", errorMsg);
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: `抱歉，处理请求时出错：${errorMsg}` },
          ]);
        }
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
        // 使用统一的解析函数，包含工具调用状态
        const restoredMessages = parseStateMessages(state.values.messages as StateMessage[]);
        setMessages(restoredMessages);
      }

      // 提取参考文档
      const refs = extractReferenceFiles(state?.values?.files);
      setReferenceFiles(refs);

      // Check for pending edits - 使用三层匹配策略
      const edit = getPendingEdit(state);
      if (edit) {
        const match = findMatchingString(edit.oldString, currentContent);
        if (match.found) {
          setPendingEdit({ ...edit, oldString: match.matchedString });
        }
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
    setReferenceFiles({});
    setActiveFile(null);
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

      for await (const event of stream) {
        console.log("Stream event:", event.type, event.data);

        // values 模式返回完整的 state
        if (event.type === "state_update") {
          const state = event.data as {
            messages?: Array<{
              type: string;
              content: string | Array<{ type: string; text?: string }>;
              tool_calls?: Array<{ name: string; args: Record<string, unknown>; id?: string }>;
              name?: string;
              tool_call_id?: string;
            }>;
            files?: Record<string, { content: string[]; modified_at?: string }>;
          };

          if (state.messages) {
            const parsedMessages = parseStateMessages(state.messages);
            setMessages(parsedMessages);
          }

          // 更新参考文档
          if (state.files) {
            const refs = extractReferenceFiles(state.files);
            setReferenceFiles(refs);
          }
        }

        // 错误处理
        if (event.type === "error") {
          const errorMsg = typeof event.data === "string" ? event.data : "未知错误";
          console.error("Stream error:", errorMsg);
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: `抱歉，处理请求时出错：${errorMsg}` },
          ]);
        }
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
              {sessions.map((session) => {
                const isCurrentSession = threadId === session.thread_id;
                const isShowingResume = isCurrentSession && activeFile === null;
                return (
                <div key={session.thread_id}>
                  <div
                    onClick={() => {
                      if (isCurrentSession) {
                        // 当前会话：点击切换回简历视图
                        setActiveFile(null);
                      } else {
                        // 其他会话：切换会话
                        handleSelectSession(session);
                        setActiveFile(null);
                      }
                    }}
                    className={`group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors ${
                      isShowingResume
                        ? "bg-accent"
                        : isCurrentSession
                        ? "bg-accent/50"
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
                  {/* Reference Files - 只在当前选中的会话下显示 */}
                  {threadId === session.thread_id && Object.keys(referenceFiles).length > 0 && (
                    <div className="ml-6 mt-1 mb-2 space-y-1">
                      <div className="flex items-center gap-1.5 px-2 py-1 text-xs text-muted-foreground">
                        <FileCode className="w-3 h-3" />
                        <span>参考文档 ({Object.keys(referenceFiles).length})</span>
                      </div>
                      {Object.entries(referenceFiles).map(([path]) => {
                        const filename = path.split("/").pop() || path;
                        const isActive = activeFile === path;
                        return (
                          <button
                            key={path}
                            onClick={(e) => {
                              e.stopPropagation();
                              setActiveFile(isActive ? null : path);
                            }}
                            className={`w-full flex items-center gap-1.5 px-2 py-1.5 text-xs transition-colors rounded-md ${
                              isActive ? "bg-accent text-accent-foreground" : "hover:bg-accent/50"
                            }`}
                          >
                            <FileText className="w-3 h-3 text-primary flex-shrink-0" />
                            <span className="truncate text-left">{filename}</span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
              })}
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
              {/* Left Panel - Markdown Viewer with Diff / Reference Doc */}
              <div className="w-1/2 bg-card overflow-hidden flex flex-col">
                {activeFile && referenceFiles[activeFile] ? (
                  /* 参考文档视图 */
                  <>
                    <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-muted/30">
                      <div className="flex items-center gap-2 text-sm">
                        <FileCode className="w-4 h-4 text-primary" />
                        <span className="font-medium truncate">{activeFile.split("/").pop()}</span>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setActiveFile(null)}
                        className="h-7 px-2 text-xs"
                      >
                        <X className="w-3 h-3 mr-1" />
                        返回简历
                      </Button>
                    </div>
                    <div className="flex-1 overflow-y-auto p-6">
                      <div className="prose prose-sm max-w-none dark:prose-invert prose-table:text-sm prose-th:bg-muted/50 prose-th:px-3 prose-th:py-2 prose-td:px-3 prose-td:py-2 prose-table:border prose-th:border prose-td:border">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {Array.isArray(referenceFiles[activeFile].content)
                            ? referenceFiles[activeFile].content.join("\n")
                            : String(referenceFiles[activeFile].content || "")}
                        </ReactMarkdown>
                      </div>
                    </div>
                  </>
                ) : (
                  /* 简历视图 */
                  <MarkdownViewer
                    content={pdfText}
                    isLoading={isParsing}
                    className="h-full"
                    pendingEdit={pendingEdit}
                    onApprove={handleApproveEdit}
                    onReject={handleRejectEdit}
                  />
                )}
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
                          /* 工具调用状态 - 流程展示 */
                          <div className="flex items-center gap-2 text-sm text-muted-foreground py-1.5 px-3 bg-muted/30 rounded-lg">
                            {msg.toolCalls.some(t => t.status === "running") ? (
                              <Loader2 className="w-4 h-4 animate-spin text-primary" />
                            ) : (
                              <svg className="w-4 h-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
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
                                  ls: "列出目录",
                                  glob: "搜索文件",
                                  grep: "搜索内容",
                                  execute: "执行命令",
                                  github_search: "搜索 GitHub",
                                  search_opensource_projects: "搜索开源项目",
                                  search_trends: "搜索技术趋势",
                                  write_todos: "更新待办",
                                  task: "调用子任务",
                                };
                                const name = toolNames[tool.name] || tool.name;
                                // 提取关键参数用于展示
                                let detail = "";
                                if (tool.args?.file_path) {
                                  detail = String(tool.args.file_path);
                                } else if (tool.args?.query) {
                                  detail = String(tool.args.query);
                                } else if (tool.args?.pattern) {
                                  detail = String(tool.args.pattern);
                                }
                                return (
                                  <span key={i}>
                                    {i > 0 && " → "}
                                    {name}
                                    {detail && <code className="text-xs bg-muted px-1.5 py-0.5 rounded ml-1.5">{detail}</code>}
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
