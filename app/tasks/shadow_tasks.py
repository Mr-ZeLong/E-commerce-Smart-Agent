import asyncio
import logging
import uuid

from app.celery_app import celery_app
from app.evaluation.shadow import ShadowOrchestrator

logger = logging.getLogger(__name__)


async def _init_graphs():
    """Initialize production and shadow graphs independently.

    Shadow graph uses a different LLM model to enable meaningful comparison.
    """
    from langgraph.checkpoint.redis import AsyncRedisSaver

    from app.agents.account import AccountAgent
    from app.agents.cart import CartAgent
    from app.agents.complaint import ComplaintAgent
    from app.agents.evaluator import ConfidenceEvaluator
    from app.agents.logistics import LogisticsAgent
    from app.agents.order import OrderAgent
    from app.agents.payment import PaymentAgent
    from app.agents.policy import PolicyAgent
    from app.agents.product import ProductAgent
    from app.agents.router import IntentRouterAgent
    from app.agents.supervisor import SupervisorAgent
    from app.core.config import settings
    from app.core.llm_factory import create_openai_llm
    from app.core.redis import create_redis_client
    from app.graph.workflow import compile_app_graph
    from app.intent.service import IntentRecognitionService
    from app.memory.structured_manager import StructuredMemoryManager
    from app.memory.vector_manager import VectorMemoryManager
    from app.retrieval import create_retriever
    from app.services.order_service import OrderService
    from app.tools import (
        AccountTool,
        CartTool,
        ComplaintTool,
        LogisticsTool,
        PaymentTool,
        ProductTool,
    )
    from app.tools.registry import ToolRegistry

    redis_client = create_redis_client()
    checkpointer = AsyncRedisSaver(redis_client=redis_client)
    await checkpointer.setup()

    prod_llm = create_openai_llm()
    shadow_model = getattr(settings, "SHADOW_MODEL", "gpt-4o-mini")
    shadow_llm = create_openai_llm(model=shadow_model)

    prod_intent_service = IntentRecognitionService(llm=prod_llm, redis_client=redis_client)
    shadow_intent_service = IntentRecognitionService(llm=shadow_llm, redis_client=redis_client)

    structured_manager = StructuredMemoryManager()
    prod_router = IntentRouterAgent(
        intent_service=prod_intent_service, llm=prod_llm, structured_manager=structured_manager
    )
    shadow_router = IntentRouterAgent(
        intent_service=shadow_intent_service, llm=shadow_llm, structured_manager=structured_manager
    )

    retriever = create_retriever(llm=prod_llm, redis_client=redis_client)

    tool_registry = ToolRegistry()
    tool_registry.register(LogisticsTool())
    tool_registry.register(AccountTool())
    tool_registry.register(PaymentTool())
    tool_registry.register(ProductTool(rewriter=retriever.rewriter))
    tool_registry.register(CartTool())
    tool_registry.register(ComplaintTool())

    policy_agent = PolicyAgent(retriever=retriever, llm=prod_llm)
    order_agent = OrderAgent(order_service=OrderService(), llm=prod_llm)
    logistics_agent = LogisticsAgent(tool_registry=tool_registry, llm=prod_llm)
    account_agent = AccountAgent(tool_registry=tool_registry, llm=prod_llm)
    payment_agent = PaymentAgent(tool_registry=tool_registry, llm=prod_llm)
    product_agent = ProductAgent(tool_registry=tool_registry, llm=prod_llm)
    cart_agent = CartAgent(tool_registry=tool_registry, llm=prod_llm)
    complaint_agent = ComplaintAgent(llm=prod_llm)
    supervisor_agent = SupervisorAgent(llm=prod_llm)
    evaluator = ConfidenceEvaluator(llm=prod_llm)
    vector_manager = VectorMemoryManager()

    production_graph = await compile_app_graph(
        router_agent=prod_router,
        policy_agent=policy_agent,
        order_agent=order_agent,
        logistics_agent=logistics_agent,
        account_agent=account_agent,
        payment_agent=payment_agent,
        evaluator=evaluator,
        checkpointer=checkpointer,
        supervisor_agent=supervisor_agent,
        product_agent=product_agent,
        cart_agent=cart_agent,
        complaint_agent=complaint_agent,
        llm=prod_llm,
        vector_manager=vector_manager,
    )

    shadow_graph = await compile_app_graph(
        router_agent=shadow_router,
        policy_agent=PolicyAgent(retriever=retriever, llm=shadow_llm),
        order_agent=OrderAgent(order_service=OrderService(), llm=shadow_llm),
        logistics_agent=LogisticsAgent(tool_registry=tool_registry, llm=shadow_llm),
        account_agent=AccountAgent(tool_registry=tool_registry, llm=shadow_llm),
        payment_agent=PaymentAgent(tool_registry=tool_registry, llm=shadow_llm),
        evaluator=ConfidenceEvaluator(llm=shadow_llm),
        checkpointer=checkpointer,
        supervisor_agent=SupervisorAgent(llm=shadow_llm),
        product_agent=ProductAgent(tool_registry=tool_registry, llm=shadow_llm),
        cart_agent=CartAgent(tool_registry=tool_registry, llm=shadow_llm),
        complaint_agent=ComplaintAgent(llm=shadow_llm),
        llm=shadow_llm,
        vector_manager=vector_manager,
    )

    return production_graph, shadow_graph


async def _run_shadow_test(query: str, thread_id: str | None = None) -> dict:
    orchestrator = ShadowOrchestrator(sample_rate=0.1)
    sid = thread_id or f"shadow-{hash(query) & 0xFFFFFFFF:08x}"
    if not orchestrator.should_sample(sid):
        return {"sampled": False, "message": "Query not sampled for shadow testing"}

    try:
        production_graph, shadow_graph = await _init_graphs()

        session_id = f"shadow-{uuid.uuid4().hex[:8]}"
        prod_result, shadow_result = await ShadowOrchestrator.run_shadow(
            query=query,
            production_graph=production_graph,
            shadow_graph=shadow_graph,
            session_id=session_id,
        )

        comparison = ShadowOrchestrator.compare_results(
            thread_id=session_id,
            production_result=prod_result,
            shadow_result=shadow_result,
        )

        report = ShadowOrchestrator.generate_report([comparison])

        return {
            "sampled": True,
            "query": query,
            "comparison": {
                "intent_match": comparison.intent_match,
                "answer_similarity": comparison.answer_similarity,
                "latency_delta_ms": comparison.latency_delta_ms,
            },
            "report": {
                "intent_match_rate": report.intent_match_rate,
                "avg_answer_similarity": report.avg_answer_similarity,
                "latency_regression": report.latency_regression,
            },
        }
    except Exception as e:
        logger.exception("Shadow test failed for query: %s", query)
        return {
            "sampled": True,
            "query": query,
            "error": str(e),
            "message": "Shadow test failed during execution.",
        }


@celery_app.task(bind=True, name="shadow.run_shadow_test")
def run_shadow_test(_self, query: str) -> dict:
    return asyncio.run(_run_shadow_test(query))
