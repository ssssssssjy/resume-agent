"""会话管理 API - 存储和检索简历会话元数据"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from .auth import get_user_from_token
from .database import get_db_context

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


class SessionCreate(BaseModel):
    """创建会话请求"""
    thread_id: str
    filename: str
    resume_content: str


class SessionResponse(BaseModel):
    """会话响应"""
    thread_id: str
    filename: str
    resume_content: str
    created_at: str
    updated_at: str


class SessionListItem(BaseModel):
    """会话列表项"""
    thread_id: str
    filename: str
    created_at: str
    updated_at: str


@router.post("", response_model=SessionResponse)
async def create_session(data: SessionCreate, authorization: Optional[str] = Header(None)):
    """创建或更新会话元数据"""
    user_id = get_user_from_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    now = datetime.now()

    with get_db_context() as conn:
        # PostgreSQL UPSERT 语法
        conn.execute("""
            INSERT INTO sessions (thread_id, user_id, filename, resume_content, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (thread_id) DO UPDATE SET
                filename = EXCLUDED.filename,
                resume_content = EXCLUDED.resume_content,
                updated_at = EXCLUDED.updated_at
        """, (data.thread_id, user_id, data.filename, data.resume_content, now, now))
        conn.commit()

    return SessionResponse(
        thread_id=data.thread_id,
        filename=data.filename,
        resume_content=data.resume_content,
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
    )


@router.get("", response_model=list[SessionListItem])
async def list_sessions(limit: int = 50, offset: int = 0, authorization: Optional[str] = Header(None)):
    """获取当前用户的会话列表（不含简历内容，节省带宽）"""
    user_id = get_user_from_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")

    with get_db_context() as conn:
        cursor = conn.execute("""
            SELECT thread_id, filename, created_at, updated_at
            FROM sessions
            WHERE user_id = %s
            ORDER BY updated_at DESC
            LIMIT %s OFFSET %s
        """, (user_id, limit, offset))

        sessions = [
            SessionListItem(
                thread_id=row["thread_id"],
                filename=row["filename"],
                created_at=row["created_at"].isoformat() if hasattr(row["created_at"], 'isoformat') else str(row["created_at"]),
                updated_at=row["updated_at"].isoformat() if hasattr(row["updated_at"], 'isoformat') else str(row["updated_at"]),
            )
            for row in cursor.fetchall()
        ]

    return sessions


@router.get("/{thread_id}", response_model=SessionResponse)
async def get_session(thread_id: str, authorization: Optional[str] = Header(None)):
    """获取单个会话详情（含简历内容）"""
    user_id = get_user_from_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")

    with get_db_context() as conn:
        cursor = conn.execute("""
            SELECT thread_id, filename, resume_content, created_at, updated_at
            FROM sessions
            WHERE thread_id = %s AND user_id = %s
        """, (thread_id, user_id))

        row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse(
        thread_id=row["thread_id"],
        filename=row["filename"],
        resume_content=row["resume_content"],
        created_at=row["created_at"].isoformat() if hasattr(row["created_at"], 'isoformat') else str(row["created_at"]),
        updated_at=row["updated_at"].isoformat() if hasattr(row["updated_at"], 'isoformat') else str(row["updated_at"]),
    )


@router.delete("/{thread_id}")
async def delete_session(thread_id: str, authorization: Optional[str] = Header(None)):
    """删除会话"""
    user_id = get_user_from_token(authorization)
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录或登录已过期")

    with get_db_context() as conn:
        cursor = conn.execute(
            "DELETE FROM sessions WHERE thread_id = %s AND user_id = %s",
            (thread_id, user_id)
        )
        conn.commit()
        deleted = cursor.rowcount > 0

    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"success": True}
