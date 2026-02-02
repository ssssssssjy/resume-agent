"""Thread 服务 - Thread CRUD 和搜索操作"""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
import logging

from langchain_core.runnables import RunnableConfig

from ..schemas import ThreadStatus

logger = logging.getLogger(__name__)


class ThreadMixin:
    """Thread 管理 Mixin

    提供 Thread 的 CRUD 和搜索功能。
    需要与 BaseService 一起使用。
    """

    # Type hints for BaseService attributes
    _executor: Any
    _graphs: Any
    _checkpointer: Any

    async def _get_graph_for_thread(self, thread_id: str) -> Any:
        ...

    def _infer_thread_status(self, thread_id: str, state: Any) -> str:
        ...

    def _serialize_state_values(self, state_values: Any) -> dict[str, Any]:
        ...

    async def create_thread(self) -> dict[str, Any]:
        """创建 Thread

        Thread 是虚拟的，返回 thread_id 即可。
        实际的 Thread 数据在首次执行 Run 时由 Checkpointer 创建。
        """
        thread_id = str(uuid4())
        now = datetime.now(timezone.utc)
        return {
            "thread_id": thread_id,
            "created_at": now,
            "updated_at": now,
            "status": ThreadStatus.IDLE.value,
            "metadata": {},
        }

    async def get_thread(self, thread_id: str) -> dict[str, Any] | None:
        """获取 Thread（从 Checkpoint 推断）"""
        graph = await self._get_graph_for_thread(thread_id)
        if not graph:
            return None

        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

        try:
            state = await graph.aget_state(config)
        except Exception as e:
            logger.warning(f"获取 Thread 状态失败: {e}")
            return None

        if not state or not state.values:
            return None

        status = self._infer_thread_status(thread_id, state)
        now = datetime.now(timezone.utc)
        created_at = getattr(state, "created_at", None) or now

        values = self._serialize_state_values(state.values or {})

        # 提取 interrupts（按任务 ID 分组）
        interrupts: dict[str, list[dict[str, Any]]] = {}
        if state.tasks:
            for t in state.tasks:
                if hasattr(t, "interrupts") and t.interrupts:
                    task_interrupts = []
                    for intr in t.interrupts:
                        task_interrupts.append({
                            "value": getattr(intr, "value", intr),
                            "when": "during",
                            "resumable": True,
                            "ns": None,
                        })
                    if task_interrupts:
                        interrupts[t.id] = task_interrupts

        return {
            "thread_id": thread_id,
            "created_at": created_at,
            "updated_at": created_at,
            "metadata": {},
            "status": status,
            "values": values,
            "interrupts": interrupts,
        }

    async def delete_thread(self, thread_id: str) -> bool:
        """删除 Thread

        包括：取消活跃 Run、删除 Checkpoint 数据。
        """
        # 取消活跃 run
        run = self._executor.get_active_run(thread_id)
        if run:
            await self._executor.cancel_run(thread_id, str(run.run_id))

        # 删除 checkpoint 数据
        if self._checkpointer:
            try:
                await self._checkpointer.adelete_thread(thread_id)
            except Exception as e:
                logger.warning(f"删除 thread {thread_id} checkpoint 失败: {e}")
                return False

        return True

    async def search_threads(
        self,
        metadata: dict[str, Any] | None = None,
        values: dict[str, Any] | None = None,
        status: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """搜索 Threads

        优化策略：
        1. 对于 PostgreSQL checkpointer，尝试直接 SQL 查询（最高效）
        2. 回退到 checkpointer.alist() 遍历（兼容所有 checkpointer）
        """
        if not self._checkpointer:
            return []

        # 尝试使用优化的 PostgreSQL 直接查询
        pg_results = await self._search_threads_postgres(limit, offset, metadata, status)
        if pg_results is not None:
            return pg_results

        # 回退到通用实现（遍历 checkpoints）
        return await self._search_threads_fallback(metadata, values, status, limit, offset)

    async def _search_threads_postgres(
        self,
        limit: int,
        offset: int,
        metadata: dict[str, Any] | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]] | None:
        """PostgreSQL 优化查询

        直接查询数据库获取 distinct thread_ids，避免遍历所有 checkpoints。
        返回 None 表示不支持，回退到通用实现。
        """
        if not self._checkpointer:
            return None

        # 检查是否是 AsyncPostgresSaver（有 conn 或 pool 属性）
        pool = getattr(self._checkpointer, "pool", None) or getattr(self._checkpointer, "conn", None)
        if not pool:
            return None

        try:
            query = """
                SELECT DISTINCT ON (thread_id) thread_id
                FROM checkpoints
                WHERE checkpoint_ns = ''
                ORDER BY thread_id, checkpoint_id DESC
                LIMIT $1 OFFSET $2
            """

            async with pool.acquire() as conn:
                rows = await conn.fetch(query, limit + 100, offset)

            results: list[dict[str, Any]] = []
            for row in rows:
                thread_id = row["thread_id"]
                thread = await self.get_thread(thread_id)
                if not thread:
                    continue

                if status and thread.get("status") != status:
                    continue

                if metadata:
                    thread_metadata = thread.get("metadata", {})
                    if not all(thread_metadata.get(k) == v for k, v in metadata.items()):
                        continue

                results.append(thread)
                if len(results) >= limit:
                    break

            return results

        except Exception as e:
            logger.debug(f"PostgreSQL 直接查询失败，回退到通用实现: {e}")
            return None

    async def _search_threads_fallback(
        self,
        metadata: dict[str, Any] | None,
        _values: dict[str, Any] | None,
        status: str | None,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        """通用实现：遍历 checkpoints

        注意：在大量 threads 时性能较差，仅作为兼容方案。
        """
        if not self._checkpointer:
            return []

        seen_threads: set[str] = set()
        results: list[dict[str, Any]] = []

        try:
            async for checkpoint_tuple in self._checkpointer.alist(None, limit=limit + offset + 100):
                thread_id = checkpoint_tuple.config.get("configurable", {}).get("thread_id")
                if not thread_id or thread_id in seen_threads:
                    continue
                seen_threads.add(thread_id)

                thread = await self.get_thread(thread_id)
                if not thread:
                    continue

                if status and thread.get("status") != status:
                    continue

                if metadata:
                    thread_metadata = thread.get("metadata", {})
                    if not all(thread_metadata.get(k) == v for k, v in metadata.items()):
                        continue

                results.append(thread)

                if len(results) >= limit + offset:
                    break

        except Exception as e:
            logger.warning(f"搜索 threads 失败: {e}")
            return []

        return results[offset : offset + limit]
