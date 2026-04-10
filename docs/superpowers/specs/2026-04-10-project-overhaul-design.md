# E-commerce Smart Agent 全面改造设计文档

**版本**: v1.0  
**日期**: 2026-04-10  
**范围**: P0 安全止血 → P1 架构精简 → P2 前端加固 → P3 长期优化  
**目标**: 将当前"技术栈先进但工程实践粗糙"的代码库，改造为现代、安全、干净、可维护的生产级系统。

---

## 1. 现状诊断

### 1.1 核心问题

| 维度 | 现状 | 风险 |
|------|------|------|
| **安全** | 安全过滤器 Fail-Open (`safety.py` 异常时返回 `is_safe=True`)；使用 `assert` 做权限校验；JWT 存 `localStorage` | 恶意输入可被放行、`-O` 模式下越权、XSS 窃取 Token |
| **测试** | 426 errors，0 passed。`conftest.py` 的 `db_setup` 为 `autouse=True` + `session` scope，连纯单元测试都被强拉数据库 | 测试体系完全失信，无法验证任何重构 |
| **架构** | 状态模型双轨制 (`retrieval_result/context`, `audit_level/audit_required`)；`graph/tools.py` 是纯装饰器转发层；遗留意图枚举兼容层 | 认知负担重，新旧代码互相牵制，边界模糊 |
| **异常处理** | 大量裸 `except Exception`，关键路径静默吞异常 | 问题被隐藏，降级策略失控，故障排查困难 |
| **异步** | Celery task 的 async 子协程中使用 `time.sleep` | 阻塞事件循环线程，Worker 吞吐量下降 |
| **前端** | `@types/node ^25.5.2` 不存在；`useNotifications.ts` 是死代码；大量 `as` 类型断言 | 构建风险、功能缺失、运行时类型安全漏洞 |

### 1.2 改造原则

1. **Fail-Closed**: 安全与风控路径异常时必须拒绝，不能放行。
2. **测试先行**: 先拯救测试体系，确保任何改造都有测试护航。
3. **删除兼容层**: 不计成本意味着可以彻底删除 v4.0 遗留的兼容代码，统一使用 v4.1 模型。
4. **显式优于隐式**: 禁止裸 `except Exception`；禁止函数内导入规避循环依赖。
5. **边界清晰**: 每个模块必须有单一职责，消费者无需阅读内部实现即可使用。

---

## 2. 总体目标与非目标

### 2.1 目标 (In Scope)

- **P0**: 修复 3 个高危安全漏洞 + 重构测试体系使其全部通过
- **P1**: 删除所有兼容层 + 统一异常处理 + 修复循环依赖 + 修复异步阻塞
- **P2**: 修正前端依赖 + 引入运行时类型校验 + 修复通知系统 + 统一 API 层
- **P3**: 升级 FastAPI/Starlette 等核心依赖 + 改进配置系统

### 2.2 非目标 (Out of Scope)

- 不替换核心技术栈（不改用 Django/Nest.js 等）
- 不重构 LLM Prompt 策略（除非因类型/边界问题必须修改）
- 不新增业务功能（如新增支付方式、新增语言支持）
- 不修改数据库 Schema（仅删除代码层双字段兼容，不动表结构）

---

## 3. P0: 安全止血与测试拯救

### 3.1 安全修复 (Security Hardening)

#### 3.1.1 `app/intent/safety.py` —— 语义检测 Fail-Closed

**当前代码 (L310-318)**:
```python
except Exception as e:
    logger.error(f"Semantic check failed: {e}")
return SafetyCheckResult(is_safe=True, ...)
```

**改造后**:
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

**设计决策**:
- LLM 调用失败（网络、超时、配置错误）时，**默认拒绝**。
- 返回 `risk_level="high"`，确保上游 decider 节点不会自动通过。

#### 3.1.2 `app/services/refund_service.py` —— 删除 assert 权限校验

**当前代码 (L46)**:
```python
assert order.id is not None
```

**改造后**:
```python
if order.id is None:
    raise ValueError("订单 ID 不能为空，数据异常")
```

**设计决策**:
- `assert` 仅用于程序不变量断言，**不得用于业务校验**。
- 使用显式异常，确保 `-O` 模式下行为一致。

#### 3.1.3 前端 JWT 存储迁移

**当前**: `frontend/src/stores/auth.ts` 使用 `zustand persist` + `localStorage`。

