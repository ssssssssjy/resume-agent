"""GitHub 相似项目搜索工具

根据简历中的项目描述，搜索 GitHub 上相似的项目：
1. 基于项目技术栈和背景生成精准检索词
2. 找到技术栈/场景相近的开源项目
3. 从这些项目中提取可学习的技术亮点
4. 生成简历优化建议

搜索结果会自动生成格式化的 Markdown 文档，
Agent 应使用 write_file 保存到 /references/ 目录。
"""
import logging
import re
from datetime import datetime
from typing import Any

import requests

from ._internal import get_document_path, get_github_headers

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"

# 需要排除的官方框架/库仓库
EXCLUDED_REPOS = {
    "langchain-ai/langchain", "langchain-ai/langgraph", "langchain-ai/langserve",
    "openai/openai-python", "openai/openai-node", "openai/whisper",
    "anthropics/anthropic-sdk-python", "run-llama/llama_index",
    "chroma-core/chroma", "qdrant/qdrant", "milvus-io/milvus",
    "facebook/react", "vuejs/vue", "vercel/next.js",
    "tiangolo/fastapi", "pallets/flask", "django/django",
    "pytorch/pytorch", "tensorflow/tensorflow", "huggingface/transformers",
}

EXCLUDED_ORGS = {
    "langchain-ai", "openai", "anthropics", "run-llama", "huggingface",
    "facebook", "vuejs", "vercel", "tiangolo", "pallets", "django",
    "pytorch", "tensorflow",
}

# 技术栈到业务场景的映射
TECH_TO_SCENARIOS = {
    # AI/LLM 相关
    "langchain": ["chatbot", "RAG", "document QA", "AI assistant", "knowledge base"],
    "langgraph": ["agent workflow", "multi-agent", "AI orchestration", "state machine"],
    "rag": ["document QA", "knowledge retrieval", "semantic search", "chat with docs"],
    "llm": ["chatbot", "text generation", "AI assistant", "content generation"],
    "openai": ["GPT integration", "AI chat", "text completion", "embeddings"],
    "embedding": ["semantic search", "similarity", "vector search", "recommendation"],
    "vector": ["similarity search", "semantic retrieval", "recommendation system"],

    # 前端
    "react": ["dashboard", "admin panel", "web app", "SPA", "UI components"],
    "nextjs": ["full-stack app", "SSR", "static site", "e-commerce", "blog"],
    "typescript": ["type-safe", "enterprise app", "scalable frontend"],

    # 后端
    "fastapi": ["REST API", "microservice", "async backend", "ML serving"],
    "python": ["backend service", "data processing", "automation", "scripting"],
    "redis": ["caching", "session", "real-time", "message queue"],
    "postgresql": ["relational data", "CRUD", "analytics", "transaction"],
    "mongodb": ["document store", "flexible schema", "real-time sync"],

    # 架构
    "microservices": ["distributed system", "service mesh", "API gateway"],
    "docker": ["containerization", "deployment", "CI/CD"],
    "kubernetes": ["orchestration", "scaling", "cloud-native"],
}


def _is_framework_repo(repo: dict) -> bool:
    """判断是否为框架/库仓库"""
    full_name = repo.get("full_name", "").lower()
    owner = full_name.split("/")[0] if "/" in full_name else ""
    description = (repo.get("description") or "").lower()

    if full_name in {r.lower() for r in EXCLUDED_REPOS}:
        return True
    if owner in {o.lower() for o in EXCLUDED_ORGS}:
        return True

    framework_keywords = ["framework for", "library for", "sdk for", "official", "a framework", "a library"]
    if any(kw in description for kw in framework_keywords):
        return True

    return False


