"""Pytest 配置"""

import pytest


@pytest.fixture
def sample_resume_content() -> str:
    """示例简历内容"""
    return """
1. 独立设计并实现了异步化的Memory组件：支持长短期记忆管理，采用 Redis 持久化存储

2. 设计并实现了 Agent 调度系统：基于优先级队列实现任务调度，支持并发控制

3. 实现了 Tool 调用框架：支持动态工具注册和执行，集成 OpenAI Function Calling
"""


@pytest.fixture
def sample_target_job() -> str:
    """示例目标职位"""
    return "AI Agent 开发工程师"
