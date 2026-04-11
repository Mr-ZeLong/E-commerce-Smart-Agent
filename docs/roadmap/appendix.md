# 附录: 风险矩阵、依赖关系与术语表

---

## 1. 综合风险矩阵

| 风险 ID | 描述 | 阶段 | 发生概率 | 影响 | 缓解措施 |
|---------|------|------|----------|------|----------|
| R1 | LangSmith API 配额/成本超支 | 1 | 中 | 中 | 5% 采样率；本地 trace 缓存 |
| R2 | Golden Dataset 标注噪声大 | 1 | 中 | 中 | 双人标注 + LLM 仲裁 |
| R3 | Logistics/Payment API 延迟或不可用 | 1 | 低 | 高 | Mock-first 实现；熔断器模式 |
| R4 | Supervisor LLM 委派决策错误 | 2 | 中 | 高 | 规则优先兜底；决策审计表 |
| R5 | 商品目录语义搜索质量差 | 2 | 中 | 中 | 专门的商品 Golden Dataset；迭代 embedding 调优 |
| R6 | 并行多意图状态合并冲突 | 2 | 低 | 中 | 不可变的 per-agent sub-state key |
| R7 | 记忆存储中发生 PII 泄漏 | 3 | 中 | 高 | 正则脱敏；人工审计；GDPR 删除权 API |
| R8 | 向量记忆检索结果无关 | 3 | 中 | 低 | 用户域过滤 + 时间衰减 + 摘要优先 |
| R9 | 配置热重载竞态条件 | 3 | 低 | 低 | TTL 内存缓存；不修改运行中 graph 实例 |
| R10 | VLM 推理延迟/成本过高 | 4 | 中 | 高 | 图片缩放 + 日配额 + 纯文本降级 |
| R11 | 推荐数据稀疏 | 4 | 中 | 中 | 先做 content-based（向量），后续引入协同过滤 |
| R12 | A/B 测试流量不足 | 4 | 中 | 低 | 限于高流量意图；使用贝叶斯监控 |

---

## 2. 依赖链

```text
第一阶段 (M1-M2)
├── LangSmith API key 已申请
├── Logistics/Account/Payment 数据 schema 已确认
└── CI pipeline 已支持 evaluation tests

第二阶段 (M3-M5)
├── 第一阶段完成（tracing + tool registry 上线）
├── 商品目录数据可用
├── Qdrant 集群容量可承载 product_catalog collection
└── B端 前端资源可支撑 KB 管理 UI

第三阶段 (M6-M8)
├── 第二阶段完成（supervisor 稳定）
├── 长期对话存储的法务/隐私审查通过
└── Qdrant 集群容量可承载 conversation_memory collection

第四阶段 (M9-M12)
├── 第三阶段完成（记忆系统上线）
├── 第一阶段可观测性成熟（支撑 A/B 分析）
├── 商品目录维护流程已建立
└── VLM API 权限与预算已获批
```

---

## 3. 术语表

| 术语 | 定义 |
|------|------|
| **Agent** | 接收 `AgentState` 并返回 `AgentProcessResult` 的自治处理单元。在本项目中，所有 Agent 继承自 `BaseAgent`。 |
| **Supervisor** | 编排其他 Agent 的元 Agent，负责决定执行顺序与并行委派。 |
| **Subgraph** | 自包含的 LangGraph 组件，代表单个 Agent 的内部工作流。 |
| **Tool** | 由 Agent 执行的标准化接口确定性函数（通常是 DB/API 查询）。 |
| **Golden Dataset** | 经人工标注的精选查询集合，用于离线评估意图识别、检索与回答质量。 |
| **LangSmith** | LangChain 的可观测性平台，用于追踪 LLM 应用运行。 |
| **OTel** | OpenTelemetry，厂商中立的分布式追踪与指标标准。 |
| **VLM** | Vision-Language Model，可同时处理文本与图片的多模态 LLM。 |
| **RRF** | Reciprocal Rank Fusion，融合多个检索来源排序结果的方法。 |
| **Structured Memory** | 存储于 PostgreSQL 的长期用户数据（事实、偏好、画像）。 |
| **Vector Memory** | 以 embedding 形式存储于 Qdrant 的长期对话数据，用于语义检索。 |
| **A/B Test Variant** | 实验中某一特定配置（prompt、模型或参数）的变体，与对照组比较。 |

---

## 4. 成本护栏参考

| 护栏机制 | 环境变量/配置 | 默认值 | 生效位置 |
|----------|---------------|--------|----------|
| LangSmith 采样率 | `LANGSMITH_SAMPLE_RATE` | `0.05` | `app/observability/langsmith_tracer.py` |
| VLM 每日配额 | `VLM_DAILY_QUOTA` | `1000` | `app/multimodal/vlm_client.py`（Redis 计数器） |
| VLM 最大图片大小 | `VLM_MAX_IMAGE_BYTES` | `2_097_152` (2MB) | FastAPI 上传校验器 |
| VLM 最大边长 | `VLM_MAX_IMAGE_DIMENSION` | `1024` | 图片预处理器 |
| Per-Agent 限流 | `RATE_LIMIT_*` 按路由 | 30–100/min | `app/core/limiter.py`（slowapi） |
| Per-User LLM 调用预算 | `USER_LLM_BUDGET_PER_HOUR` | `60` | Redis 滑动窗口 |
| Embedding 降级 | `EMBEDDING_FALLBACK_ENABLED` | `True` | `app/retrieval/embeddings.py` |
| Reranker 跳过阈值 | `RERANK_MAX_LATENCY_SECONDS` | `2.0` | `app/retrieval/retriever.py` |

---

## 5. 成功指标看板（每周追踪）

| 指标 | 目标 | 度量方式 |
|------|------|----------|
| Intent Coverage | 10/12 类 | Intent router 日志 |
| Human Transfer Rate | <15% | `decider_node` 中 `needs_human_transfer` 标记 |
| First-Response Latency (p99) | <1.5s | OTel span（首 token） |
| End-to-End Latency (p99) | <5s | OTel span（完整 graph 执行） |
| Agent Test Coverage | ≥75% per agent | `pytest --cov` |
| LangSmith Trace Coverage | 100%（采样内） | LangSmith project dashboard |
| Golden Dataset Intent Accuracy | ≥85% | `tests/evaluation/pipeline.py` |
| Memory Relevance Rate | ≥70% | 人工评估回头客标注查询 |
| Complaint Form Completion | ≥75% | 投诉工单创建率 |
| Recommendation CTR Lift | 较基线 >20% | 前端点击追踪 |
| A/B Experiment Active Count | 始终 ≥1 个 | `Experiment` 表查询 |
| Quality Degradation Alert Fidelity | ≥70% top-intent 准确率 | 事后事故分析 |

---

## 6. 文档维护

本路线图应**每季度** Review 并更新。各阶段负责人需维护对应 markdown 文件，记录:
- 实际交付日期 vs 计划日期。
- 范围裁剪或新增。
- 实施后记（哪些有效、哪些无效）。

下次计划中的路线图 Review 安排在 **M3 末**（第二阶段中期）。
