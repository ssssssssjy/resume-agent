"""LangGraph 自托管服务入口点

提供 LangGraph Platform 兼容的 API，使用 FastAPI + 自定义 checkpointer。

启动方式:
    # 开发环境（内存存储）
    ENVIRONMENT=local uv run uvicorn langgraph_server:app --reload --port 8000

    # 开发环境（SQLite 持久化，热重载不丢数据）
    ENVIRONMENT=local WORKFLOW_SQLITE_PATH=./data/langgraph.db uv run uvicorn langgraph_server:app --reload --port 8000

    # 生产环境（PostgreSQL 存储）
    ENVIRONMENT=production uv run uvicorn langgraph_server:app --host 0.0.0.0 --port 8000

环境变量:
    ENVIRONMENT: 环境名称 (local/test/production)
    WORKFLOW_DATABASE_URL: PostgreSQL 连接字符串（可选，不配置则使用内存）
    WORKFLOW_SQLITE_PATH: SQLite 数据库路径（可选，用于本地持久化）
"""

from contextlib import asynccontextmanager

import fitz  # pymupdf
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from api.sessions import router as sessions_router
from api.auth import router as auth_router

from config.app_config import config
from config.langgraph_config import _configure_langgraph_logging, get_checkpointer

# 确保第三方库日志级别被设置（在导入其他模块前）
_configure_langgraph_logging()

from infrastructure.langgraph_server import (
    LangGraphServerConfig,
    create_langgraph_router,
)

# 导入 workflow builders
from workflows.graphs.resume_enhancer.builder import _build_graph as build_resume_enhancer_graph

# Workflow 注册表
WORKFLOW_BUILDERS = {
    "resume_enhancer": build_resume_enhancer_graph,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 获取 checkpointer（根据环境自动选择内存/SQLite/PostgreSQL）
    async with get_checkpointer() as checkpointer:
        # 编译所有 workflow graphs
        graphs = {
            name: builder().compile(checkpointer=checkpointer)
            for name, builder in WORKFLOW_BUILDERS.items()
        }

        # 创建 router 和 service lifespan
        router, get_service_lifespan, assistants_router = create_langgraph_router(
            graphs=graphs,
            config=LangGraphServerConfig(),
        )

        # 动态挂载 router
        app.include_router(router)
        if assistants_router:
            app.include_router(assistants_router)  # 挂载 /assistants 到根路径

        # 启动 service
        async with get_service_lifespan():
            yield


# 创建 FastAPI 应用
app = FastAPI(
    title="Resume Enhancer API",
    description="LangGraph Platform 兼容的简历增强服务",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://47.100.221.91:3000",  # 生产服务器
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 挂载会话管理路由
app.include_router(sessions_router)
# 挂载用户认证路由
app.include_router(auth_router)


@app.get("/health")
async def health_check():
    """健康检查 - 验证数据库连接"""
    from api.database import get_db_context

    try:
        with get_db_context() as conn:
            conn.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=f"Database unavailable: {str(e)}")


MAX_PDF_SIZE = 20 * 1024 * 1024  # 20MB


@app.post("/api/parse-pdf")
async def parse_pdf(file: UploadFile = File(...)):
    """解析 PDF 文件为 Markdown 格式

    使用 pymupdf4llm 提取 PDF 内容，然后用 LLM 转换为结构化 Markdown。
    """
    import re
    from fastapi import HTTPException
    from langchain_openai import ChatOpenAI

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="请上传 PDF 文件")

    content = await file.read()

    if len(content) > MAX_PDF_SIZE:
        raise HTTPException(status_code=413, detail=f"文件过大，最大支持 {MAX_PDF_SIZE // 1024 // 1024}MB")

    try:
        import pymupdf4llm

        # 使用 pymupdf4llm 提取文本（传入字节流，提取所有页面）
        doc = fitz.open(stream=content, filetype="pdf")
        num_pages = len(doc)
        doc.close()

        # pymupdf4llm.to_markdown 需要传入文件路径或字节流，不是 doc 对象
        raw_text = pymupdf4llm.to_markdown(
            fitz.open(stream=content, filetype="pdf"),
            pages=list(range(num_pages)),  # 明确指定所有页面
        )

        # 使用 LLM 转换为结构化 Markdown
        llm = ChatOpenAI(
            model=config.openai_api_key and "gpt-4o-mini" or "deepseek-chat",
            base_url=config.openai_api_base,
            api_key=config.openai_api_key,
            temperature=0,
        )

        prompt = f"""请将以下简历内容转换为结构清晰的 Markdown 格式。

要求：
1. 使用 # 作为姓名/主标题
2. 使用 ## 作为各个板块标题（如：教育背景、工作经历、项目经验、技能等）
3. 使用 ### 作为子标题（如：公司名称、项目名称）
4. 使用 **粗体** 突出重要信息（如：职位、时间、技术栈）
5. 使用 - 列表展示具体内容
6. 保持原有信息完整，不要添加或删除内容
7. 直接输出 Markdown 内容，不要添加任何解释

简历原文：
{raw_text}

Markdown 格式简历："""

        response = await llm.ainvoke(prompt)
        md_content = response.content

        # 清理可能的代码块标记
        md_content = re.sub(r'^```markdown\s*', '', md_content)
        md_content = re.sub(r'^```\s*', '', md_content)
        md_content = re.sub(r'\s*```$', '', md_content)

        return {"markdown": md_content, "pages": num_pages}

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        return {"error": f"PDF 解析失败: {str(e)}", "detail": error_detail, "markdown": ""}
