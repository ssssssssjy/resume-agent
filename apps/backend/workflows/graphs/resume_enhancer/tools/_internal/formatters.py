"""文档格式化工具（内部使用）

将搜索结果格式化为 Markdown 文档。
"""
from datetime import datetime
from typing import Any

# 文档保存根目录
REFERENCES_DIR = "/references"


def get_document_path(doc_type: str, identifier: str) -> str:
    """生成文档保存路径

    Args:
        doc_type: 文档类型 (tech_trends, tech_articles, repo_analysis)
        identifier: 标识符（技术名、仓库名等）

    Returns:
        文档路径，如 /references/tech_trends_RAG.md
    """
    safe_identifier = identifier.replace("/", "_").replace(" ", "_").replace(",", "_")
    safe_identifier = "".join(c for c in safe_identifier if c.isalnum() or c in "_-")
    return f"{REFERENCES_DIR}/{doc_type}_{safe_identifier}.md"


def format_tech_trends_document(
    technologies: list[str],
    results: dict[str, Any],
) -> str:
    """将技术趋势查询结果格式化为 Markdown 文档"""
    lines = [
        f"# 技术趋势分析：{', '.join(technologies)}",
        f"",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"",
    ]

    # 综合推荐
    if results.get("recommendations"):
        lines.append("## 简历建议")
        lines.append("")
        for rec in results["recommendations"]:
            lines.append(f"- {rec}")
        lines.append("")

    # 各技术详情
    for tech_data in results.get("technologies", []):
        name = tech_data.get("name", "")
        lines.append(f"## {name}")
        lines.append("")

        # GitHub 数据
        github = tech_data.get("github", {})
        if github and not github.get("error"):
            lines.append("### GitHub 热度")
            lines.append(f"- 相关仓库数：{github.get('total_repos_found', 0):,}")
            lines.append(f"- Top10 总 Stars：{github.get('total_stars_top10', 0):,}")
            lines.append(f"- 活跃度评分：{github.get('activity_score', 0):.1f}%")
            lines.append("")

            top_repos = github.get("top_repos", [])
            if top_repos:
                lines.append("**热门仓库：**")
                for repo in top_repos[:3]:
                    lines.append(f"- [{repo['name']}](https://github.com/{repo['name']}) ⭐ {repo['stars']:,}")
                    if repo.get("description"):
                        lines.append(f"  - {repo['description']}")
                lines.append("")

        # Stack Overflow 数据
        so = tech_data.get("stackoverflow", {})
        if so and not so.get("error") and so.get("question_count", 0) > 0:
            lines.append("### Stack Overflow")
            lines.append(f"- 问题数：{so.get('question_count', 0):,}")
            if so.get("related_tags"):
                lines.append(f"- 相关标签：{', '.join(so['related_tags'])}")
            lines.append("")

        # 包下载数据
        packages = tech_data.get("packages", {})
        if packages:
            npm = packages.get("npm", {})
            pypi = packages.get("pypi", {})
            if npm or pypi:
                lines.append("### 包管理器")
                if npm and npm.get("weekly_downloads"):
                    lines.append(f"- npm 周下载量：{npm['weekly_downloads']:,}")
                if pypi and pypi.get("latest_version"):
                    lines.append(f"- PyPI 最新版本：{pypi['latest_version']}")
                lines.append("")

    # 对比数据
    comparison = results.get("comparison", {})
    if comparison.get("by_github_stars"):
        lines.append("## 技术对比")
        lines.append("")
        lines.append("| 技术 | GitHub Stars | 活跃度 |")
        lines.append("|------|-------------|--------|")
        for item in comparison["by_github_stars"]:
            lines.append(f"| {item['name']} | {item['total_stars']:,} | {item.get('activity_score', 0):.1f}% |")
        lines.append("")

    return "\n".join(lines)


