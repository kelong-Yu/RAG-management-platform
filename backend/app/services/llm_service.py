"""
LLM 服务 — 双模型架构：DeepSeek（纯文本）+ DashScope（多模态视觉）。
"""

import base64
from collections.abc import AsyncGenerator
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings

# ── 模块级单例 ──────────────────────────────────────────────────────────

# 纯文本模型（DeepSeek V3）
_llm = ChatOpenAI(
    model="deepseek-chat",
    api_key=settings.DEEPSEEK_API_KEY,
    base_url=settings.DEEPSEEK_API_BASE,
)

# 多模态视觉模型（DashScope Qwen）
_vision_llm: ChatOpenAI | None = None
if settings.VISION_MODEL:
    _vision_api_key = settings.DASH_SCOPE_API_KEY
    _vision_api_base = settings.DASH_SCOPE_API_BASE
    if _vision_api_key and _vision_api_base:
        _vision_llm = ChatOpenAI(
            model=settings.VISION_MODEL,
            api_key=_vision_api_key,
            base_url=_vision_api_base,
        )


# ── 视觉能力检测 ───────────────────────────────────────────────────────


def is_vision_capable() -> bool:
    """检测当前是否已配置多模态视觉模型。"""
    return _vision_llm is not None


def _get_llm_for_call(image_paths: list[str] | None = None):
    """根据是否有图片选择模型：有图用视觉模型，无图用文本模型。"""
    if image_paths and _vision_llm is not None:
        return _vision_llm
    return _llm


def _encode_image_to_base64(file_path: str) -> str:
    """将本地图片编码为 base64 data URI。"""
    path = Path(file_path)
    ext = path.suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    mime = mime_map.get(ext, "image/png")
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{data}"


def _build_multimodal_content(text: str, image_paths: list[str]) -> list[dict]:
    """构建多模态消息内容（文本 + 图片）。

    Args:
        text: 用户文本消息
        image_paths: 图片文件的本地路径列表

    Returns:
        LangChain HumanMessage 兼容的 content 列表
    """
    content: list[dict] = [{"type": "text", "text": text}]
    for path in image_paths:
        data_uri = _encode_image_to_base64(path)
        content.append({
            "type": "image_url",
            "image_url": {"url": data_uri},
        })
    return content


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


async def chat_stream_with_multimodal_context(
    messages: list[dict],
    image_paths: list[str],
) -> AsyncGenerator[str, None]:
    """带上下文和图片的流式多模态对话。

    将最后一条 user message 替换为多模态格式（文本 + base64 图片），
    使用视觉模型生成回复。无视觉模型时回退为纯文本。

    Args:
        messages: [{"role": "user"|"assistant"|"system", "content": "..."}]
        image_paths: 图片文件的本地路径列表

    Yields:
        模型生成的每个文本 Token。
    """
    if not messages:
        return

    llm = _get_llm_for_call(image_paths)

    # 无视觉模型 或 无图片 → 回退为纯文本
    if not image_paths or _vision_llm is None:
        lc_messages = _messages_to_langchain(messages)
        async for chunk in llm.astream(lc_messages):
            if chunk.content:
                yield chunk.content
        return

    # 视觉模型 + 图片 → 多模态消息
    lc_messages = _messages_to_langchain(messages[:-1])
    last = messages[-1]
    multimodal_content = _build_multimodal_content(last["content"], image_paths)
    lc_messages.append(HumanMessage(content=multimodal_content))

    async for chunk in llm.astream(lc_messages):
        if chunk.content:
            yield chunk.content


async def chat_with_multimodal_context(
    messages: list[dict],
    image_paths: list[str],
) -> str:
    """带上下文和图片的非流式多模态对话。"""
    if not messages:
        return ""

    llm = _get_llm_for_call(image_paths)

    if not image_paths or _vision_llm is None:
        lc_messages = _messages_to_langchain(messages)
        response = await llm.ainvoke(lc_messages)
        return response.content

    lc_messages = _messages_to_langchain(messages[:-1])
    last = messages[-1]
    multimodal_content = _build_multimodal_content(last["content"], image_paths)
    lc_messages.append(HumanMessage(content=multimodal_content))

    response = await llm.ainvoke(lc_messages)
    return response.content
