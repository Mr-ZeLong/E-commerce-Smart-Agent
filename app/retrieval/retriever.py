import asyncio
import logging

from pydantic import BaseModel

from app.core.cache import CacheManager
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
        cache_manager: CacheManager | None = None,
    ):
        self.qdrant_client = qdrant_client
        self.dense_embedder = dense_embedder
        self.sparse_embedder = sparse_embedder
        self.reranker = reranker
        self.rewriter = rewriter
        self.use_multi_query = use_multi_query
        self._cache = cache_manager

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
        variant_top_k: int | None = None,
        variant_reranker_enabled: bool | None = None,
    ) -> list[RetrievedChunk]:
        use_reranker = variant_reranker_enabled if variant_reranker_enabled is not None else True
        top_k = variant_top_k if variant_top_k is not None else settings.RETRIEVER_FINAL_TOPK

        if self._cache is not None and not self.use_multi_query:
            cached = await self._cache.get_retrieval(query)
            if cached is not None:
                return [RetrievedChunk.model_validate(c) for c in cached]

        if self.use_multi_query:
            variants = await self.rewriter.rewrite_multi(
                query,
                n=settings.RETRIEVER_MULTI_QUERY_N,
                conversation_history=conversation_history,
                memory_context=memory_context,
            )
            results = await asyncio.gather(
                *[self._retrieve_single(v, top_k, use_reranker) for v in variants]
            )
            all_chunks = self._deduplicate_chunks([c for r in results for c in r])
            if not all_chunks:
                return []
            if not use_reranker:
                return all_chunks[:top_k]
            documents = [c.content for c in all_chunks]
            reranked = await self.reranker.rerank(query, documents, top_n=top_k)
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

        chunks = await self._retrieve_single(query, top_k, use_reranker)

        if self._cache is not None and not self.use_multi_query:
            try:
                await self._cache.set_retrieval(query, [c.model_dump() for c in chunks])
            except Exception as exc:
                logger.warning("Failed to cache retrieval result: %s", exc)

        return chunks

    async def _retrieve_single(
        self,
        query: str,
        top_k: int | None = None,
        use_reranker: bool = True,
    ) -> list[RetrievedChunk]:
        # Parallelize dense and sparse embedding generation to reduce latency.
        dense_task = self.dense_embedder.aembed_query(query)
        sparse_task = self.sparse_embedder.aembed([query])
        dense_vec, sparse_vecs = await asyncio.gather(dense_task, sparse_task)
        sparse_vec = sparse_vecs[0]

        final_top_k = top_k if top_k is not None else settings.RETRIEVER_FINAL_TOPK

        scored_points = await self.qdrant_client.query_hybrid(
            dense_vector=dense_vec,
            sparse_vector=sparse_vec,
            dense_limit=settings.RETRIEVER_DENSE_TOPK,
            sparse_limit=settings.RETRIEVER_SPARSE_TOPK,
        )

        if not scored_points:
            return []

        documents = [str((p.payload or {}).get("content", "")) for p in scored_points]

        if not use_reranker:
            return [
                self._to_chunk(scored_points[i], 1.0)
                for i in range(min(final_top_k, len(scored_points)))
            ]

        reranked = await self.reranker.rerank(query, documents, top_n=final_top_k)

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
