"""LLM 模型配置"""

import os

# 默认模型配置
GENERAL_MODEL = os.getenv("GENERAL_MODEL", "gpt-4o")

# 模型类型映射
MODEL_TYPE_MAP = {
    "general_model": GENERAL_MODEL,
    "general": GENERAL_MODEL,
}


def get_model_by_type(model_type: str) -> str:
    """根据模型类型获取实际模型名称

    Args:
        model_type: 模型类型或实际模型名称

    Returns:
        实际模型名称
    """
    return MODEL_TYPE_MAP.get(model_type, model_type)
