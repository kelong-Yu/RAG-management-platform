# Frontend

本目录是 AI Chat 的前端应用，基于 `Vue 3 + Vite + TypeScript + Pinia + Element Plus + Tailwind CSS`。

当前前端负责：

- 登录、注册与路由守卫
- 聊天页面与流式消息展示
- 会话列表与历史消息
- 文件管理页面
- 知识库页面
- 管理员控制台
- 引用来源展示
- Markdown / 表格 / LaTeX 公式渲染

## 技术栈

- Vue 3
- Vite
- TypeScript
- Pinia
- Vue Router
- Axios
- Element Plus
- Tailwind CSS
- marked
- KaTeX

## 安装与启动

```bash
cd frontend
npm install
npm run dev
```

默认开发地址：

- `http://localhost:5173`

## 构建

```bash
npm run build
```

## 可选环境变量

```env
VITE_API_BASE_URL=http://localhost:8000
```

如果未配置，前端默认请求本地后端地址。

## 页面路由

当前主要页面：

- `/login`：登录
- `/register`：注册
- `/chat`：聊天
- `/files`：文件管理
- `/knowledge`：知识库
- `/admin`：管理员控制台

## 目录结构

```text
frontend/src/
├─ api/                 # 按领域划分的请求封装
├─ components/          # 可复用组件
│  └─ chat/             # 聊天域组件
├─ composables/         # 组合式逻辑
│  └─ chat/             # 流式消息、图片上传等逻辑
├─ layouts/             # 应用布局
├─ router/              # 路由配置与守卫
├─ stores/              # Pinia 状态
├─ types/               # 全局类型定义
├─ utils/               # 工具函数
└─ views/               # 路由级页面组件
```

## 开发命令

启动开发环境：

```bash
npm run dev
```

生产构建：

```bash
npm run build
```

本项目未单独配置前端测试命令，当前建议至少执行构建验证。

## 前端约定

根据仓库 `CLAUDE.md`，前端遵循以下原则：

- 使用 TypeScript 和组合式 API
- 统一使用 `script setup`
- 页面组件尽量保持薄，复杂逻辑抽到 `composables`
- 接口定义与类型定义同步维护
- 不使用 `any`
- 聊天流式输出必须保持逐 token 增量渲染
- 上传、知识库、RAG 页面至少覆盖 `loading / empty / error / success`

## 当前聊天渲染能力

- 普通 Markdown
- 代码块
- 表格
- 引用块
- KaTeX 数学公式
- 知识库命中内容的完整原文展示

## 相关说明

- 聊天页默认支持知识库模式开关
- 引用来源用于展示命中的原始 chunk
- 命中结构化内容时，后端会把表格/公式直接注入主回答正文
- 前端会对正文与引用统一做 Markdown + KaTeX 渲染
