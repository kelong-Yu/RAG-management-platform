# Backend

本目录是 AI Chat 的后端服务，基于 `FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL + JWT`。

当前后端负责：

- 用户注册、登录、身份鉴权
- 会话与消息持久化
- 文件上传与附件元数据管理
- PDF 文档入库、切片与状态管理
- 默认知识库同步
- RAG 检索与引用返回
- 管理员接口
- 流式聊天与多模态降级处理

## 技术栈

- FastAPI
- SQLAlchemy 2.0
- Alembic
- PostgreSQL
- pgvector
- python-jose
- PyMuPDF
- uv

## 目录结构

```text
backend/
├─ alembic/              # 数据库迁移
├─ app/
│  ├─ api/               # 路由层
│  ├─ core/              # 配置与安全
│  ├─ db/                # 数据库会话
│  ├─ models/            # ORM 模型
│  ├─ schemas/           # Pydantic schema
│  └─ services/          # 业务逻辑
├─ tests/                # smoke tests
├─ Default-know-base.md  # 默认知识库
├─ pyproject.toml
└─ README.md
```

## 环境要求

- Python 3.14+
- `uv`
- PostgreSQL 16+

## 安装与启动

```bash
cd backend
uv sync
copy app/.env.example app/.env
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

默认启动地址：

- API：`http://localhost:8000`
- OpenAPI：`http://localhost:8000/docs`

## 启动时自动执行的内容

应用启动时会尝试：

- 执行开发阶段的 `create_all` 安全兜底
- 确保默认管理员账号存在：`admin / admin`
- 同步默认知识库 `Default-know-base.md`

## 环境变量

环境变量文件位置：

- `backend/app/.env`
- 示例模板：`backend/app/.env.example`

常用变量：

```env
DATABASE_URL=postgresql://admin:admin@localhost:5432/aichat
JWT_SECRET_KEY=change-me-in-production
UPLOAD_DIR=C:\Users\<you>\.ai-chat\uploads
MAX_UPLOAD_SIZE_MB=20

DASH_SCOPE_API_KEY=
DASH_SCOPE_API_BASE=
DEEPSEEK_API_KEY=
DEEPSEEK_API_BASE=

EMBEDDING_API_KEY=
EMBEDDING_API_BASE=
EMBEDDING_MODEL=text-embedding-v2

VISION_MODEL=
```

说明：

- `UPLOAD_DIR` 默认不放在 Git 仓库内，避免私有文件误提交
- 若 Embedding 不可用，系统会回退到关键词检索
- 若视觉模型未配置，图片聊天会明确降级为纯文本能力

## 数据库与迁移

生成迁移：

```bash
uv run alembic revision --autogenerate -m "your message"
```

执行迁移：

```bash
uv run alembic upgrade head
```

回滚一步：

```bash
uv run alembic downgrade -1
```

## 测试

```bash
uv run pytest tests/test_smoke.py
```

## 核心接口分组

- `auth`：注册、登录、当前用户
- `chat`：普通聊天、流式聊天、会话管理
- `files`：上传、列表、删除
- `documents`：知识库文档、切片详情、重试处理
- `admin`：用户管理、知识库管理、默认知识库同步
- `health`：健康检查

## 后端约定

本仓库的后端分层遵循 `CLAUDE.md` 中的规则：

- Router 只负责参数校验、鉴权和响应
- Service 层承接业务逻辑
- 所有新增接口都应补充 schema
- 所有表结构变更都应通过 Alembic 提交
- 所有用户私有数据查询都必须校验资源归属

## 当前知识库能力

- PDF 文档处理
- 默认知识库自动导入
- 混合检索：语义检索 + 关键词检索
- 引用来源返回
- 表格和公式结构化内容优先保留
- 命中结构化内容时直接并入主回答正文
