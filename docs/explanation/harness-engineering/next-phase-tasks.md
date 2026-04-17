# Harness Engineering下一阶段任务

> **文档版本**: 1.0  
> **生成日期**: 2026-04-17  
> **适用阶段**: Q2-Q3 2026

---

## 总体目标

在Q2-Q3阶段，建立完整的Harness Engineering体系，实现：

- **回归测试自动化**: 每次代码/Prompt变更自动运行Golden Dataset评估
- **生产监控看板**: 实时展示核心指标和性能趋势
- **多维度评估**: 覆盖功能性、质量、效率、安全四个维度
- **持续改进闭环**: 生产数据 → 问题发现 → Golden Dataset更新 → 模型优化

---

## Phase 1: 评估基础设施完善（Q2 W1-W6）

### Task 1: Golden Dataset扩充与版本化

**目标**: 建立覆盖全面的Golden Dataset，支持版本管理

**与现有工作关系**: 补充已有的`EvaluationPipeline`（`app/evaluation/pipeline.py`），为其提供更高质量的测试数据

**数据集规划**:

| 类别 | 数量 | 示例 |
|------|------|------|
| 订单查询 | 30 | "查一下我的订单","订单SN123状态" |
| 退款申请 | 25 | "我要退货","这个商品能退吗" |
| 政策咨询 | 25 | "退换货政策","运费怎么算" |
| 商品查询 | 20 | "有红色款吗","这个多少钱" |
| 模糊意图 | 20 | "那个东西","帮我处理一下" |
| 多意图 | 15 | "查订单并申请退款" |
| 异常输入 | 15 | "你是个笨蛋","12345" |
| 长对话 | 10 | 10+轮对话场景 |

**验收标准**:
- [ ] 数据集扩充至150+条
- [ ] 覆盖8个维度
- [ ] 存储于`data/golden_dataset_v2.jsonl`
- [ ] 通过`EvaluationPipeline`验证可运行
- [ ] 数据集使用Git LFS管理

**依赖**: 无  
**预计工期**: 5天

---

### Task 2: 回归测试自动化

**目标**: 将评估集成到CI/CD流程

**参考**: [测试框架指南](../../tests/AGENTS.md)  
**与现有工作关系**: 利用已有的CI配置，扩展评估步骤

**GitHub Actions配置**:
```yaml
# .github/workflows/eval.yml
name: Evaluation
on:
  pull_request:
    paths:
      - 'app/agents/**'
      - 'app/graph/**'
      - 'app/intent/**'
      - 'data/golden_dataset*.jsonl'
  schedule:
    - cron: '0 2 * * 0'  # 每周日凌晨2点

jobs:
  regression:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Golden Dataset Evaluation
        # TODO: 需新建 app/evaluation/run.py CLI入口
        run: uv run python -m app.evaluation.run --dataset data/golden_dataset_v2.jsonl
      - name: Upload Results
        uses: actions/upload-artifact@v4
        with:
          name: eval-results
          path: reports/eval_*.json
```

**验收标准**:
- [ ] PR触发自动评估
- [ ] 生成对比报告（当前vs基准）
- [ ] 性能下降>5%时阻塞PR
- [ ] 每周定时运行benchmark测试

**依赖**: Task 1  
**预计工期**: 3天

---

### Task 3: 多维度Metrics扩展

**目标**: 补充缺失的质量和效率指标

**与现有工作关系**: 扩展`app/evaluation/metrics.py`

**新增指标**:

| 指标 | 文件 | 说明 |
|------|------|------|
| **Tone Consistency** | `app/evaluation/metrics.py` | 语气一致性评分（LLM-as-Judge） |
| **Token Efficiency** | `app/evaluation/metrics.py` | Token消耗/对话效率 |
| **Latency Tracker** | `app/observability/` | 延迟趋势追踪 |
| **Containment Rate** | `app/evaluation/metrics.py` | 对话保持率（未转人工的比例） |

**验收标准**:
- [ ] 新增4个Metrics实现
- [ ] 单元测试覆盖
- [ ] 集成到`EvaluationPipeline`

**依赖**: 无  
**预计工期**: 5天

---

## Phase 2: 生产监控与闭环（Q2 W7-W12）

### Task 4: 生产监控看板

**目标**: 建立实时性能监控看板

**监控指标**:
- 意图识别准确率（按Agent、按小时）
- RAG检索精度（score分布）
- 人工接管率（按原因分类）
- Token消耗（输入/输出token数）
- 延迟（TTFT、总耗时）
- 幻觉率（定时抽检）

**技术方案**:
- 后端：扩展Admin API，新增Metrics聚合接口
- 前端：Admin Dashboard新增Metrics页面
- 数据：从`GraphExecutionLog`聚合

