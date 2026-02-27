"use client";

import { X, FileCode } from "lucide-react";
import { Button } from "@/components/ui/button";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ReferenceFile } from "@/types";

interface ReferenceViewerProps {
  path: string;
  file: ReferenceFile;
  onClose: () => void;
}

export function ReferenceViewer({ path, file, onClose }: ReferenceViewerProps) {
  const filename = path.split("/").pop() || path;
  const content = Array.isArray(file.content)
    ? file.content.join("\n")
    : String(file.content || "");

  return (
    <>
      <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-muted/30">
        <div className="flex items-center gap-2 text-sm">
          <FileCode className="w-4 h-4 text-primary" />
          <span className="font-medium truncate">{filename}</span>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={onClose}
          className="h-7 px-2 text-xs"
        >
          <X className="w-3 h-3 mr-1" />
          返回简历
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto p-6">
        <div className="prose prose-sm max-w-none dark:prose-invert prose-table:text-sm prose-th:bg-muted/50 prose-th:px-3 prose-th:py-2 prose-td:px-3 prose-td:py-2 prose-table:border prose-th:border prose-td:border">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {content}
          </ReactMarkdown>
        </div>
      </div>
    </>
  );
}
