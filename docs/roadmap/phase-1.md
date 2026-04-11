# 第一阶段: 可观测性、评估体系与 Tool 基础设施

> **周期**: 2 个月 (M1–M2)  
> **主题**: *无法度量则无法改进。*  
> **目标**: 在扩展 Agent 舰队之前，先建立 tracing、评估基线与 tool-use 基础设施。

---

## 1. 阶段目标

交付**度量优先**的基础能力:
- 每一次 LangGraph 调用都可追溯。
- 每一个新 Agent 都能通过离线 Golden Dataset 验证。
- 存在可复用的 `BaseTool` + `ToolRegistry` 模式，支撑后续阶段快速构建专家 Agent。

---

## 2. 关键任务

### 2.1 Agent 可观测性 (M1)

**任务 P1-O1: LangSmith 集成**
- 在 `pyproject.toml` 中新增 `langsmith>=0.3.0`。
- 对 `app.graph.workflow.compile_app_graph()` 包裹 LangChain runnable，并按 Agent 名称打 tag。
- 确保 `router_node`、`policy_agent`、`order_agent`、`evaluator_node` 均传播 `config={"tags": [...]}`。
- 在 LangSmith metadata 中记录 `thread_id`、`user_id`、`intent_result`。

**任务 P1-O2: FastAPI OpenTelemetry 埋点**
- 引入 `opentelemetry-instrumentation-fastapi`、`opentelemetry-exporter-otlp`。
- 在 `app/main.py` 的 lifespan 中完成 FastAPI 埋点。
- 对 `/chat`、`/admin/*` 及 WebSocket 端点创建 span。
- 将 OTel trace ID 与 LangSmith run ID 关联，实现跨系统排障。

**任务 P1-O3: B端 性能看板 V1**
- 前端: 在 admin Dashboard 新增 "Agent 性能" Tab。
- 展示指标（来自后端新增的数据聚合 API）:
  - 总会话数（24h / 7d / 30d）
  - 按 Agent 统计的人工转接率
  - 按 Agent 统计的平均 confidence score
  - 每个 graph node 的 P99 延迟

### 2.2 评估框架 (M1–M2)

**任务 P1-E1: Golden Dataset v1**
- 精选 150 条标注查询，覆盖全部 12 个 `IntentCategory`。
- 每条标注包含: 期望意图、必填槽位、期望答案片段、期望审核级别。
- 以 JSONL 格式存储于 `tests/evaluation/golden_dataset_v1.jsonl`。

**任务 P1-E2: 离线评估 Pipeline**
- 新增模块: `app/evaluation/` + `tests/evaluation/`。
- 指标:
  - **Intent Accuracy**: `primary_intent` 完全匹配率。
  - **Slot Recall**: 必填槽位正确提取的百分比。
  - **RAG Precision**: top-3 检索片段的相关性人工/模型判定。
  - **Answer Correctness**: LLM-as-judge 对比生成答案与 gold label。
- CI 集成: 每次 PR 自动运行 `uv run pytest tests/evaluation/`。

**任务 P1-E3: 评估 B端 查看器**
- Admin UI 页面: 浏览 Golden Dataset 样本并查看最新评估运行结果。

### 2.3 Tool 基础设施 (M2)

**任务 P1-T1: BaseTool 抽象**
- 新建 `app/tools/base.py`:
  ```python
  class BaseTool(ABC):
      name: str
      description: str
      async def execute(self, state: AgentState, **kwargs) -> ToolResult: ...
  ```
- `ToolResult` 返回结构化字典，包含 `output`、`confidence`、`source`。

**任务 P1-T2: Tool Registry**
- 新建 `app/tools/registry.py`:
  ```python
  class ToolRegistry:
      def register(self, tool: BaseTool) -> None: ...
      async def execute(self, name: str, state: AgentState) -> ToolResult: ...
  ```
- Registry 以单例形式存在，通过 `Depends` 注入到各 Agent 中。

### 2.4 新增 Tool-Based Agent (M2)

这些 Agent 本质上是**数据库/API 查询包装器**，LLM 推理量极小，是验证 tool-based 模式的最佳首批对象。

**任务 P1-A1: LogisticsAgent**
- 查询 `Order.tracking_number` 与物流状态。
- Node: `app/agents/logistics.py`
- Tool: `app/tools/logistics_tool.py`
- 路由: `LOGISTICS` 意图 → `logistics_agent`

**任务 P1-A2: AccountAgent**
- 查询用户资料、会员等级、账户余额/优惠券。
- Node: `app/agents/account.py`
- Tool: `app/tools/account_tool.py`
- 路由: `ACCOUNT` 意图 → `account_agent`

**任务 P1-A3: PaymentAgent**
- 查询支付状态、发票信息、退款支付记录。
- Node: `app/agents/payment.py`
- Tool: `app/tools/payment_tool.py`
- 路由: `PAYMENT` 意图 → `payment_agent`

