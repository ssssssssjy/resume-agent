"""LangGraph Platform 兼容的 API Schemas

参考: https://langchain-ai.github.io/langgraph/cloud/reference/api/api_ref.html
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field


# ==================== Enums ====================


class RunStatus(str, Enum):
    """Run 状态"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    INTERRUPTED = "interrupted"


class ThreadStatus(str, Enum):
    """Thread 状态"""

    IDLE = "idle"
    BUSY = "busy"
    INTERRUPTED = "interrupted"
    ERROR = "error"


class StreamMode(str, Enum):
    """流式输出模式

    参考 LangGraph Platform SDK:
    https://github.com/langchain-ai/langgraph/blob/main/libs/sdk-py/langgraph_sdk/schema.py
    """

    VALUES = "values"  # 每步后发送完整状态值
    MESSAGES = "messages"  # 完整消息流
    UPDATES = "updates"  # 每步后只发送节点名和更新内容
    EVENTS = "events"  # 执行期间的事件
    DEBUG = "debug"  # 详细调试信息
    CUSTOM = "custom"  # 自定义事件（通过 StreamWriter）
    TASKS = "tasks"  # 任务开始/结束事件
    CHECKPOINTS = "checkpoints"  # checkpoint 创建事件
    MESSAGES_TUPLE = "messages-tuple"  # 流式 LLM token，格式为 (message_chunk, metadata)


class MultitaskStrategy(str, Enum):
    """多任务策略"""

    REJECT = "reject"
    ROLLBACK = "rollback"
    INTERRUPT = "interrupt"
    ENQUEUE = "enqueue"


# ==================== Thread Schemas ====================


class ThreadCreate(BaseModel):
    """创建 Thread 请求"""

    thread_id: Optional[UUID] = Field(None, description="可选的自定义 Thread ID")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="元数据"
    )
    if_exists: Optional[Literal["do_nothing", "raise"]] = Field(
        "do_nothing", description="如果 thread_id 已存在时的处理方式"
    )


class Interrupt(BaseModel):
    """中断信息"""

    value: Any = Field(..., description="中断值")
    when: str = Field("during", description="中断时机")
    resumable: bool = Field(True, description="是否可恢复")
    ns: Optional[List[str]] = Field(None, description="命名空间")


