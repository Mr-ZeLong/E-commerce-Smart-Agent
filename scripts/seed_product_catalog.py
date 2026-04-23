import asyncio
import json
import logging
import os
import sys

sys.path.append(os.getcwd())

from qdrant_client import models

from app.core.config import settings
from app.retrieval.client import QdrantKnowledgeClient
from app.retrieval.embeddings import create_embedding_model

logger = logging.getLogger(__name__)

DATA_FILE = "data/products.json"
COLLECTION_NAME = "product_catalog"


async def main():
    if not os.path.exists(DATA_FILE):
        raise FileNotFoundError(f"Product data file not found: {DATA_FILE}")

    with open(DATA_FILE, encoding="utf-8") as f:
        products = json.load(f)

    qdrant_client = QdrantKnowledgeClient(
        url=settings.QDRANT_URL,
        collection_name=COLLECTION_NAME,
        api_key=settings.QDRANT_API_KEY.get_secret_value() if settings.QDRANT_API_KEY else None,
    )
    await qdrant_client.ensure_collection()

    embedder = create_embedding_model()

    points: list[models.PointStruct] = []
    for idx, product in enumerate(products):
        text = (
            f"商品: {product['name']}\n"
            f"描述: {product['description']}\n"
            f"分类: {product['category']}\n"
            f"SKU: {product['sku']}"
        )
        vector = await embedder.aembed_query(text)
        points.append(
            models.PointStruct(
                id=idx,
                vector={"dense": vector},
                payload={
                    "name": product["name"],
                    "description": product["description"],
                    "price": product["price"],
                    "category": product["category"],
                    "sku": product["sku"],
                    "in_stock": product["in_stock"],
                    "attributes": product.get("attributes", {}),
                },
            )
        )

    await qdrant_client.upsert_chunks(points)
    logger.info("Seeded %s products into %s", len(products), COLLECTION_NAME)
    print(f"✅ Seeded {len(products)} products into {COLLECTION_NAME}")
    await qdrant_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
