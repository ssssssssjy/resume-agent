"""Thread State 服务 - Thread State 操作"""

from typing import Any
from uuid import uuid4
import logging

from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)


class StateMixin:
    """Thread State 管理 Mixin

    提供 Thread State 的读取、更新和历史查询功能。
    需要与 BaseService 一起使用。
    """

    # Type hints for BaseService attributes
    _executor: Any
    _graphs: Any

    async def _get_graph_for_thread(self, thread_id: str) -> Any:
        ...

    def _state_to_dict(self, thread_id: str, state: Any) -> dict[str, Any]:
        ...

    def _serialize_state_values(self, state_values: Any) -> dict[str, Any]:
        ...

    def _serialize_subgraph_state(self, thread_id: str, state: Any) -> dict[str, Any] | None:
        """递归序列化子图状态（用于 subgraphs=True 时）"""
        if state is None:
            return None

        # 序列化子图的 values
        values = self._serialize_state_values(state.values or {})

        # 递归处理子图的 tasks
        tasks: list[dict[str, Any]] = []
        if hasattr(state, "tasks") and state.tasks:
            for t in state.tasks:
                task_interrupts: list[dict[str, Any]] = []
                if hasattr(t, "interrupts") and t.interrupts:
                    for intr in t.interrupts:
                        task_interrupts.append({
                            "value": getattr(intr, "value", intr),
                            "id": getattr(intr, "id", ""),
                        })

                # 递归序列化嵌套的子图状态
                nested_state = None
                if hasattr(t, "state") and t.state is not None:
                    nested_state = self._serialize_subgraph_state(thread_id, t.state)

                tasks.append({
                    "id": t.id,
                    "name": t.name,
                    "error": getattr(t, "error", None),
                    "interrupts": task_interrupts,
                    "checkpoint": None,
                    "state": nested_state,
                    "result": getattr(t, "result", None),
                })

        # 提取 checkpoint 配置
        checkpoint_config = state.config.get("configurable", {}) if state.config else {}

        return {
            "values": values,
            "next": list(state.next) if state.next else [],
            "checkpoint": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_config.get("checkpoint_ns", ""),
                "checkpoint_id": checkpoint_config.get("checkpoint_id"),
                "checkpoint_map": checkpoint_config.get("checkpoint_map"),
            }
            if state.config
            else None,
            "tasks": tasks,
        }

    async def get_thread_state(
        self, thread_id: str, subgraphs: bool = False
    ) -> dict[str, Any] | None:
        """获取 Thread 状态

        Args:
            thread_id: Thread ID
            subgraphs: 是否包含子图状态。默认 False。
                      设为 True 时，会获取子图的嵌套状态，
                      返回的 tasks 中每个 task 会包含 state 字段。

        Returns:
            Thread 状态字典，包含 values, next, checkpoint, tasks 等字段
        """
        graph = await self._get_graph_for_thread(thread_id)
        if not graph:
            return None

        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}

        try:
            state = await graph.aget_state(config, subgraphs=subgraphs)
        except Exception as e:
            logger.warning(f"获取 Thread 状态失败: {e}")
            return None

        if not state:
            return None

        # 构建 tasks（符合 SDK ThreadTask 标准）
        # ThreadTask: {id, name, error, interrupts, checkpoint, state, result}
        # Interrupt: {value, id}
        tasks: list[dict[str, Any]] = []
        all_interrupts: list[dict[str, Any]] = []  # 顶级 interrupts（兼容）

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

                # 处理子图状态（仅当 subgraphs=True 时有值）
                task_state = None
                if subgraphs and hasattr(t, "state") and t.state is not None:
                    task_state = self._serialize_subgraph_state(thread_id, t.state)

                # 构建完整的 ThreadTask
                tasks.append({
                    "id": t.id,
                    "name": t.name,
                    "error": getattr(t, "error", None),
                    "interrupts": task_interrupts,
                    "checkpoint": None,  # 简化：不返回 task 级 checkpoint
                    "state": task_state,  # 子图状态（subgraphs=True 时有值）
                    "result": getattr(t, "result", None),
                })

        interrupts = all_interrupts  # 顶级 interrupts 保持兼容

        values = self._serialize_state_values(state.values or {})

        # 提取 checkpoint 配置
        checkpoint_config = state.config.get("configurable", {}) if state.config else {}
        parent_config = (
            state.parent_config.get("configurable", {})
            if getattr(state, "parent_config", None)
            else None
        )

        return {
            "values": values,
            "next": list(state.next) if state.next else [],
            "checkpoint": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_config.get("checkpoint_ns", ""),
                "checkpoint_id": checkpoint_config.get("checkpoint_id"),
                "checkpoint_map": checkpoint_config.get("checkpoint_map"),
            }
            if state.config
            else None,
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

    async def update_thread_state(
        self,
        thread_id: str,
        values: dict[str, Any] | list[dict[str, Any]] | None = None,
        as_node: str | None = None,
        checkpoint_id: str | None = None,
        checkpoint_ns: str | None = None,
    ) -> dict[str, Any]:
        """更新 Thread 状态"""
        graph = await self._get_graph_for_thread(thread_id)
        if not graph:
            raise ValueError("No graph available")

        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        if checkpoint_id:
            config["configurable"]["checkpoint_id"] = checkpoint_id
        if checkpoint_ns:
            config["configurable"]["checkpoint_ns"] = checkpoint_ns

        await graph.aupdate_state(config, values or {}, as_node=as_node)

        # 获取更新后的状态以返回正确的 checkpoint_id
        new_state = await graph.aget_state(config)
        new_checkpoint_id = (
            new_state.config.get("configurable", {}).get("checkpoint_id")
            if new_state and new_state.config
            else str(uuid4())
        )

        return {
            "checkpoint": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns or "",
                "checkpoint_id": new_checkpoint_id,
            }
        }

    async def get_thread_state_at_checkpoint(
        self,
        thread_id: str,
        checkpoint_id: str,
        checkpoint_ns: str | None = None,
    ) -> dict[str, Any] | None:
        """获取指定 Checkpoint 的 Thread 状态"""
        graph = await self._get_graph_for_thread(thread_id)
        if not graph:
            return None

        config: RunnableConfig = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
            }
        }
        if checkpoint_ns:
            config["configurable"]["checkpoint_ns"] = checkpoint_ns

        try:
            state = await graph.aget_state(config)
        except Exception as e:
            logger.warning(f"获取 Checkpoint 状态失败: {e}")
            return None

        if not state:
            return None

        return self._state_to_dict(thread_id, state)

    async def get_thread_history(
        self,
        thread_id: str,
        limit: int = 10,
        before: str | None = None,
        checkpoint_ns: str | None = None,
    ) -> list[dict[str, Any]]:
        """获取 Thread 的 Checkpoint 历史"""
        graph = await self._get_graph_for_thread(thread_id)
        if not graph:
            return []

        config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
        if before:
            config["configurable"]["checkpoint_id"] = before
        if checkpoint_ns:
            config["configurable"]["checkpoint_ns"] = checkpoint_ns

        history: list[dict[str, Any]] = []
        try:
            count = 0
            async for state in graph.aget_state_history(config):
                if count >= limit:
                    break
                history.append(self._state_to_dict(thread_id, state))
                count += 1
        except Exception as e:
            logger.warning(f"获取历史失败: {e}")

        return history
