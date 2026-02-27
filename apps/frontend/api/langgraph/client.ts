import { Client } from "@langchain/langgraph-sdk";
import { API_BASE_URL } from "../config";
import type {
  ThreadState,
  PendingEdit,
  FileData,
  StateMessage,
} from "@/types";

/**
 * Get LangGraph SDK client
 */
export function getLangGraphClient(): Client {
  return new Client({
    apiUrl: API_BASE_URL,
  });
}

/**
 * Create a new thread
 */
export async function createThread(): Promise<{ thread_id: string }> {
  const client = getLangGraphClient();
  const thread = await client.threads.create();
  return { thread_id: thread.thread_id };
}

/**
 * Get thread state
 */
export async function getThreadState(threadId: string): Promise<ThreadState> {
  const client = getLangGraphClient();
  const state = await client.threads.getState(threadId);
  return state as ThreadState;
}

/**
 * Check if thread is interrupted with a pending edit
 */
export function getPendingEdit(state: ThreadState): PendingEdit | null {
  if (!state.tasks) {
    return null;
  }

  for (const task of state.tasks) {
    if (task.interrupts && task.interrupts.length > 0) {
      for (const interrupt of task.interrupts) {
        // 检查 action_requests 中是否有 edit_file
        const actionRequests = interrupt.value?.action_requests;
        if (actionRequests && actionRequests.length > 0) {
          const editAction = actionRequests.find((ar) => ar.name === "edit_file");
          if (editAction) {
            return {
              interruptId: interrupt.id,
              filePath: editAction.args.file_path,
              oldString: editAction.args.old_string,
              newString: editAction.args.new_string,
              taskId: task.id,
              actionName: editAction.name,
            };
          }
        }
      }
    }
  }
  return null;
}

/**
 * Values mode state structure for resume
 */
interface ResumeValuesState {
  messages?: StateMessage[];
  files?: Record<string, FileData>;
}

/**
 * Resume thread with user decision (approve/reject) and stream the response
 */
export async function* resumeWithDecision(
  threadId: string,
  pendingEdit: PendingEdit,
  decision: "approve" | "reject"
): AsyncGenerator<{
  type: "state_update" | "error" | "done";
  data: unknown;
}> {
  const client = getLangGraphClient();

  // Build HITLResponse format for deepagents
  const hitlResponse = decision === "approve"
    ? { decisions: [{ type: "approve" }] }
    : { decisions: [{ type: "reject", message: "用户拒绝了此修改" }] };

  // Send Command to resume the interrupted task
  const command = {
    resume: {
      [pendingEdit.interruptId]: hitlResponse,
    },
  };

  try {
    const streamResponse = client.runs.stream(threadId, "resume_enhancer", {
      command,
      streamMode: "values",
    });

    for await (const event of streamResponse) {
      const eventName = event.event as string;

      if (eventName === "values") {
        const state = event.data as ResumeValuesState;
        yield { type: "state_update", data: state };
      } else if (eventName === "error") {
        const errorData = event.data;
        let errorMessage = "未知错误";
        if (typeof errorData === "string") {
          errorMessage = errorData;
        } else if (errorData && typeof errorData === "object") {
          const err = errorData as Record<string, unknown>;
          errorMessage = err.message as string || err.error as string || JSON.stringify(errorData);
        }
        yield { type: "error", data: errorMessage };
      }
    }

    yield { type: "done", data: null };
  } catch (error) {
    yield { type: "error", data: formatError(error) };
  }
}

/**
 * Update thread state (e.g., update files after edit approval)
 */
export async function updateThreadState(
  threadId: string,
  values: Record<string, unknown>
): Promise<void> {
  const client = getLangGraphClient();
  await client.threads.updateState(threadId, { values });
}

/**
 * Stream run for resume enhancement (chat mode)
 */
export async function* streamResumeEnhancement(
  threadId: string,
  userMessage: string,
  initialFiles?: Record<string, FileData>
): AsyncGenerator<{
  type: "state_update" | "error" | "done";
  data: unknown;
}> {
  const client = getLangGraphClient();

  // 构建输入
  const input: Record<string, unknown> = {};

  if (userMessage) {
    input.messages = [{ role: "user", content: userMessage }];
  }

  if (initialFiles) {
    input.files = initialFiles;
  }

  try {
    const streamResponse = client.runs.stream(threadId, "resume_enhancer", {
      input: Object.keys(input).length > 0 ? input : { messages: [] },
      streamMode: "values",
    });

    for await (const event of streamResponse) {
      const eventName = event.event as string;

      if (eventName === "values") {
        const state = event.data as ResumeValuesState;
        yield { type: "state_update", data: state };
      } else if (eventName === "error") {
        const errorData = event.data;
        let errorMessage = "未知错误";
        if (typeof errorData === "string") {
          errorMessage = errorData;
        } else if (errorData && typeof errorData === "object") {
          const err = errorData as Record<string, unknown>;
          errorMessage = err.message as string || err.error as string || JSON.stringify(errorData);
        }
        yield { type: "error", data: errorMessage };
      }
    }

    yield { type: "done", data: null };
  } catch (error) {
    yield { type: "error", data: formatError(error) };
  }
}

/**
 * Format error message
 */
function formatError(error: unknown): string {
  if (error instanceof Error) {
    if (error.message.includes("fetch") || error.message.includes("network") || error.message.includes("connect")) {
      return "无法连接到服务器，请检查后端服务是否正常运行";
    }
    return error.message;
  }
  if (typeof error === "object" && error !== null) {
    const err = error as Record<string, unknown>;
    return err.message as string || err.error as string || JSON.stringify(error);
  }
  return "连接服务器失败";
}

// Re-export types for convenience
export type { ThreadState, PendingEdit, FileData } from "@/types";
