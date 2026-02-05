"""技术内容/讨论搜索工具

搜索技术相关的文章、讨论和模型：
- DEV.to: 英文技术博客
- 掘金: 中文技术社区
- InfoQ: 架构/企业级文章
- Reddit: 技术讨论帖子
- HuggingFace: AI 模型和论文

返回简洁摘要 + 详细文档内容（供 Agent 使用 write_file 保存）。
"""
import logging
from datetime import datetime
from typing import Any

import requests

from ._internal import get_document_path

logger = logging.getLogger(__name__)


async def search_tech_articles(
    keywords: list[str],
    language: str = "zh",
    max_results: int = 5,
) -> dict[str, Any]:
    """搜索技术文章和讨论

    从多个技术社区搜索相关文章和讨论，获取最佳实践和技术见解。

    Args:
        keywords: 技术关键词列表 (如 ["LLM memory", "RAG architecture"])
        language: 语言偏好 ("zh" 中文优先, "en" 英文优先)
        max_results: 每个来源的最大返回结果数

    Returns:
        包含简洁摘要和文档内容的字典：
        - summary: 简洁的搜索结果摘要
        - document_content: 详细的 Markdown 文档内容
        - suggested_path: 建议保存路径
    """
    results = {
        "articles": [],
        "discussions": [],
        "models": [],
        "data_sources": [],
    }

    # 1. DEV.to (英文技术博客)
    dev_articles = await _search_devto(keywords, max_results)
    if dev_articles:
        results["data_sources"].append("DEV.to")
        results["articles"].extend(dev_articles)

    # 2. 掘金 (中文技术社区)
    if language == "zh":
        juejin_articles = await _search_juejin(keywords, max_results)
        if juejin_articles:
            results["data_sources"].append("掘金")
            results["articles"].extend(juejin_articles)

    # 3. InfoQ (架构/企业级)
    if language == "zh":
        infoq_articles = await _search_infoq(keywords, max_results)
        if infoq_articles:
            results["data_sources"].append("InfoQ")
            results["articles"].extend(infoq_articles)

    # 4. Reddit (技术讨论)
    reddit_posts = await _search_reddit(keywords, max_results)
    if reddit_posts:
        results["data_sources"].append("Reddit")
        results["discussions"].extend(reddit_posts)

    # 5. HuggingFace (AI 模型)
    hf_models = await _search_huggingface(keywords, max_results)
    if hf_models:
        results["data_sources"].append("HuggingFace")
        results["models"].extend(hf_models)

    # 生成文档内容和简洁摘要
    document_content = _format_document(keywords, results)
    suggested_path = get_document_path("tech_articles", "_".join(keywords[:3]))
    summary = _format_summary(keywords, results, suggested_path)

    return {
        "summary": summary,
        "document_content": document_content,
        "suggested_path": suggested_path,
    }


