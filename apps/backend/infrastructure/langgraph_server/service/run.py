"""Run 服务 - Run 管理操作"""

from typing import Any, AsyncIterator

from ..schemas import RunCreate, SSEEvent
from ..types import ActiveRun


class RunMixin:
    """Run 管理 Mixin

    提供 Run 的列表、获取、创建、流式执行和取消功能。
    需要与 BaseService 一起使用。
    """

    # Type hints for BaseService attributes
    _executor: Any

    async def create_run(
        self, thread_id: str, request: RunCreate
    ) -> dict[str, Any]:
        """创建 Run（后台执行，立即返回）"""
        active_run: ActiveRun = await self._executor.create_run(thread_id, request)
        return active_run.to_dict()

    async def list_runs(self, thread_id: str) -> list[dict[str, Any]]:
        """列出 Thread 的 Runs（只有活跃的）"""
        run = self._executor.get_active_run(thread_id)
        return [run.to_dict()] if run else []

    async def get_run(self, thread_id: str, run_id: str) -> dict[str, Any] | None:
        """获取 Run"""
        run = self._executor.get_active_run(thread_id)
        if run and str(run.run_id) == run_id:
            return run.to_dict()
        return None

    async def stream_run(
        self,
        thread_id: str,
        request: RunCreate,
    ) -> AsyncIterator[SSEEvent]:
        """流式执行 Run"""
        async for event in self._executor.stream_run(thread_id, request):
            yield event

    async def stream_run_output(
        self,
        thread_id: str,
        run_id: str,
    ) -> AsyncIterator[SSEEvent]:
        """订阅 Run 输出（重连用）"""
        async for event in self._executor.stream_run_output(thread_id, run_id):
            yield event

    async def cancel_run(self, thread_id: str, run_id: str) -> bool:
        """取消 Run"""
        return await self._executor.cancel_run(thread_id, run_id)
