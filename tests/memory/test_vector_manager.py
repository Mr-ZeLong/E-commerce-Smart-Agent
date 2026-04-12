from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.memory.vector_manager import VectorMemoryManager


@pytest.fixture
def manager():
    return VectorMemoryManager()


@pytest.mark.asyncio
async def test_ensure_collection_already_exists(manager):
    with patch.object(manager.client, "collection_exists", new_callable=AsyncMock) as mock_exists:
        mock_exists.return_value = True
        await manager.ensure_collection()
        mock_exists.assert_awaited_once_with("conversation_memory")


@pytest.mark.asyncio
async def test_ensure_collection_creates_when_missing(manager):
    with patch.object(manager.client, "collection_exists", new_callable=AsyncMock) as mock_exists:
        mock_exists.return_value = False
        with patch.object(
            manager.client, "create_collection", new_callable=AsyncMock
        ) as mock_create:
            await manager.ensure_collection()
            mock_exists.assert_awaited_once_with("conversation_memory")
            mock_create.assert_awaited_once()
            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs["collection_name"] == "conversation_memory"


@pytest.mark.asyncio
async def test_upsert_message(manager):
    mock_embedder = AsyncMock()
    mock_embedder.aembed_documents.return_value = [[0.1] * 1024]
    manager._embedder = mock_embedder

    with patch.object(manager.client, "collection_exists", new_callable=AsyncMock) as mock_exists:
        mock_exists.return_value = True
        with patch.object(manager.client, "upsert", new_callable=AsyncMock) as mock_upsert:
            await manager.upsert_message(
                user_id=1,
                thread_id="t1",
                message_role="user",
                content="hello",
                timestamp="2024-01-01T00:00:00Z",
                intent="GREETING",
            )
            mock_upsert.assert_awaited_once()
            call_kwargs = mock_upsert.call_args.kwargs
            assert call_kwargs["collection_name"] == "conversation_memory"
            point = call_kwargs["points"][0]
            assert point.payload["content"] == "hello"
            assert point.payload["intent"] == "GREETING"


@pytest.mark.asyncio
async def test_search_similar(manager):
    mock_embedder = AsyncMock()
    mock_embedder.aembed_documents.return_value = [[0.2] * 1024]
    manager._embedder = mock_embedder

    mock_point = MagicMock()
    mock_point.payload = {
        "user_id": 1,
        "content": "previous hello",
        "message_role": "user",
    }
    mock_response = MagicMock()
    mock_response.points = [mock_point]

    with patch.object(manager.client, "collection_exists", new_callable=AsyncMock) as mock_exists:
        mock_exists.return_value = True
        with patch.object(manager.client, "query_points", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_response
            results = await manager.search_similar(user_id=1, query_text="hello", top_k=3)

            assert len(results) == 1
            assert results[0]["content"] == "previous hello"
            mock_query.assert_awaited_once()
            call_kwargs = mock_query.call_args.kwargs
            assert call_kwargs["limit"] == 3
            assert call_kwargs["using"] == "dense"


@pytest.mark.asyncio
async def test_search_similar_no_collection(manager):
    mock_embedder = AsyncMock()
    mock_embedder.aembed_documents.return_value = [[0.2] * 1024]
    manager._embedder = mock_embedder

    with patch.object(manager.client, "collection_exists", new_callable=AsyncMock) as mock_exists:
        mock_exists.return_value = True
        with patch.object(manager.client, "query_points", new_callable=AsyncMock) as mock_query:
            mock_query.return_value = MagicMock(points=[])
            results = await manager.search_similar(user_id=1, query_text="hello")
            assert results == []


@pytest.mark.asyncio
async def test_prune_old_messages(manager):
    old_timestamp = "2020-01-01T00:00:00+00:00"
    new_timestamp = "2099-01-01T00:00:00+00:00"

    mock_old_point = MagicMock()
    mock_old_point.id = "point-1"
    mock_old_point.payload = {"timestamp": old_timestamp}

    mock_new_point = MagicMock()
    mock_new_point.id = "point-2"
    mock_new_point.payload = {"timestamp": new_timestamp}

    with patch.object(manager.client, "collection_exists", new_callable=AsyncMock) as mock_exists:
        mock_exists.return_value = True
        with patch.object(manager.client, "scroll", new_callable=AsyncMock) as mock_scroll:
            mock_scroll.return_value = ([mock_old_point, mock_new_point], None)
            with patch.object(manager.client, "delete", new_callable=AsyncMock) as mock_delete:
                await manager.prune_old_messages(retention_days=30)

                mock_delete.assert_awaited_once()
                call_kwargs = mock_delete.call_args.kwargs
                points = call_kwargs["points_selector"].points
                assert points == ["point-1"]


@pytest.mark.asyncio
async def test_prune_old_messages_collection_missing(manager):
    with patch.object(manager.client, "collection_exists", new_callable=AsyncMock) as mock_exists:
        mock_exists.return_value = False
        await manager.prune_old_messages(retention_days=30)
        mock_exists.assert_awaited_once_with("conversation_memory")


@pytest.mark.asyncio
async def test_aclose(manager):
    with patch.object(manager.client, "close", new_callable=AsyncMock) as mock_close:
        await manager.aclose()
        mock_close.assert_awaited_once()
