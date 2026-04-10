# E-commerce Smart Agent 全面改造实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前代码库从"技术栈先进但工程实践粗糙"的状态，改造为安全、测试可信、架构干净、前端健壮的生产级系统。

**Architecture:** 采用"测试先行 → 安全止血 → 架构清理 → 前端加固 → 依赖升级"的五阶段流水线。每个里程碑产生可独立验收、通过全部测试的代码增量。

**Tech Stack:** FastAPI 0.119+ / SQLModel / asyncpg / PostgreSQL 16 / Redis 7 / Celery / React 19 / Vite / Tailwind / Zustand / TanStack Query / zod / pytest

---

## 文件映射

| 类别 | 文件 | 职责 |
|------|------|------|
| **测试基础设施** | `tests/.env.test` | 本地统一测试环境变量 |
| | `tests/_db_config.py` | 测试启动前加载 `.env.test` |
| | `tests/conftest.py` | pytest fixture：引擎、会话、客户端 |
| | `pyproject.toml` | pytest markers、依赖版本 |
| **P0 安全** | `app/intent/safety.py` | 语义检测 Fail-Closed |
| | `app/services/refund_service.py` | 删除 assert，显式异常 |
| | `app/services/auth_service.py` | 删除 assert，显式异常 |
| | `app/core/security.py` | 强制 JWT exp，增加 jti |
| | `app/api/v1/websocket.py` | WebSocket Origin 校验、IP 限流 |
| | `app/api/v1/chat.py` | SSE 限流、异常处理细化 |
| | `app/main.py` | CORS 收紧、lifespan 兼容声明 |
| **P1 架构** | `app/models/state.py` | 单轨 AgentState |
| | `app/agents/router.py` | 删除遗留意图兼容层 |
| | `app/agents/base.py` | `context` 参数重命名 |
| | `app/agents/policy.py` | 同步 context_data 调用 |
| | `app/graph/tools.py` | 删除纯 wrapper 层 |
| | `app/services/refund_tool_service.py` | 下沉 `@tool` 装饰器 |
| | `app/services/risk_service.py` | 拆分 RefundRiskService |
| | `app/services/__init__.py` | 同步导出路径 |
| | `app/core/exceptions.py` | 统一异常体系 |
| | `app/tasks/refund_tasks.py` | 修复 async 阻塞、PII 脱敏 |
| **P2 前端** | `frontend/package.json` | 修正依赖版本 |
| | `frontend/tsconfig.json` | 升级 target/lib |
| | `frontend/vite.config.ts` | sourcemap |
| | `frontend/src/lib/schemas.ts` | zod 运行时 schema |
| | `frontend/src/lib/api.ts` | 统一 apiFetch + ApiError |
| | `frontend/src/stores/notifications.ts` | Zustand 通知 store |
| | `frontend/src/hooks/useAdminWebSocket.ts` | Admin WebSocket 连接管理 |
| | `frontend/src/apps/admin/pages/Dashboard.tsx` | 集成通知与 WS |
| | `frontend/src/stores/auth.ts` | localStorage → sessionStorage |
| | `frontend/src/components/ui/scroll-area.tsx` | 暴露 viewportRef |
| | `frontend/src/apps/customer/App.tsx` | 修复 scrollRef |
| | `frontend/src/hooks/useAuth.ts` | 迁移到 apiFetch |
| | `frontend/src/hooks/useTasks.ts` | 迁移到 apiFetch + zod |
| | `frontend/src/apps/customer/hooks/useChat.ts` | SSE token zod 校验 |
| **P3 长期** | `app/core/config.py` | `get_settings()` + SECRET_KEY 校验 |
| | ~60 个 backend 文件 | `settings` 导入替换 |

---

## 里程碑 1: P0 安全止血与测试拯救

> **验收标准 (M1):**
> - `POSTGRES_SERVER=nonexistent REDIS_HOST=nonexistent uv run pytest -m unit -v` 100% 通过
> - `uv run pytest` 在本地完整环境 100% 通过
> - `ruff check app tests` 全绿
> - `app/intent/safety.py` 语义检测异常时返回 `is_safe=False`
> - `app/services/refund_service.py` 与 `auth_service.py` 中无 `assert` 业务校验
> - `app/core/security.py` 解码时 `options={"require": ["exp"]}`

---

### Task 1.1: 创建本地测试环境变量文件

**Files:**
- Create: `tests/.env.test`
- Modify: `.gitignore`

- [ ] **Step 1: 写入 `tests/.env.test`**

```bash
cat > tests/.env.test << 'EOF'
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=test_knowledge_base

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=

QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=

OPENAI_API_KEY=sk-test
OPENAI_BASE_URL=http://localhost:8000/v1
DASHSCOPE_API_KEY=

SECRET_KEY=test-secret-key-at-least-32-bytes-long-123
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
ENABLE_OPENAPI_DOCS=False
CORS_ORIGINS=http://localhost:5173
EOF
```

- [ ] **Step 2: 将 `tests/.env.test` 加入 `.gitignore`**

修改 `.gitignore`，追加：
```gitignore
# Test environment variables
tests/.env.test
```

- [ ] **Step 3: Commit**

```bash
git add tests/.env.test .gitignore
git commit -m "test: add tests/.env.test for local test env isolation"
```

---

### Task 1.2: 在 `_db_config.py` 加载 `.env.test`

**Files:**
- Modify: `tests/_db_config.py`

- [ ] **Step 1: 修改 `tests/_db_config.py` 顶部**

```python
import os
from pathlib import Path

# 优先加载 tests/.env.test
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env.test"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
except ImportError:
    env_path = Path(__file__).parent / ".env.test"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def _configure_test_database() -> None:
```

- [ ] **Step 2: 运行纯单元测试验证无外部依赖**

```bash
POSTGRES_SERVER=nonexistent REDIS_HOST=nonexistent uv run pytest tests/test_security.py -v
```

**Expected:** 当前仍会失败（因为 `conftest.py` 的 `db_setup` 尚未修改），但 `_db_config.py` 应正确加载测试变量。只要报错来自 `db_setup` 的 DB 连接而非 `.env` 缺失，即说明加载成功。

- [ ] **Step 3: Commit**

```bash
git add tests/_db_config.py
git commit -m "test: load tests/.env.test before test db config"
```

---

### Task 1.3: 重构 `tests/conftest.py` 解除 `autouse` 耦合

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: 完整替换 `tests/conftest.py` 内容**

```python
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import tests._db_config  # noqa: F401, I001


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    """Session-scoped engine setup, but NOT autouse."""
    from sqlalchemy import text
    from sqlmodel import SQLModel
    from app.core.database import engine

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS confidence_audits CASCADE"))
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Test-scoped database session with automatic rollback."""
    from app.core.database import async_sessionmaker
    from sqlmodel.ext.asyncio.session import AsyncSession

    async with db_engine.connect() as conn:
        trans = await conn.begin_nested()
        Session = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
        session = Session(bind=conn)
        yield session
        await session.close()
        if trans.is_active:
            await trans.rollback()


@pytest_asyncio.fixture
async def client(db_engine):
    """API test client with database tables ready."""
    from app.core.limiter import limiter
    from app.main import app

    limiter.reset()
    async with AsyncClient(
        transport=ASGITransport(app=app, lifespan="off"), base_url="http://test"
    ) as c:
        yield c
```

- [ ] **Step 2: 在 `pyproject.toml` 注册 pytest markers**

在 `[tool.pytest.ini_options]` 中追加：

```toml
markers = [
    "unit: Pure unit tests with no DB/external services",
    "db: Tests requiring PostgreSQL",
    "redis: Tests requiring Redis",
    "api: API/integration tests",
    "websocket: WebSocket tests",
]
```

- [ ] **Step 3: 运行测试确认 fixture 可用**

```bash
uv run pytest tests/test_users.py -v -m db
```

**Expected:** `test_users.py` 通过（它直接操作 DB，此时 `db_engine` 已被显式请求）。

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py pyproject.toml
git commit -m "test: decouple conftest fixtures, remove autouse=True"
```

---

### Task 1.4: 给测试文件分类打 marker

**Files:**
- Modify: `tests/test_security.py`
- Modify: `tests/test_main_security.py`
- Modify: `tests/test_logging.py`
- Modify: `tests/test_users.py`

- [ ] **Step 1: 给 `tests/test_security.py` 顶部加 marker**

```python
import pytest

pytestmark = pytest.mark.unit
```

加到 `from datetime import timedelta` 之前。

- [ ] **Step 2: 给 `tests/test_main_security.py` 顶部加 marker，并修改 OpenAPI 测试使用 `lifespan="off"`**

顶部加：
```python
pytestmark = [pytest.mark.unit, pytest.mark.api]
```

修改 `TestOpenAPIDocsControl` 中的两个 `ASGITransport` 构造：
```python
async with httpx.AsyncClient(
    transport=ASGITransport(app=app, lifespan="off"), base_url="http://test"
) as client:
```

- [ ] **Step 3: 给 `tests/test_logging.py` 按类加 marker 并关闭 lifespan**

纯单元类标记：
```python
pytestmark = pytest.mark.unit
```

`TestMiddlewareIntegration` 和 `TestWebSocketCorrelationId` 不继承文件级 `pytestmark`，单独在类上加 `@pytest.mark.api` / `@pytest.mark.websocket`。同时，这两个类使用的 `ASGITransport` 和 `TestClient` 必须加上 `lifespan="off"`，防止触发 Redis 连接：

```python
from httpx import ASGITransport
from starlette.testclient import TestClient

