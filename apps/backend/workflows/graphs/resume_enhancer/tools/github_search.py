"""GitHub 搜索工具

用于搜索 GitHub 上的代码示例和开源项目。
"""
import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


def _get_headers() -> dict:
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
    language: str = "python",
    max_results: int = 5,
) -> dict[str, Any]:
    """搜索 GitHub 仓库

    根据关键词搜索相关的 GitHub 仓库，获取技术趋势和代码示例。

    Args:
        query: 搜索关键词 (如 "AI Agent memory", "LangGraph state")
        language: 编程语言 (如 "python", "java")
        max_results: 最大返回结果数

    Returns:
        包含仓库列表的搜索结果
    """
    try:
        url = f"{GITHUB_API_BASE}/search/repositories"
        params = {
            "q": f"{query} language:{language}",
            "sort": "stars",
            "order": "desc",
            "per_page": max_results
        }

        response = requests.get(url, headers=_get_headers(), params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        repos = []
        for item in data.get("items", []):
            repos.append({
                "name": item["full_name"],
                "description": item.get("description", "No description"),
                "stars": item["stargazers_count"],
                "url": item["html_url"],
                "language": item.get("language", "Unknown"),
                "topics": item.get("topics", [])[:5],
            })

        return {
            "query": query,
            "repos": repos,
            "total_count": data.get("total_count", 0),
        }

    except Exception as e:
        logger.error(f"GitHub 搜索失败: {e}")
        return {"query": query, "repos": [], "error": str(e)}


async def search_opensource_projects(
    tech_keywords: list[str],
    context: str = "",
) -> list[dict[str, Any]]:
    """搜索相关开源项目

    根据技术关键词搜索业界标杆开源项目。

    Args:
        tech_keywords: 技术关键词列表 (如 ["memory", "agent", "state"])
        context: 业务上下文

    Returns:
        开源项目列表
    """
    # 预设的高星开源项目映射
    TECH_TO_PROJECTS = {
        "memory": ["mem0ai/mem0", "MemoriLabs/Memori", "memvid/memvid"],
        "内存": ["mem0ai/mem0", "MemoriLabs/Memori"],
        "记忆": ["mem0ai/mem0", "MemoriLabs/Memori"],
        "agent": ["langchain-ai/langgraph", "microsoft/autogen", "crewAIInc/crewAI"],
        "langgraph": ["langchain-ai/langgraph"],
        "state": ["langchain-ai/langgraph", "facebookresearch/hydra"],
        "状态": ["langchain-ai/langgraph"],
        "async": ["aio-libs/aiohttp", "encode/starlette"],
        "异步": ["aio-libs/aiohttp", "encode/starlette"],
        "crud": ["fastapi/fastapi", "tiangolo/sqlmodel"],
        "scheduling": ["celery/celery", "rq/rq"],
        "调度": ["celery/celery", "prefecthq/prefect"],
        "决策": ["langchain-ai/langgraph", "microsoft/autogen"],
        "planning": ["langchain-ai/langgraph", "SWE-agent/SWE-agent"],
        "规划": ["langchain-ai/langgraph", "microsoft/autogen"],
    }

    projects = []
    searched_repos = set()

    for keyword in tech_keywords:
        keyword_lower = keyword.lower()
        for key, repo_list in TECH_TO_PROJECTS.items():
            if key in keyword_lower:
                for repo in repo_list:
                    if repo not in searched_repos:
                        searched_repos.add(repo)
                        try:
                            # 获取仓库详情
                            url = f"{GITHUB_API_BASE}/repos/{repo}"
                            response = requests.get(url, headers=_get_headers(), timeout=10)
                            if response.status_code == 200:
                                data = response.json()
                                projects.append({
                                    "name": data["full_name"],
                                    "stars": data["stargazers_count"],
                                    "description": data.get("description", ""),
                                    "url": data["html_url"],
                                    "relevance": key,
                                })
                        except Exception as e:
                            logger.warning(f"获取仓库 {repo} 失败: {e}")

                        if len(projects) >= 6:
                            return projects

    return projects
