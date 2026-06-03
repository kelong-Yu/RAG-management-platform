"""
LLM 服务 — 基于 LangChain ChatOpenAI 的 DeepSeek 对话接口。
"""

from collections.abc import AsyncGenerator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings

# 模块级单例 — 复用连接
_llm = ChatOpenAI(
    model="deepseek-chat",
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_API_BASE,
)


def _messages_to_langchain(messages: list[dict]) -> list:
    """将 {"role", "content"} 字典列表转换为 LangChain Message 对象列表。"""
    result = []
    for m in messages:
        role = m["role"]
        content = m["content"]
        if role == "system":
            result.append(SystemMessage(content=content))
        elif role == "assistant":
            result.append(AIMessage(content=content))
        else:
            result.append(HumanMessage(content=content))
    return result


async def chat(message: str) -> str:
    """发送单条消息给 DeepSeek，返回模型回复文本。"""
    response = await _llm.ainvoke([HumanMessage(content=message)])
    return response.content


async def chat_stream(message: str) -> AsyncGenerator[str, None]:
    """流式发送单条消息给 DeepSeek，逐 Token 返回回复内容。"""
    async for chunk in _llm.astream([HumanMessage(content=message)]):
        if chunk.content:
            yield chunk.content


async def chat_with_context(messages: list[dict]) -> str:
    """带上下文的多轮对话（非流式）。

    Args:
        messages: [{"role": "user"|"assistant"|"system", "content": "..."}]

    Returns:
        模型生成的回复内容。
    """
    lc_messages = _messages_to_langchain(messages)
    response = await _llm.ainvoke(lc_messages)
    return response.content


async def chat_stream_with_context(
    messages: list[dict],
) -> AsyncGenerator[str, None]:
    """带上下文的流式多轮对话。

    Args:
        messages: [{"role": "user"|"assistant"|"system", "content": "..."}]

    Yields:
        模型生成的每个文本 Token。
    """
    lc_messages = _messages_to_langchain(messages)
    async for chunk in _llm.astream(lc_messages):
        if chunk.content:
            yield chunk.content
