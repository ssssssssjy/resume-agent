import { Client } from "@langchain/langgraph-sdk";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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
 * Action request from deepagents interrupt
 */
interface ActionRequest {
  name: string;
  args: {
    file_path: string;
    old_string: string;
    new_string: string;
    replace_all?: boolean;
  };
  description?: string;
}

/**
 * Interrupt value from deepagents
 */
interface InterruptValue {
  action_requests: ActionRequest[];
  review_configs: Array<{
    action_name: string;
    allowed_decisions: string[];
  }>;
}

/**
 * Thread state with interrupt info
 */
export interface ThreadState {
  values: {
    messages?: Array<{ type: string; content: string }>;
    files?: Record<string, { content: string[] }>;
  };
  next?: string[];
  tasks?: Array<{
    id: string;
    name: string;
    interrupts?: Array<{
      value: InterruptValue;
      id: string;
      resumable?: boolean;
      ns?: string[];
    }>;
  }>;
}

/**
 * Pending edit info extracted from interrupt
 */
export interface PendingEdit {
  interruptId: string;
  filePath: string;
  oldString: string;
  newString: string;
  taskId: string;
  actionName: string;
}

/**
 * Check if thread is interrupted with a pending edit
 */
export function getPendingEdit(state: ThreadState): PendingEdit | null {
  if (!state.tasks) return null;

  for (const task of state.tasks) {
    if (task.interrupts && task.interrupts.length > 0) {
      for (const interrupt of task.interrupts) {
        // 检查 action_requests 中是否有 edit_file
        const actionRequests = interrupt.value?.action_requests;
        if (actionRequests && actionRequests.length > 0) {
          const editAction = actionRequests.find(ar => ar.name === "edit_file");
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
 * Resume thread with user decision (approve/reject) and stream the response
 *
 * HITLResponse format for deepagents HumanInTheLoopMiddleware:
 * { decisions: [{ type: "approve" }] } or { decisions: [{ type: "reject", message: "..." }] }
 */
export async function* resumeWithDecision(
  threadId: string,
  pendingEdit: PendingEdit,
  decision: "approve" | "reject"
): AsyncGenerator<{
  type: "state" | "message" | "error" | "done";
  data: unknown;
}> {
  const client = getLangGraphClient();

  // Build HITLResponse format for deepagents
  const hitlResponse = decision === "approve"
    ? { decisions: [{ type: "approve" }] }
    : { decisions: [{ type: "reject", message: "用户拒绝了此修改" }] };

  // Send Command to resume the interrupted task
  // 使用 interrupt id 作为 key，HITLResponse 作为 value
  const command = {
    resume: {
      [pendingEdit.interruptId]: hitlResponse,
    },
  };

  console.log("Resuming with command:", command);

  try {
    // Resume the run with streaming
    const streamResponse = client.runs.stream(threadId, "resume_enhancer", {
      command,
      streamMode: "values",
    });

    for await (const event of streamResponse) {
      if (event.event === "values") {
        yield { type: "state", data: event.data };
      } else if (event.event === "error") {
        // 尝试提取更详细的错误信息
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
    // 捕获网络错误等异常
    let errorMessage = "连接服务器失败";
    if (error instanceof Error) {
      if (error.message.includes("fetch") || error.message.includes("network") || error.message.includes("connect")) {
        errorMessage = "无法连接到服务器，请检查后端服务是否正常运行";
      } else {
        errorMessage = error.message;
      }
    } else if (typeof error === "object" && error !== null) {
      const err = error as Record<string, unknown>;
      errorMessage = err.message as string || err.error as string || JSON.stringify(error);
    }
    yield { type: "error", data: errorMessage };
  }
}

/**
 * File data structure for deepagents FilesystemMiddleware
 */
export interface FileData {
  content: string[];
  created_at: string;
  modified_at: string;
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
 * @param threadId - Thread ID
 * @param userMessage - User message
 * @param initialFiles - Optional initial files to load into agent state (first run only)
 */
export async function* streamResumeEnhancement(
  threadId: string,
  userMessage: string,
  initialFiles?: Record<string, FileData>
): AsyncGenerator<{
  type: "state" | "message" | "error" | "done";
  data: unknown;
}> {
  const client = getLangGraphClient();

  // 构建输入，包含消息和可选的初始文件
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
      if (event.event === "values") {
        yield { type: "state", data: event.data };
      } else if (event.event === "error") {
        // 尝试提取更详细的错误信息
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
    // 捕获网络错误等异常
    let errorMessage = "连接服务器失败";
    if (error instanceof Error) {
      if (error.message.includes("fetch") || error.message.includes("network") || error.message.includes("connect")) {
        errorMessage = "无法连接到服务器，请检查后端服务是否正常运行";
      } else {
        errorMessage = error.message;
      }
    } else if (typeof error === "object" && error !== null) {
      const err = error as Record<string, unknown>;
      errorMessage = err.message as string || err.error as string || JSON.stringify(error);
    }
    yield { type: "error", data: errorMessage };
  }
}

/**
 * Types for LangGraph state
 */
export interface TechPoint {
  index: number;
  title: string;
  content: string;
  technologies: string[];
  business_context: string;
}

export interface OpenSourceRef {
  name: string;
  stars: number;
  description: string;
  url: string;
  relevance: string;
}

export interface TrendingTech {
  tech: string;
  repo: string;
  url: string;
  stars: number;
  description: string;
}

export interface SearchResult {
  examples: Record<string, unknown>[];
  github_trending: TrendingTech[];
  reddit_posts: Record<string, unknown>[];
  huggingface_models: Record<string, unknown>[];
  opensource_refs: OpenSourceRef[];
  business_context: string;
}

export interface EnhancementResult {
  original_title: string;
  original_content: string;
  ai_suggestion: string;
  tech_highlights: string[];
  interview_tips: string[];
  industry_comparison: string;
}

export interface ResumeEnhancerState {
  resume_content: string;
  target_job: string;
  language: string;
  tech_points: TechPoint[];
  current_point_index: number;
  search_results: Record<number, SearchResult>;
  enhancement_results: Record<number, EnhancementResult>;
  final_report: string;
  messages: unknown[];
}
