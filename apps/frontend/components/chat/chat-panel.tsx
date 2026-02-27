"use client";

import { forwardRef } from "react";
import { MessageList } from "./message-list";
import { ChatInput } from "./chat-input";
import type { Message, PendingEdit } from "@/types";

interface ChatPanelProps {
  messages: Message[];
  isLoading: boolean;
  isParsing: boolean;
  threadId: string | null;
  pendingEdit: PendingEdit | null;
  onSend: (message: string) => void;
}

export const ChatPanel = forwardRef<HTMLDivElement, ChatPanelProps>(
  function ChatPanel(
    { messages, isLoading, isParsing, threadId, pendingEdit, onSend },
    ref
  ) {
    const inputDisabled = isLoading || isParsing || !threadId || !!pendingEdit;
    const placeholder = pendingEdit
      ? "请先处理待确认的修改..."
      : "输入您的问题或需求...";

    return (
      <div className="w-1/2 flex flex-col min-h-0 bg-background overflow-hidden">
        <MessageList
          ref={ref}
          messages={messages}
          isLoading={isLoading}
          isParsing={isParsing}
        />
        <ChatInput
          onSend={onSend}
          disabled={inputDisabled}
          isLoading={isLoading}
          placeholder={placeholder}
        />
      </div>
    );
  }
);
