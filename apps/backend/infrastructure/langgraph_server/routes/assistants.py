"""Assistant 路由 - Assistant 列表和搜索"""

from typing import Any, Callable, Coroutine, Dict, List

from fastapi import APIRouter, HTTPException

from ..service import LangGraphService
from ..schemas import AssistantSearchRequest


def create_assistants_router(
    get_service: Callable[[], Coroutine[Any, Any, LangGraphService]],
) -> APIRouter:
    """创建 Assistant 路由（独立路由器，挂载在 /assistants）"""
    router = APIRouter(prefix="/assistants", tags=["Assistants"])

    @router.get("")
    async def list_assistants() -> List[Dict[str, Any]]:
        """列出所有 Assistants"""
        service = await get_service()
        graph_names = service.list_graphs()
        return [
            {
                "assistant_id": name,
                "graph_id": name,
                "name": name,
                "created_at": None,
                "updated_at": None,
                "metadata": {},
            }
            for name in graph_names
        ]

    @router.post("/search")
    async def search_assistants(request: AssistantSearchRequest) -> List[Dict[str, Any]]:
        """搜索 Assistants"""
        service = await get_service()
        graph_names = service.list_graphs()

        # 构建 assistant 列表
        assistants = [
            {
                "assistant_id": name,
                "graph_id": name,
                "name": name,
                "created_at": None,
                "updated_at": None,
                "metadata": {},
            }
            for name in graph_names
        ]

        # 应用 graph_id 过滤
        if request.graph_id:
            assistants = [a for a in assistants if a["graph_id"] == request.graph_id]

        # 应用分页
        start = request.offset
        end = start + request.limit
        return assistants[start:end]

    @router.get("/{assistant_id}")
    async def get_assistant(assistant_id: str) -> Dict[str, Any]:
        """获取 Assistant"""
        service = await get_service()
        graph = service.get_graph(assistant_id)
        if not graph:
            raise HTTPException(
                status_code=404, detail=f"Assistant {assistant_id} not found"
            )
        return {
            "assistant_id": assistant_id,
            "graph_id": assistant_id,
            "name": assistant_id,
            "created_at": None,
            "updated_at": None,
            "metadata": {},
        }

    return router