async def _search_devto(keywords: list[str], max_results: int = 5) -> list[dict]:
    """搜索 DEV.to 文章"""
    articles = []
    try:
        for keyword in keywords[:2]:
            url = "https://dev.to/api/articles"
            params = {
                "tag": keyword.lower().replace(" ", ""),
                "per_page": max_results,
                "top": 7,
            }
            headers = {"User-Agent": "ResumeAgent/1.0"}

            response = requests.get(url, params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for item in data[:max_results]:
                    articles.append({
                        "title": item.get("title", ""),
                        "url": item.get("url", ""),
                        "summary": item.get("description", "")[:200],
                        "tags": item.get("tag_list", []),
                        "source": "DEV.to",
                        "author": item.get("user", {}).get("name", ""),
                        "reactions": item.get("positive_reactions_count", 0),
                        "published_at": item.get("published_at", ""),
                    })

            if len(articles) >= max_results:
                break

        # 如果 tag 搜索没有结果，尝试通用搜索
        if not articles:
            url = "https://dev.to/api/articles"
            params = {"per_page": max_results}
            response = requests.get(url, params=params, headers={"User-Agent": "ResumeAgent/1.0"}, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for item in data[:max_results]:
                    title = item.get("title", "").lower()
                    desc = item.get("description", "").lower()
                    if any(kw.lower() in title or kw.lower() in desc for kw in keywords):
                        articles.append({
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "summary": item.get("description", "")[:200],
                            "tags": item.get("tag_list", []),
                            "source": "DEV.to",
                            "author": item.get("user", {}).get("name", ""),
                            "reactions": item.get("positive_reactions_count", 0),
                            "published_at": item.get("published_at", ""),
                        })

    except Exception as e:
        logger.warning(f"DEV.to 搜索失败: {e}")

    return articles[:max_results]


async def _search_juejin(keywords: list[str], max_results: int = 5) -> list[dict]:
    """搜索掘金文章"""
    articles = []
    try:
        search_query = " ".join(keywords)
        url = "https://api.juejin.cn/search_api/v1/search"
        payload = {
            "cursor": "0",
            "key_word": search_query,
            "id_type": 0,
            "limit": max_results,
            "search_type": 2,
            "sort_type": 0,
        }
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "ResumeAgent/1.0",
        }

        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            items = data.get("data", [])
            for item in items[:max_results]:
                result_model = item.get("result_model", {})
                article_info = result_model.get("article_info", {})
                author_info = result_model.get("author_user_info", {})

                if article_info:
                    articles.append({
                        "title": article_info.get("title", ""),
                        "url": f"https://juejin.cn/post/{article_info.get('article_id', '')}",
                        "summary": article_info.get("brief_content", "")[:200],
                        "tags": [tag.get("tag_name", "") for tag in result_model.get("tags", [])],
                        "source": "掘金",
                        "author": author_info.get("user_name", ""),
                        "reactions": article_info.get("digg_count", 0),
                        "published_at": "",
                    })

    except Exception as e:
        logger.warning(f"掘金搜索失败: {e}")

    return articles[:max_results]


async def _search_infoq(keywords: list[str], max_results: int = 3) -> list[dict]:
    """搜索 InfoQ 中文站文章"""
    articles = []
    try:
        url = "https://www.infoq.cn/public/v1/article/getList"
        payload = {
            "type": 1,
            "size": max_results,
            "score": None,
            "id": None,
        }
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "ResumeAgent/1.0",
            "Referer": "https://www.infoq.cn/",
        }

        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            items = data.get("data", [])
            for item in items[:max_results]:
                title = item.get("article_title", "").lower()
                if any(kw.lower() in title for kw in keywords):
                    articles.append({
                        "title": item.get("article_title", ""),
                        "url": f"https://www.infoq.cn/article/{item.get('uuid', '')}",
                        "summary": item.get("article_summary", "")[:200],
                        "tags": [],
                        "source": "InfoQ",
                        "author": item.get("author", [{}])[0].get("nickname", "") if item.get("author") else "",
                        "reactions": item.get("views", 0),
                        "published_at": item.get("publish_time", ""),
                    })

    except Exception as e:
        logger.warning(f"InfoQ 搜索失败: {e}")

    return articles[:max_results]