# MiddlewareIntegration
async with httpx.AsyncClient(
    transport=ASGITransport(app=app, lifespan="off"), base_url="http://test"
) as client:

# WebSocketCorrelationId
test_client = TestClient(app, lifespan="off")
```

- [ ] **Step 4: 给 `tests/test_users.py` 顶部加 marker**

```python
import pytest

pytestmark = pytest.mark.db
```

- [ ] **Step 4.5: 修复 `tests/test_chat_api.py` 的 `auth_token` fixture 依赖**

`auth_token` fixture（约 line 15）使用 `async_session_maker()` 直接操作数据库，但未声明 `db_engine` 依赖。在新 conftest 中 `db_engine` 已不再是 `autouse`，因此必须显式依赖它：

```python
@pytest_asyncio.fixture(scope="session")
async def auth_token(db_engine):
    from app.core.database import async_session_maker
    ...
```

- [ ] **Step 5: 运行纯单元测试验收**

```bash
POSTGRES_SERVER=nonexistent REDIS_HOST=nonexistent uv run pytest -m unit -v
```

**Expected:** `test_security.py` 和 `test_main_security.py` 中的 `TestCORSDangerousComboBlock` 通过。`test_logging.py` 中的纯 unit 类也通过。

**注意：**大量测试文件尚未标记。在 M1 验收通过后，建议继续为所有测试文件补全 markers，以便 CI 选择性执行。

- [ ] **Step 6: Commit**

```bash
git add tests/test_security.py tests/test_main_security.py tests/test_logging.py tests/test_users.py
git commit -m "test: classify tests with pytest markers"
```

---

### Task 1.5: 修复 `tests/test_users.py` 使用 `db_session` fixture

**Files:**
- Modify: `tests/test_users.py`

- [ ] **Step 1: 完整替换 `tests/test_users.py`**

```python
from datetime import UTC, datetime

import pytest
from sqlmodel import select

from app.models.user import User

pytestmark = pytest.mark.db


