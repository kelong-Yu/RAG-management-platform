# AI Chat Project Rules

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

## General Rules
- 所有新增代码必须与现有项目结构保持一致，优先增量修改，不做无关重构
- 先阅读现有代码再修改，优先复用现有模块、命名风格和分层方式
- 前后端字段命名保持一致，接口定义变更时必须同步修改两侧代码
- 不允许泄露 `.env` 中的密钥、令牌或其他敏感信息
- 修改功能后必须做最小必要验证，不能只改代码不验证

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
- 涉及聊天记录功能时，前端至少支持：
  - 会话列表
  - 历史消息加载
  - 在当前会话继续发送消息

## Backend Rules
- 路由层只负责参数校验、鉴权、调用 service、返回响应
- 不允许在 Router 中编写业务逻辑
- Service 层负责业务逻辑
- 数据访问使用 SQLAlchemy session
- 所有新增接口必须补充 schema
- 所有用户私有数据查询必须校验资源归属，防止越权
- 新增 ORM 模型时使用 SQLAlchemy 2.0 typed ORM 风格
- 涉及时间字段时优先提供 `created_at`，必要时提供 `updated_at`

## Chat Domain Rules
- 聊天领域核心模型使用 `Conversation` 和 `Message`
- `Message.role` 至少支持 `system`、`user`、`assistant`
- 用户发送消息时先保存 user message，再调用模型
- AI 回复成功后保存 assistant message
- 流式回复时先累计完整文本，流结束后再保存 assistant message
- 模型上下文必须包含当前登录用户身份信息和当前会话历史消息
- 模型只允许读取当前用户当前会话的历史，不允许串入其他用户数据
- 会话列表按最近更新时间倒序返回
- 会话标题可默认使用首条用户消息截断生成
- 涉及聊天、会话、消息、用户身份相关需求时，默认检查是否需要同时修改：
  - `backend/app/models`
  - `backend/app/schemas`
  - `backend/app/services`
  - `backend/app/api`
  - `frontend/src/views`
  - `frontend/src/types` 或 `frontend/src/api`

## API Rules
- 普通接口返回结构使用 schema，不直接返回随意字典
- 流式接口与普通接口职责明确
- 新增聊天接口时，前后端都要同步更新字段定义
- 设计接口时优先复用现有 `/chat` 相关模块，不随意拆出平行体系

## UI Rules
- `App.vue` 只保留根组件职责，只包裹 router view 或核心布局
- 聊天页面优先保证功能正确，其次再做视觉增强
- 对现有页面进行改造时，优先保持已有交互习惯和布局结构稳定

## Testing Rules
- 前端改动后至少执行构建验证
- 后端改动后至少执行接口级或测试级验证
- 涉及鉴权、聊天记录、会话归属时优先补充有价值的测试
- 避免编写低价值、重复实现细节的测试

## Git Rules
- 只提交与当前任务相关的文件
- 不要自动提交无关改动
- 完成功能后提醒进行 git 提交
- commit message 尽量简洁明确，优先使用规范前缀，例如：
  - `feat(chat): add conversation history`
  - `fix(chat): persist streamed assistant reply`

## Working Style
- 前后端联动需求必须同步检查两侧代码
- 输出结果时说明：
  - 修改了哪些文件
  - 为什么这样改
  - 做了哪些验证
  - 还有哪些限制或后续优化点

# AI-Chat 开发约束（新增）

## 总原则
- 严格按阶段开发，只实现当前阶段目标，不提前混入下一阶段能力。
- 保持前后端分层清晰：路由层只做参数校验和响应封装，业务逻辑放 service 层。
- 新增后端接口时必须同步补充 schema、类型定义、错误码说明。
- 所有新增能力优先复用现有项目结构，不重写认证、聊天、会话主链路。

## 数据库与迁移
- 禁止继续依赖 `Base.metadata.create_all()` 作为正式建表方案。
- 所有表结构变更必须通过 Alembic 迁移提交。
- 新表命名、索引、外键、唯一约束必须在设计时补齐，不能等功能完成后再补。

## 文件上传
- 所有本地文件统一走 `FileStorageService`，禁止在路由函数里直接写磁盘。
- 所有上传都必须做大小限制、MIME 白名单、扩展名校验、文件名清洗。
- 所有文件都要记录元数据：原始文件名、存储路径、MIME、大小、上传用户、创建时间、处理状态。
- 图片与 PDF 共用统一附件体系，避免两套上传逻辑。

## RAG 约束
- RAG 必须拆分为：文档接收、文本提取、切片、Embedding、索引、检索、生成 7 个明确步骤。
- 检索与生成必须解耦，禁止把“向量检索”直接写死在聊天接口里。
- 回答必须返回引用来源，至少包含文档名和命中片段。
- 当知识库无命中时，必须显式回退到普通聊天流程，不能伪造引用。

## 工程与测试
- 新增重要后端能力时，至少补 1 个接口测试或 smoke test。
- 上传、解析、RAG 相关日志必须包含可追踪的 document_id / attachment_id / conversation_id。
- 所有环境变量新增时必须更新 `.env.example` 或等价配置说明。
- Python 版本优先使用稳定版本（建议 3.11/3.12），新增依赖要确认兼容性。

## 前端约束
- 前端新增上传/RAG 功能时，必须补 loading、empty、error、success 四类状态。
- 前端所有新增接口都要补 TypeScript 类型，不允许直接使用 `any`。
- 聊天页新增附件能力时，不能破坏原有纯文本发送链路。
- 引用来源、附件列表、处理状态要可视化，不把后台状态藏起来。