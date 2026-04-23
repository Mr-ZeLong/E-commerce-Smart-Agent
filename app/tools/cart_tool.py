import json
import logging

import redis.asyncio as aioredis
from redis.exceptions import RedisError

from app.core.config import settings
from app.models.state import AgentState
from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class CartTool(BaseTool):
    name = "cart"
    description = "购物车增删查改操作"

    def __init__(self, redis_client: aioredis.Redis | None = None, key_prefix: str = ""):
        self._redis = redis_client
        self._key_prefix = key_prefix

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    async def execute(self, state: AgentState, **kwargs) -> ToolResult:
        slots = state.get("slots") or {}
        user_id = state.get("user_id")
        action = (slots.get("action") or kwargs.get("action") or "QUERY").upper()
        product_id = slots.get("product_id") or kwargs.get("product_id")
        sku = slots.get("sku") or kwargs.get("sku")
        quantity = int(slots.get("quantity", 1) or kwargs.get("quantity", 1))
        name = slots.get("product_name") or kwargs.get("product_name") or product_id or sku
        price = float(slots.get("price", 0) or kwargs.get("price", 0))

        redis = await self._get_redis()
        key = f"{self._key_prefix}cart:{user_id}"

        try:
            if action == "QUERY":
                cart = await self._get_cart(redis, key)
                return ToolResult(output={"action": "QUERY", **cart})

            if action == "ADD":
                cart = await self._get_cart(redis, key)
                item_key = sku or product_id
                if not item_key:
                    return ToolResult(
                        output={"status": "error", "reason": "缺少商品标识（sku 或 product_id）"}
                    )
                cart["items"].append(
                    {
                        "product_id": product_id,
                        "sku": sku,
                        "name": name,
                        "quantity": quantity,
                        "price": price,
                        "subtotal": round(price * quantity, 2),
                    }
                )
                cart["total"] = round(sum(i["subtotal"] for i in cart["items"]), 2)
                await self._save_cart(redis, key, cart)
                return ToolResult(
                    output={"action": "ADD", "name": name, "quantity": quantity, **cart}
                )

            if action == "REMOVE":
                cart = await self._get_cart(redis, key)
                item_key = sku or product_id
                if not item_key:
                    return ToolResult(
                        output={"status": "error", "reason": "缺少商品标识（sku 或 product_id）"}
                    )
                removed_name = None
                new_items = []
                for item in cart["items"]:
                    if item.get("sku") == item_key or item.get("product_id") == item_key:
                        removed_name = item.get("name", item_key)
                    else:
                        new_items.append(item)
                cart["items"] = new_items
                cart["total"] = round(sum(i["subtotal"] for i in new_items), 2)
                await self._save_cart(redis, key, cart)
                return ToolResult(
                    output={"action": "REMOVE", "name": removed_name or item_key, **cart}
                )

            if action == "MODIFY":
                cart = await self._get_cart(redis, key)
                item_key = sku or product_id
                if not item_key:
                    return ToolResult(
                        output={"status": "error", "reason": "缺少商品标识（sku 或 product_id）"}
                    )
                modified_name = None
                for item in cart["items"]:
                    if item.get("sku") == item_key or item.get("product_id") == item_key:
                        item["quantity"] = quantity
                        item["subtotal"] = round(item["price"] * quantity, 2)
                        modified_name = item.get("name", item_key)
                        break
                else:
                    return ToolResult(output={"status": "error", "reason": "购物车中未找到该商品"})
                cart["total"] = round(sum(i["subtotal"] for i in cart["items"]), 2)
                await self._save_cart(redis, key, cart)
                return ToolResult(
                    output={"action": "MODIFY", "name": modified_name, "quantity": quantity, **cart}
                )

            return ToolResult(output={"status": "error", "reason": f"不支持的操作: {action}"})
        except (RedisError, ConnectionError, OSError, json.JSONDecodeError):
            logger.exception("Cart tool execution failed")
            return ToolResult(
                output={"status": "error", "reason": "购物车服务暂时不可用，请稍后重试"}
            )

    async def _get_cart(self, redis: aioredis.Redis, key: str) -> dict:
        data = await redis.get(key)
        if data:
            return json.loads(data)
        return {"user_id": key.split(":", 1)[1], "items": [], "total": 0.0}

    async def _save_cart(self, redis: aioredis.Redis, key: str, cart: dict) -> None:
        await redis.setex(key, 86400, json.dumps(cart))
