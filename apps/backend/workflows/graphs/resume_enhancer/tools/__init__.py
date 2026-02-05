"""简历增强工具

对外暴露的工具会注册到 Agent，供 LLM 调用。
"""

from .search_similar_projects import search_similar_projects
from .search_tech_articles import search_tech_articles
from .analyze_github_repo import analyze_github_repo

__all__ = [
    # 相似项目搜索（基于简历项目描述和技术栈搜索 GitHub 相似项目）
    "search_similar_projects",
    # 技术文章搜索（DEV.to/掘金/InfoQ/Reddit/HuggingFace）
    "search_tech_articles",
    # GitHub 仓库深度分析
    "analyze_github_repo",
]
