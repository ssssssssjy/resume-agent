# Resume Agent

基于 LangGraph 的智能简历优化 Agent，通过对话帮助用户优化简历中的技术描述。

## 功能

- **对话式简历优化** - 上传简历后与 AI 助手对话，获取优化建议
- **GitHub 项目搜索** - 搜索相似开源项目，提取可学习的技术亮点
- **技术文章搜索** - 从 DEV.to、掘金、Reddit、HuggingFace 获取技术内容
- **实时编辑预览** - 修改简历前预览变更，确认后生效 (Human-in-the-loop)
- **参考文档沉淀** - 搜索结果自动保存为 Markdown 文档

## 架构

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Frontend      │────▶│   Backend API   │────▶│   PostgreSQL    │
│   (Next.js)     │     │   (FastAPI)     │     │   (Checkpoint)  │
│   :3000         │     │   :8123         │     │   :5433         │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Resume Enhancer    │
                    │      Agent          │
                    │  (deepagents)       │
                    └─────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
            ┌───────────────┐    ┌───────────────┐
            │  主 Agent     │    │ 研究子 Agent  │
            │  - 对话       │    │  - 项目搜索   │
            │  - 文件编辑   │    │  - 文章搜索   │
            └───────────────┘    │  - 仓库分析   │
                                 └───────────────┘
```

## 快速开始

### 本地开发

```bash
# 安装依赖
uv sync

# 启动后端
cd apps/backend
uvicorn main:app --reload --port 8000

# 启动前端
cd apps/frontend
npm install
npm run dev
```

### Docker 部署

```bash
# 一键部署（国内服务器需要代理）
./deploy/deploy.sh --proxy --no-cache

# 参数说明
--proxy      # 启用代理（默认 127.0.0.1:7890）
--no-cache   # 不使用 Docker 缓存
--ip=xxx     # 自定义服务器 IP
```

## 配置

### 后端 (`apps/backend/.env`)

```bash
# OpenAI 兼容 API
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_API_KEY=sk-xxx

# 模型（支持 gpt-4o、gemini-3-flash-preview 等）
GENERAL_MODEL=gemini-3-flash-preview

# GitHub Token（用于项目搜索）
GITHUB_TOKEN=ghp_xxx
```

### 前端 (`apps/frontend/.env.production`)

```bash
NEXT_PUBLIC_API_URL=http://your-server-ip:8123
```

## 技术栈

- **后端**: FastAPI, LangGraph, deepagents
- **前端**: Next.js, TypeScript, TailwindCSS
- **数据库**: PostgreSQL (LangGraph checkpoint)
- **部署**: Docker, Docker Compose

## 目录结构

```
resume_agent/
├── apps/
│   ├── backend/                 # 后端服务
│   │   ├── infrastructure/      # LangGraph Server 兼容层
│   │   └── workflows/           # Agent 工作流
│   │       └── graphs/
│   │           └── resume_enhancer/
│   │               ├── builder.py      # Agent 构建
│   │               ├── middleware/     # 自定义中间件
│   │               └── tools/          # 搜索工具
│   └── frontend/                # 前端服务
├── deploy/                      # 部署配置
│   ├── deploy.sh               # 部署脚本
│   ├── docker-compose.yml
│   └── Dockerfile*
└── docs/                        # 文档
```

## Agent 工具

| 工具 | 说明 |
|------|------|
| `read_file` | 读取简历或参考文档 |
| `edit_file` | 修改简历（需用户确认） |
| `write_file` | 保存参考文档到 `/references/` |
| `task` | 启动研究子 Agent 执行搜索任务 |

### 研究子 Agent 工具

| 工具 | 说明 |
|------|------|
| `search_similar_projects` | 搜索 GitHub 相似项目 |
| `search_tech_articles` | 搜索技术文章（DEV.to/掘金/Reddit/HuggingFace） |
| `analyze_github_repo` | 深度分析 GitHub 仓库 |

## License

MIT