**验收标准**:
- [ ] Admin Dashboard新增Metrics页面
- [ ] 实时展示核心指标
- [ ] 支持按时间范围筛选
- [ ] 异常情况告警（阈值可配置）

**依赖**: Task 3  
**预计工期**: 10天

---

### Task 5: 持续改进闭环

**目标**: 建立"生产数据 → 问题发现 → 数据集更新 → 模型优化"的闭环

**流程设计**:
```
生产对话 → 质量抽检(5%) → 人工标注 → 问题归因 → 
Golden Dataset更新 → Prompt/模型优化 → A/B测试 → 生产验证
```

**验收标准**:
- [ ] 每周自动抽检5%对话
- [ ] 标注结果自动反馈到Golden Dataset
- [ ] 建立问题归因模板（意图错误/幻觉/延迟/安全）
- [ ] 闭环流程文档化

**依赖**: Task 1, Task 4  
**预计工期**: 7天

---

## Phase 3: 高级能力（Q3）

### Task 6: 影子测试（Shadow Testing）

**目标**: 在生产环境并行运行新旧版本，无风险对比性能

**实施方案**:
- 新模型/Prompt部署到影子环境
- 复制生产流量到影子环境
- 对比影子环境和生产环境的输出
- 无用户感知，无风险

**验收标准**:
- [ ] 影子环境部署脚本
- [ ] 流量复制机制（采样10%）
- [ ] 自动对比报告生成
- [ ] 影子测试文档化

**依赖**: Task 4  
**预计工期**: 7天

---

### Task 7: 对抗性测试套件

**目标**: 建立专门测试系统鲁棒性的对抗性数据集

**对抗Case类型**:
- Prompt注入攻击
- 敏感信息诱导
- 边界条件（超长输入、特殊字符）
- 意图混淆（语义相似但意图不同）

**验收标准**:
- [ ] 50+对抗性测试用例
- [ ] 自动化运行脚本
- [ ] 安全漏洞报告模板

**依赖**: Task 1  
**预计工期**: 5天

---

## 与现有路线图的衔接

| 本文档任务 | 对应现有路线图 | 关系说明 |
|-----------|---------------|----------|
| Task 1 (Golden Dataset) | [Context Engineering评估框架](../context-engineering/evaluation-framework.md) | 补充Golden Dataset，支撑Needle-in-Haystack等测试 |
| Task 2 (回归测试) | [测试框架指南](../../tests/AGENTS.md) | 扩展CI配置，增加自动化评估步骤 |
| Task 3 (Metrics扩展) | 新增 | Harness特有指标（语气一致性、Containment Rate等） |
| Task 4 (监控看板) | Context Engineering T8 | 实现上下文利用率遥测的可视化 |
| Task 5 (持续改进) | [Prompt Engineering Task 7](../prompt-engineering/next-phase-tasks.md) | 实现Prompt效果评估体系的生产级闭环 |
| Task 6 (影子测试) | 新增 | 生产级安全验证手段 |
| Task 7 (对抗性测试) | 新增 | 安全鲁棒性验证 |

---

## 实施路线图

### Q2 详细计划

```
Week 1-2: Task 1 (Golden Dataset)
Week 3-4: Task 2 (回归测试) + Task 3 (Metrics扩展)
Week 5-6: Task 3完成 + Review
Week 7-9: Task 4 (监控看板)
Week 10-12: Task 5 (持续改进闭环) + Q2收尾
```

### Q3 详细计划

```
Week 1-3: Task 6 (影子测试)
Week 4-6: Task 7 (对抗性测试)
Week 7-12: 优化完善 + 文档 + Q3总结
```

---

## 风险与缓解

| 风险 | 可能性 | 影响 | 缓解策略 |
|------|--------|------|----------|
| Golden Dataset标注质量差 | 低 | 中 | 多人交叉验证；标注指南；采样复查 |
| 监控看板开发延期 | 中 | 中 | MVP先实现核心指标；分阶段交付 |
| 影子测试资源消耗大 | 中 | 低 | 采样10%流量；独立轻量部署 |
| 对抗性测试发现严重漏洞 | 低 | 高 | 建立快速修复流程；安全团队介入 |

---

## 附录

### 相关代码位置

| 模块 | 主要文件 |
|------|----------|
| 评估Pipeline | `app/evaluation/pipeline.py` |
| 评估Metrics | `app/evaluation/metrics.py` |
| 执行日志 | `app/models/observability.py` |
| 实验框架 | `app/models/experiment.py`, `app/services/experiment.py` |
| 在线评估 | `app/services/online_eval.py` |

### 参考文档

- [Context Engineering路线图](../context-engineering/roadmap.md)
- [Prompt Engineering任务列表](../prompt-engineering/next-phase-tasks.md)
- [项目架构概览](../architecture/overview.md)
- [测试框架指南](../../tests/AGENTS.md)
