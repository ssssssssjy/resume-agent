"use client";

import { useState, useEffect, useCallback } from "react";
import { Loader2 } from "lucide-react";

// Components
import { LoginForm } from "@/components/auth/login-form";
import { PDFUpload } from "@/components/resume/pdf-upload";
import { MarkdownViewer } from "@/components/resume/markdown-viewer";
import { ReferenceViewer } from "@/components/resume/reference-viewer";
import { Sidebar } from "@/components/layout";
import { ChatPanel } from "@/components/chat";

// Hooks
import { useAuth, useSessions, useChat } from "@/hooks";

// Types
import type { Session } from "@/types";

export default function HomePage() {
  // 认证状态
  const { user, isCheckingAuth, logout, refreshUser } = useAuth();

  // 会话管理
  const {
    sessions,
    loadSessions,
    getSessionDetail,
    saveSession,
    updateSessionContent,
    removeSession,
  } = useSessions();

  // 聊天逻辑
  const {
    messages,
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
    restoreSession,
    resetChat,
  } = useChat({
    onSessionUpdate: (tid, content) => {
      if (pdfFilename) {
        updateSessionContent({ thread_id: tid, filename: pdfFilename, resume_content: content });
      }
    },
  });

  // 本地状态
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [pdfFilename, setPdfFilename] = useState<string>("");
  const [pdfText, setPdfText] = useState<string>("");
  const [isParsing, setIsParsing] = useState(false);
  const [activeFile, setActiveFile] = useState<string | null>(null);

  // 用户登录后加载会话
  useEffect(() => {
    if (!user) return;

    const init = async () => {
      await loadSessions();

      // 尝试恢复上次会话
      const lastThreadId = localStorage.getItem("lastThreadId");
      if (lastThreadId) {
        try {
          const detail = await getSessionDetail(lastThreadId);
          setPdfFilename(detail.filename);
          setThreadId(lastThreadId);
          setPdfFile({ name: detail.filename } as File);

          // 恢复会话状态
          const result = await restoreSession(lastThreadId, detail.resume_content);
          setPdfText(result.latestContent || detail.resume_content);

          // 如果 LangGraph state 有更新，同步到数据库
          if (result.latestContent && result.latestContent !== detail.resume_content) {
            await updateSessionContent({
              thread_id: lastThreadId,
              filename: detail.filename,
              resume_content: result.latestContent,
            });
          }
        } catch {
          // Session 不存在，清理
          localStorage.removeItem("lastThreadId");
        }
      }
    };
    init();
  }, [user, loadSessions, getSessionDetail, restoreSession, setThreadId, updateSessionContent]);

  // 处理文件上传
  const handleFileSelect = useCallback(async (file: File) => {
    setPdfFile(file);
    setPdfFilename(file.name);
    setIsParsing(true);
    setPendingEdit(null);

    const newThreadId = await handleFileUpload(file, (text) => {
      setPdfText(text);
    });

    if (newThreadId) {
      // 保存会话
      await saveSession({
        thread_id: newThreadId,
        filename: file.name,
        resume_content: pdfText,
      });
    }

    setIsParsing(false);
  }, [handleFileUpload, saveSession, pdfText, setPendingEdit]);

  // 处理选择历史会话
  const handleSelectSession = useCallback(async (session: Session) => {
    setIsParsing(true);
    setPendingEdit(null);

    try {
      const detail = await getSessionDetail(session.thread_id);
      setPdfFilename(detail.filename);
      setThreadId(session.thread_id);
      setPdfFile({ name: detail.filename } as File);

      // 恢复会话状态
      const result = await restoreSession(session.thread_id, detail.resume_content);
      setPdfText(result.latestContent || detail.resume_content);

      // 同步更新
      if (result.latestContent && result.latestContent !== detail.resume_content) {
        await updateSessionContent({
          thread_id: session.thread_id,
          filename: detail.filename,
          resume_content: result.latestContent,
        });
      }
    } catch (error) {
      console.error("Failed to restore session:", error);
    } finally {
      setIsParsing(false);
    }
  }, [getSessionDetail, restoreSession, setThreadId, updateSessionContent, setPendingEdit]);

  // 处理删除会话
  const handleDeleteSession = useCallback(async (e: React.MouseEvent, tid: string) => {
    e.stopPropagation();
    await removeSession(tid);
  }, [removeSession]);

  // 处理新建对话
  const handleNewChat = useCallback(() => {
    setPdfFile(null);
    setPdfFilename("");
    setPdfText("");
    setActiveFile(null);
    resetChat();
  }, [resetChat]);

  // 处理登出
  const handleLogout = useCallback(async () => {
    await logout();
    handleNewChat();
  }, [logout, handleNewChat]);

  // 处理登录成功
  const handleLoginSuccess = useCallback(() => {
    refreshUser();
  }, [refreshUser]);

  // 处理接受编辑
  const onApproveEdit = useCallback(async () => {
    const newContent = await handleApproveEdit(pdfText, pdfFilename);
    if (newContent) {
      setPdfText(newContent);
    }
  }, [handleApproveEdit, pdfText, pdfFilename]);

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
      <Sidebar
        user={user}
        sessions={sessions}
        currentThreadId={threadId}
        activeFile={activeFile}
        referenceFiles={referenceFiles}
        onNewChat={handleNewChat}
        onSelectSession={handleSelectSession}
        onDeleteSession={handleDeleteSession}
        onSelectFile={setActiveFile}
        onLogout={handleLogout}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
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
              {/* Left Panel - Markdown Viewer / Reference Doc */}
              <div className="w-1/2 bg-card overflow-hidden flex flex-col">
                {activeFile && referenceFiles[activeFile] ? (
                  <ReferenceViewer
                    path={activeFile}
                    file={referenceFiles[activeFile]}
                    onClose={() => setActiveFile(null)}
                  />
                ) : (
                  <MarkdownViewer
                    content={pdfText}
                    isLoading={isParsing}
                    className="h-full"
                    pendingEdit={pendingEdit}
                    onApprove={onApproveEdit}
                    onReject={handleRejectEdit}
                  />
                )}
              </div>

              {/* Right Panel - Chat */}
              <ChatPanel
                ref={scrollRef}
                messages={messages}
                isLoading={isLoading}
                isParsing={isParsing}
                threadId={threadId}
                pendingEdit={pendingEdit}
                onSend={sendMessage}
              />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