**改造后**:
- **阶段 1 (本次改造)**: 将 `localStorage` 改为 `sessionStorage`，降低 XSS 持久化风险。
- 在 `persist` 配置中增加 `storage: createJSONStorage(() => sessionStorage)`。
- **阶段 2 (未来)**: 后端提供 `httpOnly` Cookie，前端完全移除 Token 本地存储。

**本次只实施阶段 1**，因为阶段 2 涉及后端认证接口重构（超出最小改造范围）。

#### 3.1.4 `app/core/security.py` —— 强制 JWT exp

**改造**:
```python
jwt.decode(
    token,
    settings.SECRET_KEY,
    algorithms=[settings.ALGORITHM],
    options={"require": ["exp"]},
)
```

---

### 3.2 测试体系重构 (Test Rescue)

#### 3.2.1 核心诊断

`tests/conftest.py` 中 `db_setup` fixture 的 `scope="session", autouse=True` 导致：
- `test_security.py` (纯 JWT 测试) 在 setup 阶段就连接数据库
- 本地 `.env` 密码与 CI 不一致，导致 426 个测试全部因 `InvalidPasswordError` 失败

#### 3.2.2 改造方案

**步骤 1: 拆分 fixture 作用域**

```python
# conftest.py
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlmodel import SQLModel

from app.core.database import engine
from app.core.limiter import limiter
from app.main import app


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    """Session-scoped engine setup, but NOT autouse."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS confidence_audits CASCADE"))
        await conn.run_sync(SQLModel.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Test-scoped database session."""
    async with engine.connect() as conn:
        trans = await conn.begin()
        # 每个测试在独立事务中运行，测试结束后回滚
        yield conn
        await trans.rollback()


@pytest_asyncio.fixture
async def client():
    limiter.reset()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
```

**步骤 2: 分类测试标记**

引入 `pytest.mark` 对测试进行分类：

```python
# 在 conftest.py 或 pytest.ini 中注册
markers = [
    "unit: 纯单元测试，不依赖数据库",
    "db: 依赖数据库的测试",
    "api: API 集成测试",
    "websocket: WebSocket 测试",
]
```

- `test_security.py`、`test_confidence_signals.py` (mock LLM 的部分)、`test_logging.py` → 标记为 `@pytest.mark.unit`
- `test_chat_api.py`、`test_admin_api.py` → 标记为 `@pytest.mark.api` + `@pytest.mark.db`

**步骤 3: 本地测试环境统一**

新增 `tests/.env.test`：

```bash
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
```

修改 `tests/_db_config.py`，在测试启动时优先加载 `tests/.env.test`：

```python
from pathlib import Path

# 在配置数据库前加载测试环境变量
env_path = Path(__file__).parent / ".env.test"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            os.environ.setdefault(key, value.strip().strip('"').strip("'"))
```

**注意**：这种方式不引入额外依赖。如果项目中已明确安装 `python-dotenv`，也可以使用 `load_dotenv`。

**步骤 4: 纯单元测试解耦**

以 `test_security.py` 为例，当前它依赖 `client` fixture（`AsyncClient`），而 `client` 导入 `app.main`，`app.main` 在模块加载时即初始化大量依赖。但实际上 JWT 测试完全可以不依赖 FastAPI app。

改造 `test_security.py`：
- 移除 `client` fixture 依赖
- 直接导入 `app.core.security` 中的函数进行测试
- 这样即使数据库密码错误，JWT 编解码测试也能正常通过

**验收标准**:
- `uv run pytest -m unit` 必须在无数据库环境下通过
- `uv run pytest` 在本地（配合 `.env.test` 和 docker-compose db）全部通过
- CI 中 `pytest --cov=app --cov-fail-under=75` 保持通过

---

## 4. P1: 架构精简

### 4.1 删除兼容层

#### 4.1.1 `app/models/state.py` —— 状态模型单轨化

**当前问题**:
- `retrieval_result` (新) 与 `context` (旧) 并存
- `audit_level` (新) 与 `audit_required` + `audit_type` (旧) 并存
- `normalize_state` 函数需要不断同步两者

**改造方案**:

1. **TypedDict 中只保留新字段**:

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

2. **删除字段**:
   - `context`
   - `audit_required`
   - `audit_type`

3. **删除函数**:
   - `normalize_state`
   - `get_audit_required`
   - `get_audit_level_from_old`