async def search_similar_projects(
    resume_item: str,
    tech_stack: list[str],
    project_type: str = "",
    max_results: int = 8,
) -> dict[str, Any]:
    """根据简历项目描述搜索相似的 GitHub 项目

    基于你正在修改的简历项目，结合技术栈和项目背景，
    搜索 GitHub 上相似的项目，从中学习可以补充到简历的技术亮点。

    Args:
        resume_item: 简历中的项目描述（如 "设计并实现了基于 LangGraph 的多 Agent 协作系统"）
        tech_stack: 项目使用的技术栈列表（如 ["LangGraph", "FastAPI", "Redis", "PostgreSQL"]）
        project_type: 项目类型（可选，如 "AI Agent", "后端服务", "全栈应用"）
        max_results: 返回的最大项目数量（默认8个）

    Returns:
        相似项目分析结果，包含：
        - similar_projects: 相似项目列表（含 README 摘要和技术栈）
        - learnable_highlights: 可学习的技术亮点
        - enhancement_suggestions: 简历优化建议
    """
    results = {
        "original_item": resume_item,
        "tech_stack": tech_stack,
        "project_type": project_type,
        "search_queries": [],
        "similar_projects": [],
        "learnable_highlights": [],
        "enhancement_suggestions": [],
        "keywords_to_add": [],
    }

    # 1. 根据项目上下文生成精准检索词
    search_queries = _generate_context_queries(resume_item, tech_stack, project_type)
    results["search_queries"] = search_queries

    # 2. 搜索相似项目
    seen_repos = set()
    for query in search_queries:
        repos = await _search_github_repos(query, max_results=max_results)

        for repo in repos:
            repo_key = repo.get("full_name", "")
            if repo_key in seen_repos:
                continue
            seen_repos.add(repo_key)

            if _is_framework_repo(repo):
                continue

            # 计算与用户项目的相似度
            similarity = _calculate_similarity(repo, tech_stack, resume_item)
            if similarity < 0.2:  # 相似度太低的跳过
                continue

            # 获取 README
            readme = await _fetch_readme(repo_key)
            readme_summary = _summarize_readme(readme) if readme else ""

            # 提取技术亮点
            tech_highlights = _extract_tech_highlights(repo, readme)

            results["similar_projects"].append({
                "name": repo.get("full_name", ""),
                "url": repo.get("html_url", ""),
                "description": repo.get("description", "") or "",
                "stars": repo.get("stargazers_count", 0),
                "language": repo.get("language", ""),
                "topics": repo.get("topics", []),
                "similarity_score": similarity,
                "readme_summary": readme_summary,
                "tech_highlights": tech_highlights,
                "matched_query": query,
            })

    # 3. 按相似度和 stars 综合排序
    results["similar_projects"] = sorted(
        results["similar_projects"],
        key=lambda x: (x.get("similarity_score", 0) * 0.6 + min(x.get("stars", 0) / 10000, 0.4)),
        reverse=True
    )[:max_results]

    # 4. 从相似项目中提炼可学习的技术亮点
    results["learnable_highlights"] = _extract_learnable_highlights(
        results["similar_projects"], tech_stack
    )

    # 5. 生成简历优化建议
    results["enhancement_suggestions"] = _generate_enhancement_suggestions(
        resume_item, results["similar_projects"], results["learnable_highlights"]
    )

    # 6. 提取建议添加的关键词
    results["keywords_to_add"] = _extract_keywords_to_add(
        results["similar_projects"], tech_stack
    )

    # 7. 生成参考文档
    results["_document"] = {
        "content": _format_document(results),
        "suggested_path": get_document_path("similar_projects", "_".join(tech_stack[:3])),
        "save_instruction": "请使用 write_file 工具将此文档保存到 suggested_path 路径",
    }

    return results


def _generate_context_queries(resume_item: str, tech_stack: list[str], project_type: str) -> list[str]:
    """根据项目上下文生成精准检索词"""
    queries = []

    # 1. 基于技术栈组合生成查询
    if len(tech_stack) >= 2:
        queries.append(f"{tech_stack[0]} {tech_stack[1]} project")
        queries.append(f"{tech_stack[0]} {tech_stack[1]} application")

    # 2. 基于项目类型和技术栈
    if project_type:
        queries.append(f"{project_type} {tech_stack[0]}")
    else:
        # 从简历描述中推断项目类型
        item_lower = resume_item.lower()
        if any(kw in item_lower for kw in ["agent", "智能体", "多agent", "multi-agent"]):
            queries.append(f"AI agent {tech_stack[0]}")
            queries.append("multi-agent system")
        elif any(kw in item_lower for kw in ["chatbot", "对话", "chat", "问答"]):
            queries.append(f"chatbot {tech_stack[0]}")
            queries.append("conversational AI")
        elif any(kw in item_lower for kw in ["rag", "检索", "知识库", "文档"]):
            queries.append(f"RAG {tech_stack[0]}")
            queries.append("document QA system")
        elif any(kw in item_lower for kw in ["api", "服务", "后端", "backend"]):
            queries.append(f"API service {tech_stack[0]}")
            queries.append(f"{tech_stack[0]} microservice")

    # 3. 基于技术栈的典型业务场景
    for tech in tech_stack[:2]:
        tech_lower = tech.lower()
        if tech_lower in TECH_TO_SCENARIOS:
            scenarios = TECH_TO_SCENARIOS[tech_lower][:2]
            for scenario in scenarios:
                queries.append(f"{tech} {scenario}")

    # 4. 通用应用场景查询
    for tech in tech_stack[:2]:
        queries.append(f"built with {tech}")
        queries.append(f"{tech} demo")

    # 去重并限制数量
    seen = set()
    unique_queries = []
    for q in queries:
        q_lower = q.lower()
        if q_lower not in seen:
            seen.add(q_lower)
            unique_queries.append(q)

    return unique_queries[:8]


