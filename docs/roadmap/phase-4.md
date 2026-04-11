# 第四阶段: 高级智能与持续优化

> **周期**: 3–4 个月 (M9–M12)  
> **主题**: *从可用到自我进化。*  > **目标**: 交付多模态输入处理、ComplaintAgent、RecommendationAgent、A/B 测试框架与自动质量告警闭环。

---

## 1. 阶段目标

将平台推向高级 AI 能力:
- 处理用户上传的图片（商品照片、发票、快递面单）。
- 通过结构化工作流收集并分流投诉。
- 提供个性化商品推荐。
- 对 prompt 和模型进行持续 A/B 实验。
- 质量下降时自动告警。

---

## 2. 关键任务

### 2.1 多模态支持 (M9–M10)

**任务 P4-U1: 图片上传基础设施**
- 扩展 `/chat` API 以支持 multipart/form-data（`message` + 可选 `image` 文件）。
- 前端: `ChatInput` 增加图片附件按钮与预览。
- 校验: 最大 2MB，最长边缩放至 1024px，必要时转 JPEG。

**任务 P4-U2: 视觉-语言模型 (VLM) 集成**
- 新增模块: `app/multimodal/vlm_client.py`。
- 使用 `qwen-vl-plus`（或等效模型）通过 OpenAI-compatible 视觉 API 调用。
- 仅在用户上传图片时触发 VLM；纯文本查询绝不访问 VLM 端点。
- 成本护栏: Redis 日配额 1000 张图片，超限后降级为 "请用文字描述图片"。

**任务 P4-U3: 多模态 Agent 调度**
- 更新 `router_node`，检测图片存在后先路由到新的 `multimodal_assistant` subgraph，再交由 Supervisor。
- 多模态 assistant 从图片中提取文字描述，并将其作为用户 query 的一部分。
- 示例: 用户上传破损包裹照片 + "我想退这个" → VLM 描述损坏情况 → OrderAgent 处理退款。

### 2.2 ComplaintAgent (M10)

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

### 2.3 RecommendationAgent (M10–M11)

**任务 P4-R1: 推荐 Pipeline**
- 新增 `app/agents/recommendation.py`。
- 混合架构:
  - **候选生成**: 在 `product_catalog` 中基于用户近期浏览/购买历史（来自结构化记忆）做向量相似度搜索。
  - **候选重排**: 轻量级规则过滤（有货、价格带、品类偏好）。
  - **解释生成**: LLM 为每件推荐商品生成自然语言推荐理由。

**任务 P4-R2: 推荐记忆**
- `UserPreference` 事实追踪 `liked_categories`、`price_sensitivity`、`last_purchased_category`。
- 推荐结果按用户缓存于 Redis 1 小时，减少重复 LLM 调用。

**任务 P4-R3: 反馈闭环**
- 用户可对推荐回复 "我喜欢这个" / "不感兴趣"。这些信号更新 `UserPreference` 并记录用于未来模型训练。

### 2.4 A/B 测试框架 (M11)

**任务 P4-A1: 实验 Schema**
- 新表: `Experiment`、`ExperimentVariant`、`ExperimentAssignment`。
- 变体可在以下维度不同:
  - system prompt 版本
  - LLM 模型（`qwen-turbo` vs `qwen-plus`）
  - retrieval top-k 或 reranker 开关

**任务 P4-A2: 分配逻辑**
- 新增模块: `app/experiments/assigner.py`。
- 确定性分配: hash(`user_id + experiment_id`) 对变体数取模。
- 同一用户跨会话分配结果保持一致。

**任务 P4-A3: 指标与分析**
- 追踪每变体指标:
  - 人工转接率
  - 平均 confidence score
  - 对话长度
  - 隐式满意度（2 轮内无追加提问视为满意）
- Admin API: `GET /api/v1/admin/experiments/{id}/results` 返回统计数据与 chi-squared 显著性指示。

**任务 P4-A4: B端 实验 UI**
- Admin Dashboard 新增 "实验" Tab。
- 创建实验、定义变体、启动/暂停、查看结果。

