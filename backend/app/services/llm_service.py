"""
LLM 服务 — 基于 LangChain ChatOpenAI 的 DeepSeek 对话接口。
"""

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