def _calculate_similarity(repo: dict, tech_stack: list[str], resume_item: str) -> float:
    """计算仓库与用户项目的相似度（0-1）"""
    score = 0.0
    total_weight = 0.0

    # 1. 技术栈匹配（权重 0.5）
    tech_weight = 0.5
    total_weight += tech_weight

    topics = [t.lower() for t in repo.get("topics", [])]
    description = (repo.get("description") or "").lower()
    language = (repo.get("language") or "").lower()

    matched_techs = 0
    for tech in tech_stack:
        tech_lower = tech.lower()
        if tech_lower in topics or tech_lower in description or tech_lower == language:
            matched_techs += 1

    if tech_stack:
        score += tech_weight * (matched_techs / len(tech_stack))

    # 2. 描述关键词匹配（权重 0.3）
    desc_weight = 0.3
    total_weight += desc_weight

    resume_keywords = set(re.findall(r'[a-zA-Z]+', resume_item.lower()))
    resume_keywords.update(re.findall(r'[\u4e00-\u9fa5]+', resume_item))

    if resume_keywords and description:
        matched_keywords = sum(1 for kw in resume_keywords if kw in description)
        score += desc_weight * min(matched_keywords / 5, 1.0)

    # 3. 项目活跃度（权重 0.2）
    activity_weight = 0.2
    total_weight += activity_weight

    stars = repo.get("stargazers_count", 0)
    if stars > 1000:
        score += activity_weight
    elif stars > 100:
        score += activity_weight * 0.7
    elif stars > 10:
        score += activity_weight * 0.4

    return min(score / total_weight, 1.0) if total_weight > 0 else 0.0


def _extract_tech_highlights(repo: dict, readme: str) -> list[str]:
    """从仓库中提取技术亮点"""
    highlights = []

    # 从 topics 提取
    topics = repo.get("topics", [])
    if topics:
        highlights.extend(topics[:5])

    # 从 README 中提取功能特性
    if readme:
        feature_section = re.search(
            r'(?:##?\s*(?:Features?|功能|Highlights?|特性|Key Features?)[^\n]*\n)((?:[-*]\s+[^\n]+\n?)+)',
            readme, re.IGNORECASE
        )
        if feature_section:
            features = re.findall(r'[-*]\s+([^\n]+)', feature_section.group(1))
            highlights.extend(features[:5])

        # 提取技术关键词
        tech_patterns = [
            r'\b(async(?:io)?|concurrent|parallel)\b',
            r'\b(streaming|real-?time|websocket)\b',
            r'\b(cache|caching|redis|memcached)\b',
            r'\b(queue|message|kafka|rabbitmq)\b',
            r'\b(vector|embedding|semantic)\b',
            r'\b(microservice|distributed|scalable)\b',
            r'\b(CI/?CD|docker|kubernetes|k8s)\b',
            r'\b(GraphQL|REST|gRPC|API)\b',
            r'\b(authentication|OAuth|JWT)\b',
            r'\b(monitoring|logging|observability)\b',
        ]
        for pattern in tech_patterns:
            matches = re.findall(pattern, readme, re.IGNORECASE)
            highlights.extend(matches[:2])

    # 去重
    seen = set()
    unique = []
    for h in highlights:
        h_lower = h.lower().strip()
        if h_lower and h_lower not in seen and len(h_lower) > 2:
            seen.add(h_lower)
            unique.append(h)

    return unique[:10]


