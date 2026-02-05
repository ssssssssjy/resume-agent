# Resume Agent 内部记录

## 服务器

- **IP**: `47.100.221.91`
- **前端**: http://47.100.221.91:3000
- **后端 API**: http://47.100.221.91:8123

## 部署

```bash
# 一键部署（国内服务器需要代理）
./deploy/deploy.sh --proxy --no-cache

# 参数说明
--proxy      # 启用代理（默认 127.0.0.1:7890）
--no-cache   # 不使用 Docker 缓存
--ip=xxx     # 自定义服务器 IP
```

部署前先建立 SSH 隧道转发本地代理：
```bash
ssh -R 7890:127.0.0.1:7890 root@47.100.221.91
```

## 常用命令

```bash
cd deploy

# 查看状态
docker compose ps

# 查看日志
docker compose logs -f

# 重启
docker compose restart

# 停止
docker compose down
```

## 环境变量

**后端** (`apps/backend/.env`)
```
OPENAI_API_BASE=https://newapi.tsingyuai.com/v1
OPENAI_API_KEY=sk-xxx
GITHUB_TOKEN=ghp_xxx
```

**前端** (`apps/frontend/.env.production`)
```
NEXT_PUBLIC_API_URL=http://47.100.221.91:8123
```

> 前端变量是构建时注入，修改后需 `--no-cache` 重新构建

## 端口

| 服务 | 内部 | 外部 |
|-----|-----|-----|
| 前端 | 3000 | 3000 |
| 后端 | 8000 | 8123 |
| PostgreSQL | 5432 | 5433 |
