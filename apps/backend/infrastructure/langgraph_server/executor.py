"""Graph 执行器 - 负责 LangGraph workflow 的执行"""

from typing import Any, AsyncIterator
from uuid import uuid4
import asyncio
import logging

from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from .buffer import EventBuffer
from .schemas import MultitaskStrategy, RunCreate, RunStatus, SSEEvent, StreamMode
from .types import ActiveRun

logger = logging.getLogger(__name__)

# 默认递归限制
DEFAULT_RECURSION_LIMIT = 25


class GraphExecutor:
    """Graph 执行器

    职责：
    - 执行 LangGraph workflow
    - 管理活跃 Run（内存）
    - 产生 SSE 事件流
    """

    def __init__(
        self,
        graphs: dict[str, CompiledStateGraph],
        buffer: EventBuffer,
    ):
        self._graphs = graphs
        self._buffer = buffer
        self._active_runs: dict[str, ActiveRun] = {}  # thread_id → ActiveRun

    def get_graph(self, assistant_id: str) -> CompiledStateGraph | None:
        return self._graphs.get(assistant_id)

    def list_graphs(self) -> list[str]:
        return list(self._graphs.keys())

    def get_active_run(self, thread_id: str) -> ActiveRun | None:
        return self._active_runs.get(thread_id)

    def has_active_run(self, thread_id: str) -> bool:
        return thread_id in self._active_runs

    async def cancel_all(self) -> None:
        """取消所有活跃 Run"""
        for run in list(self._active_runs.values()):
            run.task.cancel()
        self._active_runs.clear()

    async def cancel_run(self, thread_id: str, run_id: str) -> bool:
        """取消指定 Run"""
        run = self._active_runs.get(thread_id)
        if run and str(run.run_id) == run_id:
            run.task.cancel()
            del self._active_runs[thread_id]
            await self._buffer.put(run_id, SSEEvent(event="end", data={"status": "cancelled"}))
            return True
        return False

    async def stream_run(
        self,
        thread_id: str,
        request: RunCreate,
    ) -> AsyncIterator[SSEEvent]:
        """流式执行 Run"""
        # 处理 multitask_strategy
        strategy = request.multitask_strategy or MultitaskStrategy.REJECT
        if thread_id in self._active_runs:
            existing_run = self._active_runs[thread_id]
            if strategy == MultitaskStrategy.REJECT:
                yield SSEEvent(
                    event="error", data={"message": "Thread already has an active run"}
                )
                return
            elif strategy == MultitaskStrategy.INTERRUPT:
                # 取消当前 Run，启动新 Run
                logger.info(
                    f"multitask_strategy=interrupt: 取消 Run {existing_run.run_id}"
                )
                existing_run.task.cancel()
                del self._active_runs[thread_id]
                await self._buffer.put(
                    str(existing_run.run_id),
                    SSEEvent(event="error", data={"message": "Run interrupted by new run"}),
                )
            elif strategy == MultitaskStrategy.ROLLBACK:
                # 取消当前 Run 并回滚（回滚需要更复杂的 checkpoint 操作，暂简化为 interrupt）
                logger.info(
                    f"multitask_strategy=rollback: 取消 Run {existing_run.run_id}"
                )
                existing_run.task.cancel()
                del self._active_runs[thread_id]
                await self._buffer.put(
                    str(existing_run.run_id),
                    SSEEvent(event="error", data={"message": "Run rolled back by new run"}),
                )
            elif strategy == MultitaskStrategy.ENQUEUE:
                # 排队策略暂不支持，降级为 reject
                yield SSEEvent(
                    event="error",
                    data={"message": "Enqueue strategy not supported, thread has active run"},
                )
                return

        graph = self.get_graph(request.assistant_id)
        if not graph:
            yield SSEEvent(
                event="error", data={"message": f"Graph {request.assistant_id} not found"}
            )
            return

        run_id = uuid4()
        run_id_str = str(run_id)

        # 创建 ActiveRun
        current_task = asyncio.current_task()
        if current_task is None:
            yield SSEEvent(event="error", data={"message": "No current task"})
            return

        active_run = ActiveRun(
            run_id=run_id,
            thread_id=thread_id,
            assistant_id=request.assistant_id,
            status=RunStatus.RUNNING,
            task=current_task,
            metadata=request.metadata or {},
            on_disconnect=request.on_disconnect or "cancel",
        )
        self._active_runs[thread_id] = active_run

        # 是否缓冲事件（用于重连）
        stream_resumable = request.stream_resumable or False

        try:
            # 延迟执行
            if request.after_seconds and request.after_seconds > 0:
                logger.info(f"Run {run_id_str} 延迟 {request.after_seconds} 秒执行")
                await asyncio.sleep(request.after_seconds)

            # 发送 metadata 事件
            metadata_event = SSEEvent(
                event="metadata", data={"run_id": run_id_str, "thread_id": thread_id}
            )
            if stream_resumable:
                await self._buffer.put(run_id_str, metadata_event)
            yield metadata_event

            # 执行 graph
            config = self._build_config(thread_id, request)
            input_data = self._build_input(request)
            stream_mode = self._parse_stream_mode(request.stream_mode)
            interrupt_before, interrupt_after = self._parse_interrupt_config(request)

            async for chunk in graph.astream(
                input_data,
                config=config,
                stream_mode=stream_mode,  # pyright: ignore[reportArgumentType]
                interrupt_before=interrupt_before,
                interrupt_after=interrupt_after,
                subgraphs=request.stream_subgraphs or False,
            ):
                event = self._chunk_to_event(chunk, stream_mode)
                if stream_resumable:
                    await self._buffer.put(run_id_str, event)
                yield event

            # 检查是否中断（仅更新内部状态，不发送额外事件）
            state = await graph.aget_state(config)
            if state and state.next:
                active_run.status = RunStatus.INTERRUPTED
            else:
                active_run.status = RunStatus.SUCCESS

            # 结束事件（data=None 符合 LangGraph SDK 规范）
            end_event = SSEEvent(event="end", data=None)
            if stream_resumable:
                await self._buffer.put(run_id_str, end_event)
            yield end_event

            # Webhook 回调
            if request.webhook:
                await self._send_webhook(
                    request.webhook,
                    run_id_str,
                    thread_id,
                    active_run.status.value,
                )

            # on_completion 处理
            if request.on_completion == "delete":
                # 清理 buffer 中的事件历史
                self._buffer.clear_run(run_id_str)

        except asyncio.CancelledError:
            if active_run.on_disconnect == "continue":
                # on_disconnect='continue'：后台继续执行，不发送错误
                logger.info(
                    f"Run {run_id_str} SSE 断开，on_disconnect='continue'，继续后台执行"
                )
                background_task = asyncio.create_task(
                    self._continue_run_in_background(
                        thread_id=thread_id,
                        run_id_str=run_id_str,
                        graph=graph,
                        config=config,
                        stream_mode=stream_mode,
                        interrupt_before=interrupt_before,
                        interrupt_after=interrupt_after,
                        active_run=active_run,
                        subgraphs=request.stream_subgraphs or False,
                        stream_resumable=stream_resumable,
                        webhook=request.webhook,
                        on_completion=request.on_completion,
                    )
                )
                active_run.task = background_task
                return
            else:
                # on_disconnect='cancel'：发送取消错误
                active_run.status = RunStatus.INTERRUPTED
                error_event = SSEEvent(event="error", data={"message": "Run cancelled"})
                if stream_resumable:
                    await self._buffer.put(run_id_str, error_event)
                yield error_event
        except Exception as e:
            logger.exception(f"Run {run_id_str} 失败")
            active_run.status = RunStatus.ERROR
            error_event = SSEEvent(event="error", data={"message": str(e)})
            await self._buffer.put(run_id_str, error_event)
            yield error_event
        finally:
            # 确保清理 active_run（除非 on_disconnect='continue' 且转为后台执行）
            current_task = asyncio.current_task()
            if active_run.task == current_task and thread_id in self._active_runs:
                del self._active_runs[thread_id]

    async def stream_run_output(
        self,
        thread_id: str,
        run_id: str,
    ) -> AsyncIterator[SSEEvent]:
        """订阅 Run 输出（用于重连）"""
        # 重放历史事件
        for event in self._buffer.get_events(run_id):
            yield event

        # 如果还在执行，订阅新事件
        if self._buffer.is_active(run_id):
            async for event in self._buffer.subscribe(run_id):
                yield event

    async def create_run(
        self,
        thread_id: str,
        request: RunCreate,
    ) -> ActiveRun:
        """创建 Run（后台执行，立即返回）"""
        # 处理 multitask_strategy
        strategy = request.multitask_strategy or MultitaskStrategy.REJECT
        if thread_id in self._active_runs:
            existing_run = self._active_runs[thread_id]
            if strategy == MultitaskStrategy.REJECT:
                raise ValueError("Thread already has an active run")
            elif strategy in (MultitaskStrategy.INTERRUPT, MultitaskStrategy.ROLLBACK):
                logger.info(
                    f"multitask_strategy={strategy.value}: 取消 Run {existing_run.run_id}"
                )
                existing_run.task.cancel()
                del self._active_runs[thread_id]
                await self._buffer.put(
                    str(existing_run.run_id),
                    SSEEvent(event="error", data={"message": f"Run {strategy.value} by new run"}),
                )
            elif strategy == MultitaskStrategy.ENQUEUE:
                raise ValueError("Enqueue strategy not supported, thread has active run")

        graph = self.get_graph(request.assistant_id)
        if not graph:
            raise ValueError(f"Graph {request.assistant_id} not found")

        run_id = uuid4()
        run_id_str = str(run_id)

        # 启动后台任务执行 workflow
        async def _run_wrapper() -> None:
            await self._execute_run_in_background(
                thread_id=thread_id,
                run_id_str=run_id_str,
                request=request,
                active_run=active_run,  # type: ignore[has-type]
            )

        background_task = asyncio.create_task(_run_wrapper())

        # 创建 ActiveRun
        active_run = ActiveRun(
            run_id=run_id,
            thread_id=thread_id,
            assistant_id=request.assistant_id,
            status=RunStatus.PENDING,
            task=background_task,
            metadata=request.metadata or {},
            on_disconnect=request.on_disconnect or "continue",  # 后台运行默认 continue
        )
        self._active_runs[thread_id] = active_run

        return active_run

    async def _execute_run_in_background(
        self,
        thread_id: str,
        run_id_str: str,
        request: RunCreate,
        active_run: ActiveRun,
    ) -> None:
        """在后台执行 workflow（create_run 调用）"""
        graph = self.get_graph(request.assistant_id)
        if not graph:
            return

        stream_resumable = request.stream_resumable or False

        try:
            # 延迟执行
            if request.after_seconds and request.after_seconds > 0:
                logger.info(f"Run {run_id_str} 延迟 {request.after_seconds} 秒执行")
                await asyncio.sleep(request.after_seconds)

            # 更新状态为 RUNNING
            active_run.status = RunStatus.RUNNING

            # 发送 metadata 事件
            metadata_event = SSEEvent(
                event="metadata", data={"run_id": run_id_str, "thread_id": thread_id}
            )
            if stream_resumable:
                await self._buffer.put(run_id_str, metadata_event)

            # 执行 graph
            config = self._build_config(thread_id, request)
            input_data = self._build_input(request)
            stream_mode = self._parse_stream_mode(request.stream_mode)
            interrupt_before, interrupt_after = self._parse_interrupt_config(request)

            async for chunk in graph.astream(
                input_data,
                config=config,
                stream_mode=stream_mode,  # pyright: ignore[reportArgumentType]
                interrupt_before=interrupt_before,
                interrupt_after=interrupt_after,
                subgraphs=request.stream_subgraphs or False,
            ):
                event = self._chunk_to_event(chunk, stream_mode)
                if stream_resumable:
                    await self._buffer.put(run_id_str, event)

            # 检查是否中断
            state = await graph.aget_state(config)
            if state and state.next:
                active_run.status = RunStatus.INTERRUPTED
            else:
                active_run.status = RunStatus.SUCCESS

            # 发送结束事件
            end_event = SSEEvent(event="end", data=None)
            if stream_resumable:
                await self._buffer.put(run_id_str, end_event)

            # Webhook 回调
            if request.webhook:
                await self._send_webhook(
                    request.webhook,
                    run_id_str,
                    thread_id,
                    active_run.status.value,
                )

            # on_completion 处理
            if request.on_completion == "delete":
                self._buffer.clear_run(run_id_str)

        except asyncio.CancelledError:
            active_run.status = RunStatus.INTERRUPTED
            error_event = SSEEvent(event="error", data={"message": "Run cancelled"})
            if stream_resumable:
                await self._buffer.put(run_id_str, error_event)
        except Exception as e:
            logger.exception(f"后台 Run {run_id_str} 失败")
            active_run.status = RunStatus.ERROR
            error_event = SSEEvent(event="error", data={"message": str(e)})
            if stream_resumable:
                await self._buffer.put(run_id_str, error_event)
        finally:
            if thread_id in self._active_runs:
                del self._active_runs[thread_id]

    def _build_config(self, thread_id: str, request: RunCreate) -> RunnableConfig:
        config: RunnableConfig = {
            "configurable": {"thread_id": thread_id},
            # 将 assistant_id 写入 metadata，供后续 get_thread/get_thread_state 使用
            "metadata": {"assistant_id": request.assistant_id},
        }

        # 支持从指定 checkpoint 恢复（用于错误重试或回退）
        if request.checkpoint_id:
            config["configurable"]["checkpoint_id"] = request.checkpoint_id
        if request.checkpoint:
            # checkpoint 对象形式：{thread_id, checkpoint_ns, checkpoint_id}
            if "checkpoint_id" in request.checkpoint:
                config["configurable"]["checkpoint_id"] = request.checkpoint["checkpoint_id"]
            if "checkpoint_ns" in request.checkpoint:
                config["configurable"]["checkpoint_ns"] = request.checkpoint["checkpoint_ns"]

        # 设置默认 recursion_limit
        if request.config:
            if request.config.recursion_limit:
                config["recursion_limit"] = request.config.recursion_limit
            else:
                config["recursion_limit"] = DEFAULT_RECURSION_LIMIT
            if request.config.tags:
                config["tags"] = request.config.tags
            if request.config.configurable:
                config["configurable"].update(request.config.configurable)
        else:
            config["recursion_limit"] = DEFAULT_RECURSION_LIMIT

        return config

    def _build_input(self, request: RunCreate) -> Any:
        """构建 graph 输入

        处理 Command 的三种操作：
        - resume: 恢复中断的 workflow
        - goto: 跳转到指定节点
        - update: 更新状态
        """
        if request.command:
            cmd = request.command
            # 构建 Command 参数
            cmd_kwargs: dict[str, Any] = {}

            if cmd.resume is not None:
                cmd_kwargs["resume"] = cmd.resume

            if cmd.goto is not None:
                cmd_kwargs["goto"] = cmd.goto

            if cmd.update is not None:
                cmd_kwargs["update"] = cmd.update

            if cmd_kwargs:
                return Command(**cmd_kwargs)

        return request.input

    def _parse_stream_mode(
        self, mode: StreamMode | list[StreamMode] | None
    ) -> str | list[str]:
        if mode is None:
            return "values"
        if isinstance(mode, list):
            return [m.value for m in mode] if len(mode) > 1 else mode[0].value if mode else "values"
        return mode.value

    def _parse_interrupt_config(
        self, request: RunCreate
    ) -> tuple[list[str] | None, list[str] | None]:
        """解析 interrupt 配置"""
        before: list[str] | None = None
        if request.interrupt_before:
            if isinstance(request.interrupt_before, str):
                before = [request.interrupt_before]
            else:
                before = list(request.interrupt_before)

        after: list[str] | None = None
        if request.interrupt_after:
            if isinstance(request.interrupt_after, str):
                after = [request.interrupt_after]
            else:
                after = list(request.interrupt_after)

        return before, after

    def _chunk_to_event(self, chunk: Any, stream_mode: str | list[str]) -> SSEEvent:
        """将 LangGraph chunk 转换为 SSE 事件。

        chunk 格式说明：
        - 单 stream_mode, 无 subgraphs: data
        - 单 stream_mode, 有 subgraphs: (namespace, data)
        - 多 stream_mode, 无 subgraphs: (mode, data)
        - 多 stream_mode, 有 subgraphs: (namespace, mode, data)

        LangGraph Platform SSE 事件名称格式：
        - 无 subgraphs: event: {mode}
        - 有 subgraphs: event: {mode}|{namespace_path}
          例如: event: messages|respond:5ecec403-30a5-ebd1-8c53-4745946ec2df
        """
        if isinstance(chunk, tuple):
            if len(chunk) == 2:
                # (mode, data) 或 (namespace, data)
                first, second = chunk
                if isinstance(first, tuple):
                    # (namespace, data) - subgraphs 单模式
                    namespace, data = chunk
                    mode = stream_mode if isinstance(stream_mode, str) else "values"
                    event_name = self._format_event_name(mode, namespace)
                    return SSEEvent(event=event_name, data=data)
                else:
                    # (mode, data) - 多模式无 subgraphs
                    mode, data = chunk
                    return SSEEvent(event=mode, data=data)
            elif len(chunk) == 3:
                # (namespace, mode, data) - 多模式有 subgraphs
                namespace, mode, data = chunk
                event_name = self._format_event_name(mode, namespace)
                return SSEEvent(event=event_name, data=data)
        # 单模式无 subgraphs: 直接返回 data
        return SSEEvent(
            event=stream_mode if isinstance(stream_mode, str) else "values", data=chunk
        )

    def _format_event_name(self, mode: str, namespace: tuple[str, ...]) -> str:
        """格式化 SSE 事件名称（含 namespace）。

        LangGraph Platform 格式：
        - 根 graph: event: {mode}
        - 子 graph: event: {mode}|{namespace_path}

        namespace 是一个 tuple，如 ("parent_node:<task_id>", "child_node:<task_id>")
        需要用 "|" 连接成路径。
        """
        if not namespace:
            return mode
        # 将 namespace tuple 转换为 | 分隔的路径
        namespace_path = "|".join(namespace)
        return f"{mode}|{namespace_path}"

    async def _send_webhook(
        self,
        webhook_url: str,
        run_id: str,
        thread_id: str,
        status: str,
    ) -> None:
        """发送 Webhook 回调"""
        import aiohttp

        try:
            payload = {
                "run_id": run_id,
                "thread_id": thread_id,
                "status": status,
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status >= 400:
                        logger.warning(
                            f"Webhook 回调失败: {webhook_url}, status={response.status}"
                        )
                    else:
                        logger.info(f"Webhook 回调成功: {webhook_url}")
        except Exception as e:
            logger.warning(f"Webhook 回调异常: {webhook_url}, error={e}")

    async def _continue_run_in_background(
        self,
        thread_id: str,
        run_id_str: str,
        graph: CompiledStateGraph,
        config: RunnableConfig,
        stream_mode: str | list[str],
        interrupt_before: list[str] | None,
        interrupt_after: list[str] | None,
        active_run: ActiveRun,
        subgraphs: bool = False,
        stream_resumable: bool = False,
        webhook: str | None = None,
        on_completion: str | None = None,
    ) -> None:
        """在后台继续执行 workflow（SSE 断开后）

        当 on_disconnect='continue' 时，SSE 连接断开后调用此方法继续执行。
        事件会被写入 buffer，供客户端重连后获取。
        """
        try:
            async for chunk in graph.astream(
                None,  # 从 checkpoint 继续
                config=config,
                stream_mode=stream_mode,  # pyright: ignore[reportArgumentType]
                interrupt_before=interrupt_before,
                interrupt_after=interrupt_after,
                subgraphs=subgraphs,
            ):
                event = self._chunk_to_event(chunk, stream_mode)
                if stream_resumable:
                    await self._buffer.put(run_id_str, event)
                # 不 yield，因为没有 SSE 连接

            # 检查是否中断
            state = await graph.aget_state(config)
            if state and state.next:
                active_run.status = RunStatus.INTERRUPTED
            else:
                active_run.status = RunStatus.SUCCESS

            # 发送结束事件
            end_event = SSEEvent(event="end", data=None)
            if stream_resumable:
                await self._buffer.put(run_id_str, end_event)

            # Webhook 回调
            if webhook:
                await self._send_webhook(
                    webhook,
                    run_id_str,
                    thread_id,
                    active_run.status.value,
                )

            # on_completion 处理
            if on_completion == "delete":
                self._buffer.clear_run(run_id_str)

        except Exception as e:
            logger.exception(f"后台 Run {run_id_str} 失败")
            active_run.status = RunStatus.ERROR
            error_event = SSEEvent(event="error", data={"message": str(e)})
            if stream_resumable:
                await self._buffer.put(run_id_str, error_event)
        finally:
            if thread_id in self._active_runs:
                del self._active_runs[thread_id]