4. **全量替换调用点**:
   - `graph/nodes.py` 中所有读取 `state["context"]` 的代码改为 `state["retrieval_result"].chunks`
   - `agents/evaluator.py` 中读取 `audit_required` 改为读取 `audit_level`
   - `agents/decider.py` (如有) 同步修改
   - `api/v1/chat.py` 中状态初始化代码同步修改

**验收标准**:
- `grep -r "audit_required\|audit_type\|normalize_state" app/ tests/` 返回 0 结果
- `make_agent_state` 工厂函数参数同步精简
- 所有测试通过

#### 4.1.2 `app/graph/tools.py` —— 删除纯 Wrapper 层

**当前**: `graph/tools.py` 中三个函数仅做 `@tool` 装饰器包装后转发。

**改造方案**:

1. **将 `@tool` 装饰器下沉到 `app/services/refund_tool_service.py`**:

```python
# app/services/refund_tool_service.py
from langchain_core.tools import tool
from pydantic import Field
from typing import Annotated

@tool
async def check_refund_eligibility(
    order_sn: Annotated[str, Field(description="订单号，格式如 SN20240001")],
    user_id: Annotated[int, Field(description="当前登录用户的ID")],
) -> str:
    """检查订单是否符合退货条件..."""
    ... # 原逻辑
```

2. **删除 `app/graph/tools.py` 文件**。

3. **修改引用点**:
   - `app/graph/nodes.py` 中 `from app.graph.tools import refund_tools` 改为 `from app.services.refund_tool_service import refund_tools`
   - 更新 `graph/workflow.py` 中的引用

**验收标准**:
- `app/graph/tools.py` 不存在
- LangGraph 工作流编译通过

#### 4.1.3 `app/agents/router.py` —— 删除遗留意图兼容层

**当前**: 存在 `_IntentMapping`、`_map_to_legacy_intent`、`Intent(str, Enum)`。

**改造方案**:

1. 删除 `Intent(str, Enum)` 枚举定义。
2. 删除 `_map_to_legacy_intent` 方法。
3. `IntentRouterAgent` 直接返回新分层意图字符串（如 `"POLICY"`、`"ORDER"`、`"REFUND"`）。
4. 确保 `graph/nodes.py` 中的 `router_node` 已完全使用新意图格式（根据代码审查，它已经是）。

**验收标准**:
- `grep -r "_map_to_legacy_intent\|class Intent" app/` 返回 0 结果

---

### 4.2 统一异常处理策略

#### 4.2.1 建立分层异常体系

新建 `app/core/exceptions.py`：

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

#### 4.2.2 替换裸 `except Exception`

**逐文件改造清单**:

| 文件 | 当前行为 | 改造后行为 |
|------|----------|------------|
| `app/services/order_service.py:49-51` | 吞掉所有异常返回 `None` | 捕获 `SQLAlchemyError` 抛 `ServiceUnavailableError`；其余异常抛 `AppError` |
| `app/retrieval/retriever.py:47-48` | 吞掉稀疏嵌入器异常 | 捕获 `fastembed` 模块的具体异常（如 `RuntimeError` 或其实际异常类），记录 warning 后降级；其余异常抛出 |
| `app/retrieval/retriever.py:73-74` | 吞掉 Reranker 异常 | 捕获 `httpx.HTTPError`/`TimeoutException`，记录 warning 后降级；其余异常抛出 |
| `app/retrieval/rewriter.py:41-42` | 吞掉查询重写异常 | 捕获 `ExternalAPIError`，返回原始 query；其余异常抛出 |
| `app/confidence/signals.py:158-161` | LLM 异常返回默认 0.5 | 捕获 `ExternalAPIError`，记录后返回 `None` 表示"无法评估"，由调用方决定是否降级 |
| `app/intent/service.py` (多处) | Redis 异常静默 | 捕获 `redis.ConnectionError`/`TimeoutError`，记录 warning；其余异常抛出 |
| `app/websocket/manager.py` | 发送异常统一断开 | 区分 `WebSocketDisconnect`（正常清理）和 `RuntimeError`（记录 error 后清理） |
| `app/services/admin_service.py:227-228` | WebSocket 通知失败静默 | 捕获 `WebSocketDisconnect`/`RuntimeError`，记录 warning；不吞掉未知异常 |

**设计决策**:
- **降级策略必须显式化**: 允许降级的地方，必须在 `except` 块中写清楚降级逻辑和原因，不能简单 `pass`。
- **异常信息必须结构化**: 所有捕获的异常必须携带 `logger.warning(..., exc_info=True)` 或 `logger.error(..., exc_info=True)`。

