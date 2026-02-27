/**
 * API 配置 - 统一管理所有 API 端点
 */

// 后端 API 基础 URL
// 开发环境: http://localhost:8000
// 生产环境: 通过 Nginx 反向代理，使用相对路径
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

// 如果 API_BASE_URL 为空（生产环境），后端 API 回退到 localhost
export const getApiBaseUrl = () => {
  if (API_BASE_URL) return API_BASE_URL;
  // 服务端渲染时需要完整 URL
  if (typeof window === "undefined") return "http://localhost:8000";
  // 客户端使用相对路径（通过 Nginx 反向代理）
  return "";
};

// API 端点
export const API_ENDPOINTS = {
  // 认证
  AUTH: {
    LOGIN: "/api/auth/login",
    REGISTER: "/api/auth/register",
    LOGOUT: "/api/auth/logout",
    ME: "/api/auth/me",
  },
  // 会话
  SESSIONS: {
    BASE: "/api/sessions",
    DETAIL: (threadId: string) => `/api/sessions/${threadId}`,
  },
  // PDF 解析
  PARSE_PDF: "/api/parse-pdf",
} as const;

// 构建完整 API URL
export const buildApiUrl = (endpoint: string): string => {
  const base = getApiBaseUrl();
  return `${base}${endpoint}`;
};
