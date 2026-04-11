import logging

from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)


class RetrievedChunk(BaseModel):
    content: str
    source: str
    score: float
    metadata: dict | None = None


class HybridRetriever:
    def __init__(
        self,
        qdrant_client,
        dense_embedder,
        sparse_embedder,
        reranker,
        rewriter,
    ):
        self.qdrant_client = qdrant_client
        self.dense_embedder = dense_embedder
        self.sparse_embedder = sparse_embedder
        self.reranker = reranker
        self.rewriter = rewriter

    @staticmethod
    def _to_chunk(point, score: float) -> RetrievedChunk:
        payload = point.payload or {}
        return RetrievedChunk(
            content=str(payload.get("content", "")),
            source=str(payload.get("source", "unknown")),
            score=score,
            metadata=dict(payload.get("meta_data") or {}),
        )

    async def retrieve(self, query: str) -> list[RetrievedChunk]:
        rewritten = await self.rewriter.rewrite(query)
        dense_vec = await self.dense_embedder.aembed_query(rewritten)

        sparse_vecs = await self.sparse_embedder.aembed([rewritten])
        sparse_vec = sparse_vecs[0]

        scored_points = await self.qdrant_client.query_hybrid(
            dense_vector=dense_vec,
            sparse_vector=sparse_vec,
            dense_limit=settings.RETRIEVER_DENSE_TOPK,
            sparse_limit=settings.RETRIEVER_SPARSE_TOPK,
        )

        if not scored_points:
            return []

        documents = [str((p.payload or {}).get("content", "")) for p in scored_points]

        reranked = await self.reranker.rerank(
            rewritten, documents, top_n=settings.RETRIEVER_FINAL_TOPK
        )

        results = []
        for r in reranked:
            if 0 <= r.index < len(scored_points):
                results.append(self._to_chunk(scored_points[r.index], r.score))

        return results