def format_tech_articles_document(
    keywords: list[str],
    articles: list[dict[str, Any]],
) -> str:
    """将技术文章搜索结果格式化为 Markdown 文档"""
    lines = [
        f"# 技术文章参考：{', '.join(keywords)}",
        f"",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"> 文章数量：{len(articles)}",
        f"",
    ]

    if not articles:
        lines.append("*未找到相关文章*")
        return "\n".join(lines)

    # 按来源分组
    by_source = {}
    for article in articles:
        source = article.get("source", "其他")
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(article)

    for source, source_articles in by_source.items():
        lines.append(f"## {source}")
        lines.append("")
        for article in source_articles:
            title = article.get("title", "无标题")
            url = article.get("url", "")
            summary = article.get("summary", "")
            author = article.get("author", "")
            reactions = article.get("reactions", 0)
            tags = article.get("tags", [])

            lines.append(f"### [{title}]({url})")
            if author:
                lines.append(f"*作者：{author}* | 👍 {reactions}")
            if summary:
                lines.append(f"")
                lines.append(f"> {summary}")
            if tags:
                lines.append(f"")
                lines.append(f"标签：{', '.join(tags[:5])}")
            lines.append("")

    # 关键词提取建议
    lines.append("## 简历关键词建议")
    lines.append("")
    lines.append("从以上文章中可提取的技术关键词：")
    all_tags = []
    for article in articles:
        all_tags.extend(article.get("tags", []))
    unique_tags = list(set(all_tags))[:10]
    if unique_tags:
        lines.append(f"- {', '.join(unique_tags)}")
    lines.append("")

    return "\n".join(lines)


def format_repo_analysis_document(
    repo: str,
    results: dict[str, Any],
) -> str:
    """将 GitHub 仓库分析结果格式化为 Markdown 文档"""
    lines = [
        f"# 项目分析：{repo}",
        f"",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"",
    ]

    if results.get("error"):
        lines.append(f"*分析失败：{results['error']}*")
        return "\n".join(lines)

    # 基本信息
    basic = results.get("basic_info", {})
    if basic:
        lines.append("## 项目概览")
        lines.append("")
        if basic.get("description"):
            lines.append(f"**描述**：{basic['description']}")
            lines.append("")
        if basic.get("homepage"):
            lines.append(f"**主页**：{basic['homepage']}")
        if basic.get("license"):
            lines.append(f"**许可证**：{basic['license']}")
        if basic.get("topics"):
            lines.append(f"**标签**：{', '.join(basic['topics'])}")
        lines.append("")

    # 指标
    metrics = results.get("metrics", {})
    if metrics:
        lines.append("## 项目指标")
        lines.append("")
        lines.append(f"- ⭐ Stars：{metrics.get('stars', 0):,}")
        lines.append(f"- 🍴 Forks：{metrics.get('forks', 0):,}")
        lines.append(f"- 👀 Watchers：{metrics.get('watchers', 0):,}")
        lines.append(f"- 🐛 Open Issues：{metrics.get('open_issues', 0):,}")
        lines.append(f"- 👥 贡献者：{metrics.get('contributors', 0)}")
        if metrics.get("latest_release"):
            lines.append(f"- 📦 最新版本：{metrics['latest_release']}")
        if metrics.get("commit_frequency"):
            lines.append(f"- 📈 提交频率：{metrics['commit_frequency']}")
        lines.append("")

    # 技术栈
    tech_stack = results.get("tech_stack", [])
    if tech_stack:
        lines.append("## 技术栈")
        lines.append("")
        lines.append("| 语言 | 占比 |")
        lines.append("|------|------|")
        for lang in tech_stack[:5]:
            lines.append(f"| {lang['language']} | {lang['percentage']}% |")
        lines.append("")

    # 核心功能
    features = results.get("key_features", [])
    if features:
        lines.append("## 核心功能")
        lines.append("")
        for feature in features:
            lines.append(f"- {feature}")
        lines.append("")

    # 架构亮点
    arch = results.get("architecture_highlights", [])
    if arch:
        lines.append("## 架构亮点")
        lines.append("")
        for highlight in arch:
            lines.append(f"- {highlight}")
        lines.append("")

    # README 摘要
    readme_summary = results.get("readme_summary", "")
    if readme_summary:
        lines.append("## README 摘要")
        lines.append("")
        lines.append(readme_summary)
        lines.append("")

    # 简历参考建议
    lines.append("## 简历参考价值")
    lines.append("")
    lines.append("从该项目可以参考的技术描述：")
    lines.append("")
    if tech_stack:
        main_langs = [t["language"] for t in tech_stack[:3]]
        lines.append(f"- 技术栈：{', '.join(main_langs)}")
    if features:
        lines.append(f"- 可借鉴的功能描述：")
        for f in features[:3]:
            lines.append(f"  - {f}")
    if metrics.get("stars", 0) > 10000:
        lines.append(f"- 这是一个高 Star 项目，如果你有类似经验可以对标描述")
    lines.append("")

    return "\n".join(lines)
