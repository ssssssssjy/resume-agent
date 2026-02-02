"""事件缓冲区 - 支持 SSE 重连和多客户端订阅"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncIterator
import asyncio
import logging

from .schemas import SSEEvent

logger = logging.getLogger(__name__)


@dataclass
class RunBuffer:
    """单个 Run 的事件缓冲"""

    events: list[SSEEvent] = field(default_factory=list)
    subscribers: list[asyncio.Queue[SSEEvent]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished: bool = False


class EventBuffer:
    """事件缓冲区

    职责：
    - 存储 Run 执行过程中的 SSE 事件
    - 支持断线重连后重放历史事件
    - 支持多客户端订阅同一 Run
    - 自动清理过期缓冲区
    """

    def __init__(self, ttl_seconds: int = 3600):
        self._buffers: dict[str, RunBuffer] = {}
        self._ttl = ttl_seconds
        self._cleanup_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """启动后台清理任务"""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("EventBuffer 已启动")

    async def stop(self) -> None:
        """停止清理任务"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("EventBuffer 已停止")

    async def put(self, run_id: str, event: SSEEvent) -> None:
        """添加事件并通知订阅者"""
        buf = self._get_or_create(run_id)
        buf.events.append(event)

        for queue in buf.subscribers:
            await queue.put(event)

        if event.event == "end":
            buf.finished = True

    def get_events(self, run_id: str) -> list[SSEEvent]:
        """获取所有历史事件"""
        buf = self._buffers.get(run_id)
        return list(buf.events) if buf else []

    def is_active(self, run_id: str) -> bool:
        """检查 Run 是否还在执行"""
        buf = self._buffers.get(run_id)
        return buf is not None and not buf.finished

    def has_run(self, run_id: str) -> bool:
        """检查 Run 是否存在"""
        return run_id in self._buffers

    def clear_run(self, run_id: str) -> None:
        """清理指定 Run 的事件缓冲"""
        if run_id in self._buffers:
            del self._buffers[run_id]

    async def subscribe(self, run_id: str) -> AsyncIterator[SSEEvent]:
        """订阅 Run 的实时事件"""
        buf = self._get_or_create(run_id)
        queue: asyncio.Queue[SSEEvent] = asyncio.Queue()
        buf.subscribers.append(queue)

        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield event
                    if event.event == "end":
                        break
                except asyncio.TimeoutError:
                    if buf.finished:
                        break
        finally:
            if queue in buf.subscribers:
                buf.subscribers.remove(queue)

    def _get_or_create(self, run_id: str) -> RunBuffer:
        if run_id not in self._buffers:
            self._buffers[run_id] = RunBuffer()
        return self._buffers[run_id]

    async def _cleanup_loop(self) -> None:
        """定期清理过期缓冲区"""
        while True:
            try:
                await asyncio.sleep(300)  # 每 5 分钟检查
                now = datetime.now(timezone.utc)
                to_remove = [
                    run_id
                    for run_id, buf in self._buffers.items()
                    if buf.finished and (now - buf.created_at).total_seconds() > self._ttl
                ]
                for run_id in to_remove:
                    del self._buffers[run_id]
                if to_remove:
                    logger.debug(f"清理了 {len(to_remove)} 个过期缓冲区")
            except asyncio.CancelledError:
                break
