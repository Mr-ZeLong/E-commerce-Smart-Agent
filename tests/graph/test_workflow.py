import pytest
from langgraph.checkpoint.memory import MemorySaver

from app.graph.workflow import workflow


@pytest.mark.asyncio
async def test_workflow_compiles():
    """验证多节点图可以成功编译"""
    checkpointer = MemorySaver()
    app_graph = workflow.compile(checkpointer=checkpointer)
    assert app_graph is not None
