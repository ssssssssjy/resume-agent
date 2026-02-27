"use client";

import { Plus, History, Trash2, FileText, FileCode, LogOut, User, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Session, UserInfo, ReferenceFiles } from "@/types";

interface SidebarProps {
  user: UserInfo;
  sessions: Session[];
  currentThreadId: string | null;
  activeFile: string | null;
  referenceFiles: ReferenceFiles;
  onNewChat: () => void;
  onSelectSession: (session: Session) => void;
  onDeleteSession: (e: React.MouseEvent, threadId: string) => void;
  onSelectFile: (path: string | null) => void;
  onLogout: () => void;
}

/**
 * 格式化日期显示
 */
function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return "今天";
  if (diffDays === 1) return "昨天";
  if (diffDays < 7) return `${diffDays}天前`;
  return date.toLocaleDateString("zh-CN", { month: "short", day: "numeric" });
}

export function Sidebar({
  user,
  sessions,
  currentThreadId,
  activeFile,
  referenceFiles,
  onNewChat,
  onSelectSession,
  onDeleteSession,
  onSelectFile,
  onLogout,
}: SidebarProps) {
  return (
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
          onClick={onNewChat}
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
            const isCurrentSession = currentThreadId === session.thread_id;
            const isShowingResume = isCurrentSession && activeFile === null;
            return (
              <div key={session.thread_id}>
                <div
                  onClick={() => {
                    if (isCurrentSession) {
                      // 当前会话：点击切换回简历视图
                      onSelectFile(null);
                    } else {
                      // 其他会话：切换会话
                      onSelectSession(session);
                      onSelectFile(null);
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
                    onClick={(e) => onDeleteSession(e, session.thread_id)}
                  >
                    <Trash2 className="w-3 h-3 text-muted-foreground" />
                  </Button>
                </div>
                {/* Reference Files - 只在当前选中的会话下显示 */}
                {currentThreadId === session.thread_id && Object.keys(referenceFiles).length > 0 && (
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
                            onSelectFile(isActive ? null : path);
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
            onClick={onLogout}
            title="退出登录"
          >
            <LogOut className="w-4 h-4 text-muted-foreground" />
          </Button>
        </div>
      </div>
    </aside>
  );
}
