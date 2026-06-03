"""
聊天服务 — 编排用户消息到 LLM 的完整流程。
"""

from app.services.llm_service import chat as llm_chat


async def chat(message: str) -> str:
    """接收用户消息，调用 LLM 并返回回复。

    Args:
        message: 用户输入的文本。

    Returns:
        模型生成的回复内容。
    """
    return await llm_chat(message)
