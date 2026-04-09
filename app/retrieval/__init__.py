from functools import lru_cache

from app.core.config import settings
from app.retrieval.client import QdrantKnowledgeClient
from app.retrieval.embeddings import get_embedding_model
from app.retrieval.reranker import QwenReranker
from app.retrieval.retriever import HybridRetriever
from app.retrieval.rewriter import QueryRewriter
from app.retrieval.sparse_embedder import SparseTextEmbedder


@lru_cache(maxsize=1)
def get_retriever() -> HybridRetriever:
    qdrant_client = QdrantKnowledgeClient(
        url=settings.QDRANT_URL,
        collection_name=settings.QDRANT_COLLECTION_NAME,
        api_key=settings.QDRANT_API_KEY,
    )
    return HybridRetriever(
        qdrant_client=qdrant_client,
        dense_embedder=get_embedding_model(),
        sparse_embedder=SparseTextEmbedder(),
        reranker=QwenReranker(),
        rewriter=QueryRewriter(),
    )


def clear_retriever_cache() -> None:
    """Clear the cached retriever singleton (useful in tests)."""
    get_retriever.cache_clear()
