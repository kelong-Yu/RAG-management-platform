"""
LLM 服务 — 基于 LangChain ChatOpenAI 的 DeepSeek 对话接口。
"""

from collections.abc import AsyncGenerator

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings

# 模块级单例 — 复用连接
_llm = ChatOpenAI(
    model="deepseek-chat",
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_API_BASE,
)


async def chat(message: str) -> str:
    """发送消息给 DeepSeek，返回模型回复文本。

    Args:
        message: 用户输入的文本。

    Returns:
        模型生成的回复内容。
    """
    response = await _llm.ainvoke([HumanMessage(content=message)])
    return response.content


async def chat_stream(message: str) -> AsyncGenerator[str, None]:
    """流式发送消息给 DeepSeek，逐 Token 返回回复内容。

    Args:
        message: 用户输入的文本。

    Yields:
        模型生成的每个文本 Token。
    """
    async for chunk in _llm.astream([HumanMessage(content=message)]):
        if chunk.content:
            yield chunk.content
