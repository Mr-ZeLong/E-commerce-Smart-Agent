from app.core.config import settings
from app.retrieval.client import QdrantKnowledgeClient
from app.retrieval.embeddings import create_embedding_model
from app.retrieval.reranker import QwenReranker
from app.retrieval.retriever import HybridRetriever
from app.retrieval.rewriter import QueryRewriter
from app.retrieval.sparse_embedder import SparseTextEmbedder


def create_retriever(llm) -> HybridRetriever:
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
        rewriter=QueryRewriter(llm=llm),
    )
