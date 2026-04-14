import logging
from typing import Any

from qdrant_client import AsyncQdrantClient, models

from app.core.config import settings
from app.models.state import AgentState
from app.retrieval.rewriter import QueryRewriter
from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ProductTool(BaseTool):
    name = "product"
    description = "搜索商品目录并回答商品相关问题"

    def __init__(
        self,
        qdrant_client: AsyncQdrantClient | None = None,
        rewriter: QueryRewriter | None = None,
    ):
        self._qdrant = qdrant_client
        self._rewriter = rewriter

    async def _get_client(self) -> AsyncQdrantClient:
        if self._qdrant is None:
            self._qdrant = AsyncQdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY or None,
                timeout=settings.QDRANT_TIMEOUT,
            )
        return self._qdrant

    async def execute(self, state: AgentState, **kwargs) -> ToolResult:
        slots = state.get("slots") or {}
        query = slots.get("product_query") or slots.get("query") or state.get("question", "")
        category = slots.get("category") or kwargs.get("category")
        min_price = slots.get("min_price") or kwargs.get("min_price")
        max_price = slots.get("max_price") or kwargs.get("max_price")
        in_stock = slots.get("in_stock") or kwargs.get("in_stock")

        if self._rewriter is not None:
            query = await self._rewriter.rewrite(
                query,
                conversation_history=state.get("history"),
                memory_context=state.get("memory_context"),
            )

        client = await self._get_client()
        collection = "product_catalog"

        conditions: list[Any] = []
        if category is not None:
            conditions.append(
                models.FieldCondition(key="category", match=models.MatchValue(value=category))
            )
        if in_stock is not None:
            conditions.append(
                models.FieldCondition(key="in_stock", match=models.MatchValue(value=bool(in_stock)))
            )
        if min_price is not None or max_price is not None:
            rng: dict[str, Any] = {}
            if min_price is not None:
                rng["gte"] = float(min_price)
            if max_price is not None:
                rng["lte"] = float(max_price)
            conditions.append(models.FieldCondition(key="price", range=models.Range(**rng)))

        query_filter = models.Filter(must=conditions) if conditions else None

        try:
            exists = await client.collection_exists(collection)
            if not exists:
                return ToolResult(output={"status": "not_found", "reason": "商品目录尚未初始化"})

            query_vector = await self._embed_query(query)
            results = await client.query_points(
                collection_name=collection,
                query=query_vector,
                using="dense",
                limit=5,
                with_payload=True,
                with_vectors=False,
                query_filter=query_filter,
            )

            products = []
            for point in results.points:
                payload = point.payload or {}
                products.append(
                    {
                        "id": point.id,
                        "name": payload.get("name", ""),
                        "description": payload.get("description", ""),
                        "price": payload.get("price"),
                        "category": payload.get("category", ""),
                        "sku": payload.get("sku", ""),
                        "in_stock": payload.get("in_stock", False),
                        "attributes": payload.get("attributes", {}),
                        "score": point.score,
                    }
                )

            direct_answer = self._try_direct_answer(query, products)
            return ToolResult(
                output={
                    "status": "success",
                    "products": products,
                    "direct_answer": direct_answer,
                    "query": query,
                }
            )
        except Exception:
            logger.exception("Product search failed")
            return ToolResult(output={"status": "error", "reason": "商品搜索失败，请稍后重试"})

    async def _embed_query(self, query: str) -> list[float]:
        try:
            from app.retrieval.embeddings import create_embedding_model

            gen = create_embedding_model()
            vector = await gen.aembed_query(query)
            return vector
        except Exception:
            return [0.0] * settings.EMBEDDING_DIM

    def _try_direct_answer(self, query: str, products: list[dict]) -> str | None:
        if not products:
            return None
        top = products[0]
        attrs = top.get("attributes") or {}
        query_lower = query.lower()

        attribute_keywords = {
            "屏幕": "屏幕",
            "刷新率": "刷新率",
            "hz": "刷新率",
            "电池": "电池",
            "相机": "相机",
            "重量": "重量",
            "尺寸": "尺寸",
            "内存": "内存",
            "存储": "存储",
            "颜色": "颜色",
            "材质": "材质",
        }

        for keyword, attr_key in attribute_keywords.items():
            if keyword in query_lower and attr_key in attrs:
                return f"{top['name']} 的{keyword}为 {attrs[attr_key]}。"

        return None