class Thread(BaseModel):
    """Thread 响应"""

    thread_id: UUID = Field(..., description="Thread ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    status: ThreadStatus = Field(ThreadStatus.IDLE, description="状态")
    values: Optional[Dict[str, Any]] = Field(None, description="当前状态值")
    interrupts: Dict[str, List[Interrupt]] = Field(
        default_factory=dict, description="中断信息（按任务 ID 分组）"
    )


class ThreadPatch(BaseModel):
    """更新 Thread 请求"""

    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")


# ==================== Thread State Schemas ====================


class ThreadCheckpoint(BaseModel):
    """Checkpoint 信息"""

    thread_id: Optional[str] = Field(None, description="Thread ID")
    checkpoint_ns: Optional[str] = Field("", description="Checkpoint 命名空间")
    checkpoint_id: Optional[str] = Field(None, description="Checkpoint ID")


class ThreadState(BaseModel):
    """Thread 状态"""

    values: Dict[str, Any] = Field(default_factory=dict, description="状态值")
    next: List[str] = Field(default_factory=list, description="下一个待执行的节点")
    checkpoint: Optional[ThreadCheckpoint] = Field(None, description="Checkpoint 信息")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")
    created_at: Optional[datetime] = Field(None, description="创建时间")
    parent_checkpoint: Optional[ThreadCheckpoint] = Field(
        None, description="父 Checkpoint"
    )
    tasks: List[Dict[str, Any]] = Field(default_factory=list, description="待处理任务")
    interrupts: List[Dict[str, Any]] = Field(
        default_factory=list, description="中断信息列表"
    )


class ThreadStateUpdate(BaseModel):
    """更新 Thread 状态请求 (用于 interrupt resume)"""

    values: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = Field(
        None, description="要更新的状态值"
    )
    checkpoint_id: Optional[str] = Field(None, description="Checkpoint ID")
    checkpoint: Optional[Dict[str, Any]] = Field(None, description="Checkpoint 配置")
    as_node: Optional[str] = Field(None, description="作为哪个节点更新")
    checkpoint_ns: Optional[str] = Field(None, description="Checkpoint 命名空间")


class ThreadStateUpdateResponse(BaseModel):
    """更新 Thread 状态响应"""

    checkpoint: ThreadCheckpoint = Field(..., description="新的 Checkpoint 信息")


class ThreadHistoryRequest(BaseModel):
    """获取 Thread 历史请求"""

    limit: Optional[int] = Field(10, ge=1, le=1000, description="返回数量限制")
    before: Optional[str] = Field(None, description="在此 checkpoint_id 之前")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据过滤")
    checkpoint: Optional[Dict[str, Any]] = Field(None, description="Checkpoint 配置")
    checkpoint_ns: Optional[str] = Field(None, description="Checkpoint 命名空间")


class ThreadSearchRequest(BaseModel):
    """搜索 Thread 请求"""

    metadata: Optional[Dict[str, Any]] = Field(None, description="按 metadata 过滤")
    values: Optional[Dict[str, Any]] = Field(None, description="按 state values 过滤")
    status: Optional[ThreadStatus] = Field(None, description="按状态过滤")
    limit: int = Field(10, ge=1, le=100, description="返回数量限制")
    offset: int = Field(0, ge=0, description="分页偏移")


class AssistantSearchRequest(BaseModel):
    """搜索 Assistant 请求"""

    metadata: Optional[Dict[str, Any]] = Field(None, description="按 metadata 精确匹配过滤")
    graph_id: Optional[str] = Field(None, description="按 graph_id 过滤")
    limit: int = Field(10, ge=1, le=100, description="返回数量限制")
    offset: int = Field(0, ge=0, description="分页偏移")


# ==================== Run Schemas ====================


class Command(BaseModel):
    """Command 用于 interrupt resume"""

    resume: Optional[Any] = Field(None, description="Resume 值")
    goto: Optional[Union[str, List[str]]] = Field(None, description="跳转到指定节点")
    update: Optional[Dict[str, Any]] = Field(None, description="更新状态")


class RunConfig(BaseModel):
    """Run 配置"""

    tags: Optional[List[str]] = Field(None, description="标签")
    recursion_limit: Optional[int] = Field(None, description="递归限制")
    configurable: Optional[Dict[str, Any]] = Field(None, description="可配置项")


class RunCreate(BaseModel):
    """创建 Run 请求"""

    assistant_id: str = Field(..., description="Assistant ID 或 Graph 名称")
    input: Optional[Any] = Field(None, description="输入数据")
    command: Optional[Command] = Field(
        None, description="Command (用于 interrupt resume)"
    )
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")
    config: Optional[RunConfig] = Field(None, description="配置")
    checkpoint: Optional[Dict[str, Any]] = Field(
        None, description="从指定 Checkpoint 恢复"
    )
    checkpoint_id: Optional[str] = Field(None, description="Checkpoint ID")
    webhook: Optional[str] = Field(None, description="Webhook URL")
    interrupt_before: Optional[Union[str, List[str]]] = Field(
        None, description="在哪些节点前中断"
    )
    interrupt_after: Optional[Union[str, List[str]]] = Field(
        None, description="在哪些节点后中断"
    )
    stream_mode: Optional[Union[StreamMode, List[StreamMode]]] = Field(
        [StreamMode.VALUES], description="流式输出模式"
    )
    stream_subgraphs: Optional[bool] = Field(False, description="是否流式输出子图")
    stream_resumable: Optional[bool] = Field(
        False, description="是否保留事件历史供重连使用"
    )
    multitask_strategy: Optional[MultitaskStrategy] = Field(
        MultitaskStrategy.ENQUEUE, description="多任务策略"
    )
    if_not_exists: Optional[Literal["create", "reject"]] = Field(
        "reject", description="Thread 不存在时的处理方式"
    )
    on_disconnect: Optional[Literal["cancel", "continue"]] = Field(
        "cancel", description="断开连接时的处理方式"
    )
    on_completion: Optional[Literal["delete", "keep"]] = Field(
        "keep", description="Run 完成后的处理方式"
    )
    after_seconds: Optional[int] = Field(
        None, description="延迟执行秒数"
    )


class Run(BaseModel):
    """Run 响应"""

    run_id: UUID = Field(..., description="Run ID")
    thread_id: UUID = Field(..., description="Thread ID")
    assistant_id: str = Field(..., description="Assistant ID")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    status: RunStatus = Field(..., description="状态")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")
    kwargs: Optional[Dict[str, Any]] = Field(None, description="运行参数")
    multitask_strategy: Optional[str] = Field(None, description="多任务策略")
    output: Optional[Dict[str, Any]] = Field(None, description="运行输出")
    error_message: Optional[str] = Field(None, description="错误信息")


class RunWaitResponse(BaseModel):
    """等待 Run 完成的响应"""

    run_id: str = Field(..., description="Run ID")
    thread_id: str = Field(..., description="Thread ID")
    status: RunStatus = Field(..., description="最终状态")
    output: Optional[Dict[str, Any]] = Field(None, description="运行输出")


# ==================== Error Schemas ====================


class ErrorResponse(BaseModel):
    """错误响应"""

    detail: str = Field(..., description="错误详情")
    status_code: Optional[int] = Field(None, description="HTTP 状态码")


# ==================== SSE Event Schemas ====================


class SSEEvent(BaseModel):
    """SSE 事件"""

    event: str = Field(..., description="事件类型")
    data: Any = Field(..., description="事件数据")
