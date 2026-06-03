# AI Chat Project Rules

## Project Context

- 当前项目是一个基于 `Vue 3 + Vite + TypeScript + FastAPI + PostgreSQL + JWT + LangChain` 的 AI Chat 应用
- 当前已实现能力包括：PostgreSQL 接入、用户注册、用户登录、JWT 认证、导航守卫、聊天页面、会话管理、聊天记录
- 后续开发主线以根目录 `tasks.md` 为准，优先推进：
  - `P0` 工程底座
  - `P1` 通用本地上传
  - `P2` PDF 文档入库
  - `P3` RAG 检索问答
  - `P4` 图片上传与多模态聊天
  - `P5` 稳定性与上线准备

## Tech Stack

### Frontend

- Vue 3
- Vite
- TypeScript
- Pinia
- Axios
- Element Plus
- TailwindCSS

### Backend

- FastAPI
- PostgreSQL
- SQLAlchemy 2.0
- JWT
- uv
- LangChain

## Phase Execution Rules

- 开始任何编码前，必须先阅读根目录 `CLAUDE.md` 和 `tasks.md`
- 默认按 `tasks.md` 分阶段推进，每次只执行一个阶段
- 不允许提前实现下一个阶段的能力，除非用户明确要求
- 编码前先基于现有代码输出实施计划，再开始修改文件
- 所有改动必须与当前阶段直接相关，避免无关重构
- 若阶段涉及前后端联动，必须同步检查并更新：
  - `backend/app/models`
  - `backend/app/schemas`
  - `backend/app/services`
  - `backend/app/api`
  - `frontend/src/views`
  - `frontend/src/api`
  - `frontend/src/types`
  - `frontend/src/stores`

## General Rules

- 所有新增代码必须与现有项目结构保持一致，优先增量修改
- 先阅读现有代码再修改，优先复用已有模块、命名风格和分层方式
- 前后端字段命名保持一致，接口变更时必须同步修改两侧代码
- 不允许泄露 `.env` 中的密钥、令牌或其他敏感信息
- 修改功能后必须做最小必要验证，不能只改代码不验证
- 输出时必须明确区分“已完成”“未完成”“后续建议”

## Frontend Rules

- 使用 TypeScript
- 使用组合式 API
- 使用 `script setup`
- 所有接口必须有明确类型定义
- 不允许使用 `any`
- 页面组件保持薄，复杂逻辑优先抽离到独立函数、store 或 api 层
- 新增接口时同步补充前端类型定义
- 不要破坏现有登录态、路由守卫和聊天基础功能
- 聊天页面的流式输出必须保持逐 token 增量渲染
- 上传、知识库、RAG 相关页面必须至少覆盖以下状态：
  - `loading`
  - `empty`
  - `error`
  - `success`
- 聊天记录相关功能前端至少支持：
  - 会话列表
  - 历史消息加载
  - 在当前会话继续发送消息
- 新增附件相关能力时，不能破坏现有纯文本聊天链路
- 引用来源、上传状态、文档状态必须可视化，不要只在控制台输出

## Backend Rules

- 路由层只负责参数校验、鉴权、调用 service、返回响应
- 不允许在 Router 中编写业务逻辑
- Service 层负责业务逻辑
- 数据访问使用 SQLAlchemy session
- 所有新增接口必须补充 schema
- 所有用户私有数据查询必须校验资源归属，防止越权
- 新增 ORM 模型时使用 SQLAlchemy 2.0 typed ORM 风格
- 涉及时间字段时优先提供 `created_at`，必要时提供 `updated_at`
- 业务错误必须返回明确、稳定、可理解的错误信息
- 上传、文档处理、检索、消息生成等关键链路要保留可追踪日志

## Database And Migration Rules

- 禁止继续依赖 `Base.metadata.create_all()` 作为正式建表方案
- 所有表结构变更必须通过 Alembic 迁移提交
- 新增表时必须同步考虑：
  - 主键
  - 外键
  - 索引
  - 唯一约束
  - 状态字段
  - 时间字段
- 数据库配置必须与 `docker-compose.yml` 和环境变量保持一致
- 涉及上传、文档、chunk、向量数据时，优先建模再写业务逻辑

## Upload And File Rules

- 图片和 PDF 必须共用统一附件体系，不允许写两套平行上传逻辑
- 所有本地文件统一走独立的文件存储 service，禁止在 router 中直接写磁盘
- 所有上传都必须做：
  - 文件大小限制
  - MIME 白名单
  - 扩展名校验
  - 文件名清洗
  - 路径安全校验
- 所有文件都必须记录元数据，至少包括：
  - 上传用户
  - 原始文件名
  - 存储文件名
  - 文件路径
  - MIME 类型
  - 文件大小
  - 状态
  - 创建时间
