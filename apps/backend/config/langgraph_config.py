"""LangGraph 工作流配置"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

from .app_config import config

logger = logging.getLogger(__name__)


# ==================== 日志配置 ====================


def _configure_langgraph_logging() -> None:
    """配置 LangGraph 相关的日志级别，减少 DEBUG 日志刷屏"""
    noisy_loggers = [
        "aiosqlite",
        "httpcore",
        "httpx",
        "openai",
        "urllib3",
        "uvicorn.access",
        "langgraph",
        "langchain",
        "langchain_core",
    ]
    for name in noisy_loggers:
        logging.getLogger(name).setLevel(logging.WARNING)


# 模块导入时自动配置日志级别
_configure_langgraph_logging()


# ==================== Checkpointer 配置 ====================


@asynccontextmanager
async def get_checkpointer() -> AsyncIterator[BaseCheckpointSaver]:
    """获取 Checkpointer（根据环境自动选择）

    优先级:
    1. WORKFLOW_DATABASE_URL → PostgreSQL（生产环境）
    2. WORKFLOW_SQLITE_PATH → SQLite（本地持久化，热重载不丢失）
    3. 默认 → MemorySaver（内存，热重载丢失）

    用法:
        async with get_checkpointer() as checkpointer:
            graph = builder.compile(checkpointer=checkpointer)
            # 使用 graph...
    """
    db_url = config.workflow_database_url
    sqlite_path = config.workflow_sqlite_path

    if db_url:
        # 生产环境：PostgreSQL
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg.rows import dict_row
        from psycopg_pool import AsyncConnectionPool

        logger.info(f"使用 PostgreSQL Checkpointer: {db_url[:50]}...")

        pool = AsyncConnectionPool(
            conninfo=db_url,
            min_size=2,
            max_size=10,
            max_idle=300.0,
            reconnect_timeout=60.0,
            open=False,
            kwargs={
                "row_factory": dict_row,
                "autocommit": True,
            },
        )

        async with pool:
            checkpointer = AsyncPostgresSaver(pool)  # type: ignore[arg-type]
            await checkpointer.setup()
            yield checkpointer

    elif sqlite_path:
        # 本地开发：SQLite（持久化，热重载不丢失）
        import aiosqlite
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        from pathlib import Path

        logger.info(f"使用 SQLite Checkpointer: {sqlite_path}")

        # 确保目录存在
        db_path = Path(sqlite_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Monkey-patch: 为 aiosqlite.Connection 添加 is_alive 方法
        if not hasattr(aiosqlite.Connection, "is_alive"):
            aiosqlite.Connection.is_alive = lambda self: self._running  # type: ignore[attr-defined]

        async with aiosqlite.connect(sqlite_path) as conn:
            checkpointer = AsyncSqliteSaver(conn)
            await checkpointer.setup()
            yield checkpointer

    else:
        # 内存（最简单，但热重载丢失）
        logger.info("使用 MemorySaver Checkpointer（内存存储）")
        yield MemorySaver()
