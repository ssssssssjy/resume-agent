"use client";

import { useMemo, useRef, useEffect, useCallback } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import ReactMarkdown from "react-markdown";
import { FileText, Loader2, Check, X } from "lucide-react";
import { diffLines, Change } from "diff";
import type { PendingEdit } from "@/api/langgraph";

// 三层匹配策略（与 page.tsx 保持一致）
function findMatchingString(
  targetString: string,
  content: string
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

  // 第三层略（组件内不做模糊匹配，依赖 page.tsx 传入已修正的值）
  return { found: false, matchedString: targetString };
}

interface MarkdownViewerProps {
  content: string;
  isLoading?: boolean;
  className?: string;
  pendingEdit?: PendingEdit | null;
  onApprove?: () => void;
  onReject?: () => void;
}

export function MarkdownViewer({
  content,
  isLoading = false,
  className = "",
  pendingEdit,
  onApprove,
  onReject,
}: MarkdownViewerProps) {
  const firstChangeRef = useRef<HTMLDivElement>(null);

  // Calculate preview content with pending edit applied
  const previewContent = useMemo(() => {
    if (!pendingEdit || !content) return null;

    // 调试：打印 oldString 和 content 的详细信息
    console.log("=== MarkdownViewer Debug ===");
    console.log("oldString length:", pendingEdit.oldString.length);
    console.log("oldString lines:", pendingEdit.oldString.split("\n").length);
    console.log("oldString (full):", JSON.stringify(pendingEdit.oldString));
    console.log("content length:", content.length);
    console.log("direct includes:", content.includes(pendingEdit.oldString));

    // 使用三层匹配策略找到实际的 oldString
    const match = findMatchingString(pendingEdit.oldString, content);
    console.log("match result:", match);

    const result = content.replace(match.matchedString, pendingEdit.newString);

    // 检查替换是否成功
    if (result === content) {
      // 检查是否是空操作（oldString === newString）
      if (pendingEdit.oldString === pendingEdit.newString) {
        console.warn("MarkdownViewer: oldString === newString (no-op edit from Agent)");
      } else {
        console.warn("MarkdownViewer: oldString not found after matching");
      }
      console.log("newString:", JSON.stringify(pendingEdit.newString));
    }
    return result;
  }, [content, pendingEdit]);

  // Calculate diff for highlighting
  const diffResult = useMemo(() => {
    if (!pendingEdit || !content || !previewContent) return null;
    return diffLines(content, previewContent);
  }, [content, previewContent, pendingEdit]);

  // 自动滚动到第一个变更位置
  useEffect(() => {
    if (pendingEdit && diffResult && firstChangeRef.current) {
      // 延迟执行以确保 DOM 已渲染
      setTimeout(() => {
        firstChangeRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 100);
    }
  }, [pendingEdit, diffResult]);

  // 包装回调以添加调试
  const handleApprove = useCallback(() => {
    console.log("Approve clicked, pendingEdit:", pendingEdit);
    onApprove?.();
  }, [onApprove, pendingEdit]);

  const handleReject = useCallback(() => {
    console.log("Reject clicked, pendingEdit:", pendingEdit);
    onReject?.();
  }, [onReject, pendingEdit]);

  if (isLoading) {
    return (
      <div className={`flex items-center justify-center h-full bg-muted/30 ${className}`}>
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <span className="ml-2 text-muted-foreground">正在解析简历...</span>
      </div>
    );
  }

  if (!content) {
    return (
      <div className={`flex items-center justify-center h-full bg-muted/30 ${className}`}>
        <FileText className="w-8 h-8 text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">请上传简历</span>
      </div>
    );
  }

  // Show diff view when there's a pending edit
  if (pendingEdit && diffResult) {
    return (
      <div className={`flex flex-col h-full ${className}`}>
        <ScrollArea className="flex-1">
          <div className="p-6">
            <div className="prose prose-sm max-w-none dark:prose-invert">
              <DiffContent
                diffResult={diffResult}
                firstChangeRef={firstChangeRef}
                onApprove={handleApprove}
                onReject={handleReject}
              />
            </div>
          </div>
        </ScrollArea>
      </div>
    );
  }

  // Normal view
  return (
    <div className={`flex flex-col h-full ${className}`}>
      <ScrollArea className="flex-1">
        <div className="p-6">
          <div className="prose prose-sm max-w-none dark:prose-invert">
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        </div>
      </ScrollArea>
    </div>
  );
}

// Component to render diff with highlighting
function DiffContent({
  diffResult,
  firstChangeRef,
  onApprove,
  onReject,
}: {
  diffResult: Change[];
  firstChangeRef: React.RefObject<HTMLDivElement | null>;
  onApprove: () => void;
  onReject: () => void;
}) {
  let firstChangeFound = false;
  let buttonsRendered = false;

  // 渲染操作按钮条
  const renderButtons = () => (
    <div className="sticky top-0 z-10 flex items-center justify-between gap-3 py-3 px-4 my-3 bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-950/50 dark:to-orange-950/50 border border-amber-200 dark:border-amber-800 rounded-lg shadow-sm">
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
        <span className="text-sm font-medium text-amber-700 dark:text-amber-300">
          AI 建议修改此处
        </span>
      </div>
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          variant="outline"
          onClick={onReject}
          className="h-8 px-3 text-xs font-medium text-red-600 border-red-300 hover:bg-red-50 hover:border-red-400 dark:text-red-400 dark:border-red-700 dark:hover:bg-red-950"
        >
          <X className="w-3.5 h-3.5 mr-1.5" />
          拒绝
        </Button>
        <Button
          size="sm"
          onClick={onApprove}
          className="h-8 px-3 text-xs font-medium bg-green-600 hover:bg-green-700 text-white shadow-sm"
        >
          <Check className="w-3.5 h-3.5 mr-1.5" />
          接受修改
        </Button>
      </div>
    </div>
  );

  return (
    <div className="space-y-0">
      {diffResult.map((part, index) => {
        const isChange = part.added || part.removed;
        const isFirstChange = isChange && !firstChangeFound;
        if (isFirstChange) {
          firstChangeFound = true;
        }

        // 在第一个变更内容后面显示按钮（无论是新增还是删除）
        const shouldRenderButtons = isFirstChange && !buttonsRendered;
        if (shouldRenderButtons) {
          buttonsRendered = true;
        }

        if (part.added) {
          // Added lines - green background
          return (
            <div key={index}>
              {shouldRenderButtons && renderButtons()}
              <div
                ref={isFirstChange ? firstChangeRef : undefined}
                className="bg-green-100/80 dark:bg-green-900/30 border-l-4 border-green-500 pl-3 py-1.5 rounded-r"
              >
                <div className="prose prose-sm max-w-none dark:prose-invert prose-p:my-1 prose-headings:my-2 text-green-800 dark:text-green-200">
                  <ReactMarkdown>{part.value}</ReactMarkdown>
                </div>
              </div>
            </div>
          );
        }
        if (part.removed) {
          // Removed lines - red background with strikethrough
          return (
            <div key={index}>
              {shouldRenderButtons && renderButtons()}
              <div
                ref={isFirstChange ? firstChangeRef : undefined}
                className="bg-red-100/60 dark:bg-red-900/20 border-l-4 border-red-400 pl-3 py-1.5 rounded-r opacity-75"
              >
                <div className="prose prose-sm max-w-none dark:prose-invert prose-p:my-1 prose-headings:my-2 text-red-700 dark:text-red-300 line-through">
                  <ReactMarkdown>{part.value}</ReactMarkdown>
                </div>
              </div>
            </div>
          );
        }
        // Unchanged lines
        return (
          <div key={index} className="pl-3 py-1">
            <div className="prose prose-sm max-w-none dark:prose-invert prose-p:my-1 prose-headings:my-2">
              <ReactMarkdown>{part.value}</ReactMarkdown>
            </div>
          </div>
        );
      })}
    </div>
  );
}
