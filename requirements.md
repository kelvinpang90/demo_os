# Demo 展示网站 — 需求文档

## 1. 项目概述

构建一个面向客户的 HTML Demo 展示网站，访客可按分类浏览各类 Demo，并在页面内通过 iframe 预览。后台提供管理面板，支持上传/删除 Demo 文件夹、增删改查分类。整体视觉风格参考 https://acuventech.com/（深色科技感主页 + 卡片式作品展示）。项目通过 GitHub 管理版本，推送 main 分支后由 GitHub Actions 自动构建并部署到 VPS 上的 Docker 容器。

## 2. 技术栈

| 模块 | 选型 |
|---|---|
| 后端 | Python + FastAPI |
| 模板/前端 | Jinja2 服务端渲染 + 原生 HTML/CSS/JS |
| 数据库 | MySQL（VPS 上现有 Docker 容器） |
| 文件存储 | VPS 本地磁盘卷（挂载到容器，存放各 Demo 静态文件） |
| 部署 | Docker + docker-compose（app 容器 + db 容器），复用现有 Nginx 反向代理与 HTTPS |
| CI/CD | GitHub Actions：push main → 构建镜像 → SSH 到 VPS → 拉取/重启容器 |
| 后台鉴权 | 单一管理员账号 + 密码（session cookie 登录），账号密码存于环境变量 |

## 3. 系统架构

```
浏览器
  ├─ 前台展示站 (/)              —— 分类列表、Demo 卡片、iframe 预览
  └─ 后台管理 (/admin)           —— 登录、分类CRUD、Demo上传/删除

FastAPI App
  ├─ 路由：前台、后台、静态Demo文件服务 (/demos/{slug}/...)
  ├─ 数据库：MySQL（categories, demos 表）
  └─ 文件系统：/data/demos/{demo_slug}/ (含 index.html 及资源)

Docker
  ├─ app 容器（FastAPI，挂载 /data/demos 卷）
  ├─ VPS 上现有 MySQL 容器（新建独立 database + 账号，与 app 容器同网络）
  └─ 现有 Nginx 反向代理 → app 容器
```

## 4. 功能需求

### 4.1 前台展示站

- 首页：Hero 区 + 分类导航 + 各分类下的 Demo 卡片网格（风格参照 acuventech.com 的深色背景、渐变强调色、卡片悬浮效果）。
- Demo 卡片展示缩略图（封面图）、名称、分类标签、浏览次数。未设置缩略图时显示默认占位图。
- 按分类筛选/锚点跳转查看该分类下所有 Demo。
- 点击 Demo 卡片：记录一次浏览（浏览次数 +1），并在页面内通过 iframe 嵌入展示该 Demo 的 index.html，保留返回/关闭入口。
- 响应式布局，适配移动端。

### 4.2 后台管理（/admin）