---

### 4.3 修复异步阻塞

**文件**: `app/tasks/refund_tasks.py`

**改造**:

```python
# 改造前
import time
time.sleep(2)

# 改造后
import asyncio
await asyncio.sleep(2)
```

同理，`process_refund_payment` 中的 `time.sleep(3)` 改为 `await asyncio.sleep(3)`。

**注意**: `send_refund_sms` 是同步 Celery task 函数，但它在 `try` 块内部，而 `run_async` 会在此 task 被调用时运行 `_process()` 协程。如果 `time.sleep` 出现在 `run_async` 启动的协程内部，就会阻塞事件循环。改造后确保所有模拟延迟都使用 `await asyncio.sleep`。

---

### 4.4 解决循环依赖

#### 4.4.1 根因分析

项目中三处函数内导入说明存在启动时序耦合：
- `app/api/v1/chat.py:30` → `app.graph.workflow`
- `app/services/refund_service.py:250-251` → `app.core.config.settings`, `app.models.audit`
- `app/agents/router.py:90-91` → `app.core.redis`

#### 4.4.2 改造方案

**方案 A: 延迟初始化 / 工厂模式（推荐）**

对于 `chat.py` 中的 `app_graph`：

```python
# app/api/v1/chat.py
from functools import lru_cache

@lru_cache
def get_app_graph():
    from app.graph.workflow import app_graph
    return app_graph
```

在 endpoint 中调用 `get_app_graph()` 而非模块级导入。

**方案 B: 依赖注入**

对于 `router.py` 中的 Redis：

```python
# app/agents/router.py
class IntentRouterAgent:
    def __init__(self, llm=None, redis_client=None):
        self.llm = llm
        self.redis = redis_client or get_redis_client()
```

将 `get_redis_client()` 从构造函数内部提到默认参数，消除运行时导入。

**方案 C: 拆分模块**

对于 `refund_service.py` 中的 `AuditLog` 导入：

当前 `RefundRiskService.assess_and_create_audit` 需要 `AuditLog`，而 `AuditLog` 可能在顶层导入时与 `refund_service` 形成循环。经过检查，实际原因是 `refund_service.py` 顶层已导入 `AuditLog`（L9），但 `assess_and_create_audit` 内部又重复导入。这说明方法内导入是**历史遗留或过度防御**。

**改造**:
- 移除 `assess_and_create_audit` 方法体内的局部导入，直接使用顶层导入的 `AuditLog` 和 `settings`。
- 如果确实出现循环导入错误，则将 `RefundRiskService` 拆分为独立模块 `app/services/risk_service.py`。

**验收标准**:
- 全项目 `grep -r "^\s*from app\..* import" app/ | grep -v "^\s*from app\.(core|models|api|agents|graph|services|utils|intent|retrieval|tasks|websocket|schemas)"` 无函数内导入（除延迟初始化工厂外）

---

## 5. P2: 前端加固

### 5.1 依赖修正

**`frontend/package.json` 改造**:

```json
{
  "devDependencies": {
    "@types/node": "^22.14.0",
    "@vitejs/plugin-react-swc": "^4.3.0",
    ...
  }
}
```

- `@types/node`: `^25.5.2` → `^22.14.0`
- `@vitejs/plugin-react-swc`: 从 `dependencies` 移至 `devDependencies`

执行 `cd frontend && npm install` 验证。

### 5.2 引入运行时类型校验

**引入 `zod`**:

```bash
cd frontend && npm install zod
```

**定义共享 Schema** (新建 `frontend/src/lib/schemas.ts`)：

```typescript
import { z } from "zod";

export const StreamTokenSchema = z.object({
  token: z.string(),
  done: z.boolean().optional(),
});

export const TaskSchema = z.object({
  id: z.number(),
  risk_level: z.enum(["low", "medium", "high"]),
  status: z.string(),
  // 其余字段根据后端 API 实际返回值补充
});

export type Task = z.infer<typeof TaskSchema>;
```

**改造 `useChat.ts`**:

```typescript
// 改造前
const parsed = JSON.parse(data) as StreamToken;

// 改造后
const raw = JSON.parse(data);
const parsed = StreamTokenSchema.parse(raw);
```

**改造 `useTasks.ts`、 `useAuth.ts`**:
- 所有 `res.json() as Xxx` 替换为 `XxxSchema.parse(await res.json())`
- 错误响应体也使用 `z.object({ detail: z.string().optional() })` 解析

