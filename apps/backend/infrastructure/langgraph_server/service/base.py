"""LangGraph Service - 基础服务类

生命周期管理和公共辅助方法。
"""

from typing import Any
import logging

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph

from ..config import LangGraphServerConfig
from ..buffer import EventBuffer
from ..executor import GraphExecutor
from ..schemas import ThreadStatus

logger = logging.getLogger(__name__)


class BaseService:
    """基础服务类

    职责：
    - 生命周期管理（start/stop）
    - Graph 访问
    - 公共辅助方法
    """

    def __init__(
        self,
        graphs: dict[str, CompiledStateGraph],
        config: LangGraphServerConfig | None = None,
    ):
        self._config = config or LangGraphServerConfig()
        self._graphs = graphs
        # 从第一个 graph 提取 checkpointer（所有 graph 共享同一个 checkpointer）
        first_graph = next(iter(graphs.values()), None)
        self._checkpointer: BaseCheckpointSaver | None = (
            first_graph.checkpointer if first_graph else None  # type: ignore[assignment]
        )
        self._buffer = EventBuffer(ttl_seconds=self._config.event_buffer_ttl)
        self._executor = GraphExecutor(graphs, self._buffer)

    async def start(self) -> None:
        """启动服务"""
        await self._buffer.start()
        logger.info(f"LangGraphService 已启动，加载 {len(self._graphs)} 个 graphs: {list(self._graphs.keys())}")

    async def stop(self) -> None:
        """停止服务"""
        await self._executor.cancel_all()
        await self._buffer.stop()
        logger.info("LangGraphService 已停止")

    # ==================== Graphs ====================

    def get_graph(self, assistant_id: str) -> CompiledStateGraph | None:
        return self._executor.get_graph(assistant_id)

    def list_graphs(self) -> list[str]:
        return self._executor.list_graphs()

    # ==================== 辅助方法 ====================

    async def _get_graph_for_thread(self, thread_id: str) -> CompiledStateGraph | None:
        """根据 thread 的 checkpoint metadata 获取正确的 graph

        LangGraph Platform 会自动将 assistant_id 存入 checkpoint metadata。
        我们在 executor._build_config() 中也实现了同样的行为。
        """
        default_graph = next(iter(self._graphs.values()), None)
        if not self._checkpointer:
            return default_graph

        try:
            config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
            checkpoint_tuple = await self._checkpointer.aget_tuple(config)

            if checkpoint_tuple and checkpoint_tuple.metadata:
                assistant_id = checkpoint_tuple.metadata.get("assistant_id")
                if assistant_id and assistant_id in self._graphs:
                    return self._graphs[assistant_id]

            return default_graph
        except Exception as e:
            logger.warning(f"获取 thread {thread_id} 的 graph 失败: {e}")
            return default_graph

    def _infer_thread_status(self, thread_id: str, state: Any) -> str:
        """从 active_runs 和 state 推断 Thread 状态

        优先级：BUSY > ERROR > INTERRUPTED > IDLE
        - BUSY: 有活跃 run 或 state.next 非空
        - ERROR: tasks 中有 error（LangGraph 自动记录）
        - INTERRUPTED: 有 interrupt 信息
        - IDLE: 其他情况
        """
        # 1. 活跃 run
        if self._executor.has_active_run(thread_id):
            return ThreadStatus.BUSY.value

        # 2. 检查 error（从 tasks 中检测，LangGraph 自动记录）
        if state.tasks and any(getattr(t, "error", None) for t in state.tasks):
            return ThreadStatus.ERROR.value

        # 3. 检查 interrupt（优先使用顶层 interrupts）
        if getattr(state, "interrupts", None) or (
            state.tasks and any(getattr(t, "interrupts", None) for t in state.tasks)
        ):
            return ThreadStatus.INTERRUPTED.value

        # 4. 还有下一个节点待执行
        if state.next:
            return ThreadStatus.BUSY.value

        return ThreadStatus.IDLE.value

    def _serialize_values(self, values: dict[str, Any]) -> dict[str, Any]:
        """递归序列化字典中的 Pydantic 对象"""
        result = {}
        for key, value in values.items():
            if hasattr(value, "model_dump"):
                result[key] = value.model_dump(mode="json")
            elif isinstance(value, dict):
                result[key] = self._serialize_values(value)
            elif isinstance(value, list):
                result[key] = [
                    item.model_dump(mode="json") if hasattr(item, "model_dump") else item
                    for item in value
                ]
            else:
                result[key] = value
        return result

    def _serialize_state_values(self, state_values: Any) -> dict[str, Any]:
        """统一的 state.values 序列化入口"""
        if hasattr(state_values, "model_dump"):
            return state_values.model_dump(mode="json")  # type: ignore
        elif isinstance(state_values, dict):
            return self._serialize_values(state_values)
        return {}

    def _state_to_dict(self, thread_id: str, state: Any) -> dict[str, Any]:
        """将 StateSnapshot 转换为字典

        符合 LangGraph SDK ThreadState 规范：
        - tasks: [{id, name, error, interrupts, ...}]
        - interrupts: 顶级中断列表（兼容）
        """
        all_interrupts: list[dict[str, Any]] = []
        tasks: list[dict[str, Any]] = []
        if state.tasks:
            for t in state.tasks:
                # 构建 task.interrupts
                task_interrupts: list[dict[str, Any]] = []
                if hasattr(t, "interrupts") and t.interrupts:
                    for intr in t.interrupts:
                        interrupt_data = {
                            "value": getattr(intr, "value", intr),
                            "id": getattr(intr, "id", ""),
                        }
                        task_interrupts.append(interrupt_data)
                        all_interrupts.append(interrupt_data)

                # 构建完整的 ThreadTask
                tasks.append({
                    "id": t.id,
                    "name": t.name,
                    "error": getattr(t, "error", None),
                    "interrupts": task_interrupts,
                    "checkpoint": None,
                    "state": None,
                    "result": getattr(t, "result", None),
                })

        interrupts = all_interrupts

        checkpoint_config = state.config.get("configurable", {}) if state.config else {}
        parent_config = (
            state.parent_config.get("configurable", {})
            if state.parent_config
            else None
        )

        values = self._serialize_state_values(state.values or {})

        return {
            "values": values,
            "next": list(state.next) if state.next else [],
            "checkpoint": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_config.get("checkpoint_ns", ""),
                "checkpoint_id": checkpoint_config.get("checkpoint_id"),
                "checkpoint_map": checkpoint_config.get("checkpoint_map"),
            },
            "metadata": state.metadata or {},
            "created_at": getattr(state, "created_at", None),
            "parent_checkpoint": {
                "thread_id": thread_id,
                "checkpoint_ns": parent_config.get("checkpoint_ns", ""),
                "checkpoint_id": parent_config.get("checkpoint_id"),
                "checkpoint_map": parent_config.get("checkpoint_map"),
            }
            if parent_config
            else None,
            "tasks": tasks,
            "interrupts": interrupts,
        }
