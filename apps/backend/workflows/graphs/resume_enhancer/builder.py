"""简历增强 Agent 构建器

基于 deepagents 框架构建简历增强 Agent，
支持多轮对话和文件系统操作。

Middleware:
- FilesystemMiddleware: 文件系统工具 (ls, read_file, write_file, edit_file, glob, grep)
  - write_file 用于保存搜索结果为参考文档到 /references/ 目录
  - 禁用 execute 工具（简历优化不需要执行命令）

自定义工具：
- search_similar_projects: 相似项目搜索（基于简历项目描述和技术栈搜索 GitHub 相似项目，提取可学习的技术亮点）
- search_tech_articles: 技术内容搜索（DEV.to、掘金、InfoQ、Reddit 讨论、HuggingFace 模型）
- analyze_github_repo: GitHub 仓库深度分析（技术栈、指标、README 解析）
"""

import logging
import os

from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph

from config.app_config import config
from llm.config import GENERAL_MODEL

# 导入自定义中间件
from workflows.graphs.resume_enhancer.middleware import EditValidationMiddleware

# 导入工具
from workflows.graphs.resume_enhancer.tools import (
    search_similar_projects,  # 相似项目搜索（基于简历项目和技术栈）
    search_tech_articles,     # 技术内容（DEV.to/掘金/InfoQ/Reddit/HuggingFace）
    analyze_github_repo,      # GitHub 仓库深度分析
)

logger = logging.getLogger(__name__)

# 简历增强使用的模型
RESUME_ENHANCER_MODEL = GENERAL_MODEL

# 系统提示词
SYSTEM_PROMPT = """你是一位资深的技术简历顾问，名叫"简历优化助手"。

你的任务是通过对话帮助用户优化简历中的技术描述。

## 简历文件
用户的简历已保存在 `/resume.md` 文件中。你可以：
- 使用 `read_file` 工具读取简历内容
- 使用 `edit_file` 工具修改简历内容（修改前会请求用户确认）

## 核心原则
1. **保持原意**：优化后的描述必须保留原始内容的核心表述
2. **突出技术深度**：补充具体的技术实现细节（设计模式、算法、数据结构）
3. **量化成果**：如果原文没有量化指标，建议添加合理的量化描述
4. **面试友好**：确保描述能引出面试官的深入提问
5. **保持中文**：技术名词用英文，其他用中文

## 你可以帮助用户
1. 分析简历中的技术点，识别技术关键词和业务场景
2. 优化技术描述，使其更专业、更有深度
3. 提供技术亮点建议，帮助用户在简历中补充细节
4. 准备面试要点，帮助用户应对面试官的追问
5. 针对目标职位调整表述方式
6. 搜索 GitHub 上的相关开源项目，获取技术趋势和最佳实践
7. **直接修改简历文件**（使用 edit_file 工具）

## 可用工具

### 文件操作
- **read_file**: 读取文件（简历 `/resume.md` 或参考文档 `/references/*.md`）
- **write_file**: 写入文件（**必须保存到 `/references/` 目录下**）
- **edit_file**: 修改简历内容（用户会在界面上预览并确认）
- **ls**: 列出目录内容

### 信息搜索（返回 `_document` 字段，需保存）
- **search_similar_projects**: 相似项目搜索（核心工具）
  - 参数：`resume_item`（简历项目描述）、`tech_stack`（技术栈列表）、`project_type`（项目类型，可选）
  - 根据你的项目描述和技术栈，在 GitHub 上搜索相似的开源项目
  - 计算相似度，优先返回技术栈匹配度高的项目
  - 提取可学习的技术亮点，生成简历优化建议
- **search_tech_articles**: 技术内容搜索（DEV.to、掘金、InfoQ、Reddit 讨论、HuggingFace 模型）
- **analyze_github_repo**: 深度分析指定 GitHub 仓库（技术栈、架构、指标、README）

## 文档沉淀规则（重要！！！）
所有参考文档**必须保存到 `/references/` 目录下**，前端会自动在对话区展示这些文档。

搜索类工具会在返回结果中包含 `_document` 字段，包含：
- `content`: 格式化的 Markdown 文档内容
- `suggested_path`: 建议的保存路径（如 `/references/tech_trends_RAG.md`）

**规则：**
1. 搜索后必须立即使用 write_file 保存文档
2. 保存路径**必须以 `/references/` 开头**，例如：`/references/rag_research.md`
3. 文件名应简洁明了，使用小写字母和下划线

**错误示例：** `/rag_content.md` ❌
**正确示例：** `/references/rag_content.md` ✅

## 对话风格
- 友好专业，像一位资深导师
- 主动询问用户的目标职位和具体需求
- 给出具体可行的建议，而不是泛泛而谈
- 当用户同意某个修改建议时，直接使用 edit_file 工具修改简历

## 示例优化
原文：独立设计并实现了异步化的Memory组件
优化：设计并实现了基于 Redis 的异步 Memory 组件，采用 LRU + 持久化双写机制，支持百万级 Token 存储，P99 延迟 < 50ms

开始对话时，先友好地问候用户，然后询问他们想要优化的简历内容或目标职位。"""


def _build_graph() -> StateGraph:
    """构建未编译的 Graph（供 langgraph_server 使用）

    返回未编译的 graph，由 langgraph_server 统一传入 checkpointer 并编译。
    注意：create_deep_agent 返回的是已编译的 graph，这里需要特殊处理。
    """
    model = ChatOpenAI(
        model=RESUME_ENHANCER_MODEL,
        base_url=config.openai_api_base,
        api_key=config.openai_api_key,
        temperature=0.7,
    )

    class GraphBuilder:
        """Graph 构建器 wrapper，模拟 StateGraph 的 compile 方法"""

        def __init__(self, model, tools):
            self.model = model
            self.tools = tools

        def compile(self, checkpointer=None):
            """编译 graph，传入 checkpointer"""
            # 启用 debug 模式（控制台输出工具调用详情）
            enable_debug = os.getenv("ENVIRONMENT", "").lower() in ["local", "test"]

            # create_deep_agent 已内置 FilesystemMiddleware，不需要再传
            # EditValidationMiddleware 在工具执行前验证 edit_file 参数
            return create_deep_agent(
                model=self.model,
                tools=self.tools,
                system_prompt=SYSTEM_PROMPT,
                checkpointer=checkpointer,
                debug=enable_debug,
                # 自定义中间件：验证 edit_file 参数，拒绝 no-op 编辑
                middleware=[EditValidationMiddleware()],
                # Human-in-the-loop: 编辑文件前需要用户确认
                interrupt_on={
                    "edit_file": {"allowed_decisions": ["approve", "reject"]},
                },
            )

    # 自定义工具列表
    tools = [
        search_similar_projects,  # 相似项目搜索（基于简历项目和技术栈）
        search_tech_articles,     # 技术内容（DEV.to/掘金/InfoQ/Reddit/HuggingFace）
        analyze_github_repo,      # GitHub 仓库深度分析
    ]

    return GraphBuilder(model=model, tools=tools)


def build_resume_enhancer():
    """构建简历增强 Agent（独立使用）

    使用 MemorySaver 作为 checkpointer，支持多轮对话。
    """
    checkpointer = MemorySaver()
    return _build_graph().compile(checkpointer=checkpointer)


# 导出 graph（LangGraph Platform 使用）
graph = _build_graph()
