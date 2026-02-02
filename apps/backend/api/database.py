"""数据库配置和连接管理 - 支持 PostgreSQL"""

import os
from contextlib import contextmanager
from typing import Generator

import psycopg
from psycopg.rows import dict_row

# 从环境变量获取数据库连接字符串
# 格式: postgresql://user:password@host:port/dbname
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/resume_agent"
)


def get_db() -> psycopg.Connection:
    """获取数据库连接"""
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    return conn


@contextmanager
def get_db_context() -> Generator[psycopg.Connection, None, None]:
    """数据库连接上下文管理器"""
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()


def init_tables():
    """初始化所有数据库表"""
    with get_db_context() as conn:
        # 创建用户表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # 创建 token 表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tokens (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # 创建索引
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tokens_user_id ON tokens(user_id)
        """)

        # 创建会话表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                thread_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL DEFAULT '',
                filename TEXT NOT NULL,
                resume_content TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # 创建索引
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at DESC)
        """)

        conn.commit()


# 应用启动时初始化表
try:
    init_tables()
except Exception as e:
    print(f"Warning: Failed to initialize database tables: {e}")
    print("Make sure PostgreSQL is running and DATABASE_URL is correctly configured.")
