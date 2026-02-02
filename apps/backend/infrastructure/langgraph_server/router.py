"""LangGraph Router 工厂函数"""

from contextlib import asynccontextmanager
from enum import Enum
from typing import AsyncContextManager, Callable, Dict, List, Optional, Tuple, Union

from fastapi import APIRouter
from langgraph.graph.state import CompiledStateGraph

from .config import LangGraphServerConfig
from .service import LangGraphService
from .routes import (
    add_thread_base_routes,
    add_thread_param_routes,
    add_runs_routes,
    create_assistants_router,
    add_system_routes,
)


def create_langgraph_router(
    graphs: Dict[str, CompiledStateGraph],
    config: Optional[LangGraphServerConfig] = None,
    *,
    prefix: str = "/threads",
    tags: Optional[List[str]] = None,
    include_assistants: bool = True,
    include_system: bool = True,
) -> Tuple[
    APIRouter,
    Callable[[], AsyncContextManager[LangGraphService]],
    Optional[APIRouter],
]:
    """创建 LangGraph 兼容的 FastAPI router

    Args:
        graphs: Graph 名称到已编译实例的映射（graph 需在编译时绑定 checkpointer）
        config: 服务配置
        prefix: 主路由前缀（默认 /threads）
        tags: OpenAPI tags
        include_assistants: 是否包含 /assistants 路由
        include_system: 是否包含 /ok, /info 路由

    Returns:
        (router, lifespan_context_manager_factory, assistants_router)
        - router: FastAPI APIRouter，包含 /threads 端点
        - lifespan_context_manager_factory: 返回用于 FastAPI lifespan 的上下文管理器
        - assistants_router: /assistants 路由（需挂载在根路径），如果 include_assistants=False 则为 None

    Example:
        from langgraph.graph import StateGraph
        from langgraph.checkpoint.memory import MemorySaver
        from infrastructure.langgraph_server import create_langgraph_router, LangGraphServerConfig

        # 构建 graph（checkpointer 在编译时绑定）
        checkpointer = MemorySaver()
        graph = my_graph_builder.compile(checkpointer=checkpointer)

        # 创建 router（不需要传入 checkpointer）
        router, get_lifespan, assistants_router = create_langgraph_router(
            graphs={"my_workflow": graph},
            config=LangGraphServerConfig(),
        )

        @asynccontextmanager
        async def lifespan(app):
            async with get_lifespan() as service:
                yield

        app = FastAPI(lifespan=lifespan)
        app.include_router(router)
        if assistants_router:
            app.include_router(assistants_router)  # 挂载在根路径 /assistants
    """
    config = config or LangGraphServerConfig()
    resolved_tags: List[Union[str, Enum]] = list(tags) if tags else ["LangGraph"]

    # 服务实例将在 lifespan 中初始化
    _service: Optional[LangGraphService] = None

    @asynccontextmanager
    async def lifespan_manager():
        """生命周期管理器"""
        nonlocal _service

        service = LangGraphService(
            graphs=graphs,
            config=config,
        )
        await service.start()
        _service = service

        try:
            yield service
        finally:
            await service.stop()
            _service = None

    async def get_service() -> LangGraphService:
        """获取服务实例"""
        if _service is None:
            raise RuntimeError(
                "LangGraph service not initialized. "
                "Make sure to use the lifespan context manager."
            )
        return _service

    # ==================== 主路由 ====================

    router = APIRouter(prefix=prefix, tags=resolved_tags)

    # 路由注册顺序很重要：
    # 1. 非参数化路由（如 /search）必须先注册
    # 2. System 路由（/ok, /info）必须在 /{thread_id} 之前
    # 3. 参数化路由（/{thread_id}/*）最后注册

    # 添加 Thread 基础路由（非参数化）
    add_thread_base_routes(router, get_service)

    # 添加 System 路由
    if include_system:
        add_system_routes(router, get_service)

    # 添加 Thread 参数化路由
    add_thread_param_routes(router, get_service)

    # 添加 Run 路由（参数化）
    add_runs_routes(router, get_service, config)

    # ==================== Assistants 路由（挂载在根路径） ====================

    assistants_router: Optional[APIRouter] = None
    if include_assistants:
        assistants_router = create_assistants_router(get_service)

    return router, lifespan_manager, assistants_router
