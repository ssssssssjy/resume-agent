"""GitHub API 封装（内部使用）

统一的 GitHub API 调用，供 tech_trends 和 repo_analyzer 使用。
"""
import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


def get_github_headers() -> dict:
    """获取 GitHub API headers"""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "ResumeAgent/1.0"
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers


async def github_search(
    query: str,
    language: str | None = None,
    max_results: int = 5,
) -> dict[str, Any]:
    """搜索 GitHub 仓库

    Args:
        query: 搜索关键词
        language: 编程语言过滤（可选）
        max_results: 最大返回结果数

    Returns:
        包含仓库列表的搜索结果
    """
    try:
        url = f"{GITHUB_API_BASE}/search/repositories"
        q = f"{query} language:{language}" if language else query
        params = {
            "q": q,
            "sort": "stars",
            "order": "desc",
            "per_page": max_results
        }

        response = requests.get(url, headers=get_github_headers(), params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        repos = []
        for item in data.get("items", []):
            repos.append({
                "name": item["full_name"],
                "description": item.get("description", ""),
                "stars": item["stargazers_count"],
                "url": item["html_url"],
                "language": item.get("language", ""),
                "topics": item.get("topics", [])[:5],
                "updated_at": item.get("updated_at", ""),
            })

        return {
            "query": query,
            "repos": repos,
            "total_count": data.get("total_count", 0),
        }

    except Exception as e:
        logger.error(f"GitHub 搜索失败: {e}")
        return {"query": query, "repos": [], "error": str(e)}
