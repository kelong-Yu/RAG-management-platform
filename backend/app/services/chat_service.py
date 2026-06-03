"""
聊天服务 — 编排用户消息到 LLM 的完整流程。
"""

from collections.abc import AsyncGenerator

from app.services.llm_service import chat as llm_chat
from app.services.llm_service import chat_stream as llm_chat_stream


async def chat(message: str) -> str:
    """接收用户消息，调用 LLM 并返回回复。

    Args:
        message: 用户输入的文本。

    Returns:
        模型生成的回复内容。
    """
    return await llm_chat(message)


async def chat_stream(message: str) -> AsyncGenerator[str, None]:
    """接收用户消息，流式调用 LLM 逐 Token 返回。

    Args:
        message: 用户输入的文本。

    Yields:
        模型生成的每个文本 Token。
    """
    async for token in llm_chat_stream(message):
        yield token