- 用户只能查看、删除、使用自己的附件

## PDF And Knowledge Base Rules

- PDF 处理流程必须与聊天接口解耦
- 文档处理流程必须拆分为明确阶段：
  - `uploaded`
  - `parsing`
  - `chunking`
  - `ready`
  - `failed`
- PDF 文本提取失败时，必须记录失败原因
- 文档切片必须保留足够元数据，至少包括：
  - `document_id`
  - `chunk_index`
  - `page_number`
  - `content`
- 文档删除时，必须明确考虑附件、chunk、索引数据是否同步清理

## RAG Rules

- RAG 必须拆分为独立步骤：
  - 文档接收
  - 文本提取
  - 切片
  - Embedding
  - 索引
  - 检索
  - 生成
- 检索逻辑和生成逻辑必须解耦，禁止把整套 RAG 直接写死在聊天路由里
- 回答必须返回引用来源，至少包含文档名和片段内容，能返回页码时优先返回
- 当知识库无命中时，必须明确回退为普通聊天流程
- 不允许伪造引用或伪造知识库命中结果
- 所有检索都必须限定在当前用户可访问的知识范围内

## Multimodal Rules

- 图片上传和图片理解是两个不同层次，必须分开设计
- 即使模型暂不支持视觉，也要先支持图片附件上传、展示和消息绑定
- 若当前模型不支持图像理解，前后端都必须明确提示降级行为
- 若接入视觉模型，必须保持文本聊天链路继续可用
- 图片能力优先复用统一附件模型，不允许新增独立图片资源体系

## Chat Domain Rules

- 聊天领域核心模型使用 `Conversation` 和 `Message`
- `Message.role` 至少支持 `system`、`user`、`assistant`
- 用户发送消息时先保存 user message，再调用模型
- AI 回复成功后保存 assistant message
- 流式回复时先累计完整文本，流结束后再保存 assistant message
- 模型上下文只允许读取当前登录用户可访问的数据
- 会话列表按最近更新时间倒序返回
- 会话标题可默认使用首条用户消息截断生成
- 新增附件消息、知识库聊天、多模态聊天时，优先扩展现有聊天体系，而不是另建平行体系

## API Rules

- 普通接口返回结构使用 schema，不直接返回随意字典
- 流式接口与普通接口职责明确
- 新增聊天接口时，前后端都要同步更新字段定义
- 设计接口时优先复用现有 `/chat` 相关模块，不随意拆出平行体系
- 上传、知识库、RAG、新增资源接口时，优先保持 REST 风格和清晰命名
- 需要返回任务状态时，返回结构必须稳定，避免前端猜字段

## UI Rules

- `App.vue` 只保留根组件职责，只包裹 router view 或核心布局
- 聊天页面优先保证功能正确，其次再做视觉增强
- 对现有页面进行改造时，优先保持已有交互习惯和布局结构稳定
- 文件上传、知识库、引用来源、错误提示都应以用户可理解的方式展示
- 不要为了新功能破坏当前登录、会话切换、历史消息加载体验

## Testing Rules

- 前端改动后至少执行构建验证
- 后端改动后至少执行接口级、测试级或最小 smoke 验证
- 涉及鉴权、聊天记录、会话归属时优先补充有价值的测试
- 涉及上传、PDF、RAG 时优先补充关键主链路验证
- 避免编写低价值、重复实现细节的测试
- 若未补测试，必须说明原因和当前风险

## Git Rules

- 只提交与当前任务相关的文件
- 不要自动提交无关改动
- 完成功能后提醒进行 git 提交
- commit message 尽量简洁明确，优先使用规范前缀，例如：
  - `chore(core): add migrations and document foundation`
  - `feat(upload): add local attachment upload flow`
  - `feat(kb): add pdf ingestion and chunk pipeline`
  - `feat(rag): add retrieval augmented chat with citations`
  - `feat(chat): support image attachments and multimodal flow`

## Output Rules

- 完成任务后必须说明：
  - 修改了哪些文件
  - 为什么这样改
  - 做了哪些验证
  - 当前阶段还有哪些限制或后续优化点
- 若本次只完成阶段中的一部分，必须明确指出未完成项
- 若发现当前阶段应该先修底座问题，必须先说明原因，再编码

## Working Style

- 前后端联动需求必须同步检查两侧代码
- 优先做“当前阶段最小可用版本”，不要一次性把后续所有能力混进来
- 新需求若涉及上传、知识库、RAG、多模态，默认先检查是否与 `tasks.md` 当前阶段冲突
- 若实现路径存在明显歧义，先给出可选方案和推荐方案，再开始改代码
