import asyncio
import threading

from qdrant_client import models

try:
    from fastembed import SparseTextEmbedding
except ImportError as e:  # pragma: no cover
    raise ImportError("fastembed is required for sparse embeddings") from e

from app.core.config import settings


class SparseTextEmbedder:
    def __init__(self, model_name: str = "Qdrant/bm25"):
        self.model_name = model_name
        self._model = None
        self._init_error = None
        self._lock = threading.Lock()

    def _get_model(self):
        if self._init_error is not None:
            raise self._init_error
        if self._model is None:
            with self._lock:
                if self._init_error is not None:
                    raise self._init_error
                if self._model is None:
                    kwargs = {}
                    if settings.FASTEMBED_CACHE_PATH:
                        kwargs["cache_dir"] = settings.FASTEMBED_CACHE_PATH
                    try:
                        self._model = SparseTextEmbedding(model_name=self.model_name, **kwargs)
                    except Exception as e:
                        self._init_error = e
                        raise
        return self._model

    def _embed_sync(self, texts: list[str]) -> list[models.SparseVector]:
        model = self._get_model()
        raw_embeddings = list(model.embed(texts))
        results = []
        for emb in raw_embeddings:
            indices = emb.indices.tolist()
            values = emb.values.tolist()
            results.append(models.SparseVector(indices=indices, values=values))
        return results

    async def aembed(self, texts: list[str]) -> list[models.SparseVector]:
        return await asyncio.to_thread(self._embed_sync, texts)