### 5.3 修复通知系统

**诊断**: `useNotifications.ts` 中 `notifications` 状态从未被 `setNotifications` 更新。

**改造方案**:

1. **在 WebSocket 连接中推送通知**:
   管理员 WebSocket 收到 `admin_notification` 消息后，应调用 `useNotifications` 暴露的 `addNotification` 方法。

2. **改造 `useNotifications.ts`**:

```typescript
import { create } from "zustand";

interface Notification {
  id: string;
  title: string;
  message: string;
  read: boolean;
}

interface NotificationStore {
  notifications: Notification[];
  addNotification: (n: Omit<Notification, "id" | "read">) => void;
  markAsRead: (id: string) => void;
  clearAll: () => void;
}

export const useNotificationStore = create<NotificationStore>((set) => ({
  notifications: [],
  addNotification: (n) =>
    set((state) => ({
      notifications: [
        { ...n, id: crypto.randomUUID(), read: false },
        ...state.notifications,
      ],
    })),
  markAsRead: (id) =>
    set((state) => ({
      notifications: state.notifications.map((n) =>
        n.id === id ? { ...n, read: true } : n
      ),
    })),
  clearAll: () => set({ notifications: [] }),
}));
```

3. **在 Dashboard WebSocket 消息处理器中集成**:

```typescript
// Dashboard.tsx 或 useAdminWebSocket.ts
import { useNotificationStore } from "@/stores/notifications";

const addNotification = useNotificationStore((s) => s.addNotification);

// 当收到 websocket message 时
if (message.type === "admin_notification") {
  addNotification({
    title: "新审核任务",
    message: message.payload.message,
  });
}
```

### 5.4 统一 API 层

**改造 `src/lib/api.ts`**:

```typescript
export const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1";

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
  schema?: z.ZodType<T>
): Promise<T> {
  const token = useAuthStore.getState().token;
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...getApiHeaders(token),
      ...options.headers,
    },
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Request failed: ${res.status}`);
  }

  const data = await res.json();
  if (schema) {
    return schema.parse(data);
  }
  return data;
}
```

**改造各 hooks**:
- `useAuth.ts`、`useTasks.ts` 等不再重复定义 `API_BASE` 和 `Authorization` header，统一使用 `apiFetch`。

### 5.5 其他前端修复

- **`tsconfig.json`**: `"target": "ES2020"` → `"ES2022"`
- **移除** `"ignoreDeprecations": "6.0"`（如果已无非 6.0 语法）
- **`vite.config.ts`**: 增加 `build.sourcemap: true`
- **`src/stores/auth.ts`**: `localStorage` → `sessionStorage`

---

## 6. P3: 长期优化

### 6.1 依赖升级

| 包 | 当前 | 目标 | 风险 |
|---|---|---|---|
| `fastapi` | `0.119.1` | `^0.135.0` | 需验证 `slowapi` 兼容性 |
| `starlette` | `0.48.0` | `^1.0.0` | FastAPI 升级会连带升级 |
| `pydantic-core` | `2.41.5` | 跟随 FastAPI/Pydantic 最新 | 通常自动解析 |
| `typer` | `0.15.4` | `^0.24.0` | 需验证 CLI 脚本兼容性 |
| `bcrypt` | `4.3.0` | `^5.0.0` | major 升级，密码哈希格式需验证 |
| `click` | `8.1.8` | `^8.3.0` | 低风险 |

**注意**: `typer<0.16.0` 和 `click-plugins==1.1.1` 的 pin 在本次改造后应重新评估上游安全状态。如果恶意版本已被 PyPI 清理，可解除 pin；否则保留。

**升级流程**:
1. 修改 `pyproject.toml`
2. `uv lock --upgrade-package fastapi --upgrade-package starlette ...`
3. `uv run pytest` 全量通过
4. `uv run ty check` 通过

### 6.2 配置系统改进

**`app/core/config.py` 改造**:

1. **延迟实例化**:

```python
from functools import lru_cache

@lru_cache
def get_settings() -> Settings:
    return Settings()

# 不再在模块级实例化
# settings = Settings()  # 删除这一行
```

2. **SECRET_KEY 校验**:

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
```

3. **全局替换 `from app.core.config import settings`**:
   - 所有文件改为 `from app.core.config import get_settings`
   - 在函数内部调用 `settings = get_settings()`
   - 这也能帮助解决部分循环依赖问题

