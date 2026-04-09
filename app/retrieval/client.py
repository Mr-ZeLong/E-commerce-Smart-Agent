import contextlib

from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, Modifier, SparseVectorParams, VectorParams

from app.core.config import settings


class QdrantKnowledgeClient:
    def __init__(
        self,
        url: str | None = None,
        *,
        collection_name: str,
        api_key: str | None = None,
        client: AsyncQdrantClient | None = None,
    ):
        self.collection_name = collection_name
        if client is not None:
            self.client = client
        elif url == ":memory:":
            self.client = AsyncQdrantClient(location=":memory:", timeout=settings.QDRANT_TIMEOUT)
        else:
            self.client = AsyncQdrantClient(url=url, api_key=api_key, timeout=settings.QDRANT_TIMEOUT)

    async def aclose(self) -> None:
        await self.client.close()

    async def ensure_collection(self) -> None:
        exists = await self.client.collection_exists(self.collection_name)
        if exists:
            return

        await self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={
                "dense": VectorParams(size=settings.EMBEDDING_DIM, distance=Distance.COSINE)
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(modifier=Modifier.IDF)
            },
        )

    async def recreate_collection(self) -> None:
        with contextlib.suppress(UnexpectedResponse):
            await self.client.delete_collection(self.collection_name)
        await self.ensure_collection()

    async def upsert_chunks(self, points: list[models.PointStruct]) -> None:
        await self.client.upsert(collection_name=self.collection_name, points=points)

    async def query_hybrid(
        self,
        dense_vector: list[float],
        sparse_vector: models.SparseVector,
        dense_limit: int = 15,
        sparse_limit: int = 15,
        limit: int = 10,
    ) -> list[models.ScoredPoint]:
        response = await self.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                models.Prefetch(
                    query=dense_vector,
                    using="dense",
                    limit=dense_limit,
                ),
                models.Prefetch(
                    query=sparse_vector,
                    using="sparse",
                    limit=sparse_limit,
                ),
            ],
            query=models.RrfQuery(rrf=models.Rrf(k=settings.RETRIEVER_RRF_K)),
            limit=limit,
            with_payload=True,
        )
        return list(response.points)

    async def query_dense(
        self,
        dense_vector: list[float],
        limit: int = 15,
    ) -> list[models.ScoredPoint]:
        response = await self.client.query_points(
            collection_name=self.collection_name,
            query=dense_vector,
            using="dense",
            limit=limit,
            with_payload=True,
        )
        return list(response.points)
