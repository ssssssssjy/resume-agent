"use client";

import { forwardRef } from "react";
import { Loader2 } from "lucide-react";
import { MessageItem } from "./message-item";
import type { Message } from "@/types";

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  isParsing: boolean;
}

export const MessageList = forwardRef<HTMLDivElement, MessageListProps>(
  function MessageList({ messages, isLoading, isParsing }, ref) {
    return (
      <div className="flex-1 overflow-y-auto p-5" ref={ref}>
        <div className="space-y-5">
          {messages.map((msg, idx) => (
            <MessageItem key={idx} message={msg} />
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
    );
  }
);
