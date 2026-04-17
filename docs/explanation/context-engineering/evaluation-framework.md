# 评估框架（验证上下文工程效果）

上下文工程是经验驱动的学科，任何优化都需要通过定量评估验证。建议建立以下三类基准测试：

## Needle-in-HayStack 准确性测试

- **目的**：验证关键信息（如用户身份、安全策略）在不同记忆负载和位置下能否被正确回忆
- **方法**：构造合成会话，在大量填充文本中插入一个关键事实，检查 Agent 是否能正确回答相关问题
- **指标**：Recall@K、Answer Accuracy
- **目标阈值**：
  - 在 75% 上下文利用率下，关键事实回忆准确率 ≥ **90%**
  - 在 90% 上下文利用率下，关键事实回忆准确率 ≥ **75%**
- **测试位置**：`tests/benchmarks/test_context_needle.py`

## Token 成本回归测试

- **目的**：量化 compaction、masking 等措施对 token 消耗的降低效果
- **方法**：使用代表性的多轮客服对话（≥20 轮，含工具调用）作为基准，在执行上下文工程优化前后分别统计：
  - 每次 LLM 调用的平均输入 token 数
  - 单次完整会话的总输入 token 数
  - checkpointer 中存储的平均状态体积
- **指标**：平均输入 token 减少百分比、checkpoint 体积减少百分比
- **目标阈值**：
  - 启用 Observation Masking + Compaction 后，单次会话平均输入 token 减少 ≥ **30%**
  - checkpointer 中平均状态体积减少 ≥ **25%**
- **测试位置**：`tests/benchmarks/test_token_regression.py`

## 延迟回归测试

- **目的**：验证 KV-Cache 优化和 checkpointer 压缩是否降低了端到端延迟
- **方法**：在相同对话 trace 上运行 10 次取平均
- **指标**：
  - 首 token 延迟（TTFT）
  - 图执行总耗时
  - checkpoint 反序列化耗时
- **目标阈值**：
  - 启用 KV-Cache（前缀命中）后，TTFT 降低 ≥ **20%**
  - 启用 checkpoint compaction 后，单步图调用总耗时增长控制在 **5%** 以内（避免 compaction 本身引入过多开销）
- **测试位置**：`tests/benchmarks/test_latency_regression.py`

## 评估基础设施

- 建议复用现有 `tests/integration/test_workflow_invoke.py` 的集成测试模式
- 在 CI 中增加可选的 benchmark 任务（不阻塞 PR，但定期运行并记录趋势）
