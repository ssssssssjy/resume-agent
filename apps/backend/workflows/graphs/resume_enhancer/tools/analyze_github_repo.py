"""GitHub 项目深度分析工具

深入分析 GitHub 仓库的技术栈、架构特点、核心功能等，
为简历提供可参考的技术细节和量化指标。

分析结果会自动生成格式化的 Markdown 文档，
Agent 应使用 write_file 保存到 /references/ 目录。
"""
import logging
from typing import Any

import requests

from ._internal import format_repo_analysis_document, get_document_path, get_github_headers

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


async def analyze_github_repo(repo: str) -> dict[str, Any]:
    """深度分析 GitHub 仓库

    获取仓库的技术栈、架构亮点、核心功能、贡献者活跃度等信息，
    为简历优化提供技术细节参考。

    Args:
        repo: 仓库名称，格式为 "owner/repo" (如 "langchain-ai/langgraph")

    Returns:
        仓库分析结果，包含技术栈、架构亮点、核心功能、指标等
    """
    result = {
        "repo": repo,
        "basic_info": {},
        "tech_stack": [],
        "architecture_highlights": [],
        "key_features": [],
        "metrics": {},
        "readme_summary": "",
        "recent_activity": [],
        "error": None,
    }

    try:
        # 1. 获取仓库基本信息
        repo_info = await _get_repo_info(repo)
        if "error" in repo_info:
            result["error"] = repo_info["error"]
            return result

        result["basic_info"] = {
            "name": repo_info.get("full_name", ""),
            "description": repo_info.get("description", ""),
            "homepage": repo_info.get("homepage", ""),
            "topics": repo_info.get("topics", []),
            "license": repo_info.get("license", {}).get("name", "Unknown"),
            "created_at": repo_info.get("created_at", ""),
            "updated_at": repo_info.get("updated_at", ""),
        }

        result["metrics"] = {
            "stars": repo_info.get("stargazers_count", 0),
            "forks": repo_info.get("forks_count", 0),
            "watchers": repo_info.get("subscribers_count", 0),
            "open_issues": repo_info.get("open_issues_count", 0),
            "size_kb": repo_info.get("size", 0),
        }

        # 2. 获取语言分布（技术栈）
        languages = await _get_languages(repo)
        if languages:
            total_bytes = sum(languages.values())
            result["tech_stack"] = [
                {
                    "language": lang,
                    "percentage": round(bytes_count / total_bytes * 100, 1),
                    "bytes": bytes_count,
                }
                for lang, bytes_count in sorted(languages.items(), key=lambda x: x[1], reverse=True)
            ]

        # 3. 获取贡献者信息
        contributors = await _get_contributors(repo)
        result["metrics"]["contributors"] = len(contributors)
        result["metrics"]["top_contributors"] = [
            {"login": c.get("login", ""), "contributions": c.get("contributions", 0)}
            for c in contributors[:5]
        ]

        # 4. 获取最近的提交活动
        commits = await _get_recent_commits(repo)
        result["recent_activity"] = commits
        if commits:
            result["metrics"]["commit_frequency"] = f"{len(commits)} commits in last 30 days"

        # 5. 获取 README 并提取摘要
        readme = await _get_readme(repo)
        if readme:
            result["readme_summary"] = _extract_readme_summary(readme)
            result["key_features"] = _extract_features_from_readme(readme)
            result["architecture_highlights"] = _extract_architecture_from_readme(readme)

        # 6. 获取仓库的 releases 信息
        releases = await _get_releases(repo)
        if releases:
            result["metrics"]["latest_release"] = releases[0].get("tag_name", "")
            result["metrics"]["total_releases"] = len(releases)

    except Exception as e:
        logger.error(f"分析仓库 {repo} 失败: {e}")
        result["error"] = str(e)

    # 生成参考文档（供 Agent 保存）
    result["_document"] = {
        "content": format_repo_analysis_document(repo, result),
        "suggested_path": get_document_path("repo_analysis", repo),
        "save_instruction": "请使用 write_file 工具将此文档保存到 suggested_path 路径",
    }

    return result


