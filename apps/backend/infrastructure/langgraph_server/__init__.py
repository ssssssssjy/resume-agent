"""LangGraph Server 兼容层

提供 LangGraph Platform 兼容的 API 实现，可用于 FastAPI 应用。

Checkpointer 说明:
    Checkpointer 由 LangGraph 库管理，在 graph 编译时绑定。
    Service 层通过已编译的 graph 访问状态，不直接操作 checkpointer。
    这与 LangGraph Platform 的设计一致。

基本用法:
    from langgraph.graph import StateGraph
    from langgraph.checkpoint.memory import MemorySaver
    from infrastructure.langgraph_server import (
        create_langgraph_router,
        LangGraphServerConfig,
    )

    # 构建 graph（checkpointer 在编译时绑定）
    checkpointer = MemorySaver()  # 或 AsyncPostgresSaver 等
    graph = my_graph_builder.compile(checkpointer=checkpointer)

    # 创建 router（不需要传入 checkpointer）
    router, get_lifespan, assistants_router = create_langgraph_router(
        graphs={"my_workflow": graph},
        config=LangGraphServerConfig(),
    )

    # 在 lifespan 中启动/停止
    @asynccontextmanager
    async def lifespan(app):
        async with get_lifespan() as service:
            yield

    app = FastAPI(lifespan=lifespan)
    app.include_router(router)
    if assistants_router:
        app.include_router(assistants_router)  # 挂载 /assistants 到根路径
"""

from .config import LangGraphServerConfig
from .router import create_langgraph_router
from .schemas import (
    AssistantSearchRequest,
    Command,
    ErrorResponse,
    MultitaskStrategy,
    Run,
    RunConfig,
    RunCreate,
    RunStatus,
    RunWaitResponse,
    SSEEvent,
    StreamMode,
    Thread,
    ThreadCheckpoint,
    ThreadCreate,
    ThreadHistoryRequest,
    ThreadPatch,
    ThreadSearchRequest,
    ThreadState,
    ThreadStateUpdate,
    ThreadStateUpdateResponse,
    ThreadStatus,
)
from .service import LangGraphService
from .buffer import EventBuffer
from .executor import GraphExecutor
from .types import ActiveRun

__all__ = [
    # 核心工厂函数
    "create_langgraph_router",
    # 配置
    "LangGraphServerConfig",
    # 服务
    "LangGraphService",
    # 内部组件（高级用法）
    "EventBuffer",
    "GraphExecutor",
    "ActiveRun",
    # Schemas - Enums
    "RunStatus",
    "ThreadStatus",
    "StreamMode",
    "MultitaskStrategy",
    # Schemas - Thread
    "Thread",
    "ThreadCheckpoint",
    "ThreadCreate",
    "ThreadHistoryRequest",
    "ThreadPatch",
    "ThreadSearchRequest",
    "ThreadState",
    "ThreadStateUpdate",
    "ThreadStateUpdateResponse",
    # Schemas - Assistant
    "AssistantSearchRequest",
    # Schemas - Run
    "Run",
    "RunCreate",
    "RunConfig",
    "RunWaitResponse",
    "Command",
    # Schemas - Other
    "SSEEvent",
    "ErrorResponse",
]