**任务 P1-A4: Router 增强**
- 更新 `IntentRouterAgent._INTENT_MAPPINGS`，将 `LOGISTICS`、`ACCOUNT`、`PAYMENT` 路由到对应 Agent。
- 更新 `app/graph/workflow.py` 与 `app/graph/nodes.py` 注册新节点。
- 更新 `evaluator_node` 逻辑以适配扩展后的 Agent 集合。

### 2.5 B端 会话日志查看器 (M2)

**任务 P1-B1: Thread 历史 UI**
- Admin Dashboard 新增 "会话日志" Tab。
- 列表展示近期 thread，支持按日期范围和意图筛选。
- 点击可查看完整消息轨迹（user + assistant 轮次）。
- 可选: 跳转 LangSmith trace 页面链接。

---

## 3. 核心交付物

| 交付物 | 位置 |
|--------|------|
| LangSmith tracing 中间件 | `app/observability/langsmith_tracer.py` |
| OpenTelemetry FastAPI 埋点 | `app/observability/otel_setup.py` |
| B端 Agent 性能看板 V1 | `frontend/src/apps/admin/pages/Performance.tsx` |
| Golden Dataset v1 | `tests/evaluation/golden_dataset_v1.jsonl` |
| 离线评估 pipeline | `app/evaluation/pipeline.py` |
| BaseTool + ToolRegistry | `app/tools/base.py`、`app/tools/registry.py` |
| LogisticsAgent / AccountAgent / PaymentAgent | `app/agents/logistics.py`、`app/agents/account.py`、`app/agents/payment.py` |
| 会话日志查看器 | `frontend/src/apps/admin/pages/ConversationLogs.tsx` |

---

## 4. 验收标准

### 可观测性
- [ ] staging 环境 100% 的 `/chat` 调用产生 LangSmith trace。
- [ ] FastAPI 响应头中包含 OTel trace ID（`X-Trace-ID`）。
- [ ] B端 性能看板能无错误渲染 4 项指标。

### 评估体系
- [ ] Golden Dataset 包含 ≥150 条标注查询。
- [ ] CI 每次 PR 运行 `tests/evaluation/` 并输出 4 项指标。
- [ ] 现有 Agent 在 Golden Dataset 上的意图准确率 ≥85%。

### Agent & Tool
- [ ] `LogisticsAgent`、`AccountAgent`、`PaymentAgent` 各自 pytest 覆盖率 ≥90%。
- [ ] 3 个 Agent 均可通过 `/chat` 端到端调用并返回正确 DB 结果。
- [ ] Tool Registry 支持动态注册与执行 tool。

### 前端
- [ ] Admin 用户可查看会话日志并点击进 thread 详情。

---

## 5. 风险与依赖

| 风险 | 发生概率 | 缓解措施 |
|------|----------|----------|
| LangSmith API 配额超支 | 中 | 实施 5% 采样率；本地缓存 trace 元数据 |
| Golden Dataset 标注质量差 | 中 | 双人标注 + LLM-as-judge 仲裁分歧 |
| Payment/Logistics 数据源不可用 | 低 | 先以 mock tool 实现；后续替换为真实 API |
| 新 Agent 降低现有 router 准确率 | 中 | 在评估数据集上 A/B test 路由变更后再合并 |

### 依赖项
- 已配置 LangSmith API key。
- 物流追踪 API 或表 schema 已确认。
- Payment/invoice 表可通过现有 PostgreSQL 访问。

---

## 6. Agent 相关重点

第一阶段为后续所有阶段奠定**工程推进速度**:

1. **Tracing 作为一等要求**: 每个新 Agent PR 必须带上 LangSmith tag 与 OTel span。不可追溯则不能合并。
2. **Tool 模式收敛**: `LogisticsAgent`、`AccountAgent`、`PaymentAgent` 必须验证 `BaseTool` 模式的可扩展性。该模式将在第二阶段复用于 `CartAgent`。
3. **评估驱动验证**: 没有 Agent 能在不通过 Golden Dataset 意图准确率门槛（≥85%）的情况下从第一阶段毕业。这防止了低质量专家 Agent 上线后推高人工转接率。

---

## 7. TDD 导向任务拆分示例: LogisticsAgent

为强制 TDD，每个 Agent 遵循以下严格顺序:

1. **Spec commit**: `docs/specs/logistics-agent.md`（验收标准、数据模型、prompt 设计）
2. **Test commit**: `tests/agents/test_logistics.py` + `tests/tools/test_logistics_tool.py`（red 状态）
   - Mock `Order` DB 响应
   - Assert 正确提取 tracking number
   - Assert 优雅的 "not found" 处理
3. **Impl commit**: `app/agents/logistics.py` + `app/tools/logistics_tool.py`
4. **Integrate commit**: `app/graph/nodes.py`（新增 `build_logistics_node`）、`app/main.py`（DI 接线）
5. **Frontend commit**: `frontend/src/apps/admin/pages/Performance.tsx`（在指标筛选中增加 LogisticsAgent）
6. **Docs commit**: 更新 `AGENTS.md` 中的 LogisticsAgent 行为规则

*对 AccountAgent 与 PaymentAgent 重复上述 6 步流程。*
