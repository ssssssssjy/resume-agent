"""LangGraph Server 配置"""

from dataclasses import dataclass


@dataclass
class LangGraphServerConfig:
    """LangGraph Server 配置

    注意：Checkpointer 配置已移至 config/langgraph_config.py，
    在 graph 编译时绑定，不再由 LangGraphServer 管理。

    Attributes:
        event_buffer_ttl: 事件缓冲区 TTL（秒）
        sse_ping_interval: SSE ping 间隔（秒）
    """

    # 事件缓冲配置
    event_buffer_ttl: int = 3600  # 事件保留时间（秒）

    # SSE 配置
    sse_ping_interval: int = 30
