"""简历增强 Agent 构建器

基于 deepagents 框架构建简历增强 Agent，
支持多轮对话和文件系统操作。

架构：
- 主 Agent: 负责与用户对话、分析简历、修改文件
- 研究子 Agent: 负责执行搜索任务，自动保存文档，返回简洁摘要

Middleware:
- FilesystemMiddleware: 文件系统工具 (ls, read_file, write_file, edit_file, glob, grep)
- SubAgentMiddleware: 提供 task 工具启动子 Agent 执行研究任务
- EditValidationMiddleware: 验证 edit_file 参数

自定义工具（研究子 Agent 专用）：
- search_similar_projects: 相似项目搜索
- search_tech_articles: 技术内容搜索
- analyze_github_repo: GitHub 仓库深度分析
"""

import logging
import os

from deepagents import create_deep_agent
from deepagents.middleware.subagents import SubAgent
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

# 研究子 Agent 的系统提示词
RESEARCH_AGENT_PROMPT = """你是简历优化的研究助手，专门负责执行搜索和分析任务。

## 你的职责
1. 执行 GitHub 项目搜索、技术文章搜索等研究任务
2. 分析搜索结果，提取有价值的信息
3. **自动保存详细的研究文档**到 `/references/` 目录
4. 返回**简洁的摘要**给主 Agent

## 工作流程
1. 根据任务描述执行搜索
2. 使用 write_file 将详细结果保存到 `/references/` 目录
3. 返回简洁摘要（包含：找到多少项目、Top 3 推荐、核心建议、文档保存路径）

## 返回格式示例
```
找到 8 个相似项目：

**Top 3 推荐：**
1. OpenSPG/KAG (⭐8,516) - 知识图谱增强 RAG
2. Mintplex-Labs/anything-llm (⭐54,213) - 企业级 RAG 应用
3. labring/FastGPT (⭐27,076) - 知识库问答平台

**核心建议：**
- 补充 knowledge-graph、multi-hop-reasoning 等关键词
- 添加量化指标（如检索准确率、响应延迟）
- 参考高星项目的技术描述方式

详细报告已保存到 `/references/similar_projects_RAG.md`
```

## 注意事项
- 文档路径必须以 `/references/` 开头
- 返回内容要简洁，详细信息放在文档中
- 如果搜索无结果，也要说明原因"""

# 主 Agent 系统提示词
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
6. **使用研究子 Agent 搜索相关项目和技术文章**
7. **直接修改简历文件**（使用 edit_file 工具）

## 可用工具

### 文件操作
- **read_file**: 读取文件（简历 `/resume.md` 或参考文档 `/references/*.md`）
- **write_file**: 写入文件（保存到 `/references/` 目录下）
- **edit_file**: 修改简历内容（用户会在界面上预览并确认）
- **ls**: 列出目录内容

### 研究任务（使用 task 工具）
当需要搜索 GitHub 项目、技术文章时，使用 `task` 工具启动研究子 Agent：
- **subagent_type**: "research"
- **description**: 详细描述搜索任务，例如：
  - "搜索与 RAG、LangChain 相关的 GitHub 项目，分析技术亮点"
  - "搜索 '基于多跳检索的问答系统' 相关项目，提取可学习的技术点"

研究子 Agent 会：
1. 执行搜索
2. 自动保存详细文档到 `/references/`
3. 返回简洁摘要

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

    # 研究子 Agent 使用的工具
    research_tools = [
        search_similar_projects,  # 相似项目搜索（基于简历项目和技术栈）
        search_tech_articles,     # 技术内容（DEV.to/掘金/InfoQ/Reddit/HuggingFace）
        analyze_github_repo,      # GitHub 仓库深度分析
    ]

    # 定义研究子 Agent
    research_subagent: SubAgent = {
        "name": "research",
        "description": "执行 GitHub 项目搜索、技术文章搜索等研究任务，自动保存详细文档到 /references/ 目录，返回简洁摘要给主 Agent",
        "system_prompt": RESEARCH_AGENT_PROMPT,
        "tools": research_tools,
    }

    class GraphBuilder:
        """Graph 构建器 wrapper，模拟 StateGraph 的 compile 方法"""

        def __init__(self, model, research_subagent):
            self.model = model
            self.research_subagent = research_subagent

        def compile(self, checkpointer=None):
            """编译 graph，传入 checkpointer"""
            # 启用 debug 模式（控制台输出工具调用详情）
            enable_debug = os.getenv("ENVIRONMENT", "").lower() in ["local", "test"]

            # create_deep_agent 已内置 SubAgentMiddleware，通过 subagents 参数传入
            return create_deep_agent(
                model=self.model,
                tools=[],  # 主 Agent 不直接使用搜索工具，通过 task 调用子 Agent
                system_prompt=SYSTEM_PROMPT,
                checkpointer=checkpointer,
                debug=enable_debug,
                subagents=[self.research_subagent],  # 传入研究子 Agent
                middleware=[
                    EditValidationMiddleware(),  # 验证 edit_file 参数
                ],
                # Human-in-the-loop: 编辑文件前需要用户确认
                interrupt_on={
                    "edit_file": {"allowed_decisions": ["approve", "reject"]},
                },
            )

    return GraphBuilder(model=model, research_subagent=research_subagent)


def build_resume_enhancer():
    """构建简历增强 Agent（独立使用）

    使用 MemorySaver 作为 checkpointer，支持多轮对话。
    """
    checkpointer = MemorySaver()
    return _build_graph().compile(checkpointer=checkpointer)


# 导出 graph（LangGraph Platform 使用）
graph = _build_graph()
