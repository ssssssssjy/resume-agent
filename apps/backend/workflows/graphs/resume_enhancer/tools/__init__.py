"""简历增强工具"""

from .github_search import github_search, search_opensource_projects
from .trend_search import search_trends

__all__ = [
    "github_search",
    "search_opensource_projects",
    "search_trends",
]
