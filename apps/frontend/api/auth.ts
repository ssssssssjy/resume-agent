import { buildApiUrl, API_ENDPOINTS } from "./config";
import type { AuthResponse, UserInfo } from "@/types";

// Token 管理
const TOKEN_KEY = "auth_token";
const USER_KEY = "auth_user";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getStoredUser(): UserInfo | null {
  if (typeof window === "undefined") return null;
  const user = localStorage.getItem(USER_KEY);
  return user ? JSON.parse(user) : null;
}

export function setStoredUser(user: UserInfo): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

// 获取带 token 的 headers
export function getAuthHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// 注册
export async function register(
  username: string,
  password: string
): Promise<AuthResponse> {
  const response = await fetch(buildApiUrl(API_ENDPOINTS.AUTH.REGISTER), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "注册失败");
  }

  const data = await response.json();
  setToken(data.token);
  setStoredUser({ user_id: data.user_id, username: data.username });
  return data;
}

// 登录
export async function login(
  username: string,
  password: string
): Promise<AuthResponse> {
  const response = await fetch(buildApiUrl(API_ENDPOINTS.AUTH.LOGIN), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "登录失败");
  }

  const data = await response.json();
  setToken(data.token);
  setStoredUser({ user_id: data.user_id, username: data.username });
  return data;
}

// 登出
export async function logout(): Promise<void> {
  const token = getToken();
  if (token) {
    await fetch(buildApiUrl(API_ENDPOINTS.AUTH.LOGOUT), {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }).catch(() => {});
  }
  clearToken();
}

// 获取当前用户
export async function getCurrentUser(): Promise<UserInfo | null> {
  const token = getToken();
  if (!token) return null;

  try {
    const response = await fetch(buildApiUrl(API_ENDPOINTS.AUTH.ME), {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!response.ok) {
      clearToken();
      return null;
    }

    const user = await response.json();
    setStoredUser(user);
    return user;
  } catch {
    return getStoredUser();
  }
}