---

## 7. 实施顺序与里程碑

### 里程碑 1: P0 止血 (Week 1)
1. 写 `tests/.env.test`，修改 `_db_config.py`
2. 重构 `conftest.py` fixture 体系
3. 解耦纯单元测试（`test_security.py`、`test_logging.py` 等）
4. 修复 3 个安全漏洞（`safety.py`、`refund_service.py`、`security.py`）
5. **验收**: `pytest -m unit` 100% 通过；`pytest` 全绿

### 里程碑 2: P1 架构精简 (Week 2)
1. `state.py` 单轨化 + 全量替换调用点
2. 删除 `graph/tools.py`，下沉 `@tool`
3. 删除 `agents/router.py` 遗留意图层
4. 新建 `exceptions.py`，逐文件替换裸 `except Exception`
5. 修复 `time.sleep` → `asyncio.sleep`
6. 消除函数内导入，拆分/延迟初始化模块
7. **验收**: `pytest` 全绿，`ruff`/`ty` 全绿

### 里程碑 3: P2 前端加固 (Week 3)
1. 修正 `package.json` 依赖，重新安装
2. 引入 `zod`，定义共享 Schema
3. 统一 `src/lib/api.ts`，改造各 hooks
4. 修复 `useNotifications.ts` + Dashboard 集成
5. `localStorage` → `sessionStorage`
6. 升级 `tsconfig.json` target
7. **验收**: `npm run build` 成功，E2E 测试通过

### 里程碑 4: P3 长期优化 (Week 4)
1. 升级 FastAPI、Starlette、Typer、bcrypt
2. `config.py` 延迟实例化 + SECRET_KEY 校验
3. 全项目替换 `settings` 导入
4. 文档同步更新
5. **验收**: 全量测试通过，CI 绿灯

---

## 8. 测试策略

### 8.1 后端

- **单元测试**: 不依赖数据库/外部服务，使用 `unittest.mock` 和 `pytest-mock`。
- **API 集成测试**: 使用 `AsyncClient` + 内存/测试数据库，覆盖认证、聊天、管理接口。
- **Graph 集成测试**: 使用 `make_agent_state` 工厂构造状态，验证节点流转逻辑。
- **回归测试**: 每次改造后 `uv run pytest --cov=app --cov-fail-under=75`

### 8.2 前端

- **类型检查**: `npm run build` (Vite 构建会触发 TypeScript 编译)
- **E2E 回归**: `npm run test:e2e`
- **运行时校验回归**: 修改后端 mock 返回异常数据，验证 `zod` 是否能正确抛出

---

## 9. 风险与回滚

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 状态模型单轨化影响面过大 | 中 | 使用全局搜索 + `ty check` 确保无遗漏字段；改造前写好 `make_agent_state` |
| FastAPI 大版本升级破坏 `slowapi` | 中 | 升级后在本地手动测试限流接口；如失败则降级 FastAPI 到兼容版本 |
| 删除 `graph/tools.py` 后 LangGraph 编译失败 | 低 | `@tool` 装饰器行为一致，只需验证 `workflow.py` 编译 |
| 前端 `zod` 引入后大量类型不匹配 | 中 | 逐步替换，先改高频接口（`useChat.ts`、`useTasks.ts`），再改低频接口 |
| `settings` 延迟实例化导致启动时行为变化 | 低 | 在 `main.py` 启动时显式调用 `get_settings()` 验证配置完整性 |

**回滚策略**:
- 每个里程碑独立分支开发，通过 PR 合并。
- 任何一个里程碑的验收测试失败，不合并，不影响主线。

---

## 10. 验收清单

- [ ] `pytest -m unit` 在无数据库环境下 100% 通过
- [ ] `pytest` 在本地完整环境 100% 通过，覆盖率 >= 75%
- [ ] `ruff check app tests` 全绿
- [ ] `ty check --error-on-warning` 全绿
- [ ] `grep -r "audit_required\|audit_type\|normalize_state" app/ tests/` 返回空
- [ ] `app/graph/tools.py` 已删除
- [ ] `grep -r "time.sleep" app/` 返回空（Celery task 的 async 协程内无阻塞）
- [ ] 前端 `npm run build` 成功，无类型错误
- [ ] 前端 `npm run test:e2e` 通过
- [ ] `@types/node` 版本为 `22.x`
- [ ] 管理员通知功能在 E2E 中可验证（收到 WebSocket 消息后 Toast 弹出）
