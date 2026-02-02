"""简历增强 Agent 的状态定义

参考 survey_agent 的 base_state.py 设计，
定义简历增强流程中的状态结构。
"""
import operator
from typing import Annotated, Any

from pydantic import BaseModel, Field
from langgraph.graph import MessagesState


class TechPoint(BaseModel):
    """技术点"""
    index: int
    title: str
    content: str
    technologies: list[str] = Field(default_factory=list)
    business_context: str = ""
    search_keywords: list[str] = Field(default_factory=list)


class OpenSourceRef(BaseModel):
    """开源项目参考"""
    name: str
    stars: int = 0
    description: str = ""
    url: str = ""
    relevance: str = ""


class TrendingTech(BaseModel):
    """趋势技术"""
    tech: str
    repo: str = ""
    url: str = ""
    stars: int = 0
    description: str = ""


class SearchResult(BaseModel):
    """搜索结果"""
    examples: list[dict] = Field(default_factory=list)
    github_trending: list[TrendingTech] = Field(default_factory=list)
    reddit_posts: list[dict] = Field(default_factory=list)
    huggingface_models: list[dict] = Field(default_factory=list)
    opensource_refs: list[OpenSourceRef] = Field(default_factory=list)
    business_context: str = ""


class EnhancementResult(BaseModel):
    """增强结果"""
    original_title: str
    original_content: str
    ai_suggestion: str = ""
    tech_highlights: list[str] = Field(default_factory=list)
    interview_tips: list[str] = Field(default_factory=list)
    industry_comparison: str = ""


class ResumeEnhancerState(MessagesState):
    """简历增强 Agent 状态

    继承自 MessagesState，支持消息历史追踪。

    Attributes:
        resume_content: 原始简历内容
        target_job: 目标职位
        language: 编程语言 (用于搜索代码示例)
        tech_points: 解析出的技术点列表
        current_point_index: 当前处理的技术点索引
        search_results: 搜索结果 (按技术点索引存储)
        enhancement_results: 增强结果 (按技术点索引存储)
        final_report: 最终报告
    """
    # 输入
    resume_content: str = ""
    target_job: str = "高级 AI 应用开发工程师"
    language: str = "python"

    # 中间状态
    tech_points: list[TechPoint] = Field(default_factory=list)
    current_point_index: int = 0
    search_results: dict[int, SearchResult] = Field(default_factory=dict)
    enhancement_results: dict[int, EnhancementResult] = Field(default_factory=dict)

    # 输出
    final_report: str = ""

    # 配置 (从 runtime config 传入)
    workspace_id: int | None = None
