"""System 路由 - 健康检查和服务信息"""

from typing import Any, Callable, Coroutine, Dict

from fastapi import APIRouter

from ..service import LangGraphService


def add_system_routes(
    router: APIRouter,
    get_service: Callable[[], Coroutine[Any, Any, LangGraphService]],
) -> None:
    """添加 System 路由到现有路由器"""

    @router.get("/ok")
    async def health_check() -> Dict[str, str]:
        """健康检查"""
        return {"status": "ok"}

    @router.get("/info")
    async def get_info() -> Dict[str, Any]:
        """获取服务信息"""
        service = await get_service()
        return {
            "version": "1.0.0",
            "graphs": service.list_graphs(),
        }
