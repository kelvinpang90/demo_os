# Demo 展示网站

## 本地运行

1. 创建虚拟环境并安装依赖

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. 复制 `.env.example` 为 `.env`，并填写本地 MySQL 连接信息（需提前创建好对应数据库与账号）

   ```bash
   copy .env.example .env
   ```

3. 执行数据库迁移，创建 `categories` / `demos` 表

   ```bash
   alembic upgrade head
   ```

4. （可选）首次运行时导入演示数据

   ```bash
   python -m app.seed
   ```

5. 启动开发服务器

   ```bash
   uvicorn app.main:app --reload
   ```

6. 访问 http://127.0.0.1:8000/health 确认服务正常（返回 `{"status": "ok"}`）。
7. 访问 http://127.0.0.1:8000/admin 进入后台管理（账号密码见 `.env` 中的 `ADMIN_USERNAME` / `ADMIN_PASSWORD`）。

## 项目结构

```
app/
  main.py       FastAPI 入口
  config.py     环境变量配置
  database.py   SQLAlchemy engine/session
  models.py     ORM 模型 (Category, Demo)
  seed.py       演示数据导入脚本
  admin/        后台管理路由（登录、分类/Demo CRUD）
alembic/         数据库迁移脚本
```

## Docker 部署

### 本地构建与运行

```bash
copy .env.example .env
# 按需修改 .env（数据库连接、管理员账号、SECRET_KEY 等）

docker compose build
docker compose up -d
```

容器启动时会自动执行 `alembic upgrade head` 再启动 uvicorn，监听容器内 `8000` 端口，
默认映射到宿主机 `127.0.0.1:8000`。`./data/demos` 与 `./data/thumbnails` 通过卷挂载持久化。

### VPS 部署

1. 在 VPS 上克隆本仓库到部署目录（如 `/opt/demo-os`）。
2. 在该目录下创建 `.env`（参考 `.env.example`）：
   - `DB_HOST` 填写 VPS 上现有 MySQL 容器的容器名/服务名（与 app 容器需在同一 docker 网络）。
   - `IMAGE` 填写 `ghcr.io/<owner>/<repo>:latest`（小写），用于 `docker compose pull` 拉取 CI 构建好的镜像。
3. `docker-compose.yml` 中已配置 `data_net`（MySQL 容器所在网络）和 `proxy_net`
   （Nginx 容器所在网络），与 VPS 上现有 aisearch 项目一致，通常无需修改；
   如有差异可用 `docker network ls` 核实后调整。
4. 把 [deploy/nginx/demo_os.conf](deploy/nginx/demo_os.conf) 复制到 Nginx 的 `conf.d` 目录
   （参照现有 vhost 的部署路径，如 `/srv/infra/nginx/conf.d/demo_os.conf`），
   reload 后即可通过 `https://demo.acuventech.com` 访问。该配置通过容器名
   `demo_os_backend:8000` 转发请求，要求 app 容器与 Nginx 容器在同一个 docker 网络（`proxy_net`）。

### GitHub Actions 自动部署

`.github/workflows/deploy.yml` 在 push 到 `main` 分支时会：

1. 构建镜像并推送到 GitHub Container Registry（`ghcr.io/<owner>/<repo>`）。
2. SSH 登录 VPS，在部署目录执行 `git pull` + `docker compose pull` + `docker compose up -d`。

需要在仓库 Settings → Secrets 中配置：

| Secret | 说明 |
|---|---|
| `VPS_HOST` | VPS IP（如 103.40.204.95） |
| `VPS_USER` | SSH 登录用户名 |
| `VPS_SSH_KEY` | 部署用的 SSH 私钥 |
| `VPS_DEPLOY_PATH` | 项目在 VPS 上的部署目录路径 |
