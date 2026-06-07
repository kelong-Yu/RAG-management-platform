# AI Chat

一个基于 `Vue 3 + Vite + TypeScript + FastAPI + PostgreSQL + JWT` 的全栈 AI 聊天应用，支持会话管理、知识库 RAG、默认知识库、混合检索、图片附件和管理员能力。

本项目同时包含给 AI 协作开发使用的规范文档：

- `CLAUDE.md`：仓库级开发约束、分层规则、RAG/上传/管理员能力约定
- `tasks.md`：按阶段推进的开发任务清单与执行提示词

## 当前能力

- 用户注册、登录、JWT 认证
- 路由守卫与登录态恢复
- 会话列表、历史消息、流式聊天
- 本地文件上传与文件管理
- PDF 文档入库、切片、状态流转
- 默认知识库 `backend/Default-know-base.md` 自动导入
- RAG 检索问答
- 混合检索：语义检索 + 关键词检索
- 引用来源展示
- 图片附件上传与多模态聊天降级支持
- 管理员控制台：用户管理、知识库管理、默认知识库同步
- 表格与公式类知识内容渲染增强

## 技术栈

- 前端：`Vue 3`、`Vite`、`TypeScript`、`Pinia`、`Vue Router`、`Element Plus`、`Tailwind CSS`
- 后端：`FastAPI`、`SQLAlchemy 2.0`、`Alembic`、`PostgreSQL`、`pgvector`、`JWT`
- 文档与检索：`PyMuPDF`、Embedding、混合检索、RAG
- 开发工具：`uv`、`npm`

## 仓库结构

```text
AI-Chat/
├─ backend/          # FastAPI 后端、数据库模型、迁移、RAG 服务
├─ frontend/         # Vue 前端、页面、组件、状态管理
├─ CLAUDE.md         # AI 协作开发规则
├─ tasks.md          # 分阶段开发任务
├─ docker-compose.yml
└─ README.md
```

## 关键设计

- 统一附件体系：图片和 PDF 共用同一套附件模型与上传链路
- 聊天领域模型：基于 `Conversation` 和 `Message` 组织上下文与消息持久化
- 知识库流程：`uploaded -> parsing -> chunking -> embedding -> ready / failed`
- 检索范围控制：仅检索“当前用户可访问文档 + 系统默认知识库”
- 默认知识库策略：`backend/Default-know-base.md` 自动导入，系统可读、不可删除
- 回答策略：普通文本由模型生成，命中表格/公式时会把结构化原文直接并入主回答正文

## 快速启动

### 1. 准备环境

- Node.js 20+
- Python 3.14+
- `uv`
- Docker Desktop 或本地 PostgreSQL

### 2. 启动数据库

在仓库根目录执行：

```bash
docker compose up -d
```

默认数据库配置与 `docker-compose.yml` 一致：

- Host：`localhost`
- Port：`5432`
- Database：`aichat`
- Username：`admin`
- Password：`admin`

### 3. 启动后端

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

后端默认会在启动时自动：

- 确保存在管理员账号 `admin / admin`
- 尝试同步默认知识库 `backend/Default-know-base.md`

### 4. 启动前端

另开一个终端：

```bash
cd frontend
npm install
npm run dev
```

默认前端开发地址：

- Frontend：`http://localhost:5173`
- Backend API：`http://localhost:8000`

## 常用命令

### 根目录

```bash
docker compose up -d
docker compose down
```

### 后端

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
uv run pytest tests/test_smoke.py
```

### 前端

```bash
cd frontend
npm install
npm run dev
npm run build
```

## 配置说明

后端环境变量通过 `backend/app/.env` 读取，常用项包括：

- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `UPLOAD_DIR`
- `MAX_UPLOAD_SIZE_MB`
- `DASH_SCOPE_API_KEY`
- `DASH_SCOPE_API_BASE`
- `DEEPSEEK_API_KEY`
- `DEEPSEEK_API_BASE`
- `EMBEDDING_API_KEY`
- `EMBEDDING_API_BASE`
- `EMBEDDING_MODEL`
- `VISION_MODEL`

前端可选环境变量：

- `VITE_API_BASE_URL`

## 测试与验证

建议至少执行以下验证：

```bash
cd backend
uv run pytest tests/test_smoke.py

cd ../frontend
npm run build
```

## AI 协作开发建议

如果你打算继续让 AI 在这个仓库里开发，建议固定遵循下面流程：

1. 先让 AI 阅读 `CLAUDE.md` 和 `tasks.md`
2. 每次只执行一个阶段，不要跨阶段堆功能
3. 先输出实施计划，再开始修改代码
4. 完成后要求 AI 说明修改文件、验证结果、剩余风险
5. 每完成一个阶段单独提交一次 Git

推荐提示词模板已整理在 `tasks.md` 中。

## 相关文档

- [后端说明](file:///e:/Code/AI-Chat/backend/README.md)
- [前端说明](file:///e:/Code/AI-Chat/frontend/README.md)
- [开发规则](file:///e:/Code/AI-Chat/CLAUDE.md)
- [阶段任务](file:///e:/Code/AI-Chat/tasks.md)