@pytest.mark.asyncio
async def test_create_and_query_user(db_session):
    from app.core.database import async_session_maker

    # 清理可能存在的旧测试数据
    result = await db_session.exec(select(User).where(User.username == "test_alice_pytest"))
    existing = result.one_or_none()
    if existing:
        await db_session.delete(existing)
        await db_session.commit()

    now = datetime.now(UTC).replace(tzinfo=None)
    user = User(
        username="test_alice_pytest",
        email="alice_pytest@test.com",
        full_name="Alice Test",
        phone="13800138001",
        password_hash="fakehash",
        is_admin=False,
        created_at=now,
        updated_at=now,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    result = await db_session.exec(select(User).where(User.username == "test_alice_pytest"))
    found = result.one_or_none()
    assert found is not None
    assert found.email == "alice_pytest@test.com"
```

- [ ] **Step 2: 运行测试**

```bash
uv run pytest tests/test_users.py -v
```

**Expected:** PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_users.py
git commit -m "test: refactor test_users.py to use db_session fixture"
```

---

### Task 1.6: `safety.py` 语义检测 Fail-Closed

**Files:**
- Modify: `app/intent/safety.py` (~L310)

- [ ] **Step 1: 修改 `_check_semantic` 的异常处理**

找到 `_check_semantic` 方法中的：
```python
except Exception as e:
    logger.error(f"Semantic check failed: {e}")
```

在其后、方法返回之前，插入 Fail-Closed 返回：

```python
        except Exception as e:
            logger.error(f"Semantic check failed: {e}")
            return SafetyCheckResult(
                is_safe=False,
                risk_level="high",
                risk_type="semantic",
                reason="语义检测服务异常，请求已被拦截",
            )
```

确保原方法末尾的 `return SafetyCheckResult(is_safe=True, ...)` 被这个异常分支替代。

- [ ] **Step 2: 运行 safety 相关测试**

```bash
uv run pytest tests/intent/test_safety.py -v
```

**Expected:** 测试通过（如有失败，检查测试是否预期了旧行为）。

- [ ] **Step 3: Commit**

```bash
git add app/intent/safety.py
git commit -m "security: fail-closed semantic safety check on LLM error"
```

---

### Task 1.7: 删除 `refund_service.py` 与 `auth_service.py` 中的 assert

**Files:**
- Modify: `app/services/refund_service.py`
- Modify: `app/services/auth_service.py`

- [ ] **Step 1: 修改 `app/services/refund_service.py` L46**

```python
# 改造前
assert order.id is not None

# 改造后
if order.id is None:
    raise ValueError("订单 ID 不能为空，数据异常")
```

- [ ] **Step 2: 修改 `app/services/auth_service.py` L17 附近**

```python
# 改造前
assert user.id is not None

# 改造后
if user.id is None:
    raise ValueError("用户 ID 不能为空")
```

- [ ] **Step 3: 运行相关测试**

```bash
uv run pytest tests/test_refund_service.py tests/test_auth_api.py -v
```

**Expected:** PASS（或至少不因为此修改产生新失败）。

- [ ] **Step 4: Commit**

```bash
git add app/services/refund_service.py app/services/auth_service.py
git commit -m "security: replace assert-based validation with explicit ValueError"
```

---

### Task 1.8: `security.py` 强制 JWT exp 与增加 jti

**Files:**
- Modify: `app/core/security.py`

- [ ] **Step 1: 修改 `create_access_token` 增加 jti**

```python
import uuid

# 在 create_access_token 中
    to_encode = {
        "sub": str(user_id),
        "is_admin": is_admin,
        "jti": str(uuid.uuid4()),
    }
    expire = utc_now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": utc_now()})
```

- [ ] **Step 2: 修改 `_decode_token` 要求 exp**

找到 `jwt.decode` 调用，改为：
```python
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp"]},
        )
```

- [ ] **Step 3: 运行 security 测试**

```bash
uv run pytest tests/test_security.py -v
```

**Expected:** PASS

- [ ] **Step 4: Commit**

```bash
git add app/core/security.py
git commit -m "security: require JWT exp and add jti claim"
```

---

### Task 1.9: WebSocket Origin 校验与 CORS 收紧

**Files:**
- Modify: `app/api/v1/websocket.py`
- Modify: `app/main.py`

- [ ] **Step 1: 修改 `app/api/v1/websocket.py`，在两个 endpoint 开头增加 Origin 校验**

在 `websocket_endpoint` 中，token 提取之后、用户验证之前：
```python
    origin = websocket.headers.get("origin", "")
    allowed_origins = set(settings.CORS_ORIGINS)
    if origin and origin not in allowed_origins:
        await websocket.close(code=1008)
        return
```

同理在 `admin_websocket_endpoint` 中也加入完全相同的校验块。

- [ ] **Step 2: 修改 `app/main.py` CORS 配置**

```python
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Correlation-ID"],
        max_age=600,
    )
```

- [ ] **Step 3: 运行受影响测试**

```bash
uv run pytest tests/test_main_security.py tests/test_websocket.py -v
```

**Expected:** PASS

- [ ] **Step 4: Commit**

```bash
git add app/api/v1/websocket.py app/main.py
git commit -m "security: add WebSocket origin validation and tighten CORS"
```

---

### Task 1.10: 后端 Rate Limiting 补全

**Files:**
- Modify: `app/api/v1/chat.py`
- Modify: `app/api/v1/auth.py`
- Modify: `app/api/v1/websocket.py`

- [ ] **Step 1: 给 `/register` 和 `/login` 加限流**

在 `app/api/v1/auth.py` 中，找到 `/register` 和 `/login` endpoint，分别增加：
```python
@limiter.limit("5/minute")
```

确保已导入 `from app.core.limiter import limiter`。

- [ ] **Step 2: 给 SSE `/chat` 加限流**

在 `app/api/v1/chat.py` 的 `chat` endpoint 上增加：
```python
@limiter.limit("30/minute")
```

并确保 endpoint 签名包含 `Request` 对象（`slowapi` 需要它）：
```python
from fastapi import Request

@router.post("/chat")
@limiter.limit("30/minute")
async def chat(
    request: Request,
    chat_request: ChatRequest,
    current_user_id: int = Depends(get_current_user_id),
):
```

- [ ] **Step 3: WebSocket IP 并发限流（Redis 计数）**

修改 `app/api/v1/websocket.py`：

```python
from app.core.redis import get_redis_client

_MAX_WS_PER_IP = 5
_WS_IP_KEY = "ws:conn:{ip}"

async def _check_ws_ip_limit(ip: str) -> bool:
    try:
        redis = get_redis_client()
        key = _WS_IP_KEY.format(ip=ip)
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, 60)
        return current <= _MAX_WS_PER_IP
    except Exception:
        # Redis 不可用时 fail-closed：拒绝连接
        return False

async def _release_ws_ip_limit(ip: str) -> None:
    try:
        redis = get_redis_client()
        key = _WS_IP_KEY.format(ip=ip)
        current = await redis.get(key)
        if current and int(current) > 0:
            await redis.decr(key)
    except Exception:
        pass
```

在两个 WebSocket endpoint 的 `manager.connect_*` 之前调用（**注意**：`manager.connect_user()` / `manager.connect_admin()` 内部已调用 `accept()`，此处不要再重复调用）：
```python
    client_ip = websocket.client.host if websocket.client else "unknown"
    if not await _check_ws_ip_limit(client_ip):
        await websocket.close(code=1008)
        return
```

在连接关闭的 finally 块中调用（使用正确的 disconnect 方法名）：
```python
    finally:
        if is_user_endpoint:
            await manager.disconnect_user(websocket)
        else:
            await manager.disconnect_admin(websocket)
        await _release_ws_ip_limit(client_ip)
```

- [ ] **Step 4: 运行测试**

```bash
uv run pytest tests/test_auth_rate_limit.py tests/test_chat_api.py -v
```

**Expected:** PASS

- [ ] **Step 5: Commit**

```bash
git add app/api/v1/auth.py app/api/v1/chat.py app/api/v1/websocket.py
git commit -m "security: add rate limiting to auth, chat, and websocket endpoints"
```

---

### Task 1.11: 密码策略强化

**Files:**
- Modify: `app/api/v1/auth.py` (包含 `RegisterRequest` 的文件)

- [ ] **Step 1: 找到 `RegisterRequest` 并修改密码校验**

```python
from pydantic import field_validator

class RegisterRequest(BaseModel):
    # ... existing fields ...
    password: str

    @field_validator("password")
    @classmethod
    def _validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("密码长度至少为 8 位")
        has_lower = any(c.islower() for c in v)
        has_upper = any(c.isupper() for c in v)
        has_digit = any(c.isdigit() for c in v)
        if sum([has_lower, has_upper, has_digit]) < 2:
            raise ValueError("密码必须包含大写字母、小写字母、数字中的至少两种")
        return v
```

- [ ] **Step 2: 运行 auth 测试**

```bash
uv run pytest tests/test_auth_api.py -v
```

**Expected:** 可能需要同步更新测试中的测试密码（从 6 位改为 8 位且含两种字符类型）。

- [ ] **Step 3: Commit**

```bash
git add app/api/v1/auth.py
git commit -m "security: strengthen password policy to 8 chars with 2 of 3 character types"
```

---

### Task 1.12: PII 日志脱敏

**Files:**
- Modify: `app/tasks/refund_tasks.py`

- [ ] **Step 1: 在 `send_refund_sms` 和相关日志处增加脱敏辅助函数**

在文件顶部增加：
```python
def _mask_phone(phone: str | None) -> str:
    if not phone or len(phone) < 7:
        return "***"
    return f"{phone[:3]}****{phone[-4:]}"
```

- [ ] **Step 2: 替换日志中的敏感信息**

找到所有包含 `phone` 和 `content` 的 `logger.info` / `logger.error`，将 `phone` 替换为 `_mask_phone(phone)`，将短信 `content` 替换为仅记录长度：
```python
logger.info(
    f"发送退款短信通知给用户 {_mask_phone(phone)}，内容长度 {len(content)} 字符"
)
```

- [ ] **Step 3: Commit**

```bash
git add app/tasks/refund_tasks.py
git commit -m "security: mask phone numbers and omit SMS content from logs"
```

---

### Task 1.13: M1 回归测试

- [ ] **Step 1: 全量测试**

```bash
uv run pytest -v
```

- [ ] **Step 2: 纯单元测试隔离验证**

```bash
POSTGRES_SERVER=nonexistent REDIS_HOST=nonexistent uv run pytest -m unit -v
```

**Expected:** 100% PASS

- [ ] **Step 3: 覆盖率检查**

```bash
uv run pytest --cov=app --cov-fail-under=75
```

**Expected:** PASS

- [ ] **Step 4: ruff 检查**

```bash
uv run ruff check app tests
```

**Expected:** 全绿

---

## 里程碑 2: P1 架构精简

> **验收标准 (M2):**
> - `grep -r "audit_required\|audit_type\|normalize_state\|get_audit_required\|get_audit_level_from_old\|\"context\"\b" app/ tests/` 返回 0 结果
> - `app/graph/tools.py` 已删除
> - `grep -r "time.sleep" app/` 返回空（ Celery async 协程内无阻塞）
> - `app/core/exceptions.py` 已创建，所有裸 `except Exception` 已替换为精确异常捕获
> - `uv run pytest` 100% 通过

---

### Task 2.1: 状态模型单轨化 — `app/models/state.py`

**Files:**
- Modify: `app/models/state.py`
- Modify: `app/agents/policy.py`
- Modify: `app/api/v1/chat.py`
- Modify: `app/agents/router.py`
- Modify: `app/agents/base.py`
- Modify: `app/agents/__init__.py`

- [ ] **Step 1: 精简 `AgentState` TypedDict**

修改 `app/models/state.py`：

```python
class AgentState(TypedDict):
    question: str
    user_id: int
    thread_id: str
    intent: str | None
    current_agent: str | None
    next_agent: str | None
    iteration_count: int
    retry_requested: bool
    history: Annotated[list[dict[str, Any]], operator.add]
    retrieval_result: RetrievalResult | None
    order_data: dict[str, Any] | None
    audit_level: str | None  # "none" | "auto" | "manual"
    audit_log_id: int | None
    audit_reason: str | None
    confidence_score: float | None
    confidence_signals: dict[str, Any] | None
    needs_human_transfer: bool
    transfer_reason: str | None
    messages: Annotated[list[dict[str, Any]], operator.add]
    answer: str
    refund_flow_active: bool | None
    refund_order_sn: str | None
    refund_step: str | None
```

删除 `context`、`audit_required`、`audit_type` 字段。

- [ ] **Step 2: 删除 `normalize_state` 及相关兼容函数**

删除 `normalize_state`、`get_audit_required`、`get_audit_level_from_old` 三个函数的全部定义。

- [ ] **Step 3: 精简 `make_agent_state` 签名**

```python
def make_agent_state(
    question: str,
    user_id: int,
    thread_id: str,
    history: list[dict[str, Any]] | None = None,
    retrieval_result: RetrievalResult | None = None,
    order_data: dict[str, Any] | None = None,
    audit_level: str | None = None,
    audit_log_id: int | None = None,
    audit_reason: str | None = None,
    confidence_score: float | None = None,
    confidence_signals: dict[str, Any] | None = None,
    needs_human_transfer: bool = False,
    transfer_reason: str | None = None,
    messages: list[dict[str, Any]] | None = None,
    answer: str = "",
    refund_flow_active: bool | None = None,
    refund_order_sn: str | None = None,
    refund_step: str | None = None,
) -> AgentState:
```

函数体同步删除 `context`、`audit_required`、`audit_type` 参数和字典赋值。

- [ ] **Step 4: 修改 `app/agents/policy.py` 删除 `context` 兼容字段**

找到返回 `AgentState` 更新的地方，删除 `"context": chunks` 或类似字段。只保留 `"retrieval_result": retrieval_result`。

- [ ] **Step 5: 修改 `app/agents/base.py` 参数重命名**

```python
    def _create_messages(
        self, user_message: str, context_data: dict[str, Any] | None = None
    ) -> list[BaseMessage]:

    def _build_contextual_message(
        self, question: str, context_data: dict[str, Any] | None = None
    ) -> SystemMessage:
```

同步修改方法体内的 `context` 引用为 `context_data`。注意：`_build_contextual_message` 内部读取的 dict key 仍为 `"context"`（与现有 Prompt 模板兼容），因此 `PolicyAgent` 调用时继续传入 `"context"` 键。

- [ ] **Step 6: 修改 `app/agents/policy.py` 调用点**

```python
context_data={"context": chunks, "order_data": state.get("order_data")}
```

- [ ] **Step 7: 修改 `app/api/v1/chat.py` 的 `initial_state`**

删除 `"context"`、`"audit_required"`、`"audit_type"`，改为使用 `make_agent_state`：

```python
from app.models.state import make_agent_state

initial_state = make_agent_state(
    question=request.question,
    user_id=current_user_id,
    thread_id=thread_id,
)
```

- [ ] **Step 8: 修改 `app/agents/router.py` 删除遗留意图层**

删除 `Intent` Enum 定义、`_map_to_legacy_intent` 方法。`RouterState` 中的 `intent` 字段类型改为 `str`。

将 `process` 方法中的 `legacy_intent = self._map_to_legacy_intent(result)` 改为直接使用 `result.primary_intent`（根据 `IntentResult` 实际结构使用其字符串值）。确保 `OTHER` intent 的处理逻辑同步更新为字符串比较。

- [ ] **Step 9: 修改 `app/agents/__init__.py`**

删除 `RouterAgent = IntentRouterAgent` 兼容别名。

- [ ] **Step 10: 更新相关测试文件中的 `context` 引用**

修改以下测试文件，将 `"context"` 替换为 `"retrieval_result"`：
- `tests/graph/test_nodes.py`：将 `updated_state={"context": [...]}` 改为使用 `retrieval_result`
- `tests/agents/test_policy_legacy.py`：将 `result.updated_state["context"]` 断言改为 `result.updated_state["retrieval_result"]`

- [ ] **Step 11: 全局搜索确认无遗漏**

```bash
grep -r "audit_required\|audit_type\|normalize_state\|get_audit_required\|get_audit_level_from_old\|\"context\"\b" app/ tests/
```

**Expected:** 0 结果。

- [ ] **Step 12: 运行测试**

```bash
uv run pytest tests/agents/ tests/graph/ tests/test_chat_api.py -v
```

**Expected:** PASS

- [ ] **Step 13: Commit**

```bash
git add app/models/state.py app/agents/policy.py app/agents/base.py app/agents/router.py app/agents/__init__.py app/api/v1/chat.py
git commit -m "arch: single-track AgentState, remove legacy context and audit compatibility"
```

---

### Task 2.2: 拆分 `RefundRiskService` 至独立模块

**Files:**
- Create: `app/services/risk_service.py`
- Modify: `app/services/refund_service.py`
- Modify: `app/services/__init__.py`

- [ ] **Step 1: 新建 `app/services/risk_service.py`**

```python
from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.core.config import settings
from app.models.audit import AuditAction, AuditTriggerType, RiskLevel

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.models.order import Order


class RefundRiskService:
    """评估退款风险并创建审计记录。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def assess_and_create_audit(
        self,
        session: AsyncSession,
        refund: object,
        order: Order,
        user_id: int,
        thread_id: str,
    ) -> AuditLog | None:
        """保持与现有调用方 `order_service.py:106` 的签名兼容。"""
        if order.id is None:
            raise ValueError("订单 ID 不能为空，数据异常")

        refund_reason = getattr(refund, "reason", "")
        refund_amount = getattr(refund, "amount", 0.0)

        # 简化风险规则：高额退款或特定原因触发人工审核
        if refund_amount > 1000 or "欺诈" in refund_reason:
            risk_level = RiskLevel.HIGH
            audit_action = AuditAction.MANUAL_REVIEW
        else:
            risk_level = RiskLevel.LOW
            audit_action = AuditAction.AUTO_APPROVE

        audit_log = AuditLog(
            order_id=order.id,
            action=audit_action,
            trigger_type=AuditTriggerType.REFUND,
            risk_level=risk_level,
            reason=refund_reason,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(audit_log)
        await session.commit()
        await session.refresh(audit_log)

        return audit_log
```

- [ ] **Step 2: 从 `app/services/refund_service.py` 删除 `RefundRiskService` 类**

保留 `RefundEligibilityChecker`、`RefundApplicationService`、`process_refund_for_order` 和 `get_order_by_sn`。

- [ ] **Step 3: 更新 `app/services/__init__.py`**

```python
from app.services.refund_service import (
    RefundApplicationService,
    RefundEligibilityChecker,
    get_order_by_sn,
    process_refund_for_order,
)
from app.services.risk_service import RefundRiskService

__all__ = [
    "RefundApplicationService",
    "RefundEligibilityChecker",
    "RefundRiskService",
    "get_order_by_sn",
    "process_refund_for_order",
]
```

- [ ] **Step 4: 更新 `app/services/order_service.py` 导入路径**

将 `app/services/order_service.py` 中的 `RefundRiskService` 导入改为：
```python
from app.services import RefundRiskService
# 或 from app.services.risk_service import RefundRiskService
```

确保 `order_service.py:106` 附近的调用方式保持不变（因为 `assess_and_create_audit` 签名已保持兼容）。

- [ ] **Step 5: 全局搜索其他 `RefundRiskService` 引用并更新**

```bash
grep -r "RefundRiskService" app/ tests/
```

将所有剩余的 `from app.services.refund_service import RefundRiskService` 改为从新路径导入。

- [ ] **Step 6: 运行退款相关测试**

```bash
uv run pytest tests/test_refund_service.py tests/test_refund_tasks.py -v
```

**Expected:** PASS

- [ ] **Step 7: Commit**

```bash
git add app/services/risk_service.py app/services/refund_service.py app/services/__init__.py app/services/order_service.py
git commit -m "arch: extract RefundRiskService into risk_service.py"
```

---

### Task 2.3: 删除 `graph/tools.py` 并下沉 `@tool`

**Files:**
- Delete: `app/graph/tools.py`
- Modify: `app/services/refund_tool_service.py`

- [ ] **Step 1: 在 `app/services/refund_tool_service.py` 中添加 `@tool` 装饰器**

确保三个函数已有 `@tool` 装饰器（如没有则添加）：

```python
from langchain_core.tools import tool
from pydantic import Field
from typing import Annotated

@tool
async def check_refund_eligibility(
    order_sn: Annotated[str, Field(description="订单号，格式如 SN20240001")],
    user_id: Annotated[int, Field(description="当前登录用户的ID")],
) -> str:
    ...

@tool
async def submit_refund_application(...) -> str:
    ...

@tool
async def query_refund_status(...) -> str:
    ...
```

并在文件末尾导出：
```python
refund_tools = [
    check_refund_eligibility,
    submit_refund_application,
    query_refund_status,
]
```

- [ ] **Step 2: 删除 `app/graph/tools.py`**

```bash
rm app/graph/tools.py
```

- [ ] **Step 3: 更新引用并处理测试文件**

```bash
grep -r "app.graph.tools" app/ tests/
```

如 `graph/nodes.py` 或 `graph/workflow.py` 有引用，改为：
```python
from app.services.refund_tool_service import refund_tools
```

同时更新 `tests/graph/test_tools.py`：将其导入源从 `app.graph.tools` 改为 `app.services.refund_tool_service`，并调整 patch 路径。如果该测试仅验证装饰器包装行为，可直接删除该测试文件。

- [ ] **Step 4: 运行 graph 测试**

```bash
uv run pytest tests/graph/ -v
```

**Expected:** PASS

- [ ] **Step 5: Commit**

```bash
git add -A app/graph/ app/services/refund_tool_service.py
git commit -m "arch: delete graph/tools.py wrapper, move @tool to refund_tool_service"
```

---

### Task 2.4: 建立统一异常体系 `app/core/exceptions.py`

**Files:**
- Create: `app/core/exceptions.py`

- [ ] **Step 1: 创建异常基类**

```python
class AppError(Exception):
    """应用层根异常"""
    pass


class ExternalAPIError(AppError):
    """外部 API 调用失败（LLM、Embedding、Qdrant 等）"""
    def __init__(self, message: str, source: str):
        super().__init__(message)
        self.source = source


class ServiceUnavailableError(AppError):
    """内部服务不可用（数据库、Redis、WebSocket）"""
    pass


class ValidationError(AppError):
    """业务校验失败"""
    pass


class SecurityCheckError(AppError):
    """安全检查未通过"""
    pass
```

- [ ] **Step 2: Commit**

```bash
git add app/core/exceptions.py
git commit -m "arch: introduce unified exception hierarchy in app/core/exceptions.py"
```

---

### Task 2.5: 逐文件替换裸 `except Exception`

**Files:**
- Modify: `app/services/order_service.py`
- Modify: `app/retrieval/retriever.py`
- Modify: `app/retrieval/rewriter.py`
- Modify: `app/confidence/signals.py`
- Modify: `app/intent/service.py`
- Modify: `app/websocket/manager.py`
- Modify: `app/services/admin_service.py`
- Modify: `app/api/v1/chat.py`
- Modify: `app/api/v1/websocket.py`
- Modify: `app/tasks/refund_tasks.py`

- [ ] **Step 1: `app/services/order_service.py`**

```python
from sqlalchemy.exc import SQLAlchemyError
from app.core.exceptions import ServiceUnavailableError, AppError

try:
    ...
except SQLAlchemyError as exc:
    logger.warning("Database error in order_service", exc_info=True)
    raise ServiceUnavailableError("订单数据库暂不可用") from exc
except Exception as exc:
    logger.error("Unexpected error in order_service", exc_info=True)
    raise AppError("查询订单失败") from exc
```

- [ ] **Step 2: `app/retrieval/retriever.py`**

稀疏嵌入器降级：
```python
except RuntimeError as exc:
    logger.warning("Sparse embedder failed, falling back", exc_info=True)
    sparse_results = []
except Exception as exc:
    raise AppError("稀疏检索意外失败") from exc
```

Reranker 降级：
```python
except (httpx.HTTPError, httpx.TimeoutException) as exc:
    logger.warning("Reranker failed, returning unsorted results", exc_info=True)
    return results
except Exception as exc:
    raise AppError("重排序意外失败") from exc
```

- [ ] **Step 3: `app/retrieval/rewriter.py`**

```python
from app.core.exceptions import ExternalAPIError

try:
    ...
except ExternalAPIError as exc:
    logger.warning("Query rewrite failed, using original query", exc_info=True)
    return query
except Exception as exc:
    raise AppError("查询重写意外失败") from exc
```

- [ ] **Step 4: `app/confidence/signals.py`**

```python
from app.core.exceptions import ExternalAPIError

try:
    ...
except ExternalAPIError as exc:
    logger.warning("Confidence LLM evaluation failed", exc_info=True)
    return None
except Exception as exc:
    raise AppError("置信度评估意外失败") from exc
```

- [ ] **Step 5: `app/intent/service.py`**

```python
import redis

try:
    ...
except (redis.ConnectionError, redis.TimeoutError) as exc:
    logger.warning("Redis unavailable for intent cache", exc_info=True)
    return None
except Exception as exc:
    raise AppError("意图服务意外失败") from exc
```

- [ ] **Step 6: `app/websocket/manager.py` 与 `app/services/admin_service.py`**

区分 `WebSocketDisconnect`（正常）与 `RuntimeError`（记录 warning）：

```python
from starlette.websockets import WebSocketDisconnect

try:
    await websocket.send_text(message)
except WebSocketDisconnect:
    await self.disconnect(websocket)
except RuntimeError as exc:
    logger.warning("WebSocket send failed", exc_info=True)
    await self.disconnect(websocket)
except Exception as exc:
    logger.error("Unexpected WebSocket error", exc_info=True)
    await self.disconnect(websocket)
```

- [ ] **Step 7: `app/api/v1/chat.py` SSE 异常处理细化**

```python
import asyncio
from fastapi import HTTPException
from app.core.exceptions import AppError

try:
    ...
except asyncio.CancelledError:
    raise
except HTTPException:
    raise
except AppError as exc:
    logger.error("Chat AppError", exc_info=True)
    yield create_stream_metadata_message({"error": "服务内部错误"})
except Exception as exc:
    logger.error("Unexpected chat error", exc_info=True)
    yield create_stream_metadata_message({"error": "服务内部错误"})
```

- [ ] **Step 8: `app/api/v1/websocket.py`**

```python
from starlette.websockets import WebSocketDisconnect
from fastapi import HTTPException

try:
    ...
except WebSocketDisconnect:
    logger.info("WebSocket disconnected")
except HTTPException:
    logger.warning("WebSocket HTTP exception")
except Exception as exc:
    logger.error("Unexpected WebSocket error", exc_info=True)
finally:
    await manager.disconnect(websocket)
```

- [ ] **Step 9: `app/tasks/refund_tasks.py`**

捕获具体异常类型，避免裸 `except Exception`：

```python
from sqlalchemy.exc import SQLAlchemyError
from app.core.exceptions import AppError

try:
    ...
except SQLAlchemyError as exc:
    logger.error("Refund task DB error", exc_info=True)
    raise
except AppError as exc:
    logger.error("Refund task business error", exc_info=True)
    raise
except Exception as exc:
    logger.error("Refund task unexpected error", exc_info=True)
    raise
```

- [ ] **Step 10: 运行全量测试**

```bash
uv run pytest -v
```

**Expected:** PASS

- [ ] **Step 11: Commit**

```bash
git add app/services/order_service.py app/retrieval/retriever.py app/retrieval/rewriter.py app/confidence/signals.py app/intent/service.py app/websocket/manager.py app/services/admin_service.py app/api/v1/chat.py app/api/v1/websocket.py app/tasks/refund_tasks.py
git commit -m "arch: replace bare except Exception with precise exception handling"
```

---

### Task 2.6: 修复 Celery 异步阻塞

**Files:**
- Modify: `app/tasks/refund_tasks.py`

- [ ] **Step 1: 将 `time.sleep` 替换为 `asyncio.sleep`**

删除 `import time`，确保 `import asyncio` 存在。

在 `send_refund_sms` 的异步子协程中：
```python
# 改造前
import time
time.sleep(2)

# 改造后
import asyncio
await asyncio.sleep(2)
```

在 `process_refund_payment` 的异步子协程中：
```python
# 改造前
time.sleep(3)

# 改造后
await asyncio.sleep(3)
```

- [ ] **Step 2: 验证无遗漏**

```bash
grep -r "time.sleep" app/
```

**Expected:** 0 结果（仅限 app/ 目录）。

- [ ] **Step 3: 运行 refund task 测试**

```bash
uv run pytest tests/test_refund_tasks.py -v
```

**Expected:** PASS

- [ ] **Step 4: Commit**

```bash
git add app/tasks/refund_tasks.py
git commit -m "fix: replace time.sleep with asyncio.sleep in Celery async coroutines"
```

---

### Task 2.7: 消除函数内导入与循环依赖

**Files:**
- Modify: `app/api/v1/chat.py`
- Modify: `app/agents/router.py`
- Modify: `app/services/refund_service.py`

- [ ] **Step 1: `app/api/v1/chat.py` 延迟初始化工厂**

删除顶部的 `from app.graph.workflow import app_graph`。

添加工厂函数：
```python
def get_app_graph():
    from app.graph.workflow import app_graph
    return app_graph
```

在 `chat` endpoint 中：
```python
graph = get_app_graph()
if graph is None:
    raise HTTPException(status_code=503, detail="Chat service not ready")
```

- [ ] **Step 2: `app/agents/router.py` 依赖注入 Redis**

```python
from app.core.redis import get_redis_client

class IntentRouterAgent:
    def __init__(self, llm=None, redis_client=None) -> None:
        super().__init__(name="intent_router", system_prompt=None)
        self.intent_service = IntentRecognitionService(
            redis_client=redis_client or get_redis_client()
        )
```

删除 `__init__` 中的 `from app.core.redis import get_redis_client` 局部导入。

- [ ] **Step 3: `app/services/refund_service.py` 删除方法内局部导入**

在 `assess_and_create_audit`（若仍存在于 refund_service.py 中；如已拆分则跳过）中，删除：
```python
from app.core.config import settings
from app.models.audit import AuditAction, AuditTriggerType, RiskLevel
```

因为该文件顶部已导入 `AuditLog` 和 `settings`。

- [ ] **Step 4: 验证**

```bash
grep -r "^\s*from app\.\..* import" app/ | grep -v "^\s*from app\.(core|models|api|agents|graph|services|utils|intent|retrieval|tasks|websocket|schemas)" | grep -v "def get_app_graph"
```

**Expected:** 无非法函数内导入。

- [ ] **Step 5: 运行全量测试**

```bash
uv run pytest -v
```

- [ ] **Step 6: Commit**

```bash
git add app/api/v1/chat.py app/agents/router.py app/services/refund_service.py
git commit -m "arch: eliminate lazy imports via factory and dependency injection"
```

---

### Task 2.8: 迁移 `chat_utils.py` 业务常量

**Files:**
- Create: `app/core/constants.py` (或 `app/schemas/chat.py`)
- Modify: `app/api/v1/chat_utils.py`

- [ ] **Step 1: 创建 `app/core/constants.py`**

```python
from enum import Enum


class TransferReason(str, Enum):
    POLICY = "policy"
    ORDER = "order"
    REFUND = "refund"
    CONFIDENCE = "confidence"
    SAFETY = "safety"
    ERROR = "error"


TRANSFER_REASON_MAP: dict[TransferReason, str] = {
    TransferReason.POLICY: "政策相关问题需要人工确认",
    TransferReason.ORDER: "订单问题需要人工处理",
    TransferReason.REFUND: "退款问题需要人工审核",
    TransferReason.CONFIDENCE: "系统置信度低，需要人工介入",
    TransferReason.SAFETY: "检测到潜在风险，已转交人工",
    TransferReason.ERROR: "系统处理异常，已转交人工",
}
```

- [ ] **Step 2: 修改 `app/api/v1/chat_utils.py`**

删除文件中的 `TransferReason` 和 `TRANSFER_REASON_MAP` 定义，改为：
```python
from app.core.constants import TransferReason, TRANSFER_REASON_MAP
```

- [ ] **Step 3: Commit**

```bash
git add app/core/constants.py app/api/v1/chat_utils.py
git commit -m "arch: move TransferReason constants from api layer to core/constants"
```

---

### Task 2.9: M2 回归测试

- [ ] **Step 1: 全量测试**

```bash
uv run pytest -v
```

- [ ] **Step 2: 关键 grep 验收**

```bash
grep -r "audit_required\|audit_type\|normalize_state\|get_audit_required\|get_audit_level_from_old\|\"context\"\b" app/ tests/ || echo "PASS"
grep -r "time.sleep" app/ || echo "PASS"
```

**Expected:** 均输出 "PASS"（即 grep 无结果）。

- [ ] **Step 3: ruff + ty**

```bash
uv run ruff check app tests
uv run ty check --error-on-warning
```

**Expected:** 全绿

---

## 里程碑 3: P2 前端加固

> **验收标准 (M3):**
> - `npm run build` 成功，无类型错误
> - `npm run test:e2e` 通过
> - `@types/node` 版本为 `22.x`，`typescript` 版本为 `~5.8.2`，`react-router-dom` 版本为 `^6.30.0`
> - `localStorage` 已替换为 `sessionStorage`
> - `scrollRef` 自动滚底功能正常
> - 管理员通知功能在 E2E 中可验证（WebSocket mock 或 HTTP fallback）

---

### Task 3.1: 修正前端依赖版本

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/tsconfig.json`
- Modify: `frontend/vite.config.ts`

- [ ] **Step 1: 修改 `frontend/package.json` 关键依赖**

```json
{
  "dependencies": {
    "react": "^19.2.4",
    "react-dom": "^19.2.4",
    "react-router-dom": "^6.30.0",
    "@tanstack/react-query": "^5.96.2",
    "zustand": "^5.0.12",
    "zod": "^3.24.0"
  },
  "devDependencies": {
    "@types/node": "^22.14.0",
    "@vitejs/plugin-react-swc": "^4.3.0",
    "typescript": "~5.8.2",
    "vite": "^8.0.4"
  }
}
```

注意：
- `@types/node` 从 `^25.5.2` 改为 `^22.14.0`
- `typescript` 从 `~6.0.2` 改为 `~5.8.2`
- `react-router-dom` 从 `^7.14.0` 降级为 `^6.30.0`
- `@vitejs/plugin-react-swc` 从 `dependencies` 移到 `devDependencies`
- 新增 `zod` 到 `dependencies`

- [ ] **Step 2: 修改 `frontend/tsconfig.json`**

**保留所有现有字段**，仅做以下变更：
- `"target"` 改为 `"ES2022"`
- `"lib"` 改为 `["ES2022", "DOM", "DOM.Iterable"]`
- 移除 `"ignoreDeprecations": "6.0"`（如有）

不要删除 `jsx`、`noEmit`、`skipLibCheck`、`baseUrl`、`references` 等现有选项。

- [ ] **Step 3: 修改 `frontend/vite.config.ts` 增加 sourcemap**

```typescript
export default defineConfig({
  // ... existing config ...
  build: {
    sourcemap: true,
    rollupOptions: {
      // ... existing ...
    },
  },
})
```

- [ ] **Step 4: 重新安装依赖**

```bash
cd frontend && rm -rf node_modules package-lock.json && npm install
```

- [ ] **Step 5: 验证构建**

```bash
cd frontend && npm run build
```

**Expected:** 构建成功，无类型错误。

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/tsconfig.json frontend/vite.config.ts
git commit -m "frontend: fix deps (ts 5.8, rr v6, @types/node 22, add zod)"
```

---

### Task 3.2: 创建运行时 Schema 与统一 API 层

**Files:**
- Create: `frontend/src/lib/schemas.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: 创建 `frontend/src/lib/schemas.ts`**

```typescript
import { z } from "zod";

export const StreamTokenSchema = z.union([
  z.object({ token: z.string() }),
  z.object({ type: z.literal("metadata"), payload: z.record(z.unknown()) }),
  z.object({ done: z.literal(true) }),
]);

export const NotificationPayloadSchema = z.object({
  title: z.string(),
  message: z.string(),
});

export const NotificationSchema = z.object({
  type: z.enum(["admin_notification", "system"]),
  payload: NotificationPayloadSchema,
});

export const TaskSchema = z.object({
  id: z.number(),
  risk_level: z.enum(["low", "medium", "high"]),
  status: z.string(),
  order_sn: z.string().optional(),
  reason: z.string().optional(),
  created_at: z.string().optional(),
});

export const TaskStatsSchema = z.object({
  pending: z.number(),
  high_risk: z.number(),
});

export const LoginResponseSchema = z.object({
  access_token: z.string(),
  user_id: z.number(),
  username: z.string(),
  full_name: z.string(),
  is_admin: z.boolean(),
});

export const ApiErrorSchema = z.object({
  detail: z.string().optional(),
});

export type StreamToken = z.infer<typeof StreamTokenSchema>;
export type Notification = z.infer<typeof NotificationSchema>;
export type Task = z.infer<typeof TaskSchema>;
export type TaskStats = z.infer<typeof TaskStatsSchema>;
export type LoginResponse = z.infer<typeof LoginResponseSchema>;
```

- [ ] **Step 2: 重写 `frontend/src/lib/api.ts`**

```typescript
import { z } from "zod";

export const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public detail?: unknown
  ) {
    super(message);
  }
}