async def _search_reddit(keywords: list[str], max_results: int = 5) -> list[dict]:
    """搜索 Reddit 讨论"""
    posts = []
    try:
        for keyword in keywords[:2]:
            # 针对 AI 相关关键词优化搜索
            search_term = keyword
            if "agent" in keyword.lower():
                search_term = "AI Agent"
            elif "memory" in keyword.lower() or "记忆" in keyword.lower():
                search_term = "LLM memory"

            url = "https://www.reddit.com/search.json"
            params = {
                "q": search_term,
                "sort": "relevance",
                "limit": max_results,
                "restrict_sr": False,
            }
            headers = {"User-Agent": "ResumeAgent/1.0"}

            response = requests.get(url, params=params, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for child in data.get("data", {}).get("children", [])[:max_results]:
                    post = child.get("data", {})
                    posts.append({
                        "title": post.get("title", ""),
                        "subreddit": post.get("subreddit", ""),
                        "score": post.get("score", 0),
                        "num_comments": post.get("num_comments", 0),
                        "url": f"https://reddit.com{post.get('permalink', '')}",
                        "source": "Reddit",
                    })

    except Exception as e:
        logger.warning(f"Reddit 搜索失败: {e}")

    return posts[:max_results]


async def _search_huggingface(keywords: list[str], max_results: int = 5) -> list[dict]:
    """搜索 HuggingFace 模型"""
    models = []
    try:
        for keyword in keywords[:2]:
            url = "https://huggingface.co/api/models"
            params = {
                "search": keyword,
                "sort": "likes",
                "direction": -1,
                "limit": max_results
            }
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                for m in data[:max_results]:
                    models.append({
                        "model_id": m.get("modelId", ""),
                        "likes": m.get("likes", 0),
                        "downloads": m.get("downloads", 0),
                        "task": m.get("pipeline_tag", ""),
                        "url": f"https://huggingface.co/{m.get('modelId', '')}",
                        "source": "HuggingFace",
                    })

    except Exception as e:
        logger.warning(f"HuggingFace 搜索失败: {e}")

    return models[:max_results]


def _format_summary(keywords: list[str], results: dict, suggested_path: str) -> str:
    """生成简洁的搜索结果摘要"""
    articles = results.get("articles", [])
    discussions = results.get("discussions", [])
    models = results.get("models", [])
    sources = results.get("data_sources", [])

    lines = []

    # 统计
    lines.append(f"搜索关键词：{', '.join(keywords)}")
    lines.append(f"数据来源：{', '.join(sources)}")
    lines.append(f"共找到 {len(articles)} 篇文章、{len(discussions)} 条讨论、{len(models)} 个模型")
    lines.append("")

    # Top 文章
    if articles:
        lines.append("**热门文章：**")
        for article in articles[:3]:
            title = article.get("title", "")[:50]
            source = article.get("source", "")
            reactions = article.get("reactions", 0)
            lines.append(f"- [{source}] {title}... (👍{reactions})")
        lines.append("")

    # Top 模型
    if models:
        lines.append("**相关模型：**")
        for m in models[:3]:
            model_id = m.get("model_id", "")
            likes = m.get("likes", 0)
            lines.append(f"- {model_id} (❤️{likes})")
        lines.append("")

    # 保存提示
    lines.append(f"请使用 write_file 将详细报告保存到 `{suggested_path}`")

    return "\n".join(lines)


def _format_document(keywords: list[str], results: dict) -> str:
    """生成格式化的 Markdown 文档"""
    lines = [
        f"# 技术内容搜索报告",
        f"",
        f"**查询关键词**: {', '.join(keywords)}",
        f"**数据来源**: {', '.join(results.get('data_sources', []))}",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"",
    ]

    # 技术文章
    articles = results.get("articles", [])
    if articles:
        lines.append("## 📝 技术文章")
        lines.append("")

        # 按来源分组
        by_source = {}
        for article in articles:
            source = article.get("source", "其他")
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(article)

        for source, source_articles in by_source.items():
            lines.append(f"### {source}")
            lines.append("")
            for article in source_articles:
                title = article.get("title", "无标题")
                url = article.get("url", "")
                summary = article.get("summary", "")
                author = article.get("author", "")
                reactions = article.get("reactions", 0)
                tags = article.get("tags", [])

                lines.append(f"**[{title}]({url})**")
                if author:
                    lines.append(f"*作者：{author}* | 👍 {reactions}")
                if summary:
                    lines.append(f"> {summary[:150]}...")
                if tags:
                    lines.append(f"标签：{', '.join(tags[:5])}")
                lines.append("")

    # Reddit 讨论
    discussions = results.get("discussions", [])
    if discussions:
        lines.append("## 💬 Reddit 讨论")
        lines.append("")
        for post in discussions:
            title = post.get("title", "")
            url = post.get("url", "")
            subreddit = post.get("subreddit", "")
            score = post.get("score", 0)
            comments = post.get("num_comments", 0)
            lines.append(f"- [{title[:80]}...]({url})")
            lines.append(f"  - r/{subreddit} | 👍 {score} | 💬 {comments} 评论")
        lines.append("")

    # HuggingFace 模型
    models = results.get("models", [])
    if models:
        lines.append("## 🤗 HuggingFace 模型")
        lines.append("")
        lines.append("| 模型 | 任务 | Likes | Downloads |")
        lines.append("|------|------|-------|-----------|")
        for m in models:
            model_id = m.get("model_id", "")
            url = m.get("url", "")
            task = m.get("task", "-")
            likes = m.get("likes", 0)
            downloads = m.get("downloads", 0)
            lines.append(f"| [{model_id}]({url}) | {task} | ❤️ {likes:,} | 📥 {downloads:,} |")
        lines.append("")

    # 简历关键词建议
    lines.append("## 💡 简历关键词建议")
    lines.append("")
    lines.append("从以上内容中可提取的技术关键词：")
    all_tags = []
    for article in articles:
        all_tags.extend(article.get("tags", []))
    unique_tags = list(set(all_tags))[:10]
    if unique_tags:
        lines.append(f"- {', '.join(unique_tags)}")
    else:
        lines.append(f"- {', '.join(keywords)}")
    lines.append("")

    return "\n".join(lines)
