# app/main.py
import asyncio
import contextlib
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from opentelemetry import trace
from prometheus_client import make_asgi_app
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router
from app.api.v1.chat import router as chat_router
from app.api.v1.status import router as status_router
from app.api.v1.websocket import router as websocket_router
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import CorrelationIdFilter, generate_correlation_id, set_correlation_id
from app.observability.otel_setup import instrument_fastapi, setup_otel_tracing
from app.websocket.manager import get_manager
from app.websocket.redis_bridge import RedisBroadcastBridge

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_logging()
    _setup_langsmith_tracing()
    logger.info(" Starting E-commerce Smart Agent v4.1...")

    setup_otel_tracing()
    instrument_fastapi(app)

    if "*" in settings.CORS_ORIGINS:
        raise RuntimeError(
            "CORS allow_origins=['*'] combined with allow_credentials=True is not allowed. "
            "Please restrict CORS_ORIGINS to specific domains."
        )

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
    from app.core.database import async_engine
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

    redis_client = None
    retriever = None
    vector_manager = None
    bridge = None
    listener_task = None
    try:
        redis_client = create_redis_client()
        checkpointer = AsyncRedisSaver(redis_client=redis_client)
        await checkpointer.setup()

        llm = create_openai_llm()
        eval_llm = create_openai_llm(model=settings.CONFIDENCE.EVALUATION_MODEL)
        intent_service = IntentRecognitionService(llm=llm, redis_client=redis_client)
        structured_manager = StructuredMemoryManager()
        router_agent = IntentRouterAgent(
            intent_service=intent_service, llm=llm, structured_manager=structured_manager
        )
        retriever = create_retriever(llm=llm, redis_client=redis_client)

        app.state.manager = get_manager()

        bridge = RedisBroadcastBridge(settings.REDIS_URL)

        async def _redis_listener() -> None:
            try:
                async for payload in bridge.subscribe("admins"):
                    if payload.get("room") == "admins":
                        await get_manager().broadcast_to_admins(payload.get("data", {}))
            except asyncio.CancelledError:
                raise
            except (ConnectionError, OSError, RuntimeError):
                logger.exception("Redis broadcast listener error")

        listener_task = asyncio.create_task(_redis_listener())

        tool_registry = ToolRegistry()
        tool_registry.register(LogisticsTool())
        tool_registry.register(AccountTool())
        tool_registry.register(PaymentTool())
        tool_registry.register(ProductTool(rewriter=retriever.rewriter))
        tool_registry.register(CartTool())
        tool_registry.register(ComplaintTool())
        app.state.tool_registry = tool_registry
        policy_agent = PolicyAgent(retriever=retriever, llm=llm)
        order_agent = OrderAgent(order_service=OrderService(), llm=llm)
        logistics_agent = LogisticsAgent(tool_registry=tool_registry, llm=llm)
        account_agent = AccountAgent(tool_registry=tool_registry, llm=llm)
        payment_agent = PaymentAgent(tool_registry=tool_registry, llm=llm)
        product_agent = ProductAgent(tool_registry=tool_registry, llm=llm)
        cart_agent = CartAgent(tool_registry=tool_registry, llm=llm)
        complaint_agent = ComplaintAgent(llm=llm)
        supervisor_agent = SupervisorAgent(llm=llm)
        evaluator = ConfidenceEvaluator(llm=eval_llm)
        vector_manager = VectorMemoryManager()

        app.state.intent_service = intent_service
        app.state.llm = llm
        app.state.vector_manager = vector_manager
        app.state.app_graph = await compile_app_graph(
            router_agent=router_agent,
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
            llm=llm,
            structured_manager=structured_manager,
            vector_manager=vector_manager,
        )
        logger.info(" Infrastructure is ready.")

        try:
            logger.info("Warming up LLM...")
            await llm.ainvoke([{"role": "user", "content": "Hello"}])
            logger.info("LLM warm-up complete.")
        except (TimeoutError, OSError):
            logger.warning("LLM warm-up failed, will warm up on first request")

        yield
    finally:
        logger.info("Shutting down...")
        if listener_task is not None:
            listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await listener_task
        if bridge is not None:
            await bridge.close()
        if redis_client is not None:
            await redis_client.close()
        if retriever is not None:
            await retriever.qdrant_client.aclose()
        if vector_manager is not None:
            await vector_manager.aclose()
        await async_engine.dispose()


