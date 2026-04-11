import asyncio

from fastembed import SparseTextEmbedding
from qdrant_client import models

from app.core.config import settings


class SparseTextEmbedder:
    def __init__(self, model_name: str = "Qdrant/bm25"):
        self.model_name = model_name
        kwargs = {}
        if settings.FASTEMBED_CACHE_PATH:
            kwargs["cache_dir"] = settings.FASTEMBED_CACHE_PATH
        self._model = SparseTextEmbedding(model_name=self.model_name, **kwargs)

    def _embed_sync(self, texts: list[str]) -> list[models.SparseVector]:
        raw_embeddings = list(self._model.embed(texts))
        results = []
        for emb in raw_embeddings:
            indices = emb.indices.tolist()
            values = emb.values.tolist()
            results.append(models.SparseVector(indices=indices, values=values))
        return results

    async def aembed(self, texts: list[str]) -> list[models.SparseVector]:
        return await asyncio.to_thread(self._embed_sync, texts)
