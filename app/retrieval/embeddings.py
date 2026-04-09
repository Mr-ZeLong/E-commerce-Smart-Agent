import functools

import httpx
from langchain_core.embeddings import Embeddings

from app.core.config import settings


class QwenEmbeddings(Embeddings):
    """通义千问 Embedding API 适配器"""

    def __init__(self, base_url: str, api_key: str, model: str, dimensions: int):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("请使用异步方法 aembed_documents")

    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError("请使用异步方法 aembed_query")

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "input": texts,
                    "dimensions": self.dimensions
                },
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            return [item["embedding"] for item in data["data"]]

    async def aembed_query(self, text: str) -> list[float]:
        results = await self.aembed_documents([text])
        return results[0]


@functools.lru_cache(maxsize=1)
def get_embedding_model() -> QwenEmbeddings:
    return QwenEmbeddings(
        base_url=settings.OPENAI_BASE_URL,
        api_key=settings.OPENAI_API_KEY,
        model=settings.EMBEDDING_MODEL,
        dimensions=settings.EMBEDDING_DIM,
    )


def clear_embedding_model_cache() -> None:
    """Clear the cached embedding model singleton (useful in tests)."""
    get_embedding_model.cache_clear()
