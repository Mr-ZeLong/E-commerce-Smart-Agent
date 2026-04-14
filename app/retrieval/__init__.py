from app.core.config import settings
from app.core.llm_factory import create_openai_llm
from app.retrieval.client import QdrantKnowledgeClient
from app.retrieval.embeddings import create_embedding_model
from app.retrieval.reranker import QwenReranker
from app.retrieval.retriever import HybridRetriever
from app.retrieval.rewriter import QueryRewriter
from app.retrieval.sparse_embedder import SparseTextEmbedder


def create_retriever(llm, redis_client=None) -> HybridRetriever:
    _ = llm
    return HybridRetriever(
        qdrant_client=QdrantKnowledgeClient(
            url=settings.QDRANT_URL,
            collection_name=settings.QDRANT_COLLECTION_NAME,
            api_key=settings.QDRANT_API_KEY,
        ),
        dense_embedder=create_embedding_model(),
        sparse_embedder=SparseTextEmbedder(),
        reranker=QwenReranker(
            api_key=settings.DASHSCOPE_API_KEY,
            base_url=settings.RERANK_BASE_URL,
            model=settings.RERANK_MODEL,
        ),
        rewriter=QueryRewriter(
            llm=create_openai_llm(
                model=settings.REWRITE_MODEL,
                timeout=settings.REWRITE_TIMEOUT,
            ),
            redis_client=redis_client,
        ),
        use_multi_query=settings.RETRIEVER_MULTI_QUERY,
    )