def _extract_learnable_highlights(projects: list[dict], user_tech_stack: list[str]) -> list[dict]:
    """从相似项目中提炼可学习的技术亮点"""
    highlights = []
    seen_highlights = set()

    user_tech_lower = {t.lower() for t in user_tech_stack}

    for project in projects[:5]:
        project_highlights = project.get("tech_highlights", [])

        for h in project_highlights:
            h_lower = h.lower()
            if h_lower in user_tech_lower:
                continue
            if h_lower in seen_highlights:
                continue

            seen_highlights.add(h_lower)
            highlights.append({
                "highlight": h,
                "source_project": project.get("name", ""),
                "source_stars": project.get("stars", 0),
            })

    return highlights[:15]


def _generate_enhancement_suggestions(
    resume_item: str,
    similar_projects: list[dict],
    learnable_highlights: list[dict]
) -> list[str]:
    """生成简历优化建议"""
    suggestions = []

    if not similar_projects:
        return ["未找到足够相似的项目，建议手动搜索相关开源项目作为参考"]

    # 1. 基于高星项目的通用建议
    top_project = similar_projects[0] if similar_projects else None
    if top_project and top_project.get("stars", 0) > 100:
        suggestions.append(
            f"参考项目 [{top_project['name']}]({top_project['url']}) (⭐{top_project['stars']:,}) "
            f"的描述方式，这是一个高关注度的同类项目"
        )

    # 2. 基于可学习亮点的具体建议
    tech_keywords = [h["highlight"] for h in learnable_highlights[:5]]
    if tech_keywords:
        suggestions.append(
            f"考虑在描述中补充以下技术细节：{', '.join(tech_keywords)}"
        )

    # 3. 检查是否缺少量化指标
    has_numbers = bool(re.search(r'\d+', resume_item))
    if not has_numbers:
        suggestions.append(
            "建议添加量化指标（如：处理 X 条数据、延迟降低 X%、支持 X 并发）"
        )

    # 4. 基于相似项目的功能对比建议
    common_features = {}
    for project in similar_projects[:5]:
        for h in project.get("tech_highlights", []):
            h_lower = h.lower()
            common_features[h_lower] = common_features.get(h_lower, 0) + 1

    frequent_features = [f for f, count in common_features.items() if count >= 2]
    if frequent_features:
        suggestions.append(
            f"同类项目常见特性：{', '.join(frequent_features[:5])}，"
            "如果你的项目也实现了这些，建议突出说明"
        )

    return suggestions


def _extract_keywords_to_add(projects: list[dict], user_tech_stack: list[str]) -> list[str]:
    """提取建议添加到简历的关键词"""
    keyword_counts = {}
    user_tech_lower = {t.lower() for t in user_tech_stack}

    for project in projects:
        for topic in project.get("topics", []):
            topic_lower = topic.lower()
            if topic_lower not in user_tech_lower:
                keyword_counts[topic_lower] = keyword_counts.get(topic_lower, 0) + 1

        for h in project.get("tech_highlights", []):
            h_lower = h.lower()
            if h_lower not in user_tech_lower and len(h_lower) > 2:
                keyword_counts[h_lower] = keyword_counts.get(h_lower, 0) + 1

    sorted_keywords = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)
    return [kw for kw, _ in sorted_keywords[:15]]


async def _search_github_repos(query: str, max_results: int = 10) -> list[dict]:
    """搜索 GitHub 仓库"""
    try:
        url = f"{GITHUB_API_BASE}/search/repositories"
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": max_results,
        }

        response = requests.get(url, headers=get_github_headers(), params=params, timeout=15)

        if response.status_code == 200:
            return response.json().get("items", [])
        else:
            logger.warning(f"GitHub 搜索失败: {response.status_code} - {query}")

    except Exception as e:
        logger.error(f"GitHub 搜索异常 ({query}): {e}")

    return []


async def _fetch_readme(repo: str) -> str:
    """获取仓库 README 内容"""
    try:
        url = f"{GITHUB_API_BASE}/repos/{repo}/readme"
        headers = get_github_headers()
        headers["Accept"] = "application/vnd.github.v3.raw"

        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code == 200:
            return response.text

    except Exception as e:
        logger.debug(f"README 获取异常 ({repo}): {e}")

    return ""


def _summarize_readme(readme: str, max_length: int = 600) -> str:
    """从 README 提取摘要"""
    if not readme:
        return ""

    lines = readme.split("\n")
    summary_parts = []
    in_code_block = False
    char_count = 0

    for line in lines:
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        if re.match(r'^\s*(\[?!\[|<img|<a href="https://)', line):
            continue

        stripped = line.strip()
        if not stripped:
            if summary_parts and summary_parts[-1]:
                summary_parts.append("")
            continue

        cleaned = stripped
        cleaned = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', cleaned)
        cleaned = re.sub(r'`([^`]+)`', r'\1', cleaned)
        cleaned = re.sub(r'\*\*([^*]+)\*\*', r'\1', cleaned)
        cleaned = re.sub(r'\*([^*]+)\*', r'\1', cleaned)

        if cleaned.startswith("#"):
            cleaned = cleaned.lstrip("#").strip()
            if cleaned:
                cleaned = f"【{cleaned}】"

        summary_parts.append(cleaned)
        char_count += len(cleaned)

        if char_count >= max_length:
            break

    summary = "\n".join(summary_parts).strip()
    if len(summary) > max_length:
        summary = summary[:max_length] + "..."

    return summary


def _format_document(results: dict) -> str:
    """生成格式化的 Markdown 文档"""
    lines = [
        "# 相似项目分析报告",
        "",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## 📋 原始简历项目",
        "",
        f"> {results.get('original_item', '')}",
        "",
        f"**技术栈**: {', '.join(results.get('tech_stack', []))}",
        "",
    ]

    if results.get("project_type"):
        lines.append(f"**项目类型**: {results['project_type']}")
        lines.append("")

    # 检索策略
    queries = results.get("search_queries", [])
    if queries:
        lines.append("## 🔍 检索策略")
        lines.append("")
        lines.append("基于项目上下文生成的检索词：")
        for q in queries[:6]:
            lines.append(f"- `{q}`")
        lines.append("")

    # 相似项目
    projects = results.get("similar_projects", [])
    if projects:
        lines.append("## 📦 相似项目")
        lines.append("")

        for i, project in enumerate(projects[:8], 1):
            name = project.get("name", "")
            url = project.get("url", "")
            stars = project.get("stars", 0)
            similarity = project.get("similarity_score", 0)
            description = project.get("description", "")[:120]

            lines.append(f"### {i}. [{name}]({url})")
            lines.append(f"⭐ {stars:,} | 相似度: {similarity:.0%}")
            if description:
                lines.append(f"> {description}")
            lines.append("")

            readme_summary = project.get("readme_summary", "")
            if readme_summary:
                lines.append("**项目简介:**")
                for p in readme_summary.split("\n\n")[:2]:
                    if p.strip():
                        lines.append(f"> {p.strip()}")
                lines.append("")

            highlights = project.get("tech_highlights", [])
            if highlights:
                lines.append(f"**技术亮点:** {', '.join(highlights[:8])}")
                lines.append("")

    # 可学习的技术亮点
    learnable = results.get("learnable_highlights", [])
    if learnable:
        lines.append("## 💡 可学习的技术亮点")
        lines.append("")
        lines.append("从相似项目中发现的、你可能可以补充到简历的技术点：")
        lines.append("")
        for h in learnable[:10]:
            lines.append(f"- **{h['highlight']}** (来自 {h['source_project']})")
        lines.append("")

    # 简历优化建议
    suggestions = results.get("enhancement_suggestions", [])
    if suggestions:
        lines.append("## ✨ 简历优化建议")
        lines.append("")
        for i, s in enumerate(suggestions, 1):
            lines.append(f"{i}. {s}")
        lines.append("")

    # 建议添加的关键词
    keywords = results.get("keywords_to_add", [])
    if keywords:
        lines.append("## 🏷️ 建议添加的关键词")
        lines.append("")
        lines.append("这些关键词在相似项目中出现频率较高，考虑在简历中使用：")
        lines.append("")
        lines.append("```")
        lines.append(", ".join(keywords[:15]))
        lines.append("```")
        lines.append("")

    return "\n".join(lines)
