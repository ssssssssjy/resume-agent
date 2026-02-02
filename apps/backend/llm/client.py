"""LLM 客户端封装

提供统一的 OpenAI 兼容接口调用。
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Type, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from config.app_config import config
from .config import get_model_by_type

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

# 全局 OpenAI 客户端
_openai_client: AsyncOpenAI | None = None

# 并发控制
_llm_semaphore: asyncio.Semaphore | None = None
_max_concurrent_llm: int = 50


def init_openai_client():
    """初始化全局 OpenAI 客户端"""
    global _openai_client
    if _openai_client is None:
        import httpx

        http_client = httpx.AsyncClient(
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=50
            ),
            timeout=httpx.Timeout(
                connect=60.0,
                read=300.0,
                write=30.0,
                pool=120.0
            ),
        )
        _openai_client = AsyncOpenAI(
            base_url=config.openai_api_base,
            api_key=config.openai_api_key,
            http_client=http_client,
            max_retries=2
        )
        logger.info("✅ OpenAI 客户端已初始化")


def _get_openai_client() -> AsyncOpenAI:
    """获取全局 OpenAI 客户端"""
    if _openai_client is None:
        raise RuntimeError(
            "OpenAI 客户端未初始化，请先调用 init_openai_client()"
        )
    return _openai_client


def _get_semaphore() -> asyncio.Semaphore:
    """获取并发控制信号量"""
    global _llm_semaphore
    if _llm_semaphore is None:
        _llm_semaphore = asyncio.Semaphore(_max_concurrent_llm)
    return _llm_semaphore


async def llm_request(
    messages: list[dict[str, Any]],
    model: str = "general_model",
    temperature: float = 0.7,
    timeout: int = 300
) -> str | None:
    """发送 LLM 请求，返回文本内容

    Args:
        messages: 消息列表
        model: 模型类型或具体模型名称
        temperature: 温度参数
        timeout: 超时时间（秒）

    Returns:
        模型生成的文本内容
    """
    model = get_model_by_type(model)

    async with _get_semaphore():
        start_time = time.time()
        client = _get_openai_client()

        logger.info(f"🚀 LLM 请求: model={model}, temperature={temperature}")

        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            timeout=timeout
        )

        elapsed_time = time.time() - start_time
        logger.info(f"✅ {model} 响应成功，耗时: {elapsed_time:.2f}秒")

        return resp.choices[0].message.content


async def llm_request_structured(
    messages: list[dict[str, Any]],
    response_format: Type[T],
    model: str = "general_model",
    temperature: float = 0.7,
    timeout: int = 300
) -> T | None:
    """发送结构化 LLM 请求，返回 Pydantic 对象

    Args:
        messages: 消息列表
        response_format: Pydantic 模型类
        model: 模型类型或具体模型名称
        temperature: 温度参数
        timeout: 超时时间（秒）

    Returns:
        Pydantic 对象实例
    """
    import json

    model = get_model_by_type(model)

    async with _get_semaphore():
        start_time = time.time()
        client = _get_openai_client()

        logger.info(f"🚀 结构化请求: model={model}, format={response_format.__name__}")

        # 添加 JSON 输出指令
        system_msg = messages[0] if messages and messages[0].get("role") == "system" else None
        if system_msg:
            system_msg["content"] += "\n\n请以 JSON 格式返回结果。"
        else:
            messages.insert(0, {
                "role": "system",
                "content": "请以 JSON 格式返回结果。"
            })

        resp = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            timeout=timeout
        )

        elapsed_time = time.time() - start_time
        logger.info(f"✅ {model} 结构化响应成功，耗时: {elapsed_time:.2f}秒")

        content = resp.choices[0].message.content
        if not content:
            return None

        # 清理 Markdown 代码块
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # 解析 JSON 并构建 Pydantic 对象
        data = json.loads(content)
        return response_format.model_validate(data)
