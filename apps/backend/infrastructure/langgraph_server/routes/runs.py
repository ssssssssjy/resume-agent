"""Run 路由 - Run 流式执行和管理"""

import asyncio
import dataclasses
import json
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from ..config import LangGraphServerConfig
from ..service import LangGraphService
from ..schemas import Run, RunCreate


class _PydanticJSONEncoder(json.JSONEncoder):
    """自定义 JSON 编码器

    处理 SSE 事件数据序列化，支持：
    - Pydantic BaseModel
    - dataclass（包括 LangGraph 的 Interrupt）
    - Enum
    - 普通对象（有 __dict__）
    """

    def default(self, o: Any) -> Any:
        if isinstance(o, BaseModel):
            return o.model_dump()
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            # 处理 dataclass 实例（如 LangGraph 的 Interrupt）
            return dataclasses.asdict(o)
        if isinstance(o, Enum):
            return o.value
        if hasattr(o, "__dict__"):
            return o.__dict__
        return str(o)


def _serialize_event_data(data: Any) -> str:
    """序列化 SSE 事件数据"""
    return json.dumps(data, ensure_ascii=False, cls=_PydanticJSONEncoder)


def add_runs_routes(
    router: APIRouter,
    get_service: Callable[[], Coroutine[Any, Any, LangGraphService]],
    config: LangGraphServerConfig,
) -> None:
    """添加 Run 路由到现有路由器"""

    @router.post("/{thread_id}/runs/stream")
    async def stream_run(
        thread_id: UUID,
        request: RunCreate,
        last_event_id: Optional[str] = Header(
            None, alias="Last-Event-Id", description="SSE 重连时的最后事件 ID"
        ),
    ) -> EventSourceResponse:
        """流式运行 Run"""
        service = await get_service()

        if not service.get_graph(request.assistant_id):
            raise HTTPException(
                status_code=404,
                detail=f"Graph {request.assistant_id} not found. Available: {service.list_graphs()}",
            )

        # 注意：LangGraph 的 Thread 是虚拟的，首次 run 时会自动创建 checkpoint
        # if_not_exists 参数在此场景下不适用，因为我们无法区分：
        # 1. 从未使用过的 thread_id（应该检查 if_not_exists）
        # 2. 通过 POST /threads 创建但还没执行 run 的 thread（应该允许）
        # 因此直接允许所有 thread_id 执行 run，首次执行会自动创建 checkpoint

        seq_counter = 0

        async def event_generator():
            nonlocal seq_counter
            try:
                async for event in service.stream_run(str(thread_id), request):
                    yield {
                        "event": event.event,
                        "data": _serialize_event_data(event.data),
                        "id": str(seq_counter),
                    }
                    seq_counter += 1
            except asyncio.CancelledError:
                pass
            except GeneratorExit:
                pass
            except Exception as e:
                yield {
                    "event": "error",
                    "data": _serialize_event_data({"message": str(e)}),
                    "id": str(seq_counter),
                }

        return EventSourceResponse(
            event_generator(),
            media_type="text/event-stream",
            ping=config.sse_ping_interval,
        )

    @router.get("/{thread_id}/runs/{run_id}/stream")
    async def stream_run_output(
        thread_id: UUID,
        run_id: UUID,
        last_event_id: Optional[str] = Header(
            None, alias="Last-Event-Id", description="SSE 重连时的最后事件 ID"
        ),
    ) -> EventSourceResponse:
        """订阅 Run 的输出（用于重连）"""
        service = await get_service()

        run = await service.get_run(str(thread_id), str(run_id))
        if not run:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

        seq_counter = 0
        if last_event_id is not None:
            try:
                seq_counter = int(last_event_id) + 1
            except ValueError:
                pass

        async def event_generator():
            nonlocal seq_counter
            try:
                async for event in service.stream_run_output(str(thread_id), str(run_id)):
                    yield {
                        "event": event.event,
                        "data": _serialize_event_data(event.data),
                        "id": str(seq_counter),
                    }
                    seq_counter += 1
            except asyncio.CancelledError:
                pass
            except GeneratorExit:
                pass
            except Exception as e:
                yield {
                    "event": "error",
                    "data": _serialize_event_data({"message": str(e)}),
                    "id": str(seq_counter),
                }

        return EventSourceResponse(
            event_generator(),
            media_type="text/event-stream",
            ping=config.sse_ping_interval,
        )

    @router.post("/{thread_id}/runs", response_model=Run)
    async def create_run(
        thread_id: UUID,
        request: RunCreate,
    ) -> Dict[str, Any]:
        """创建 Run（后台执行）

        创建 Run 并在后台开始执行。立即返回 Run 对象。
        客户端可通过 GET /threads/{thread_id}/runs/{run_id}/stream 接入流。

        注意：如需启用断点续连，请设置 stream_resumable=true
        """
        service = await get_service()

        if not service.get_graph(request.assistant_id):
            raise HTTPException(
                status_code=404,
                detail=f"Graph {request.assistant_id} not found. Available: {service.list_graphs()}",
            )

        try:
            run = await service.create_run(str(thread_id), request)
            return run
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))

    @router.get("/{thread_id}/runs", response_model=List[Run])
    async def list_runs(
        thread_id: UUID,
        limit: int = Query(10, ge=1, le=100),
        offset: int = Query(0, ge=0),
        status: Optional[str] = Query(None),
    ) -> List[Dict[str, Any]]:
        """列出 Thread 的 Runs（仅返回活跃 Run）"""
        service = await get_service()
        runs = await service.list_runs(str(thread_id))
        return runs

    @router.get("/{thread_id}/runs/{run_id}", response_model=Run)
    async def get_run(
        thread_id: UUID,
        run_id: UUID,
    ) -> Dict[str, Any]:
        """获取 Run"""
        service = await get_service()
        run = await service.get_run(str(thread_id), str(run_id))
        if not run:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        return run

    @router.post("/{thread_id}/runs/{run_id}/cancel")
    async def cancel_run(
        thread_id: UUID,
        run_id: UUID,
    ) -> Dict[str, Any]:
        """取消 Run"""
        service = await get_service()
        success = await service.cancel_run(str(thread_id), str(run_id))
        if not success:
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        return {"status": "cancelled"}
