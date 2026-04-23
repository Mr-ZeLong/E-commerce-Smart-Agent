import logging
import uuid
from datetime import UTC, datetime, timedelta

from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, VectorParams
from sqlalchemy.exc import SQLAlchemyError

from app.context.pii_filter import log_pii_detection, pii_filter
from app.core.config import settings
from app.retrieval.embeddings import create_embedding_model

logger = logging.getLogger(__name__)


class VectorMemoryManager:
    """Manages conversation memory vectors in Qdrant's `conversation_memory` collection."""

    COLLECTION_NAME = "conversation_memory"

    def __init__(self, client=None, embedder=None):
        if client is None:
            if settings.QDRANT_URL == ":memory:":
                self.client = AsyncQdrantClient(
                    location=":memory:", timeout=settings.QDRANT_TIMEOUT
                )
            else:
                self.client = AsyncQdrantClient(
                    url=settings.QDRANT_URL,
                    api_key=settings.QDRANT_API_KEY.get_secret_value(),
                    timeout=settings.QDRANT_TIMEOUT,
                )
        else:
            self.client = client
        self._embedder = embedder if embedder is not None else create_embedding_model()
        self._collection_ensured: bool = False

    async def aclose(self) -> None:
        await self.client.close()

    async def ensure_collection(self) -> None:
        if self._collection_ensured:
            return
        exists = await self.client.collection_exists(self.COLLECTION_NAME)
        if exists:
            self._collection_ensured = True
            return

        await self.client.create_collection(
            collection_name=self.COLLECTION_NAME,
            vectors_config={
                "dense": VectorParams(size=settings.EMBEDDING_DIM, distance=Distance.COSINE)
            },
        )
        try:
            await self.client.create_payload_index(
                collection_name=self.COLLECTION_NAME,
                field_name="user_id",
                field_schema=models.PayloadSchemaType.INTEGER,
            )
        except (SQLAlchemyError, RuntimeError, OSError):
            logger.exception("Failed to create payload index for user_id")
        self._collection_ensured = True

    async def upsert_message(
        self,
        user_id: int,
        thread_id: str,
        message_role: str,
        content: str,
        timestamp: str,
        intent: str | None = None,
    ) -> None:
        await self.ensure_collection()

        pii_result = pii_filter.filter_text(content)
        filtered_content = pii_result.redacted_text
        if pii_result.has_pii:
            log_pii_detection(
                user_id=user_id,
                thread_id=thread_id,
                source="vector_memory",
                detections=pii_result.detections,
            )

        embeddings = await self._embedder.aembed_documents([filtered_content])
        vector = embeddings[0]

        point_id = str(uuid.uuid4())
        payload: dict[str, object] = {
            "user_id": user_id,
            "thread_id": thread_id,
            "message_role": message_role,
            "content": filtered_content,
            "timestamp": timestamp,
        }
        if intent is not None:
            payload["intent"] = intent

        await self.client.upsert(
            collection_name=self.COLLECTION_NAME,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector={"dense": vector},
                    payload=payload,
                )
            ],
        )

    async def search_similar(
        self,
        user_id: int,
        query_text: str,
        top_k: int = 5,
        message_role: str | None = None,
    ) -> list[dict]:
        await self.ensure_collection()

        embeddings = await self._embedder.aembed_documents([query_text])
        query_vector = embeddings[0]

        must_conditions: list = [
            models.FieldCondition(
                key="user_id",
                match=models.MatchValue(value=user_id),
            )
        ]
        if message_role is not None:
            must_conditions.append(
                models.FieldCondition(
                    key="message_role",
                    match=models.MatchValue(value=message_role),
                )
            )

        response = await self.client.query_points(
            collection_name=self.COLLECTION_NAME,
            query=query_vector,
            using="dense",
            query_filter=models.Filter(must=must_conditions),
            limit=top_k,
            with_payload=True,
        )

        return [
            {**point.payload, "score": point.score}
            for point in response.points
            if point.payload is not None
        ]

    async def prune_old_messages(self, retention_days: int) -> None:
        exists = await self.client.collection_exists(self.COLLECTION_NAME)
        if not exists:
            return

        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        cutoff_iso = cutoff.isoformat()

        total_pruned = 0
        offset = None

        while True:
            try:
                batch, offset = await self.client.scroll(
                    collection_name=self.COLLECTION_NAME,
                    limit=1000,
                    offset=offset,
                    with_payload=True,
                )
            except UnexpectedResponse as exc:
                if exc.status_code == 404:
                    return
                raise

            if not batch:
                break

            batch_ids: list[str | int | uuid.UUID] = []
            for point in batch:
                ts = point.payload.get("timestamp") if point.payload else None
                if isinstance(ts, str) and ts < cutoff_iso:
                    batch_ids.append(str(point.id))

            if batch_ids:
                await self.client.delete(
                    collection_name=self.COLLECTION_NAME,
                    points_selector=models.PointIdsList(points=batch_ids),
                )
                total_pruned += len(batch_ids)

            if offset is None:
                break

        if total_pruned:
            logger.info(
                "Pruned %d old messages from %s",
                total_pruned,
                self.COLLECTION_NAME,
            )
