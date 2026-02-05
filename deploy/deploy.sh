#!/bin/bash

# Resume Agent 部署脚本
# 用法：
#   ./deploy.sh              # 普通部署（无代理）
#   ./deploy.sh --proxy      # 使用代理构建（适用于国内服务器）
#   ./deploy.sh --no-cache   # 不使用缓存构建
#   ./deploy.sh --proxy --no-cache  # 组合使用

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 默认配置
USE_PROXY=false
PROXY_URL="http://127.0.0.1:7890"
NO_CACHE=""
SERVER_IP="47.100.221.91"

for arg in "$@"; do
    case $arg in
        --proxy)
            USE_PROXY=true
            shift
            ;;
        --proxy=*)
            USE_PROXY=true
            PROXY_URL="${arg#*=}"
            shift
            ;;
        --no-cache)
            NO_CACHE="--no-cache"
            shift
            ;;
        --ip=*)
            SERVER_IP="${arg#*=}"
            shift
            ;;
    esac
done

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    log_error "Docker 未安装，请先安装 Docker"
    exit 1
fi

# 检查 docker compose 是否可用
if ! docker compose version &> /dev/null; then
    log_error "Docker Compose 未安装，请先安装 Docker Compose"
    exit 1
fi

log_info "开始部署 Resume Agent..."

# 进入项目目录
cd "$PROJECT_DIR"

# 如果使用代理，设置 git 代理
if [ "$USE_PROXY" = true ]; then
    log_info "设置 git 代理..."
    git config --global http.proxy "$PROXY_URL"
    git config --global https.proxy "$PROXY_URL"
    export http_proxy="$PROXY_URL"
    export https_proxy="$PROXY_URL"
fi

# 拉取最新代码（如果是 git 仓库）
if [ -d ".git" ]; then
    log_info "拉取最新代码..."
    git pull || log_warn "Git pull 失败，使用本地代码继续"
fi

# 生成前端环境变量文件
log_info "配置前端 API 地址: http://$SERVER_IP:8123"
echo "NEXT_PUBLIC_API_URL=http://$SERVER_IP:8123" > apps/frontend/.env.production

# 检查 .env 文件
if [ ! -f "apps/backend/.env" ]; then
    log_warn ".env 文件不存在，创建示例文件..."
    cat > apps/backend/.env << 'EOF'
# OpenAI 兼容 API
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_API_KEY=your-api-key-here

# GitHub Token（可选）
GITHUB_TOKEN=your-github-token-here
EOF
    log_error "请编辑 apps/backend/.env 文件，填入正确的 API 密钥"
    exit 1
fi

# 构建镜像
log_info "构建 Docker 镜像..."

BUILD_ARGS=""
NETWORK_ARG=""

if [ "$USE_PROXY" = true ]; then
    log_info "使用代理: $PROXY_URL"
    BUILD_ARGS="--build-arg HTTP_PROXY=$PROXY_URL --build-arg HTTPS_PROXY=$PROXY_URL"
    NETWORK_ARG="--network host"

    # 测试代理是否可用
    if curl -x "$PROXY_URL" -s --connect-timeout 5 https://www.google.com > /dev/null 2>&1; then
        log_info "代理连接正常"
    else
        log_warn "代理可能不可用，继续尝试构建..."
    fi
fi

# 构建后端镜像
log_info "构建后端镜像..."
docker build $NO_CACHE $NETWORK_ARG -f deploy/Dockerfile -t resume-agent:latest $BUILD_ARGS .

# 构建前端镜像
log_info "构建前端镜像..."
docker build $NO_CACHE $NETWORK_ARG -f deploy/Dockerfile.frontend -t resume-agent-frontend:latest $BUILD_ARGS .

# 启动服务
log_info "启动服务..."
cd deploy
docker compose down 2>/dev/null || true
docker compose up -d

# 等待服务启动
log_info "等待服务启动..."
sleep 10

# 检查服务状态
log_info "检查服务状态..."
docker compose ps

# 显示访问地址
echo ""
log_info "部署完成！"
echo ""
echo "访问地址："
echo "  前端界面: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost'):3000"
echo "  后端 API: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost'):8123"
echo ""
echo "常用命令："
echo "  查看日志: cd $SCRIPT_DIR && docker compose logs -f"
echo "  重启服务: cd $SCRIPT_DIR && docker compose restart"
echo "  停止服务: cd $SCRIPT_DIR && docker compose down"
