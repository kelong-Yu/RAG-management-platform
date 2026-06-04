"""
Embedding Service — 文本向量化，使用 DashScope (OpenAI 兼容 API)。

配置自动从 Settings 读取，默认复用 DASHSCOPE_API_KEY/BASE。
"""

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# 如果未单独配置 Embedding，回退使用 DashScope 配置
EMBEDDING_API_KEY = settings.EMBEDDING_API_KEY or settings.DASH_SCOPE_API_KEY
EMBEDDING_API_BASE = settings.EMBEDDING_API_BASE or settings.DASH_SCOPE_API_BASE
EMBEDDING_MODEL = settings.EMBEDDING_MODEL
EMBEDDING_DIM = 1536  # text-embedding-v2 输出维度


async def generate_embedding(text: str) -> list[float]:
    """为单个文本生成 embedding 向量。

    Raises:
        RuntimeError: API 调用失败
    """
    embeddings = await _call_embedding_api([text])
    return embeddings[0]


async def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """批量为文本列表生成 embedding 向量。"""
    if not texts:
        return []

    # 分批处理，避免单次请求过大
    batch_size = 25
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        batch_embeddings = await _call_embedding_api(batch)
        all_embeddings.extend(batch_embeddings)

    return all_embeddings


async def _call_embedding_api(texts: list[str]) -> list[list[float]]:
    """调用 OpenAI 兼容的 Embedding API。

    DashScope text-embedding-v2 支持批量输入。
    """
    if not EMBEDDING_API_KEY:
        raise RuntimeError("未配置 EMBEDDING_API_KEY 或 DASH_SCOPE_API_KEY")

    url = f"{EMBEDDING_API_BASE.rstrip('/')}/embeddings"

    payload: dict[str, Any] = {
        "model": EMBEDDING_MODEL,
        "input": texts,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {EMBEDDING_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Embedding API error: %s", e)
            raise RuntimeError(f"Embedding API 调用失败: {e}") from e

    data = response.json()

    # OpenAI 兼容格式: {"data": [{"embedding": [...], "index": 0}, ...]}
    items = sorted(data.get("data", []), key=lambda x: x.get("index", 0))

    if len(items) != len(texts):
        raise RuntimeError(
            f"Embedding API 返回数量不匹配: 期望 {len(texts)}, 实际 {len(items)}"
        )

    return [item["embedding"] for item in items]
