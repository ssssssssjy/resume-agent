/**
 * 消息解析工具
 * 将 LangGraph state 的 messages 数组解析为前端 Message 格式
 */

import type { Message, StateMessage, ToolCall, FileData, ReferenceFiles } from "@/types";

/**
 * 从 LangGraph state 的 messages 数组解析为前端 Message 格式
 */
export function parseStateMessages(stateMessages: StateMessage[]): Message[] {
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

/**
 * 从 LangGraph state 的 files 中提取 /references/ 目录下的参考文档
 */
export function extractReferenceFiles(
  files: Record<string, FileData> | undefined
): ReferenceFiles {
  if (!files) return {};
  const refs: ReferenceFiles = {};
  for (const [path, data] of Object.entries(files)) {
    if (path.startsWith("/references/")) {
      refs[path] = data;
    }
  }
  return refs;
}
