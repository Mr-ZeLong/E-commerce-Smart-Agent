# 第二阶段: 专家 Agent 扩展

> **周期**: 2–3 个月 (M3–M5)  
> **主题**: *从简单路由到真正的协作。*  
> **目标**: 将 Graph 演进为 Supervisor 模式，新增 ProductAgent 与 CartAgent，并实现独立多意图的并行执行。

---

## 1. 阶段目标

将现有的线性 router → specialist → evaluator pipeline 改造为**灵活的 supervisor-based graph**，使其能够:
- 向任意专家 Agent 委派任务。
- 在意图相互依赖时串行调用 Agent。
- 在子意图独立时并行执行。
- 覆盖完整的高优先级意图集合: `LOGISTICS`、`ACCOUNT`、`PAYMENT`、`PRODUCT`、`CART`。

---

## 2. 关键任务

### 2.1 Supervisor 模式重构 (M3)

**任务 P2-S1: Supervisor Node 设计**
- 新增 `app/agents/supervisor.py`: 元 Agent，负责决定**下一个调用谁**、**是否并行**、**何时终止**。
- Supervisor 输入:
  - `intent_result`（主意图 + 次意图 + 多意图列表）
  - `history`
  - 已执行 Agent 的部分状态更新
- Supervisor 输出 `Command`:
  - `goto`: 单个 Agent 名称或并行 Agent 名称列表
  - `update`: 推理轨迹

**任务 P2-S2: 每个 Agent 一个 Subgraph**
- 将各专家 Agent（`policy_agent`、`order_agent`、`logistics_agent`、`account_agent`、`payment_agent`、`product_agent`、`cart_agent`）转换为具有标准化输入/输出接口的 **subgraph**。
- 每个 subgraph:
  - 消费 `AgentState` 的子集
  - 返回标准化的 `AgentProcessResult`
  - 可独立测试

**任务 P2-S3: Graph 重写**
- 用 supervisor-centric graph 替换 `app/graph/workflow.py`:
  ```
  START → router_node → supervisor_node → [subgraph(s)] → evaluator_node → decider_node → END
  ```
- `router_node` 仅负责意图识别与澄清；路由决策移交 `supervisor_node`。
- 更新 `compile_app_graph()`，使其接受 Agent subgraph 字典而非单个 Agent 实例。

### 2.2 ProductAgent (M3–M4)

**任务 P2-P1: 商品目录集成**
- 新增 `app/agents/product.py` 与 `app/tools/product_tool.py`。
- 商品搜索基于商品目录的**语义检索**（Qdrant collection `product_catalog`）。
- 对商品描述、名称、SKU 做 dense embedding。
- Tool 支持过滤条件: category、price range、in-stock flag。

**任务 P2-P2: 商品问答**
- Agent 回答如 "iPhone 16 Pro 有没有 120Hz 屏幕？" 这类问题。
- 若精确参数在目录元数据中，直接作答。
- 否则回退到基于检索到的商品描述片段进行 LLM 推理。

### 2.3 CartAgent (M4)

**任务 P2-C1: 购物车操作**
- 新增 `app/agents/cart.py` + `app/tools/cart_tool.py`。
- 支持的操作（映射自 `IntentAction.ADD`、`REMOVE`、`QUERY`、`MODIFY`，当 `primary_intent == CART` 时）:
  - 查看购物车
  - 按 SKU/product_id 添加商品
  - 移除商品
  - 修改数量

**任务 P2-C2: 购物车状态持久化**
- 购物车状态按 `user_id` 存储在 Redis 中（临时态，24h TTL）。
- Tool 以 JSON 形式读写 Redis cart key（`cart:{user_id}`）。

### 2.4 多意图并行执行 (M4–M5)

**任务 P2-M1: 并行 Subgraph 编译器**
- 当 `MultiIntentProcessor` 识别出 ≥2 个独立意图时（如 "查一下我的订单状态，并告诉我退货政策"），Supervisor 通过 LangGraph 的 `Send` 分支将它们并行派发。
- 各 Agent 运行结果合并回 `AgentState`，以子答案列表形式存在。

**任务 P2-M2: 回复融合节点**
- 在并行执行完成与 `evaluator_node` 之间新增 `synthesis_node`。
- `synthesis_node` 通过一次轻量 LLM 调用，将多个 Agent 的答案融合为一条连贯回复。

**任务 P2-M3: 意图独立性分类器**
- 在 `app/intent/multi_intent.py` 中新增 `are_independent(intent_a, intent_b) -> bool`。
- 采用兼容性矩阵: `ORDER` 与 `POLICY` 独立；`CART` 与 `PAYMENT` 依赖（需串行）。

### 2.5 B端 知识库管理 (M4–M5)

**任务 P2-B1: KB CRUD API**
- 新增 Admin API 端点:
  - `GET /api/v1/admin/knowledge`（文档列表）
  - `POST /api/v1/admin/knowledge`（上传 PDF/Markdown）
  - `DELETE /api/v1/admin/knowledge/{doc_id}`