async def _get_repo_info(repo: str) -> dict:
    """获取仓库基本信息"""
    try:
        url = f"{GITHUB_API_BASE}/repos/{repo}"
        response = requests.get(url, headers=get_github_headers(), timeout=10)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return {"error": f"仓库 {repo} 不存在"}
        else:
            return {"error": f"GitHub API 错误: {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


async def _get_languages(repo: str) -> dict:
    """获取仓库语言分布"""
    try:
        url = f"{GITHUB_API_BASE}/repos/{repo}/languages"
        response = requests.get(url, headers=get_github_headers(), timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.warning(f"获取语言分布失败: {e}")
    return {}


async def _get_contributors(repo: str, max_count: int = 30) -> list:
    """获取贡献者列表"""
    try:
        url = f"{GITHUB_API_BASE}/repos/{repo}/contributors"
        params = {"per_page": max_count}
        response = requests.get(url, headers=get_github_headers(), params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        logger.warning(f"获取贡献者失败: {e}")
    return []


async def _get_recent_commits(repo: str, days: int = 30) -> list:
    """获取最近的提交记录"""
    try:
        from datetime import datetime, timedelta
        since = (datetime.utcnow() - timedelta(days=days)).isoformat() + "Z"

        url = f"{GITHUB_API_BASE}/repos/{repo}/commits"
        params = {"since": since, "per_page": 100}
        response = requests.get(url, headers=get_github_headers(), params=params, timeout=10)
        if response.status_code == 200:
            commits = response.json()
            return [
                {
                    "sha": c.get("sha", "")[:7],
                    "message": c.get("commit", {}).get("message", "").split("\n")[0][:80],
                    "author": c.get("commit", {}).get("author", {}).get("name", ""),
                    "date": c.get("commit", {}).get("author", {}).get("date", ""),
                }
                for c in commits[:10]  # 只返回最近 10 条
            ]
    except Exception as e:
        logger.warning(f"获取提交记录失败: {e}")
    return []


async def _get_readme(repo: str) -> str:
    """获取 README 内容"""
    try:
        url = f"{GITHUB_API_BASE}/repos/{repo}/readme"
        headers = get_github_headers()
        headers["Accept"] = "application/vnd.github.v3.raw"
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.text
    except Exception as e:
        logger.warning(f"获取 README 失败: {e}")
    return ""


async def _get_releases(repo: str, max_count: int = 10) -> list:
    """获取发布版本列表"""
    try:
        url = f"{GITHUB_API_BASE}/repos/{repo}/releases"
        params = {"per_page": max_count}
        response = requests.get(url, headers=get_github_headers(), params=params, timeout=10)
        if response.status_code == 200:
            releases = response.json()
            return [
                {
                    "tag_name": r.get("tag_name", ""),
                    "name": r.get("name", ""),
                    "published_at": r.get("published_at", ""),
                    "prerelease": r.get("prerelease", False),
                }
                for r in releases
            ]
    except Exception as e:
        logger.warning(f"获取 releases 失败: {e}")
    return []


def _extract_readme_summary(readme: str, max_length: int = 500) -> str:
    """从 README 中提取摘要"""
    if not readme:
        return ""

    lines = readme.split("\n")
    summary_lines = []
    in_code_block = False
    char_count = 0

    for line in lines:
        # 跳过代码块
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        # 跳过标题行（但保留第一个标题后的内容）
        if line.startswith("#"):
            continue

        # 跳过徽章行
        if "![" in line or "[![" in line:
            continue

        # 跳过空行（连续的空行只保留一个）
        if not line.strip():
            if summary_lines and summary_lines[-1].strip():
                summary_lines.append("")
            continue

        # 累加内容
        summary_lines.append(line)
        char_count += len(line)

        if char_count >= max_length:
            break

    return "\n".join(summary_lines).strip()[:max_length]


def _extract_features_from_readme(readme: str) -> list[str]:
    """从 README 中提取关键功能"""
    features = []
    lines = readme.split("\n")

    in_features_section = False
    feature_keywords = ["feature", "功能", "特性", "highlights", "what", "why"]

    for i, line in enumerate(lines):
        line_lower = line.lower()

        # 检测是否进入 features 部分
        if line.startswith("#") and any(kw in line_lower for kw in feature_keywords):
            in_features_section = True
            continue

        # 如果遇到新的标题，退出 features 部分
        if in_features_section and line.startswith("#"):
            break

        # 提取列表项
        if in_features_section:
            stripped = line.strip()
            if stripped.startswith(("- ", "* ", "• ")):
                feature = stripped[2:].strip()
                if feature and len(feature) > 5:
                    # 清理 markdown 格式
                    feature = feature.replace("**", "").replace("*", "").replace("`", "")
                    features.append(feature[:100])  # 限制长度

                    if len(features) >= 10:
                        break

    return features


def _extract_architecture_from_readme(readme: str) -> list[str]:
    """从 README 中提取架构亮点"""
    highlights = []
    lines = readme.split("\n")

    arch_keywords = ["architecture", "design", "how it works", "概述", "架构", "设计", "原理", "implementation"]

    in_arch_section = False

    for line in lines:
        line_lower = line.lower()

        # 检测架构相关部分
        if line.startswith("#") and any(kw in line_lower for kw in arch_keywords):
            in_arch_section = True
            continue

        if in_arch_section and line.startswith("#"):
            break

        if in_arch_section:
            stripped = line.strip()
            # 提取关键描述（非空行，非代码，有意义的内容）
            if stripped and not stripped.startswith(("```", "![", "<")):
                if len(stripped) > 20:  # 过滤太短的行
                    clean = stripped.replace("**", "").replace("*", "").replace("`", "")
                    highlights.append(clean[:150])

                    if len(highlights) >= 5:
                        break

    return highlights
