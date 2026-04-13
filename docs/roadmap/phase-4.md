# 第四阶段: 高级智能与持续优化

> **周期**: 3–4 个月 (M9–M12)  
> **主题**: *从可用到自我进化。*  > **目标**: 交付 ComplaintAgent、A/B 测试框架与自动质量告警闭环。

---

## 1. 阶段目标

将平台推向高级 AI 能力:
- 通过结构化工作流收集并分流投诉。

- 质量下降时自动告警。

---

## 2. 关键任务

### 2.1 ComplaintAgent (M10)

**任务 P4-C1: 投诉受理工作流**
- 新增 `app/agents/complaint.py` 与 `ComplaintTool`。
- 将 `COMPLAINT` 意图映射为结构化表单填写工作流:
  1. 识别投诉类别（商品缺陷、服务、物流、其他）。
  2. 收集订单号（如适用）。
  3. 收集详细描述。
  4. 收集期望解决方案（退款、换货、道歉、赔偿）。
- 复用现有的 clarification engine 进行渐进式槽位填充。

**任务 P4-C2: 投诉分流与工单**
- 表单填写完成后，在 PostgreSQL 中创建 `ComplaintTicket` 记录。
- Celery 任务通过邮件与 WebSocket 通知客服团队。
- B端: 新增 "投诉" Tab，展示工单队列、状态更新与客服分配。

### 2.2 在线评估与自动告警 (M11–M12)

**任务 P4-E1: 反馈收集**
- C端: 每条 assistant 消息旁显示 thumbs up/down 按钮。
- 显式反馈存入 `MessageFeedback` 表（消息索引、评分、自由文本评论）。

**任务 P4-E2: 隐式信号**
- 定义 "隐式负向" 信号:
  - 立刻要求人工转接
  - 追问问题与上一回合回答矛盾
  - 低 confidence score + retry loop
- 每日聚合为 `QualityScore`。

**任务 P4-E3: 自动告警**
- Celery beat 任务每小时运行一次。
- 若 `QualityScore` 较 7 日滚动均值下降 >15%，通过 WebSocket + 邮件向 admin 告警。
- 告警附带 top 3 劣化意图及 sample trace IDs。

### 2.4 B端 高级数据分析 (M12)

**任务 P4-B1: 数据分析看板 V2**
- 在 Agent 性能 Tab 中扩展:
  - CSAT 趋势（显式 + 隐式）
  - 升级根因分析（导致转接的主要意图与 Agent）
  - Agent 对比报告（10 个 Agent 并排指标）
  - 会话回放 + 完整 LangSmith trace 链接

---

## 3. 核心交付物

| 交付物 | 位置 |
|--------|------|
| ComplaintAgent | `app/agents/complaint.py` |
| 投诉工单系统 | `app/models/complaint.py`、`app/tasks/complaint_tasks.py` |

| 在线评估 pipeline | `app/evaluation/online.py` |
| 自动告警任务 | `app/tasks/quality_alert_tasks.py` |
| 高级数据分析 UI | `frontend/src/apps/admin/pages/AnalyticsV2.tsx` |

---

## 4. 验收标准

### ComplaintAgent
- [ ] 启动投诉意图的用户中，表单完成率 ≥75%。
- [ ] 表单完成后 10 秒内在 B端 可见工单。

### 在线评估
- [ ] 质量下降 15% 后 1 小时内触发告警。
- [ ] 告警在 ≥70% 的事故中正确识别出 top 2 劣化意图。

---

## 5. 风险与依赖

| 风险 | 发生概率 | 缓解措施 |
|------|----------|----------|
| ComplaintAgent 反而增加人工工作量 | 低 | 明确升级规则；自动分类与预填表单减少客服处理时间 |

### 依赖项
- 第三阶段记忆系统已上线。
- 第一阶段可观测性已成熟。
- 商品目录维护流程已建立。

---

## 6. Agent 相关重点

第四阶段代表 Agent 平台的**打磨与规模化**。

### 6.1 持续改进文化
到第四阶段末，团队应建立:
- 每季度更新的 Golden Dataset。

- 每周 review LangSmith trace，聚焦 confidence 最低的会话。
- 自动质量告警防止回退。

这完成了闭环: **度量 → 构建 → 记忆 → 优化**。
