"""用户认证 API - 简单的用户名/密码认证"""

import secrets
from datetime import datetime
from typing import Optional

import bcrypt
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from .database import get_db_context

router = APIRouter(prefix="/api/auth", tags=["auth"])


def hash_password(password: str) -> str:
    """使用 bcrypt 进行安全的密码哈希"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """验证密码"""
    return bcrypt.checkpw(password.encode(), hashed.encode())


def generate_token() -> str:
    """生成随机 token"""
    return secrets.token_hex(32)


class RegisterRequest(BaseModel):
    """注册请求"""
    username: str
    password: str


class LoginRequest(BaseModel):
    """登录请求"""
    username: str
    password: str


class AuthResponse(BaseModel):
    """认证响应"""
    user_id: str
    username: str
    token: str


class UserInfo(BaseModel):
    """用户信息"""
    user_id: str
    username: str


@router.post("/register", response_model=AuthResponse)
async def register(data: RegisterRequest):
    """注册新用户"""
    if len(data.username) < 2:
        raise HTTPException(status_code=400, detail="用户名至少需要2个字符")
    if len(data.password) < 4:
        raise HTTPException(status_code=400, detail="密码至少需要4个字符")

    with get_db_context() as conn:
        # 检查用户名是否已存在
        cursor = conn.execute(
            "SELECT id FROM users WHERE username = %s",
            (data.username,)
        )
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="用户名已存在")

        # 创建用户
        user_id = secrets.token_hex(16)
        password_hash = hash_password(data.password)
        now = datetime.now()

        conn.execute(
            "INSERT INTO users (id, username, password_hash, created_at) VALUES (%s, %s, %s, %s)",
            (user_id, data.username, password_hash, now)
        )

        # 创建 token
        token = generate_token()
        conn.execute(
            "INSERT INTO tokens (token, user_id, created_at) VALUES (%s, %s, %s)",
            (token, user_id, now)
        )

        conn.commit()

    return AuthResponse(user_id=user_id, username=data.username, token=token)


@router.post("/login", response_model=AuthResponse)
async def login(data: LoginRequest):
    """用户登录"""
    with get_db_context() as conn:
        cursor = conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = %s",
            (data.username,)
        )
        user = cursor.fetchone()

        if not user or not verify_password(data.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        # 查找已有 token，如果没有则创建新的
        cursor = conn.execute(
            "SELECT token FROM tokens WHERE user_id = %s LIMIT 1",
            (user["id"],)
        )
        existing = cursor.fetchone()

        if existing:
            token = existing["token"]
        else:
            token = generate_token()
            now = datetime.now()
            conn.execute(
                "INSERT INTO tokens (token, user_id, created_at) VALUES (%s, %s, %s)",
                (token, user["id"], now)
            )
            conn.commit()

    return AuthResponse(user_id=user["id"], username=user["username"], token=token)


@router.post("/logout")
async def logout(authorization: Optional[str] = Header(None)):
    """用户登出"""
    if not authorization:
        return {"success": True}

    token = authorization.replace("Bearer ", "")
    with get_db_context() as conn:
        conn.execute("DELETE FROM tokens WHERE token = %s", (token,))
        conn.commit()

    return {"success": True}


@router.get("/me", response_model=UserInfo)
async def get_current_user(authorization: Optional[str] = Header(None)):
    """获取当前用户信息"""
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录")

    token = authorization.replace("Bearer ", "")
    with get_db_context() as conn:
        cursor = conn.execute("""
            SELECT u.id, u.username
            FROM users u
            JOIN tokens t ON u.id = t.user_id
            WHERE t.token = %s
        """, (token,))
        user = cursor.fetchone()

    if not user:
        raise HTTPException(status_code=401, detail="登录已过期")

    return UserInfo(user_id=user["id"], username=user["username"])


def get_user_from_token(authorization: Optional[str]) -> Optional[str]:
    """从 token 获取 user_id（供其他模块使用）"""
    if not authorization:
        return None

    token = authorization.replace("Bearer ", "")
    with get_db_context() as conn:
        cursor = conn.execute(
            "SELECT user_id FROM tokens WHERE token = %s",
            (token,)
        )
        result = cursor.fetchone()

    return result["user_id"] if result else None
