import asyncio
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
        use_multi_query: bool = False,
    ):
        self.qdrant_client = qdrant_client
        self.dense_embedder = dense_embedder
        self.sparse_embedder = sparse_embedder
        self.reranker = reranker
        self.rewriter = rewriter
        self.use_multi_query = use_multi_query

    @staticmethod
    def _to_chunk(point, score: float) -> RetrievedChunk:
        payload = point.payload or {}
        return RetrievedChunk(
            content=str(payload.get("content", "")),
            source=str(payload.get("source", "unknown")),
            score=score,
            metadata=dict(payload.get("meta_data") or {}),
        )

    async def retrieve(
        self,
        query: str,
        conversation_history: list[dict] | None = None,
        memory_context: dict | None = None,
    ) -> list[RetrievedChunk]:
        if self.use_multi_query:
            variants = await self.rewriter.rewrite_multi(
                query,
                n=settings.RETRIEVER_MULTI_QUERY_N,
                conversation_history=conversation_history,
                memory_context=memory_context,
            )
            results = await asyncio.gather(*[self._retrieve_single(v) for v in variants])
            all_chunks = self._deduplicate_chunks([c for r in results for c in r])
            if not all_chunks:
                return []
            documents = [c.content for c in all_chunks]
            reranked = await self.reranker.rerank(
                query, documents, top_n=settings.RETRIEVER_FINAL_TOPK
            )
            final = []
            for r in reranked:
                if 0 <= r.index < len(all_chunks):
                    final.append(
                        RetrievedChunk(
                            content=all_chunks[r.index].content,
                            source=all_chunks[r.index].source,
                            score=r.score,
                            metadata=all_chunks[r.index].metadata,
                        )
                    )
            return final

        return await self._retrieve_single(query)

    async def _retrieve_single(self, query: str) -> list[RetrievedChunk]:
        dense_vec = await self.dense_embedder.aembed_query(query)
        sparse_vecs = await self.sparse_embedder.aembed([query])
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

        reranked = await self.reranker.rerank(query, documents, top_n=settings.RETRIEVER_FINAL_TOPK)

        results = []
        for r in reranked:
            if 0 <= r.index < len(scored_points):
                results.append(self._to_chunk(scored_points[r.index], r.score))

        return results

    @staticmethod
    def _deduplicate_chunks(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        seen: set[str] = set()
        unique: list[RetrievedChunk] = []
        for chunk in chunks:
            key = chunk.content.strip()
            if key and key not in seen:
                seen.add(key)
                unique.append(chunk)
        return unique