export function getApiHeaders(token?: string | null): HeadersInit {
  const headers: HeadersInit = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  token: string | null = null,
  schema: z.ZodType<T>
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...getApiHeaders(token),
      ...options.headers,
    },
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(
      err.detail || `Request failed: ${res.status}`,
      res.status,
      err
    );
  }

  const data = await res.json();
  return schema.parse(data);
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/schemas.ts frontend/src/lib/api.ts
git commit -m "frontend: add zod schemas and unified apiFetch with ApiError"
```

---

### Task 3.3: JWT 存储从 localStorage 迁移到 sessionStorage

**Files:**
- Modify: `frontend/src/stores/auth.ts`

- [ ] **Step 1: 修改 persist storage**

```typescript
import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type { User } from '@/types'

interface AuthState {
  token: string | null
  user: User | null
  isAuthenticated: boolean
  setAuth: (token: string, user: User) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      setAuth: (token, user) => set({ token, user, isAuthenticated: true }),
      logout: () => set({ token: null, user: null, isAuthenticated: false }),
    }),
    {
      name: 'auth-storage',
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/stores/auth.ts
git commit -m "security: migrate JWT storage from localStorage to sessionStorage"
```

---

### Task 3.4: 修复 `scroll-area.tsx` 暴露 `viewportRef`

**Files:**
- Modify: `frontend/src/components/ui/scroll-area.tsx`
- Modify: `frontend/src/apps/customer/App.tsx`

- [ ] **Step 1: 修改 `ScrollArea` 组件支持 `viewportRef`**

```typescript
import * as React from "react"
import * as ScrollAreaPrimitive from "@radix-ui/react-scroll-area"
import { cn } from "@/lib/utils"

interface ScrollAreaProps extends React.ComponentPropsWithoutRef<typeof ScrollAreaPrimitive.Root> {
  viewportRef?: React.Ref<HTMLDivElement>
}

const ScrollArea = React.forwardRef<
  React.ElementRef<typeof ScrollAreaPrimitive.Root>,
  ScrollAreaProps
>(({ className, children, viewportRef, ...props }, ref) => (
  <ScrollAreaPrimitive.Root
    ref={ref}
    className={cn("relative overflow-hidden", className)}
    {...props}
  >
    <ScrollAreaPrimitive.Viewport
      ref={viewportRef}
      className="h-full w-full rounded-[inherit]"
    >
      {children}
    </ScrollAreaPrimitive.Viewport>
    <ScrollBar />
    <ScrollAreaPrimitive.Corner />
  </ScrollAreaPrimitive.Root>
))
ScrollArea.displayName = ScrollAreaPrimitive.Root.displayName
```

`ScrollBar` 保持不变。

- [ ] **Step 2: 修改 `frontend/src/apps/customer/App.tsx` 使用 `viewportRef`**

```typescript
// 改造前
const scrollRef = useRef<HTMLDivElement>(null)
// ...
<ChatMessageList messages={messages} isLoading={isLoading} ref={scrollRef} />

// 改造后（假设 ChatMessageList 渲染在 ScrollArea 内部）
const scrollRef = useRef<HTMLDivElement>(null)
// ...
<ScrollArea viewportRef={scrollRef} className="flex-1">
  <ChatMessageList messages={messages} isLoading={isLoading} />
</ScrollArea>
```

- [ ] **Step 3: 修改 `ChatMessageList.tsx` 移除内部 `ScrollArea` 或转发 `viewportRef`**

`frontend/src/apps/customer/components/ChatMessageList.tsx` 内部已包含 `ScrollArea`。为避免嵌套，做以下二者之一：
- **方案 A（推荐）**：移除 `ChatMessageList` 内部的 `ScrollArea`，改为由调用方（`App.tsx`）的 `ScrollArea` 包裹。`ChatMessageList` 只负责渲染消息列表。
- **方案 B**：在 `ChatMessageList` 上新增 `viewportRef` prop，并将其转发给内部使用的 `ScrollArea`。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/scroll-area.tsx frontend/src/apps/customer/App.tsx frontend/src/apps/customer/components/ChatMessageList.tsx
git commit -m "frontend: expose viewportRef on ScrollArea and fix customer App scroll"
```

---

### Task 3.5: 重构通知系统 — Zustand Store + useAdminWebSocket

**Files:**
- Create: `frontend/src/stores/notifications.ts`
- Create: `frontend/src/hooks/useAdminWebSocket.ts`
- Modify: `frontend/src/hooks/useNotifications.ts` (或删除)
- Modify: `frontend/src/apps/admin/pages/Dashboard.tsx`

- [ ] **Step 1: 创建 `frontend/src/stores/notifications.ts`**

```typescript
import { create } from "zustand";

export interface Notification {
  id: string;
  title: string;
  message: string;
  read: boolean;
}

interface NotificationStore {
  notifications: Notification[];
  unreadCount: number;
  addNotification: (n: Omit<Notification, "id" | "read">) => void;
  markAsRead: (id: string) => void;
  markAllAsRead: () => void;
  clearAll: () => void;
}

function stripHtml(input: string): string {
  return input.replace(/<[^>]+>/g, "");
}

export const useNotificationStore = create<NotificationStore>((set, get) => ({
  notifications: [],
  get unreadCount() {
    return get().notifications.filter((n) => !n.read).length;
  },
  addNotification: (n) =>
    set((state) => ({
      notifications: [
        {
          ...n,
          title: stripHtml(n.title),
          message: stripHtml(n.message),
          id: crypto.randomUUID(),
          read: false,
        },
        ...state.notifications,
      ],
    })),
  markAsRead: (id) =>
    set((state) => ({
      notifications: state.notifications.map((n) =>
        n.id === id ? { ...n, read: true } : n
      ),
    })),
  markAllAsRead: () =>
    set((state) => ({
      notifications: state.notifications.map((n) => ({ ...n, read: true })),
    })),
  clearAll: () => set({ notifications: [] }),
}));
```

- [ ] **Step 2: 创建 `frontend/src/hooks/useAdminWebSocket.ts`**

```typescript
import { useEffect, useRef, useState, useCallback } from "react";
import { useNotificationStore } from "@/stores/notifications";
import { NotificationSchema } from "@/lib/schemas";

const WS_BASE = import.meta.env.VITE_WS_BASE_URL || "ws://localhost:8000/api/v1";
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_INTERVAL = 3000;

export function useAdminWebSocket(adminId: number | undefined, token: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const [messages, setMessages] = useState<unknown[]>([]);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimerRef = useRef<number | null>(null);
  const shouldReconnectRef = useRef(true);
  const addNotification = useNotificationStore((s) => s.addNotification);

  const connect = useCallback(() => {
    if (!adminId || !token) return;
    if (import.meta.env.VITE_MOCK_WS === "true") return;

    const url = `${WS_BASE}/ws/admin/${adminId}?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      reconnectAttemptsRef.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const raw = JSON.parse(event.data);
        setMessages((prev) => [...prev, raw]);

        const parsed = NotificationSchema.safeParse(raw);
        if (parsed.success && parsed.data.type === "admin_notification") {
          addNotification({
            title: parsed.data.payload.title,
            message: parsed.data.payload.message,
          });
        }
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      if (shouldReconnectRef.current && reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttemptsRef.current += 1;
        reconnectTimerRef.current = window.setTimeout(() => {
          connect();
        }, RECONNECT_INTERVAL);
      }
    };

    ws.onerror = () => {
      // silently fail; onclose will handle reconnect
    };
  }, [adminId, token, addNotification]);

  useEffect(() => {
    shouldReconnectRef.current = true;
    connect();
    return () => {
      shouldReconnectRef.current = false;
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  return { messages };
}
```

- [ ] **Step 3: 修改 `Dashboard.tsx` 集成 WebSocket 和通知 Store**

```typescript
import { useAuthStore } from "@/stores/auth";
import { useNotificationStore } from "@/stores/notifications";
import { useAdminWebSocket } from "@/hooks/useAdminWebSocket";

// 在 Dashboard 组件中
const { user, logout } = useAuth();
const token = useAuthStore.getState().token;
const { notifications, unreadCount, markAsRead, markAllAsRead } = useNotificationStore();
useAdminWebSocket(user?.user_id, token);
```

删除 `import { useNotifications } from "@/hooks/useNotifications"` 及其调用。

- [ ] **Step 4: 运行前端构建验证**

```bash
cd frontend && npm run build
```

**Expected:** 成功

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/notifications.ts frontend/src/hooks/useAdminWebSocket.ts frontend/src/apps/admin/pages/Dashboard.tsx
git commit -m "frontend: add notification store and admin WebSocket hook"
```

---

### Task 3.6: 迁移 hooks 到 `apiFetch` 与 zod

**Files:**
- Modify: `frontend/src/hooks/useAuth.ts`
- Modify: `frontend/src/hooks/useTasks.ts`
- Modify: `frontend/src/apps/customer/hooks/useChat.ts`

- [ ] **Step 1: 修改 `useAuth.ts`**

```typescript
import { apiFetch, ApiError } from "@/lib/api";
import { LoginResponseSchema } from "@/lib/schemas";

// 在 login mutation 中
const data = await apiFetch(
  "/login",
  {
    method: "POST",
    body: JSON.stringify(credentials),
  },
  null,
  LoginResponseSchema
);
```

- [ ] **Step 2: 修改 `useTasks.ts`**

```typescript
import { apiFetch } from "@/lib/api";
import { TaskSchema, TaskStatsSchema } from "@/lib/schemas";
import { z } from "zod";

const TasksResponseSchema = z.array(TaskSchema);
const AllTasksResponseSchema = z.object({
  risk_tasks: z.number(),
  confidence_tasks: z.number(),
  manual_tasks: z.number(),
  total: z.number(),
});

// queryFn for tasks
const token = useAuthStore.getState().token;
const data = await apiFetch(
  `/admin/tasks?${params.toString()}`,
  {},
  token,
  TasksResponseSchema
);
return data;

// queryFn for stats
const data = await apiFetch(
  "/admin/tasks-all",
  {},
  token,
  AllTasksResponseSchema
);
const mapped: TaskStats = {
  pending: data.total,
  high_risk: data.risk_tasks,
};
return mapped;

// submitDecision mutation
const token = useAuthStore.getState().token;
await apiFetch(
  `/admin/resume/${payload.audit_log_id}`,
  {
    method: "POST",
    body: JSON.stringify({
      action: payload.action,
      admin_comment: payload.comment,
    }),
  },
  token,
  z.object({ success: z.boolean() })
);
```

- [ ] **Step 3: 修改 `useChat.ts` 的 SSE token 解析**

```typescript
import { StreamTokenSchema } from "@/lib/schemas";

// 在 SSE reader loop 中
const raw = JSON.parse(data);
const result = StreamTokenSchema.safeParse(raw);
if (!result.success) {
  console.warn("Invalid SSE token", result.error);
  continue;
}
const parsed = result.data;
```

- [ ] **Step 4: 构建验证**

```bash
cd frontend && npm run build
```

**Expected:** 成功

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useAuth.ts frontend/src/hooks/useTasks.ts frontend/src/apps/customer/hooks/useChat.ts
git commit -m "frontend: migrate hooks to apiFetch and zod runtime validation"
```

---

### Task 3.7: 清理前端代码风格问题

**Files:**
- Modify: `frontend/src/apps/customer/App.tsx`
- 其他含有 `FC` 类型注解或空 `catch` 的文件

- [ ] **Step 1: 移除 `FC` 类型注解**

搜索并替换：
```bash
grep -r ": FC" frontend/src/apps/
```

将 `const App: FC = () => {` 改为 `function App() {` 或 `const App = () => {`。

- [ ] **Step 2: 修复空 catch 块**

在 `frontend/src/apps/customer/App.tsx` 的 `handleLogin` 中，空 `catch {}` 改为：
```typescript
try {
  await login(credentials)
} catch (err) {
  console.error("Login failed", err)
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/apps/customer/App.tsx
git commit -m "frontend: remove FC annotations and fix empty catch blocks"
```

---

### Task 3.8: M3 回归测试

- [ ] **Step 1: 前端构建**

```bash
cd frontend && npm run build
```

- [ ] **Step 2: E2E 测试**

```bash
cd frontend && npm run test:e2e
```

**Expected:** PASS（若 WebSocket 导致 E2E 不稳定，可在 E2E 启动前设置 `VITE_MOCK_WS=true`）。

- [ ] **Step 3: 验证依赖版本**

```bash
cd frontend && npm ls typescript @types/node react-router-dom
```

**Expected:**
- `typescript@5.8.x`
- `@types/node@22.x`
- `react-router-dom@6.30.x`

---

## 里程碑 4: P3 长期优化

> **验收标准 (M4):**
> - `app/core/config.py` 使用 `get_settings()` 延迟实例化
> - `SECRET_KEY` 长度不足时启动报错
> - 全项目 `from app.core.config import settings` 已替换为 `from app.core.config import get_settings`
> - `uv run pytest` 100% 通过
> - CI 绿灯

---

### Task 4.1: `config.py` 延迟实例化与 SECRET_KEY 校验

**Files:**
- Modify: `app/core/config.py`

- [ ] **Step 1: 引入延迟实例化**

在 `app/core/config.py` 末尾：

```python
from functools import lru_cache

@lru_cache
def get_settings() -> Settings:
    return Settings()

# 兼容导出（后续逐步替换）
settings = get_settings()
```

先保留 `settings = get_settings()` 以避免一次性全量替换导致 CI 崩溃。

- [ ] **Step 2: 增加 SECRET_KEY 校验**

```python
from pydantic import field_validator

class Settings(BaseSettings):
    SECRET_KEY: str

    @field_validator("SECRET_KEY")
    @classmethod
    def _validate_secret_key(cls, v: str) -> str:
        if len(v.encode()) < 32:
            raise ValueError("SECRET_KEY must be at least 32 bytes")
        return v

    # ... rest of fields ...
```

- [ ] **Step 3: 运行测试验证启动**

```bash
uv run pytest tests/test_main_security.py -v
```

**Expected:** PASS（`test_secret_key` 如存在则需满足 >=32 bytes）。

- [ ] **Step 4: Commit**

```bash
git add app/core/config.py
git commit -m "config: add get_settings() factory and SECRET_KEY length validation"
```

---

### Task 4.2: 全局替换 `settings` 导入

**Files:**
- Modify: ~60 个 backend 文件（见下方列表）

**核心策略：**
- 将所有 `from app.core.config import settings` 改为 `from app.core.config import get_settings`
- 在**函数/方法内部**调用 `settings = get_settings()`，避免模块级实例化
- 模块级常量（如 `oauth2_scheme` 中的 `tokenUrl`）需改为动态获取或延迟初始化

- [ ] **Step 1: 批量搜索所有导入点**

```bash
grep -rl "from app.core.config import settings" app/ tests/
```

- [ ] **Step 2: 逐个文件替换（重点文件清单）**

| 文件 | 改造方式 |
|------|----------|
| `app/core/security.py` | 工厂函数内获取；`oauth2_scheme` 延迟到函数内创建 |
| `app/main.py` | lifespan 内 `settings = get_settings()` |
| `app/api/v1/*.py` | endpoint 内获取 |
| `app/services/*.py` | 方法内获取 |
| `app/agents/*.py` | 方法内获取 |
| `app/graph/*.py` | 方法/节点内获取 |
| `app/retrieval/*.py` | 方法内获取 |
| `app/intent/*.py` | 方法内获取 |
| `app/tasks/*.py` | task 函数内获取 |
| `tests/test_security.py` | 导入 `get_settings`，在类/方法内调用 |

**示例改造（`app/core/security.py`）：**

```python
from app.core.config import get_settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login", auto_error=False)

def create_access_token(user_id: int, is_admin: bool = False) -> str:
    settings = get_settings()
    to_encode = {"sub": str(user_id), "is_admin": is_admin, "jti": str(uuid.uuid4())}
    expire = utc_now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": utc_now()})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
```

**测试文件改造（`tests/test_security.py`）：**

```python
from app.core.config import get_settings

# 在每个测试方法或 setup 中
settings = get_settings()
```

- [ ] **Step 3: 运行全量测试**

```bash
uv run pytest -v
```

**Expected:** PASS

- [ ] **Step 4: Commit**

由于改动文件众多，建议分 2-3 个 commit 提交：

```bash
git add app/core/security.py app/main.py app/api/v1/ ...
git commit -m "config: migrate core modules to get_settings() factory"
```

---

### Task 4.3: 升级核心依赖

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 修改依赖版本**

```toml
[project.dependencies]
fastapi = "^0.135.0"
starlette = "^1.0.0"
typer = "^0.24.0"
bcrypt = "^5.0.0"
```

- [ ] **Step 2: 锁定并安装**

```bash
uv lock --upgrade-package fastapi --upgrade-package starlette --upgrade-package typer --upgrade-package bcrypt
```

- [ ] **Step 3: 运行全量测试 + 类型检查**

```bash
uv run pytest -v
uv run ty check --error-on-warning
```

**Expected:** PASS

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "deps: upgrade fastapi, starlette, typer, bcrypt"
```

---

### Task 4.4: 创建一次性 checkpoint 清理脚本

**Files:**
- Create: `scripts/clear_legacy_checkpoints.py`

- [ ] **Step 1: 创建脚本**

```python
#!/usr/bin/env python3
"""
一次性运维脚本：清空 Redis 中所有旧格式 checkpoint（thread:* 键）。
该脚本不得在应用运行时通过 Web API、CLI 命令或 Celery task 暴露。
"""

import asyncio
import os
import sys

import redis.asyncio as redis


async def main() -> int:
    host = os.environ.get("REDIS_HOST", "localhost")
    port = int(os.environ.get("REDIS_PORT", "6379"))
    password = os.environ.get("REDIS_PASSWORD") or None

    r = redis.Redis(host=host, port=port, password=password, decode_responses=True)
    keys = []
    async for k in r.scan_iter(match="thread:*"):
        keys.append(k)

    if not keys:
        print("No legacy checkpoint keys found.")
        return 0

    print(f"Found {len(keys)} legacy checkpoint keys. Deleting...")
    await r.delete(*keys)
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

- [ ] **Step 2: Commit**

```bash
chmod +x scripts/clear_legacy_checkpoints.py
git add scripts/clear_legacy_checkpoints.py
git commit -m "ops: add one-time script to clear legacy Redis checkpoints"
```

---

### Task 4.5: M4 回归测试与最终验收

- [ ] **Step 1: 后端全量测试**

```bash
uv run pytest -v
```

- [ ] **Step 2: 后端类型检查**

```bash
uv run ty check --error-on-warning
```

- [ ] **Step 3: 后端 lint**

```bash
uv run ruff check app tests
```

- [ ] **Step 4: 前端构建 + E2E**

```bash
cd frontend && npm run build && npm run test:e2e
```

- [ ] **Step 5: 最终验收清单核对**

| 检查项 | 命令/方法 | 预期结果 |
|--------|-----------|----------|
| unit 测试无外部依赖 | `POSTGRES_SERVER=nonexistent REDIS_HOST=nonexistent pytest -m unit` | 100% 通过 |
| 全量测试通过 | `uv run pytest` | 100% 通过 |
| 覆盖率 | `uv run pytest --cov=app --cov-fail-under=75` | PASS |
| ruff | `uv run ruff check app tests` | 全绿 |
| ty | `uv run ty check --error-on-warning` | 全绿 |
| 旧字段清理 | `grep -r "audit_required\|audit_type\|normalize_state\|get_audit_required\|get_audit_level_from_old\|\"context\"\b" app/ tests/` | 0 结果 |
| tools.py 删除 | `ls app/graph/tools.py` | 不存在 |
| time.sleep 清理 | `grep -r "time.sleep" app/` | 0 结果 |
| WS Origin | 手动测试非法 Origin | 返回 1008 |
| CORS 收紧 | 检查 `app/main.py` | 显式白名单 |
| PII 脱敏 | 检查 `app/tasks/refund_tasks.py` | 无完整手机号/短信内容 |
| 前端构建 | `cd frontend && npm run build` | 成功 |
| TS 版本 | `npm ls typescript` | 5.8.x |
| RR 版本 | `npm ls react-router-dom` | 6.30.x |
| 通知 E2E | Playwright E2E | Toast 可验证 |

---

## Self-Review

**1. Spec coverage:**
- P0 安全：Fail-Closed (`safety.py`)、assert 移除、`security.py` exp/jti、CORS、WS Origin、Rate Limiting、PII 脱敏、密码策略 —— 全部有对应 Task。
- P0 测试：`tests/.env.test`、`_db_config.py`、marker 注册、conftest 拆分、纯单元测试解耦 —— 全部覆盖。
- P1 架构：`state.py` 单轨化、`graph/tools.py` 删除、`router.py` 兼容层删除、`exceptions.py`、异步阻塞修复、循环依赖消除、`risk_service.py` 拆分、常量迁移 —— 全部覆盖。
- P2 前端：依赖修正、zod schema、`apiFetch`、sessionStorage、`scrollRef`、通知系统、`useAdminWebSocket` —— 全部覆盖。
- P3 长期：FastAPI 升级、`get_settings()`、SECRET_KEY 校验、全局替换、checkpoint 清理脚本 —— 全部覆盖。

**2. Placeholder scan:**
- 计划中无 "TBD"、"TODO"、"implement later"。
- 每个代码步骤都包含完整代码块。
- 无 "Similar to Task N" 的省略。

**3. Type consistency:**
- `AgentState` 字段在 `state.py`、`chat.py`、`policy.py`、`router.py` 中保持一致。
- `apiFetch` 签名在 `api.ts`、`useAuth.ts`、`useTasks.ts` 中保持一致（`token` 参数 + `schema` 必填）。
- `RefundRiskService` 拆分后，导入路径在 `__init__.py` 和各调用点一致。

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-10-project-overhaul.md`.**

**Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. REQUIRED SUB-SKILL: `superpowers:subagent-driven-development`.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints for review.

**Which approach would you like?**
