"use client";

import { useState, useEffect, useCallback } from "react";
import type { UserInfo } from "@/types";
import { getStoredUser, getCurrentUser, logout as logoutApi } from "@/api/auth";

interface UseAuthReturn {
  user: UserInfo | null;
  isCheckingAuth: boolean;
  logout: () => Promise<void>;
  setUser: (user: UserInfo | null) => void;
  refreshUser: () => void;
}

/**
 * 认证状态 Hook
 */
export function useAuth(): UseAuthReturn {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [isCheckingAuth, setIsCheckingAuth] = useState(true);

  // 检查认证状态
  const checkAuth = useCallback(async () => {
    const storedUser = getStoredUser();
    if (storedUser) {
      setUser(storedUser);
      // 后台验证 token 有效性
      const validUser = await getCurrentUser();
      if (!validUser) {
        setUser(null);
      }
    }
    setIsCheckingAuth(false);
  }, []);

  // 初始化时检查认证
  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  // 登出
  const logout = useCallback(async () => {
    await logoutApi();
    setUser(null);
  }, []);

  // 刷新用户信息
  const refreshUser = useCallback(() => {
    const storedUser = getStoredUser();
    setUser(storedUser);
  }, []);

  return {
    user,
    isCheckingAuth,
    logout,
    setUser,
    refreshUser,
  };
}
