"""
Smoke tests — 验证关键模块能正确导入，核心逻辑不抛异常。

这些测试覆盖 P0-P4 阶段的主链路（不含真实外部 API 调用）。
"""
import pytest
from fastapi.testclient import TestClient


# ── 模块导入测试 ──────────────────────────────────────────────────────────


def test_config_imports():
    """Settings 应该包含所有必要配置项。"""
    from app.core.config import settings

    assert settings.APP_NAME == "AI Chat"
    assert settings.DATABASE_URL
    assert settings.JWT_SECRET_KEY
    assert settings.UPLOAD_DIR
    assert settings.MAX_UPLOAD_SIZE_MB > 0
    assert len(settings.ALLOWED_IMAGE_MIME_TYPES) > 0
    assert "application/pdf" in settings.ALLOWED_DOCUMENT_MIME_TYPES


def test_models_import():
    """所有 ORM 模型应能正确导入。"""
    from app.models import (
        Attachment,
        Conversation,
        Document,
        DocumentChunk,
        Message,
        User,
    )
    # 验证模型类存在
    assert Attachment.__tablename__
    assert Conversation.__tablename__
    assert Document.__tablename__
    assert DocumentChunk.__tablename__
    assert Message.__tablename__
    assert User.__tablename__


def test_schemas_import():
    """所有 Pydantic schema 应能正确导入。"""
    from app.schemas.chat import (
        ChatRequest,
        ChatResponse,
        CitationSchema,
        ConversationResponse,
        MessageResponse,
    )
    from app.schemas.attachment import AttachmentResponse
    from app.schemas.document import DocumentResponse, DocumentChunkResponse

    # 快速验证 schema 实例化
    req = ChatRequest(message="测试消息")
    assert req.message == "测试消息"
    assert req.use_rag is False
    assert req.attachment_ids == []

    citation = CitationSchema(
        document_name="测试文档.pdf",
        page_number=1,
        chunk_index=0,
        content_snippet="这是一段测试内容",
        similarity=0.95,
    )
    assert citation.similarity == 0.95


def test_services_import():
    """所有 Service 模块应能正确导入。"""
    from app.services import (
        chat_service,
        conversation_service,
        document_service,
        embedding_service,
        file_service,
        llm_service,
        retriever_service,
        user_service,
    )
    assert chat_service is not None
    assert file_service is not None
    assert document_service is not None
    assert retriever_service is not None


# ── 文件校验逻辑测试 ──────────────────────────────────────────────────────


def test_filename_sanitization():
    """文件名清洗应正确处理危险字符。"""
    from app.services.file_service import _sanitize_filename

    assert _sanitize_filename("test.pdf") == "test.pdf"
    assert _sanitize_filename("Test File.PDF") == "Test_File.pdf"  # 空格被替换为下划线
    assert _sanitize_filename("../etc/passwd") != "../etc/passwd"
    # 不应包含路径分隔符
    result = _sanitize_filename("a/b/c.pdf")
    assert "/" not in result
    assert "\\" not in result


def test_file_validation_logic():
    """文件校验函数应拒绝非法输入。"""
    from app.services.file_service import _validate_file
    from unittest.mock import MagicMock

    # 模拟合法的图片上传
    mock_file = MagicMock()
    mock_file.size = 1024
    mock_file.content_type = "image/png"
    mock_file.filename = "test.png"

    # 不应该抛出异常
    _validate_file(mock_file)

    # 模拟非法类型
    mock_file.content_type = "application/exe"
    mock_file.filename = "test.exe"
    with pytest.raises(ValueError, match="不支持的文件类型"):
        _validate_file(mock_file)


def test_chunk_splitting():
    """文档切片逻辑应正确分页。"""
    from app.services.document_service import _chunk_pages

    pages = [
        {"page_number": 1, "text": "第一页内容。" * 500},
        {"page_number": 2, "text": "第二页内容。" * 500},
    ]

    chunks = _chunk_pages(pages, chunk_size=500, chunk_overlap=50)
    assert len(chunks) > 0
    for chunk in chunks:
        assert "chunk_index" in chunk
        assert "page_number" in chunk
        assert "content" in chunk
        assert len(chunk["content"]) > 0


def test_title_generation():
    """会话标题生成应正确处理各种输入。"""
    from app.services.conversation_service import _build_conversation_title

    assert _build_conversation_title("") == "新对话"
    assert _build_conversation_title("   ") == "新对话"
    assert len(_build_conversation_title("这是一个很长的测试问题" * 10)) <= 27
    # "帮我" 前缀应被剥离
    title = _build_conversation_title("帮我写一份报告")
    assert not title.startswith("帮我")


# ── API 路由测试（无数据库） ──────────────────────────────────────────────


@pytest.fixture
def client():
    """创建不带数据库连接的测试客户端。"""
    from app.main import app
    return TestClient(app)


def test_health_endpoint(client):
    """健康检查端点应返回 200。"""
    response = client.get("/health")
    assert response.status_code == 200


def test_chat_capabilities_endpoint(client):
    """聊天能力端点应返回 200。"""
    response = client.get("/chat/capabilities")
    assert response.status_code == 200
    data = response.json()
    assert "vision_capable" in data


def test_unauthorized_access(client):
    """未认证请求应被拦截。"""
    # 会话列表需要认证
    response = client.get("/chat/conversations")
    assert response.status_code in (401, 403)


def test_file_upload_validation(client):
    """未认证上传应被拦截。"""
    response = client.post("/files/upload")
    assert response.status_code in (401, 403, 422)


# ── 安全校验测试 ──────────────────────────────────────────────────────────


def test_jwt_token_flow():
    """JWT 令牌生成和验证流程。"""
    from app.core.security import create_access_token, verify_token

    token = create_access_token({"sub": "42"})
    assert token is not None
    assert isinstance(token, str)

    payload = verify_token(token)
    assert payload is not None
    assert payload["sub"] == "42"


def test_invalid_token_rejected():
    """无效令牌应被拒绝。"""
    from app.core.security import verify_token

    assert verify_token("invalid-token-string") is None
    assert verify_token("") is None


# ── RAG prompt 构建测试 ───────────────────────────────────────────────────


def test_rag_system_prefix():
    """RAG system prompt 应包含关键指令。"""
    from app.services.chat_service import RAG_SYSTEM_PREFIX

    assert "知识库问答助手" in RAG_SYSTEM_PREFIX
    assert "检索到的文档片段" in RAG_SYSTEM_PREFIX
    assert "[来源:" in RAG_SYSTEM_PREFIX


# ── Retriever citation 测试 ────────────────────────────────────────────────


def test_citation_dataclass():
    """Citation 数据类应正确创建。"""
    from app.services.retriever_service import Citation

    c = Citation(
        chunk_id=1,
        document_id=10,
        document_name="测试.pdf",
        chunk_index=0,
        page_number=3,
        content="这是测试内容",
        similarity=0.85,
    )
    assert c.document_name == "测试.pdf"
    assert c.page_number == 3
    assert c.similarity == 0.85


# ── Rate limiting 测试 ─────────────────────────────────────────────────────


def test_rate_limit_configuration():
    """限流配置应覆盖关键接口。"""
    from app.main import _RATE_LIMITS

    assert "/chat/" in _RATE_LIMITS
    assert "/chat/stream" in _RATE_LIMITS
    assert "/files/upload" in _RATE_LIMITS
    assert "/auth/login" in _RATE_LIMITS
    assert "/auth/register" in _RATE_LIMITS
