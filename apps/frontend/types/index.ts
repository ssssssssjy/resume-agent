/**
 * 统一类型定义
 */

// ============ 认证相关 ============

export interface AuthResponse {
  user_id: string;
  username: string;
  token: string;
}

export interface UserInfo {
  user_id: string;
  username: string;
}

// ============ 会话相关 ============

export interface Session {
  thread_id: string;
  filename: string;
  created_at: string;
  updated_at: string;
}

export interface SessionDetail extends Session {
  resume_content: string;
}

// ============ 消息相关 ============

export interface ToolCall {
  name: string;
  args: Record<string, unknown>;
  status?: "running" | "success" | "error";
  result?: string;
}

export interface Message {
  role: "user" | "assistant" | "tool";
  content: string;
  toolCalls?: ToolCall[];
}

// LangGraph state message 类型
export interface StateMessage {
  type: string;
  content: string | Array<{ type: string; text?: string }>;
  tool_calls?: Array<{ name: string; args: Record<string, unknown>; id?: string }>;
  name?: string;
  tool_call_id?: string;
}

// ============ LangGraph 相关 ============

// Action request from deepagents interrupt
export interface ActionRequest {
  name: string;
  args: {
    file_path: string;
    old_string: string;
    new_string: string;
    replace_all?: boolean;
  };
  description?: string;
}

// Interrupt value from deepagents
export interface InterruptValue {
  action_requests: ActionRequest[];
  review_configs: Array<{
    action_name: string;
    allowed_decisions: string[];
  }>;
}

// Thread state with interrupt info
export interface ThreadState {
  values: {
    messages?: StateMessage[];
    files?: Record<string, FileData>;
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

// Pending edit info extracted from interrupt
export interface PendingEdit {
  interruptId: string;
  filePath: string;
  oldString: string;
  newString: string;
  taskId: string;
  actionName: string;
}

// File data structure for deepagents FilesystemMiddleware
export interface FileData {
  content: string[];
  created_at?: string;
  modified_at?: string;
}

// ============ 简历增强相关 ============

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

// ============ 参考文档 ============

export interface ReferenceFile {
  content: string[];
  modified_at?: string;
}

export type ReferenceFiles = Record<string, ReferenceFile>;
