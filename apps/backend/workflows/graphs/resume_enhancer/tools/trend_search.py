"""趋势搜索工具

整合 GitHub、HuggingFace、Reddit 等平台的趋势数据。
"""
import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)


async def search_trends(
    tech_keywords: list[str],
    business_context: str = "",
) -> dict[str, Any]:
    """搜索技术趋势

    从多个平台搜索与技术点相关的趋势数据。

    Args:
        tech_keywords: 技术关键词列表
        business_context: 业务场景

    Returns:
        包含各平台趋势数据的结果
    """
    results = {
        "github_trending": [],
        "huggingface_models": [],
        "reddit_posts": [],
    }

    # 1. GitHub 趋势搜索
    results["github_trending"] = await _search_github_trending(tech_keywords)

    # 2. HuggingFace 模型搜索
    results["huggingface_models"] = await _search_huggingface(tech_keywords)

    # 3. Reddit 讨论搜索
    results["reddit_posts"] = await _search_reddit(tech_keywords)

    return results


async def _search_github_trending(keywords: list[str]) -> list[dict]:
    """搜索 GitHub 趋势项目"""
    from .github_search import github_search

    trending = []
    for keyword in keywords[:2]:
        result = await github_search(keyword, max_results=3)
        for repo in result.get("repos", []):
            trending.append({
                "tech": keyword,
                "repo": repo["name"],
                "url": repo["url"],
                "stars": repo["stars"],
                "description": repo.get("description", ""),
            })
    return trending[:5]


async def _search_huggingface(keywords: list[str]) -> list[dict]:
    """搜索 HuggingFace 模型"""
    try:
        models = []
        for keyword in keywords[:2]:
            url = "https://huggingface.co/api/models"
            params = {
                "search": keyword,
                "sort": "likes",
                "direction": -1,
                "limit": 3
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for m in data[:2]:
                    models.append({
                        "model_id": m.get("modelId", ""),
                        "likes": m.get("likes", 0),
                        "downloads": m.get("downloads", 0),
                        "task": m.get("pipeline_tag", ""),
                        "url": f"https://huggingface.co/{m.get('modelId', '')}",
                    })
        return models[:5]
    except Exception as e:
        logger.warning(f"HuggingFace 搜索失败: {e}")
        return []


async def _search_reddit(keywords: list[str]) -> list[dict]:
    """搜索 Reddit 讨论"""
    try:
        posts = []
        # 使用 Reddit 的公开 JSON API
        for keyword in keywords[:2]:
            # 针对 AI 相关关键词优化搜索
            search_term = keyword
            if "agent" in keyword.lower():
                search_term = "AI Agent"
            elif "memory" in keyword.lower() or "记忆" in keyword.lower():
                search_term = "LLM memory"

            url = f"https://www.reddit.com/search.json"
            params = {
                "q": search_term,
                "sort": "relevance",
                "limit": 5,
                "restrict_sr": False,
            }
            headers = {"User-Agent": "ResumeAgent/1.0"}

            response = requests.get(url, params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for child in data.get("data", {}).get("children", [])[:3]:
                    post = child.get("data", {})
                    posts.append({
                        "title": post.get("title", ""),
                        "subreddit": post.get("subreddit", ""),
                        "score": post.get("score", 0),
                        "url": f"https://reddit.com{post.get('permalink', '')}",
                    })

        return posts[:5]
    except Exception as e:
        logger.warning(f"Reddit 搜索失败: {e}")
        return []
