"use client";

import { Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import type { Message } from "@/types";

// 工具名称映射
const TOOL_NAMES: Record<string, string> = {
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

interface MessageItemProps {
  message: Message;
}

export function MessageItem({ message }: MessageItemProps) {
  // 工具调用状态
  if (message.role === "tool" && message.toolCalls) {
    const isRunning = message.toolCalls.some(t => t.status === "running");

    return (
      <div className="flex justify-start">
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-1.5 px-3 bg-muted/30 rounded-lg">
          {isRunning ? (
            <Loader2 className="w-4 h-4 animate-spin text-primary" />
          ) : (
            <svg className="w-4 h-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          )}
          <span>
            {message.toolCalls.map((tool, i) => {
              const name = TOOL_NAMES[tool.name] || tool.name;
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
            {isRunning && "..."}
          </span>
        </div>
      </div>
    );
  }

  // 用户消息或助手消息
  return (
    <div className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 ${
          message.role === "user"
            ? "bg-primary text-primary-foreground"
            : "bg-secondary"
        }`}
      >
        {message.role === "assistant" ? (
          <div className="prose prose-sm max-w-none dark:prose-invert prose-p:leading-relaxed prose-headings:font-semibold">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        ) : (
          <p className="text-sm whitespace-pre-wrap leading-relaxed">{message.content}</p>
        )}
      </div>
    </div>
  );
}