def _setup_langsmith_tracing() -> None:
    """Configure LangSmith tracing based on application settings.

    If LANGSMITH_API_KEY is configured, automatically set the environment
    variables required for LangChain/LangSmith automatic tracing. This ensures
    all LLM calls (via LangChain) are traced without requiring code changes
    at each call site.
    """
    if not settings.LANGSMITH_API_KEY:
        return

    # Set required environment variables for LangChain automatic tracing
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.LANGSMITH_API_KEY.get_secret_value())
    os.environ.setdefault("LANGCHAIN_PROJECT", settings.LANGSMITH_PROJECT)

    # Log tracing status (avoid logging the full API key)
    secret_key = settings.LANGSMITH_API_KEY.get_secret_value()
    masked_key = f"{secret_key[:8]}..." if len(secret_key) > 8 else "***"
    logger.info(
        "LangSmith tracing enabled (project=%s, api_key=%s)",
        settings.LANGSMITH_PROJECT,
        masked_key,
    )


class SafeFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "correlation_id"):
            record.correlation_id = "-"
        return super().format(record)


def _setup_logging() -> None:
    formatter = SafeFormatter(
        "%(asctime)s [%(correlation_id)s] %(levelname)s %(name)s - %(message)s"
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        root_logger.addHandler(handler)
    root_logger.addFilter(CorrelationIdFilter())

    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logging.getLogger(name).addFilter(CorrelationIdFilter())


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="4.1.0",
    description="全栈·沉浸式人机协作系统 (The Immersive System) - v4.1",
    docs_url="/docs" if settings.ENABLE_OPENAPI_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_OPENAPI_DOCS else None,
    openapi_url="/openapi.json" if settings.ENABLE_OPENAPI_DOCS else None,
    lifespan=lifespan,
)
app.state.limiter = limiter


def _rate_limit_handler(request: Request, exc: Exception) -> Response:
    if not isinstance(exc, RateLimitExceeded):
        raise TypeError(f"Unexpected exception type: {type(exc).__name__}")
    return _rate_limit_exceeded_handler(request, exc)


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    cid = request.headers.get("x-correlation-id") or generate_correlation_id()
    set_correlation_id(cid)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = cid
    return response


# 1. 配置跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 2. OpenTelemetry trace-id response middleware (after CORS)
@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    response = await call_next(request)
    span = trace.get_current_span()
    span_context = span.get_span_context()
    if span_context.is_valid:
        trace_id = format(span_context.trace_id, "032x")
        response.headers["X-Trace-ID"] = trace_id
    return response


# 3. Rate limiting middleware
app.add_middleware(SlowAPIMiddleware)

# 3. 注册路由
app.include_router(auth_router, prefix=settings.API_V1_STR, tags=["Auth"])  # v4.0 新增
app.include_router(chat_router, prefix=settings.API_V1_STR, tags=["Chat"])
app.include_router(status_router, prefix=settings.API_V1_STR, tags=["Status"])
app.include_router(admin_router, prefix=settings.API_V1_STR, tags=["Admin"])
app.include_router(websocket_router, prefix=settings.API_V1_STR, tags=["WebSocket"])

app.mount("/metrics", make_asgi_app())

# 3. 静态文件托管
frontend_dist_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

if os.path.exists(frontend_dist_path):
    app.mount(
        "/customer",
        StaticFiles(directory=os.path.join(frontend_dist_path, "customer")),
        name="customer_assets",
    )
    app.mount(
        "/shared",
        StaticFiles(directory=os.path.join(frontend_dist_path, "shared")),
        name="shared_assets",
    )
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(frontend_dist_path, "assets")),
        name="root_assets",
    )

    @app.get("/app")
    @app.get("/app/{full_path:path}")
    async def serve_customer_spa(full_path: str = ""):
        base_dir = os.path.realpath(os.path.join(frontend_dist_path, "customer"))
        file_path = os.path.realpath(os.path.join(base_dir, full_path))
        if file_path.startswith(base_dir) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_dist_path, "index.html"))

    @app.get("/admin")
    @app.get("/admin/{full_path:path}")
    async def serve_admin_spa(full_path: str = ""):
        base_dir = os.path.realpath(os.path.join(frontend_dist_path, "admin"))
        file_path = os.path.realpath(os.path.join(base_dir, full_path))
        if file_path.startswith(base_dir) and os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_dist_path, "admin.html"))

    @app.get("/favicon.svg")
    async def serve_favicon():
        return FileResponse(os.path.join(frontend_dist_path, "favicon.svg"))

    @app.get("/icons.svg")
    async def serve_icons():
        return FileResponse(os.path.join(frontend_dist_path, "icons.svg"))

    @app.get("/index.html")
    async def serve_index_html():
        return FileResponse(os.path.join(frontend_dist_path, "index.html"))

    @app.get("/admin.html")
    async def serve_admin_html():
        return FileResponse(os.path.join(frontend_dist_path, "admin.html"))

    @app.get("/")
    async def root():
        return RedirectResponse(url="/app")


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "v4.1",
        "features": [
            "用户登录认证",
            "多租户数据隔离",
            "订单查询",
            "政策咨询",
            "退货申请",
            "人工审核",
            "实时状态同步",
            "管理员工作台",
        ],
    }
