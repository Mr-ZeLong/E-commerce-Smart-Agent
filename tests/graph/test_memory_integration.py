import pytest
from langgraph.types import Command

from app.core.config import settings
from app.graph.nodes import build_memory_node
from app.memory.structured_manager import StructuredMemoryManager
from app.memory.vector_manager import VectorMemoryManager
from app.models.memory import UserProfile
from app.models.state import make_agent_state
from app.models.user import User


class _FakeEmbedder:
    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        dim = settings.EMBEDDING_DIM
        return [[0.1] * dim for _ in texts]

    async def aembed_query(self, text: str) -> list[float]:
        dim = settings.EMBEDDING_DIM
        return [0.1] * dim


def _make_user(username: str) -> User:
    return User(
        username=username,
        email=f"{username}@test.com",
        full_name=f"User {username}",
        password_hash=User.hash_password("secret"),
    )


@pytest.mark.asyncio
async def test_memory_node_routes_to_supervisor(db_session, qdrant_client):
    user = _make_user("mem_route")
    db_session.add(user)
    await db_session.flush()
    assert user.id is not None

    profile = UserProfile(
        user_id=user.id,
        membership_level="gold",
        preferred_language="zh",
        timezone="Asia/Shanghai",
        total_orders=5,
        lifetime_value=1000.0,
    )
    db_session.add(profile)

    manager = StructuredMemoryManager()
    await manager.save_user_fact(
        session=db_session,
        user_id=user.id,
        fact_type="preference",
        content="fast shipping",
        confidence=0.9,
    )
    await db_session.commit()

    qdrant, collection_name = qdrant_client
    vector_manager = VectorMemoryManager(client=qdrant, embedder=_FakeEmbedder())
    vector_manager.COLLECTION_NAME = collection_name
    await vector_manager.ensure_collection()
    await vector_manager.upsert_message(
        user_id=user.id,
        thread_id="t1",
        message_role="user",
        content="previous question",
        timestamp="2024-01-01T00:00:00Z",
    )

    node = build_memory_node(
        structured_manager=manager,
        vector_manager=vector_manager,
        use_supervisor=True,
        session=db_session,
    )
    state = make_agent_state(
        question="hello again",
        user_id=user.id,
        thread_id="t1",
        history=[{"role": "user", "content": "hello again"}],
    )
    result = await node(state)

    assert isinstance(result, Command)
    assert result.goto == "supervisor_node"
    assert result.update is not None
    assert "memory_context" in result.update
    assert result.update["memory_context"]["user_profile"]["membership_level"] == "gold"
    assert len(result.update["memory_context"]["structured_facts"]) == 1
    assert len(result.update["memory_context"]["relevant_past_messages"]) == 1


@pytest.mark.asyncio
async def test_memory_node_handles_structured_exception(db_session):
    user = _make_user("mem_struct_exc")
    db_session.add(user)
    await db_session.flush()
    assert user.id is not None
    await db_session.commit()

    node = build_memory_node(
        structured_manager=StructuredMemoryManager(),
        vector_manager=None,
        use_supervisor=True,
        session=db_session,
    )
    state = make_agent_state(
        question="hello",
        user_id=user.id,
        thread_id="t1",
        history=[{"role": "user", "content": "hello"}],
    )
    result = await node(state)

    assert isinstance(result, Command)
    assert result.goto == "supervisor_node"
    assert result.update is not None
    assert "memory_context" in result.update
    assert "user_profile" not in result.update["memory_context"]


@pytest.mark.asyncio
async def test_memory_node_handles_vector_exception(db_session):
    user = _make_user("mem_vec_exc")
    db_session.add(user)
    await db_session.flush()
    assert user.id is not None
    await db_session.commit()

    node = build_memory_node(
        structured_manager=StructuredMemoryManager(),
        vector_manager=None,
        use_supervisor=True,
        session=db_session,
    )
    state = make_agent_state(
        question="hello",
        user_id=user.id,
        thread_id="t1",
        history=[{"role": "user", "content": "hello"}],
    )
    result = await node(state)

    assert isinstance(result, Command)
    assert result.goto == "supervisor_node"
    assert result.update is not None
    assert "memory_context" in result.update
    assert "relevant_past_messages" not in result.update["memory_context"]


@pytest.mark.asyncio
async def test_memory_node_no_managers():
    node = build_memory_node(structured_manager=None, vector_manager=None)
    state = make_agent_state(
        question="hello",
        user_id=1,
        thread_id="t1",
        history=[{"role": "user", "content": "hello"}],
    )
    result = await node(state)

    assert isinstance(result, Command)
    assert result.goto == "supervisor_node"
    assert result.update is not None
    assert result.update["memory_context"] == {}