- 文档元数据存储于 PostgreSQL（`KnowledgeDocument` 表）。

**任务 P2-B2: ETL 触发 API**
- `POST /api/v1/admin/knowledge/{doc_id}/sync` 通过 Celery 任务触发 `scripts/etl_qdrant.py`。
- Admin UI 显示同步状态（排队中 / 运行中 / 完成 / 失败）。

**任务 P2-B3: 前端 KB 管理 UI**
- Admin Dashboard 新增 "知识库" Tab。
- 文档列表、上传按钮、删除确认、"同步到 Qdrant" 操作。

---

## 3. 核心交付物

| 交付物 | 位置 |
|--------|------|
| SupervisorAgent | `app/agents/supervisor.py` |
| 重构后的 LangGraph workflow | `app/graph/workflow.py`（重写） |
| Agent subgraph 标准 | `app/graph/subgraphs.py` |
| ProductAgent | `app/agents/product.py` |
| 商品目录 Qdrant collection | `product_catalog` |
| CartAgent | `app/agents/cart.py` |
| 多意图并行执行器 | `app/graph/parallel.py` |
| 回复融合节点 | `app/graph/nodes.py::synthesis_node` |
| B端 KB 管理 UI | `frontend/src/apps/admin/pages/KnowledgeBase.tsx` |

---

## 4. 验收标准

### Supervisor & Graph
- [ ] 一次对话可串行流经 3 个以上不同 Agent 且无需人工转接。
- [ ] Supervisor 决策延迟（LLM 调用）p99 <500ms。
- [ ] 重构后所有现有测试（`tests/graph/`、`tests/integration/`）通过。

### ProductAgent
- [ ] 针对商品相关 Golden Dataset 查询，语义搜索 top-3 相关率 ≥80%。
- [ ] 库存类查询能基于真实目录数据正确回答。

### CartAgent
- [ ] 购物车增删查操作可通过 `/chat` 端到端成功执行。
- [ ] 购物车状态在 24h 内多次消息间正确保持。

### 多意图
- [ ] 并行多意图执行耗时 < 2 倍最慢单 Agent 延迟。
- [ ] 融合后的回复经人工评估，≥80% 的并行场景被判定为连贯。

### B端
- [ ] Admin 可上传 Markdown 文件、触发 ETL，并在 5 分钟内于 policy 搜索结果中看到更新。

---

## 5. 风险与依赖

| 风险 | 发生概率 | 缓解措施 |
|------|----------|----------|
| Supervisor LLM 委派决策错误 | 中 | 先采用规则优先的 Supervisor（intent→agent 硬映射），随着 trace 质量提升再逐步释放 LLM 自主权 |
| 商品目录语义搜索质量低 | 中 | 准备专门的商品 Golden Dataset；迭代 chunking 与 embedding 策略 |
| 并行 subgraph 状态合并冲突 | 低 | 强制每个 Agent 使用不可变的子状态 key（如 `product_data`、`cart_data`） |
| CartAgent 状态与生产订单流冲突 | 低 | 使用隔离的 Redis key，与 `Order` DB 实体明确区分 |

### 依赖项
- 第一阶段可观测性已上线，用于度量 Supervisor 延迟与委派准确率。
- 商品目录数据已可用且质量达标。
- Qdrant 集群容量已确认可承载 `product_catalog` collection。

---

## 6. Agent 相关重点

第二阶段是整个路线图的**架构心脏**。此阶段的决策决定了系统能否扩展到 10+ Agent。

### 6.1 Supervisor 作为唯一真相源
Supervisor 取代 router 成为编排中枢。其设计必须具备:
- **确定性降级**: 若 Supervisor LLM 失败或返回非法 `goto`，回退到硬编码的 intent→agent 映射。
- **可观测性**: 每次 Supervisor 决策连同完整推理轨迹一起记录（LangSmith + 自定义表 `supervisor_decisions`）。

### 6.2 Tool-Based vs LLM-Based Agent 分类
到第二阶段末，Agent 分类应清晰如下:

| Agent 类型 | 包含 Agent | 模式 |
|------------|------------|------|
| Tool Wrapper | Logistics、Account、Payment、Cart | 极简 system prompt + tool result 格式化 |
| RAG Specialist | Policy、Product | HybridRetriever 加持的检索增强生成 |
| Workflow Specialist | Order | DB 查询、业务规则与副作用（Celery）混合 |

该分类指导第三阶段记忆注入: RAG Agent 接收用户偏好向量；Tool Agent 接收结构化用户事实。

### 6.3 并行执行作为竞争壁垒
电商用户经常把多个问题打包提出（"我的订单到哪了，还能退吗？"）。并行多意图能力直接提升响应速度与准确性。它是第二阶段技术最复杂的任务，应投入专门的工程时间。
