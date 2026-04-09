# app/main.py
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

import app.graph.workflow as workflow_module
from app.api.v1.admin import router as admin_router
from app.api.v1.auth import router as auth_router  # v4.0 新增
from app.api.v1.chat import router as chat_router
from app.api.v1.status import router as status_router
from app.api.v1.websocket import router as websocket_router
from app.core.config import settings
from app.core.limiter import limiter
from app.graph.workflow import compile_app_graph

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(" Starting E-commerce Smart Agent v4.0...")
    workflow_module.app_graph = await compile_app_graph()
    logger.info(" Infrastructure is ready.")
    yield
    # Shutdown: close cached Qdrant client if it was created
    try:
        from app.retrieval import get_retriever
        retriever = get_retriever()
        await retriever.qdrant_client.aclose()
        logger.info(" Qdrant client closed.")
    except Exception:
        logger.warning("⚠️  Failed to close Qdrant client during shutdown")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="4.0.0",
    description="全栈·沉浸式人机协作系统 (The Immersive System) - v4.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 1. 配置跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if "*" in settings.CORS_ORIGINS:
    logger.warning(
        "CORS is configured with allow_origins=['*'] and allow_credentials=True, "
        "which poses a security risk in production."
    )

# 2. Rate limiting middleware
app.add_middleware(SlowAPIMiddleware)

# 3. 注册路由
app.include_router(auth_router, prefix=settings.API_V1_STR, tags=["Auth"])  # v4.0 新增
app.include_router(chat_router, prefix=settings.API_V1_STR, tags=["Chat"])
app.include_router(status_router, prefix=settings.API_V1_STR, tags=["Status"])
app.include_router(admin_router, prefix=settings.API_V1_STR, tags=["Admin"])
app.include_router(websocket_router, prefix=settings.API_V1_STR, tags=["WebSocket"])

# 3. 静态文件托管
frontend_dist_path = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist')

if os.path.exists(frontend_dist_path):
    @app.get('/app/{full_path:path}')
    async def serve_customer_spa(full_path: str):
        return FileResponse(os.path.join(frontend_dist_path, 'customer', 'index.html'))

    app.mount('/app', StaticFiles(directory=os.path.join(frontend_dist_path, 'customer'), html=True), name='customer_app')

    @app.get('/admin/{full_path:path}')
    async def serve_admin_spa(full_path: str):
        return FileResponse(os.path.join(frontend_dist_path, 'admin', 'index.html'))

    app.mount('/admin', StaticFiles(directory=os.path.join(frontend_dist_path, 'admin'), html=True), name='admin_app')

    @app.get('/')
    async def root():
        return RedirectResponse(url='/app')


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "v4.0",
        "features": [
            "用户登录认证",
            "多租户数据隔离",
            "订单查询",
            "政策咨询",
            "退货申请",
            "人工审核",
            "实时状态同步",
            "管理员工作台"
        ]
    }
