import pytest
import asyncio
from app.graph.workflow import app_graph


@pytest.fixture(scope="session")
def event_loop():
    """创建一个全局的事件循环供整个测试会话使用"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()

    
# 1. 必须使用这个装饰器，否则 pytest 找不到 query 变量
@pytest.mark.parametrize("query", [
    "内衣拆封了可以退吗？",
    "帮我写一个 Python 贪吃蛇游戏。",
    "新疆运费多少钱？"
])
@pytest.mark.asyncio
async def test_agent(query: str):  # 注意：函数名必须以 test_ 开头
    print(f"\n" + "="*30)
    print(f"❓ 用户提问: {query}")

    initial_state = {"question": query, "context": [], "answer": ""}
    config = {"configurable": {"thread_id": "test_001"}}

    # 用于最后断言
    final_answer = None

    async for event in app_graph.astream(initial_state, config):  # ty:ignore[unresolved-attribute]
        for node_name, output in event.items():
            if node_name == "retrieve":
                # 注意：根据你的 LangGraph 定义，output 可能是字典也可能是对象
                context = output.get('context', [])
                print(f"✅ 检索完成，找到 {len(context)} 条相关上下文")
            elif node_name == "generate":
                final_answer = output.get('answer')
                print(f"🤖 最终回答: {final_answer}")

    # 2. 只有加上 assert，pytest 才能判断是成功还是失败
    assert final_answer is not None, f"提问 [{query}] 没有得到回答"