- 登录页：账号 + 密码，登录后建立 session，未登录访问 /admin/* 自动跳转登录页。
- 分类管理（CRUD）：
  - 新增/编辑分类：名称、slug、排序、描述（可选）。
  - 删除分类：需处理该分类下已有 Demo 的归属（提示先迁移或一并删除）。
  - 列表展示所有分类及排序，支持拖拽或数字调整排序。
- Demo 管理（CRUD）：
  - 新增 Demo：名称、slug、所属分类、描述（可选）、排序、缩略图。
  - 缩略图上传：单独上传图片（jpg/png/webp）作为 Demo 卡片封面，存储于 `/data/thumbnails/{demo_slug}.{ext}`；可随时替换或删除（删除后回退为默认占位图）。
  - Demo 文件上传方式：
    1. 上传 ZIP 压缩包 → 服务端自动解压到对应 Demo 目录；
    2. 浏览器多文件/文件夹拖拽上传 → 保留原始目录结构写入对应 Demo 目录。
  - 校验：解压/上传后的目录中必须存在 `index.html`，否则提示错误并回滚。
  - 删除 Demo：删除数据库记录并清理对应文件目录及缩略图。
  - 列表展示所有 Demo（缩略图、所属分类、浏览次数、创建时间），支持编辑与删除，支持手动重置浏览次数。

### 4.3 文件存储与服务

- 所有 Demo 文件存放于宿主机持久化目录（如 `/data/demos/{demo_slug}/`），通过 Docker 卷挂载到 app 容器。
- 缩略图存放于 `/data/thumbnails/`，同卷挂载，与 Demo 文件分目录管理。
- FastAPI 提供静态文件路由 `/demos/{demo_slug}/...` 对外提供 Demo 内容（供前台 iframe 加载），以及 `/thumbnails/...` 提供封面图。

### 4.4 数据模型（MySQL）

**categories**
- id (PK)
- name
- slug (unique)
- sort_order
- description (nullable)
- created_at / updated_at

**demos**
- id (PK)
- name
- slug (unique，对应文件目录名)
- category_id (FK → categories)
- description (nullable)
- thumbnail_path (nullable，缩略图相对路径)
- view_count (默认 0)
- sort_order
- created_at / updated_at

## 5. 视觉设计规范

参考 acuventech.com 风格：

- 深色主题背景（深灰/近黑），搭配蓝紫色渐变作为强调色（按钮、标题高亮、徽标）。
- 大字号 Hero 标题 + 简短副标题 + CTA 按钮风格的导航。
- 作品/Demo 展示区采用卡片网格，卡片含标题、分类标签、"Live Demo" 风格角标，hover 时有轻微上浮/阴影效果。
- 圆角卡片、柔和阴影、统一的图标风格（emoji 或简单线性图标均可）。
- 字体：现代无衬线字体（如 Inter / system-ui）。
- 整体保持简洁、专业、科技感，避免花哨配色。

## 6. 部署与 CI/CD

- 部署目标：VPS（IP 103.40.204.95），域名 demo.acuventech.com，已配置 HTTPS 与 Nginx 反向代理，需新增对该域名指向本项目 app 容器的转发规则。
- 仓库：新建 GitHub 仓库，包含 app 源码、Dockerfile、docker-compose.yml、GitHub Actions workflow。
- 数据库：直接使用 VPS 上已有的 MySQL 容器，新建独立的 database 与账号供本项目使用；app 容器需与该 MySQL 容器在同一 Docker 网络下（或通过宿主机端口连接）。
- GitHub Actions 流程（push main 触发）：
  1. 构建应用 Docker 镜像；
  2. 推送镜像到镜像仓库（或直接打包传输）；
  3. SSH 登录 VPS，拉取最新镜像/代码；
  4. `docker compose up -d --build` 重启 app 服务，demo 文件卷与现有 MySQL 容器不受影响。
- 环境变量（.env，不入库）：MySQL 连接信息（host/port/database/user/password）、管理员账号密码、session 密钥等。
- 现有 Nginx 反向代理与 HTTPS 配置保持不变，仅需新增/确认对 app 容器端口的转发规则。

## 7. 开发阶段拆分（按独立 Session 交付）

| 阶段 | 内容 | 交付物 |
|---|---|---|
| 阶段一：项目脚手架与数据模型 | 初始化 FastAPI 项目结构、MySQL 连接、ORM 模型（categories/demos）、数据库迁移脚本、本地运行说明 | 可独立运行的空骨架 + 数据库表 |
| 阶段二：前台展示页面 | 首页模板、分类导航、Demo 卡片网格（含缩略图、浏览次数展示）、iframe 预览交互（含浏览计数接口）、响应式样式（参照 acuventech.com 风格） | 可用模拟数据渲染的完整前台页面 |
| 阶段三：后台管理面板 | 登录鉴权、分类CRUD界面与接口、Demo 列表/编辑/删除界面与接口（含缩略图上传与浏览次数展示/重置） | 可登录并完成增删改查的后台 |
| 阶段四：文件上传与部署逻辑 | ZIP上传解压、文件夹拖拽上传、index.html 校验、缩略图上传存储、文件系统与数据库联动 | 后台可实际上传并在前台展示新Demo |
| 阶段五：Docker化与 CI/CD | Dockerfile、docker-compose（app+卷，连接现有 MySQL 容器）、GitHub Actions 自动部署脚本、对接现有 Nginx | 推送代码后自动部署到 VPS 并可访问 |

每个阶段在独立开发 Session 中完成，阶段之间通过约定好的接口/数据结构衔接，前一阶段产出作为后一阶段输入。

## 8. 验收标准

- 前台：分类与 Demo 正常展示，卡片正确显示缩略图（或默认占位图）与浏览次数，点击后 iframe 正确加载 index.html 并使浏览次数 +1，移动端布局正常。
- 后台：管理员可登录，可对分类与 Demo 进行增删改查，可上传/替换/删除缩略图，可查看与重置浏览次数，操作后前台实时反映变化。
- 上传：ZIP 与文件夹拖拽均可成功上传并解压/写入，无 index.html 时给出明确错误提示。
- 部署：本地 docker-compose 一键启动；push 到 GitHub main 分支后，VPS（103.40.204.95）自动更新，并可通过 https://demo.acuventech.com 正常访问，HTTPS 正常。

## 9. 待确认/后续可扩展项

- 不需要多管理员账号；如后续需要操作日志等功能，可作为独立扩展阶段加入。