### 2.5 在线评估与自动告警 (M11–M12)

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

### 2.6 B端 高级数据分析 (M12)

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
| 图片上传 API & UI | `app/api/v1/chat.py`、`frontend/src/apps/customer/components/ChatInput.tsx` |
| VLM client | `app/multimodal/vlm_client.py` |
| 多模态 assistant subgraph | `app/graph/multimodal.py` |
| ComplaintAgent | `app/agents/complaint.py` |
| 投诉工单系统 | `app/models/complaint.py`、`app/tasks/complaint_tasks.py` |
| RecommendationAgent | `app/agents/recommendation.py` |
| A/B 测试框架 | `app/experiments/` |
| 在线评估 pipeline | `app/evaluation/online.py` |
| 自动告警任务 | `app/tasks/quality_alert_tasks.py` |
| 高级数据分析 UI | `frontend/src/apps/admin/pages/AnalyticsV2.tsx` |

---

## 4. 验收标准

### 多模态
- [ ] 图片上传端到端处理耗时 <3s（不含网络）。
- [ ] VLM 日配额强制执行生效；超配额时优雅降级为纯文本提示。
- [ ] 90% 的上传图片能被正确描述，且描述与后续 Agent 处理相关。

### ComplaintAgent
- [ ] 启动投诉意图的用户中，表单完成率 ≥75%。
- [ ] 表单完成后 10 秒内在 B端 可见工单。

### RecommendationAgent
- [ ] 推荐 CTR（点击或加购）相较 "随机有货商品" 基线提升 >20%。
- [ ] 推荐解释经人工评估，≥80% 被判定为连贯合理。

### A/B 测试
- [ ] 可在 B端 UI 中完成包含 2 个 prompt 变体的实验创建、启动与分析。
- [ ] 用户分配稳定（同一用户反复访问获得同一变体）。

### 在线评估
- [ ] 质量下降 15% 后 1 小时内触发告警。
- [ ] 告警在 ≥70% 的事故中正确识别出 top 2 劣化意图。

---

## 5. 风险与依赖

| 风险 | 发生概率 | 缓解措施 |
|------|----------|----------|
| VLM 推理过慢或成本过高 | 中 | 积极压缩图片；1000/天硬配额；降级为纯文本模式 |
| RecommendationAgent 行为数据不足 | 中 | 先从简单向量相似度 + 显式偏好事实做起；数据量足够后再引入协同过滤 |
| A/B 测试样本不足达不到显著性 | 中 | 仅在高流量意图上跑实验；低流量意图接受方向性信号 |
| ComplaintAgent 反而增加人工工作量 | 低 | 明确升级规则；自动分类与预填表单减少客服处理时间 |

### 依赖项
- 第三阶段记忆系统已上线（推荐依赖用户历史）。
- 第一阶段可观测性已成熟（A/B 分析依赖干净的事件日志）。
- 商品目录维护流程已建立（推荐需要及时库存数据）。

---

## 6. Agent 相关重点

第四阶段代表 Agent 平台的**打磨与规模化**。

### 6.1 多模态作为 Router 预处理步骤
VLM 不被视为独立 Agent，而是 graph 中的**预处理步骤**，将视觉输入转化为结构化文本。这保持了现有 Agent 分类的整洁: 所有 Agent 仍消费文本，VLM 是多模态适配器。

### 6.2 推荐作为混合系统
纯 LLM 推荐既昂贵又常幻想库存。`RecommendationAgent` 明确**不是**纯 LLM Agent，而是 retrieval + filtering + explanation pipeline，与项目的 RAG-first 理念一致。

### 6.3 持续改进文化
到第四阶段末，团队应建立:
- 每季度更新的 Golden Dataset。
- 始终至少有一个运行中的 A/B 实验。
- 每周 review LangSmith trace，聚焦 confidence 最低的会话。
- 自动质量告警防止回退。

这完成了闭环: **度量 → 构建 → 记忆 → 优化**。
