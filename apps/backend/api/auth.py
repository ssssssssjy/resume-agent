"""用户认证 API - 用户名/密码 + Google OAuth 认证"""

import hashlib
import logging
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from config.app_config import config

from .database import get_db_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def hash_password(password: str) -> str:
    """使用 SHA256 + salt 进行密码哈希"""
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}${hashed}"


def verify_password(password: str, hashed: str) -> bool:
    """验证密码"""
    try:
        salt, stored_hash = hashed.split("$")
        return hashlib.sha256((password + salt).encode()).hexdigest() == stored_hash
    except ValueError:
        return False


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


class GoogleLoginRequest(BaseModel):
    """Google OAuth 登录请求"""
    credential: str  # Google ID token (JWT)


class AuthResponse(BaseModel):
    """认证响应"""
    user_id: str
    username: str
    token: str


class UserInfo(BaseModel):
    """用户信息"""
    user_id: str
    username: str
    email: str | None = None
    avatar_url: str | None = None


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

        if not user or not user["password_hash"] or not verify_password(data.password, user["password_hash"]):
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
            SELECT u.id, u.username, u.email, u.avatar_url
            FROM users u
            JOIN tokens t ON u.id = t.user_id
            WHERE t.token = %s
        """, (token,))
        user = cursor.fetchone()

    if not user:
        raise HTTPException(status_code=401, detail="登录已过期")

    return UserInfo(
        user_id=user["id"],
        username=user["username"],
        email=user.get("email"),
        avatar_url=user.get("avatar_url"),
    )


@router.post("/google", response_model=AuthResponse)
async def google_login(data: GoogleLoginRequest):
    """Google OAuth 登录"""
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    client_id = config.google_client_id
    if not client_id:
        raise HTTPException(status_code=500, detail="Google OAuth 未配置")

    # 验证 Google ID token
    try:
        idinfo = id_token.verify_oauth2_token(
            data.credential,
            google_requests.Request(),
            client_id,
        )
    except ValueError as e:
        logger.warning("Google ID token 验证失败: %s", e)
        raise HTTPException(status_code=401, detail="Google 登录验证失败")

    google_id = idinfo["sub"]
    email = idinfo.get("email", "")
    name = idinfo.get("name", "")
    picture = idinfo.get("picture", "")

    with get_db_context() as conn:
        # 查找已有 Google 用户
        cursor = conn.execute(
            "SELECT id, username FROM users WHERE google_id = %s",
            (google_id,),
        )
        user = cursor.fetchone()

        if not user:
            # 首次 Google 登录，创建新用户
            user_id = secrets.token_hex(16)
            # 用邮箱前缀作为用户名，冲突时加随机后缀
            base_username = name or email.split("@")[0] or "google_user"
            username = base_username
            cursor = conn.execute(
                "SELECT id FROM users WHERE username = %s", (username,)
            )
            if cursor.fetchone():
                username = f"{base_username}_{secrets.token_hex(3)}"

            now = datetime.now()
            conn.execute(
                "INSERT INTO users (id, username, google_id, email, avatar_url, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (user_id, username, google_id, email, picture, now),
            )
            user = {"id": user_id, "username": username}
        else:
            user_id = user["id"]
            # 更新 email 和头像
            conn.execute(
                "UPDATE users SET email = %s, avatar_url = %s WHERE id = %s",
                (email, picture, user_id),
            )

        # 查找或创建 token
        cursor = conn.execute(
            "SELECT token FROM tokens WHERE user_id = %s LIMIT 1",
            (user["id"],),
        )
        existing = cursor.fetchone()

        if existing:
            token = existing["token"]
        else:
            token = generate_token()
            now = datetime.now()
            conn.execute(
                "INSERT INTO tokens (token, user_id, created_at) VALUES (%s, %s, %s)",
                (token, user["id"], now),
            )

        conn.commit()

    return AuthResponse(user_id=user["id"], username=user["username"], token=token)


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
