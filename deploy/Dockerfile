FROM python:3.11-slim

WORKDIR /app

# 从官方镜像复制 uv 二进制（约 10MB，非常快）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件（利用 Docker 缓存，依赖不变时跳过安装）
COPY pyproject.toml uv.lock* /app/

# 使用 uv 安装依赖到系统 Python
RUN uv export --frozen --no-dev --no-hashes -o requirements.txt 2>/dev/null || \
    uv pip compile pyproject.toml -o requirements.txt && \
    uv pip install --system -r requirements.txt && \
    rm requirements.txt

# 复制源码
COPY apps/backend/ /app/apps/backend/

# 复制环境配置文件到镜像（如果有）
# COPY .env.production /app/.env.production

# 设置 Python 路径
ENV PYTHONPATH=/app/apps/backend

# 暴露端口
EXPOSE 8000

# 健康检查（使用 /health 端点）
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令
CMD ["uvicorn", "langgraph_server:app", "--host", "0.0.0.0", "--port", "8000"]
