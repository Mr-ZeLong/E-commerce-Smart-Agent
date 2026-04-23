import hashlib

import httpx

from app.core.config import settings


class QwenEmbeddings:
    """通义千问 Embedding API 适配器"""

    def __init__(self, base_url: str, api_key: str, model: str, dimensions: int):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self._cache: dict[str, list[float]] = {}

    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        uncached_texts: list[str] = []
        uncached_indices: list[int] = []

        for idx, text in enumerate(texts):
            key = self._cache_key(text)
            if key in self._cache:
                results.append(self._cache[key])
            else:
                results.append([])
                uncached_texts.append(text)
                uncached_indices.append(idx)

        if uncached_texts:
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(
                        f"{self.base_url}/embeddings",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.model,
                            "input": uncached_texts,
                            "dimensions": self.dimensions,
                        },
                        timeout=10.0,
                    )
                    response.raise_for_status()
                    data = response.json()
                    embeddings = [item["embedding"] for item in data["data"]]
                    for text, emb, idx in zip(
                        uncached_texts, embeddings, uncached_indices, strict=True
                    ):
                        results[idx] = emb
                        self._cache[self._cache_key(text)] = emb
                except (httpx.HTTPError, OSError):
                    logger = __import__("logging").getLogger(__name__)
                    logger.warning("Embedding API call failed or timed out, returning zero vectors")
                    for idx in uncached_indices:
                        results[idx] = [0.0] * self.dimensions

        return results

    async def aembed_query(self, text: str) -> list[float]:
        results = await self.aembed_documents([text])
        return results[0]


def create_embedding_model() -> QwenEmbeddings:
    return QwenEmbeddings(
        base_url=settings.OPENAI_BASE_URL,
        api_key=settings.OPENAI_API_KEY.get_secret_value(),
        model=settings.EMBEDDING_MODEL,
        dimensions=settings.EMBEDDING_DIM,
    )
