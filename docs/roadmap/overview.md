# E-commerce Smart Agent v4.1 — Agent 6~12 个月演进路线图

> **版本**: 1.0  
> **日期**: 2026-04-11  
> **范围**: Agent 架构、多 Agent 协作、记忆系统、可观测性与高级智能  
> **规划原则**: *先度量，再扩展；先个性化，再优化。*

---

## 1. 愿景与战略目标

本路线图将 E-commerce Smart Agent 从现有的**双 Agent 路由系统**（Order + Policy）演进为能够覆盖完整电商客户意图谱系的**记忆增强型多 Agent 协作平台**。

### North Star 指标
| 指标 | 当前基线 | 12 个月目标 |
|------|----------|-------------|
| 意图覆盖率（12 类中） | 4/12 (33%) | 10/12 (83%) |
| 人工转接率 | 待定（第一阶段度量） | <15% |
| 首响延迟（p99） | 待定 | <1.5s |
| 对话满意度（隐式） | 待定 | >80% 无升级 |
| B端 Admin 使用率 | 100%（强制） | 100% 且具备数据分析能力 |

---

## 2. 阶段总览

| 阶段 | 主题 | 周期 | 月份 |
|------|------|------|------|
| [第一阶段](phase-1.md) | 可观测性、评估体系与 Tool 基础设施 | 2 个月 | M1-M2 |
| [第二阶段](phase-2.md) | 专家 Agent 扩展 | 2-3 个月 | M3-M5 |
| [第三阶段](phase-3.md) | 记忆系统与 Agent 协作 | 2-3 个月 | M6-M8 |
| [第四阶段](phase-4.md) | 高级智能与持续优化 | 3-4 个月 | M9-M12 |

---

## 3. 里程碑时间线

```text
M1  M2  M3  M4  M5  M6  M7  M8  M9  M10 M11 M12
|===[P1]===|
                |=======[P2]=======|
                                    |=======[P3]=======|
                                                        |==========[P4]==========|

关键里程碑:
● M1  LangSmith tracing 上线, Golden Dataset v1 定义完成
● M2  Evaluation CI pipeline 运行, 3 个 tool-based agents (Logistics/Account/Payment) 交付
● M4  Supervisor pattern 重构完成, ProductAgent + CartAgent 上线
● M5  多意图并行执行投入运行
● M7  长期记忆集成到所有 Agent prompt
● M8  Admin KB 管理后台 + Agent Config Center 上线
● M10 多模态（图片）端到端支持
● M12 ComplaintAgent + RecommendationAgent 生产化, A/B testing framework 启用
```

---

## 4. 架构演进

### 当前状态 (v4.1)
```
START → router_node → (policy_agent | order_agent) → evaluator_node → decider_node → END
```

### 目标状态 (v4.4+)
```
START → router_node → supervisor_node
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
  policy_agent    →    order_agent    →    product_agent
        │                     │                     │
  logistics_agent           cart_agent        recommendation_agent
        │                     │
  account_agent           payment_agent
        │
  complaint_agent

        └─────────────────────┬─────────────────────┘
                              ▼
                    evaluator_node → decider_node → END
                              │
                              ▼
                      memory_persistence_node
```

**核心演进点**:
1. **Supervisor Node** (第二阶段): 成为中央编排节点，支持串行调用而不仅是一次路由。
2. **并行执行通道** (第二阶段): 针对多意图查询，独立 Agent 在并行 subgraph 中运行。
3. **记忆注入** (第三阶段): 结构化记忆（PostgreSQL）与向量记忆（Qdrant `conversation_memory`）共同前置到每次 Agent invocation 的上下文中。
4. **Tool Registry** (第一阶段): 将 LLM 推理型专家（Policy、Product）与工具包装型 Agent（Logistics、Account）统一在 `BaseAgent` 下管理。

---

## 5. 原子化提交策略

每个阶段拆分为**功能分支**，每次 commit 必须原子化，禁止混用目的。

| 提交顺序 | 目的 | 内容 |
|----------|------|------|
| `spec` | 设计文档 | 子功能的 Markdown spec（如 `logistics-agent-spec.md`） |
| `test` | TDD red 状态 | 新模块的所有 pytest 用例，**故意失败** |
| `impl` | 核心逻辑 | 后端实现，使单元测试通过 |
| `integrate` | 系统接线 | Graph node 更新、依赖注入、API 路由新增 |
| `frontend` | UI 改动 | React 组件、hooks、Zustand stores |
| `docs` | 文档更新 | `AGENTS.md`、`README.md`、inline docstrings 更新 |

**Git Workflow**:
- 分支命名: `feat/phase-{N}-{kebab-description}`
- 每个 `test` commit 必须通过 `uv run pytest` 验证（预期: red → green）
- 合并前要求: `ruff check`、`ty check --error-on-warning`、`pytest --cov=app --cov-fail-under=75`

---

## 6. 成本护栏（全局）

为防止系统规模化后 LLM/VLM/API 成本失控，以下控制在所有阶段**强制生效**:

| 护栏机制 | 实现方式 | 默认值 |
|----------|----------|--------|
| **LangSmith Sampling** | `LANGSMITH_SAMPLE_RATE` 环境变量 (0.0–1.0) | `0.05`（生产环境采样 5%） |
| **VLM 每日配额** | Redis 日计数器，超限时降级为纯文本 | 1000 请求/天 |
| **VLM 图片限制** | 最大 2MB，最大边 1024px，上传前自动缩放 | API Gateway 硬拒绝 |
| **Per-Agent 限流** | slowapi 分层: 轻量 Agent `100/min`，推理 Agent `30/min` | 按路由可配置 |
| **Per-User LLM 预算** | Redis 滑动窗口，统计每用户每小时 LLM token 调用次数 | 60 次/小时 |
| **Embedding 降级** | Qwen embedding 连续失败 >3 次时跳过嵌入，使用关键词兜底 | tenacity 自动触发 |
| **Reranker 跳过** | 若 rerank 延迟 >2s 或成本预算耗尽，直接返回 RRF top-k | 可配置开关 |

上述控制项必须在 `app/core/config.py` 中实现，并在 `app/core/limiter.py` 中强制执行。

---

## 7. 路线图成功标准

若在 M12 达成以下标准，视为路线图执行成功:
1. **12 类意图中有 10 类**具备专属专家 Agent 覆盖。
2. **人工转接率**可度量且非投诉类意图 <15%。
3. **所有新 Agent**具备 LangSmith trace 覆盖且 pytest 覆盖率 >75%。
4. **B端 admin**无需发版即可更新 KB 文档和 Agent 配置。
5. **无因缺失成本护栏导致的生产事故**。

---

## 8. 参考文档

- [第一阶段: 可观测性与评估体系](phase-1.md)
- [第二阶段: 专家 Agent 扩展](phase-2.md)
- [第三阶段: 记忆系统](phase-3.md)
- [第四阶段: 高级智能](phase-4.md)
- [附录: 风险、依赖与术语](appendix.md)
