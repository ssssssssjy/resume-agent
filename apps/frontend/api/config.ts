/**
 * API 配置 - 统一管理所有 API 相关配置
 *
 * 环境变量:
 *   NEXT_PUBLIC_API_URL - 后端 API 地址
 *     - 开发环境: http://localhost:8000
 *     - 生产环境: 留空（使用 Nginx 反向代理）
 */

// ============ 常量配置 ============

/** 开发环境默认后端地址 */
const DEV_API_URL = "http://localhost:8000";

/** 从环境变量读取 API URL */
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

// ============ URL 获取函数 ============

/**
 * 获取 API 基础 URL
 * - 如果设置了 NEXT_PUBLIC_API_URL，使用它
 * - 服务端渲染时使用开发环境默认地址
 * - 客户端使用相对路径（通过 Nginx 反向代理）
 */
export const getApiBaseUrl = (): string => {
  if (API_BASE_URL) return API_BASE_URL;

  // 服务端渲染时需要完整 URL
  if (typeof window === "undefined") return DEV_API_URL;

  // 客户端使用相对路径（通过 Nginx 反向代理）
  return "";
};

/**
 * 获取 LangGraph SDK 使用的 API URL
 * LangGraph SDK 需要完整 URL，不能使用相对路径
 */
export const getLangGraphApiUrl = (): string => {
  if (API_BASE_URL) return API_BASE_URL;

  // 客户端使用当前页面的 origin
  if (typeof window !== "undefined") {
    return window.location.origin;
  }

  // 服务端使用开发环境默认地址
  return DEV_API_URL;
};

// ============ API 端点 ============

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

// ============ 工具函数 ============

/**
 * 构建完整 API URL
 * 用于普通 fetch 请求
 */
export const buildApiUrl = (endpoint: string): string => {
  const base = getApiBaseUrl();
  return `${base}${endpoint}`;
};
