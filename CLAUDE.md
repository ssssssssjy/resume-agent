# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Resume Agent is an AI-powered resume optimization platform. Users upload a PDF resume, which gets converted to Markdown, then interact with a conversational AI agent to improve their technical descriptions. The system uses a multi-agent architecture: a main agent handles dialogue and file editing, while a research sub-agent searches GitHub and tech articles for reference material.

## Architecture

- **Frontend**: Next.js 15 + React 19 + TypeScript (`apps/frontend/`), communicates with backend via LangGraph SDK and REST APIs
- **Backend**: FastAPI + LangGraph (`apps/backend/`), entry point is `langgraph_server.py`
- **Agent Framework**: Built on `deepagents` library, which wraps LangGraph for multi-agent orchestration
- **Database**: PostgreSQL (production) or SQLite (local dev) for LangGraph checkpoint persistence

### Agent Architecture

The core workflow is in `apps/backend/workflows/graphs/resume_enhancer/builder.py`:

- **Main Agent** — converses with user, reads/edits resume via filesystem middleware tools (`read_file`, `edit_file`, `write_file`, `ls`). Does NOT directly use search tools.
- **Research Sub-Agent** — invoked by main agent via `task` tool. Has access to `search_similar_projects`, `search_tech_articles`, `analyze_github_repo`. Saves detailed results to `/references/` and returns summaries.
- **Middleware**: `EditValidationMiddleware` validates edit_file parameters. `SubAgentMiddleware` (from deepagents) provides the `task` tool.
- **Human-in-the-loop**: `edit_file` calls trigger an interrupt requiring user approval before execution.

### Key Backend Modules

- `apps/backend/langgraph_server.py` — FastAPI app, registers workflows, mounts routers, PDF parsing endpoint
- `apps/backend/infrastructure/langgraph_server.py` — LangGraph Platform compatibility layer
- `apps/backend/config/app_config.py` — Environment-based config, loads `.env.{ENVIRONMENT}` files
- `apps/backend/api/sessions.py` — Session CRUD API
- `apps/backend/api/auth.py` — Token-based authentication
- `apps/backend/workflows/graphs/resume_enhancer/tools/` — Research tools (GitHub API, article search)

### Frontend Structure

- `apps/frontend/app/page.tsx` — Main page integrating PDF upload, markdown editor, and chat
- `apps/frontend/api/langgraph/` — LangGraph SDK client for agent communication
- `apps/frontend/components/resume/` — PDF upload and markdown viewer components
- State management: Zustand. Data fetching: TanStack React Query. UI: Radix UI + Tailwind CSS.

## Common Commands

### Backend

```bash
# Install Python dependencies
uv sync

# Local dev with hot reload (in-memory state, lost on restart)
cd apps/backend
ENVIRONMENT=local uv run uvicorn langgraph_server:app --reload --port 8000

# Local dev with SQLite persistence (state survives restarts)
ENVIRONMENT=local WORKFLOW_SQLITE_PATH=./data/langgraph.db uv run uvicorn langgraph_server:app --reload --port 8000

# Production
ENVIRONMENT=production uv run uvicorn langgraph_server:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd apps/frontend
npm install
npm run dev       # Dev server with Turbopack on port 3000
npm run build     # Production build
npm run lint      # ESLint
```

### Testing & Linting

```bash
# Python tests (pytest with async support, configured in pyproject.toml)
pytest apps/backend/tests/ -v

# Python linting
ruff check apps/backend/

# TypeScript linting
cd apps/frontend && npm run lint
```

### Docker Deployment

```bash
# One-command deploy (--proxy for China servers)
./deploy/deploy.sh --proxy --no-cache

# Manual
docker compose -f deploy/docker-compose.yml up -d --build
docker compose -f deploy/docker-compose.yml logs -f
```

## Environment Configuration

Backend env files live at `apps/backend/.env.{ENVIRONMENT}` (falls back to `.env`):

- `ENVIRONMENT` — `local`, `test`, or `production`
- `OPENAI_API_BASE` — OpenAI-compatible API base URL (required)
- `OPENAI_API_KEY` — API key (required)
- `GENERAL_MODEL` — Model name, e.g. `gpt-4o`, `gemini-3-flash-preview`
- `GITHUB_TOKEN` — For GitHub API searches (optional)
- `WORKFLOW_DATABASE_URL` — PostgreSQL connection string (production)
- `WORKFLOW_SQLITE_PATH` — SQLite path (local persistence)

Frontend: `apps/frontend/.env.production` with `NEXT_PUBLIC_API_URL`.

## Code Conventions

- Python: async-first with FastAPI. Pydantic models for data structures. Ruff for linting (line-length 100, ignores E501).
- TypeScript: Next.js App Router conventions. Radix UI + Tailwind for components.
- pytest configured with `asyncio_mode = "auto"` and `pythonpath = ["apps/backend"]`.
- The project uses Chinese for UI text, comments, and prompts. Technical terms remain in English.
