"""LangGraph Service - 服务门面

对外提供统一的 API 接口，组合：
- BaseService: 生命周期管理 + 辅助方法
- ThreadMixin: Thread CRUD + 搜索
- StateMixin: Thread State 操作
- RunMixin: Run 管理

注意：Checkpointer 由 LangGraph 库管理，在 graph 编译时绑定。
      Service 通过已编译的 graph 访问状态，不直接操作 checkpointer。
"""

from .base import BaseService
from .thread import ThreadMixin
from .state import StateMixin
from .run import RunMixin


class LangGraphService(BaseService, ThreadMixin, StateMixin, RunMixin):
    """LangGraph 服务门面

    使用 Mixin 模式组合各领域功能：
    - BaseService: 生命周期、Graph 访问、辅助方法
    - ThreadMixin: Thread CRUD 和搜索
    - StateMixin: Thread State 读写和历史
    - RunMixin: Run 执行和管理

    用法：
        service = LangGraphService(graphs)
        await service.start()
        # ...
        await service.stop()
    """
    pass


__all__ = ["LangGraphService"]
