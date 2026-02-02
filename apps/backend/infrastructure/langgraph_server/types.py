"""LangGraph Server 内部类型定义

仅包含内部使用的类型，API 类型复用 schemas 模块。
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID
import asyncio

from .schemas import RunStatus


@dataclass
class ActiveRun:
    """活跃的 Run

    每个 Thread 最多只有一个 ActiveRun。
    仅在内存中维护，用于 Run 管理和取消。
    """

    run_id: UUID
    thread_id: str
    assistant_id: str
    status: RunStatus
    task: asyncio.Task[Any]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)
    on_disconnect: str = "cancel"  # "cancel" | "continue"

    def to_dict(self) -> dict[str, Any]:
        """转换为 API 响应格式"""
        return {
            "run_id": str(self.run_id),
            "thread_id": self.thread_id,
            "assistant_id": self.assistant_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }
