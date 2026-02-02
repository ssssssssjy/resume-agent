"""Thread 路由 - Thread CRUD 和 State 操作"""

from typing import Any, Callable, Coroutine, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from ..service import LangGraphService
from ..schemas import (
    Thread,
    ThreadCreate,
    ThreadPatch,
    ThreadSearchRequest,
    ThreadState,
    ThreadStateUpdate,
    ThreadStateUpdateResponse,
    ThreadHistoryRequest,
)


def add_thread_base_routes(
    router: APIRouter,
    get_service: Callable[[], Coroutine[Any, Any, LangGraphService]],
) -> None:
    """添加 Thread 基础路由（非参数化路由，必须先注册）"""

    @router.post("", response_model=Thread)
    async def create_thread(request: ThreadCreate) -> Dict[str, Any]:
        """创建 Thread"""
        try:
            service = await get_service()
            thread = await service.create_thread()
            return thread
        except ValueError as e:
            raise HTTPException(status_code=409, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.post("/search", response_model=List[Thread])
    async def search_threads(request: ThreadSearchRequest) -> List[Dict[str, Any]]:
        """搜索 Threads"""
        service = await get_service()
        threads = await service.search_threads(
            metadata=request.metadata,
            values=request.values,
            status=request.status.value if request.status else None,
            limit=request.limit,
            offset=request.offset,
        )
        return threads


def add_thread_param_routes(
    router: APIRouter,
    get_service: Callable[[], Coroutine[Any, Any, LangGraphService]],
) -> None:
    """添加 Thread 参数化路由（/{thread_id}，必须在 /ok 和 /info 之后注册）"""

    # ==================== Thread CRUD ====================

    @router.get("/{thread_id}", response_model=Thread)
    async def get_thread(thread_id: UUID) -> Dict[str, Any]:
        """获取 Thread"""
        service = await get_service()
        thread = await service.get_thread(str(thread_id))
        if not thread:
            raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
        return thread

    @router.delete("/{thread_id}")
    async def delete_thread(thread_id: UUID) -> Dict[str, Any]:
        """删除 Thread"""
        service = await get_service()
        success = await service.delete_thread(str(thread_id))
        if not success:
            raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
        return {}

    @router.patch("/{thread_id}", response_model=Thread)
    async def patch_thread(thread_id: UUID, request: ThreadPatch) -> Dict[str, Any]:
        """更新 Thread（当前仅返回现有 Thread）"""
        service = await get_service()
        thread = await service.get_thread(str(thread_id))
        if not thread:
            raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
        return thread

    # ==================== Thread State ====================

    @router.get("/{thread_id}/state", response_model=ThreadState)
    async def get_thread_state(
        thread_id: UUID,
        subgraphs: bool = Query(False, description="是否包含子图状态"),
    ) -> Dict[str, Any]:
        """获取 Thread 状态

        Args:
            thread_id: Thread ID
            subgraphs: 是否包含子图状态。默认 False，只返回根图状态。
                      设为 True 时，返回的 tasks 中会包含嵌套的子图 state。
        """
        service = await get_service()
        state = await service.get_thread_state(str(thread_id), subgraphs=subgraphs)
        if not state:
            raise HTTPException(status_code=404, detail=f"Thread {thread_id} not found")
        return state

    @router.post("/{thread_id}/state", response_model=ThreadStateUpdateResponse)
    async def update_thread_state(
        thread_id: UUID,
        request: ThreadStateUpdate,
    ) -> Dict[str, Any]:
        """更新 Thread 状态"""
        try:
            service = await get_service()
            result = await service.update_thread_state(
                str(thread_id),
                values=request.values,
                as_node=request.as_node,
                checkpoint_id=request.checkpoint_id,
                checkpoint_ns=request.checkpoint_ns,
            )
            return result
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @router.get("/{thread_id}/state/{checkpoint_id}", response_model=ThreadState)
    async def get_thread_state_at_checkpoint(
        thread_id: UUID,
        checkpoint_id: str,
        checkpoint_ns: Optional[str] = Query(None, description="Checkpoint 命名空间"),
    ) -> Dict[str, Any]:
        """获取指定 Checkpoint 的 Thread 状态"""
        service = await get_service()
        state = await service.get_thread_state_at_checkpoint(
            str(thread_id), checkpoint_id, checkpoint_ns
        )
        if not state:
            raise HTTPException(
                status_code=404, detail=f"Checkpoint {checkpoint_id} not found"
            )
        return state

    # ==================== Thread History ====================

    @router.get("/{thread_id}/history", response_model=List[ThreadState])
    async def get_thread_history(
        thread_id: UUID,
        limit: int = Query(10, ge=1, le=1000, description="返回数量限制"),
        before: Optional[str] = Query(None, description="在此 checkpoint_id 之前"),
        checkpoint_ns: Optional[str] = Query(None, description="Checkpoint 命名空间"),
    ) -> List[Dict[str, Any]]:
        """获取 Thread 的 Checkpoint 历史"""
        service = await get_service()
        history = await service.get_thread_history(
            str(thread_id), limit=limit, before=before, checkpoint_ns=checkpoint_ns
        )
        return history

    @router.post("/{thread_id}/history", response_model=List[ThreadState])
    async def get_thread_history_post(
        thread_id: UUID,
        request: ThreadHistoryRequest,
    ) -> List[Dict[str, Any]]:
        """获取 Thread 的 Checkpoint 历史（POST）"""
        service = await get_service()
        history = await service.get_thread_history(
            str(thread_id),
            limit=request.limit or 10,
            before=request.before,
            checkpoint_ns=request.checkpoint_ns,
        )
        return history
