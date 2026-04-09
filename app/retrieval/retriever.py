from dataclasses import dataclass

from app.core.config import settings


@dataclass
class RetrievedChunk:
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

    async def retrieve(self, query: str) -> list[RetrievedChunk]:
        rewritten = await self.rewriter.rewrite(query)
        dense_vec = await self.dense_embedder.aembed_query(rewritten)

        # Fallback: if sparse embedder fails, do pure dense retrieval
        try:
            sparse_vecs = await self.sparse_embedder.aembed([rewritten])
            sparse_vec = sparse_vecs[0]
        except Exception:
            sparse_vec = None

        if sparse_vec is not None:
            scored_points = await self.qdrant_client.query_hybrid(
                dense_vector=dense_vec,
                sparse_vector=sparse_vec,
                dense_limit=settings.RETRIEVER_DENSE_TOPK,
                sparse_limit=settings.RETRIEVER_SPARSE_TOPK,
            )
        else:
            scored_points = await self.qdrant_client.query_dense(
                dense_vector=dense_vec,
                limit=settings.RETRIEVER_DENSE_TOPK,
            )

        if not scored_points:
            return []

        documents = [str(p.payload.get("content", "")) for p in scored_points]

        # Try rerank; on failure return RRF/dense results with original scores
        try:
            reranked = await self.reranker.rerank(rewritten, documents, top_n=settings.RETRIEVER_FINAL_TOPK)
        except Exception:
            reranked = None

        results = []
        if reranked is not None and len(reranked) > 0:
            for r in reranked:
                if 0 <= r.index < len(scored_points):
                    point = scored_points[r.index]
                    payload = point.payload or {}
                    results.append(RetrievedChunk(
                        content=str(payload.get("content", "")),
                        source=str(payload.get("source", "unknown")),
                        score=r.score,
                        metadata=dict(payload.get("meta_data", {})),
                    ))
        else:
            # Fallback: return top results from Qdrant with their original scores
            for point in scored_points[:settings.RETRIEVER_FINAL_TOPK]:
                payload = point.payload or {}
                results.append(RetrievedChunk(
                    content=str(payload.get("content", "")),
                    source=str(payload.get("source", "unknown")),
                    score=point.score,
                    metadata=dict(payload.get("meta_data", {})),
                ))

        return results
