# 下一阶段目标与任务

## 总体目标

在 **Q2 季度内**，将本系统的 Prompt Engineering 能力从 "可用" 提升到 "可度量、可实验、可快速迭代" 的水平，核心指标：

- 意图识别准确率 ≥ 92%
- RAG 回答幻觉率 ≤ 5%
- 人工接管率 ≤ 15%
- Prompt A/B 实验覆盖全部核心 Agent

## 任务分解

### 任务 1：激活 A/B 实验的 Prompt 变体能力

**优先级**：P0  
**负责人**：后端 Agent 团队  
**验收标准**：
- [ ] `ExperimentAssigner.assign()` 返回类型从 `str | None`（variant name）改为 `int | None`（variant id）
- [ ] `AgentState` / `make_agent_state()` 增加 `experiment_variant_id: int | None` 字段
- [ ] `chat.py` 请求入口处（或 graph 入口节点中）获取用户对应的实验 `variant_id` 并写入 `AgentState`
- [ ] `BaseAgent` 新增 `async def _resolve_experiment_prompt(self, state: AgentState) -> str | None` 方法；各 Agent 子类在 `process()` 中调用该方法并将结果写入 `self._dynamic_system_prompt`
- [ ] 补充单元测试：验证实验变体 prompt 的生效逻辑

### 任务 2：引入 Prompt 模板变量系统

**优先级**：P1  
**负责人**：后端 Agent 团队 + B 端前端  
**验收标准**：
- [ ] 在 `AgentConfig.system_prompt` 中支持 `{{variable}}` 语法
- [ ] 定义标准变量库：`{{company_name}}`、`{{current_date}}`、`{{user_membership_level}}`
- [ ] `BaseAgent._create_messages()` 中自动替换变量
- [ ] Admin 配置页面增加变量提示和实时预览

### 任务 3：建立 Few-shot 示例库（Intent + Complaint）

**优先级**：P1  
**负责人**：算法/数据团队  
**验收标准**：
- [ ] 收集并标注 50+ 条意图分类边界 case
- [ ] 将示例按 Agent / 场景分类存储（建议新建 `data/prompt_examples/`）
- [ ] `IntentClassifier` 支持动态注入 top-k 相似示例
- [ ] 评估：加入 few-shot 后意图准确率提升 ≥ 3%

### 任务 4：增强 Prompt 版本管理与 Diff 能力

**优先级**：P1  
**负责人**：后端 + B 端前端  
**现状说明**：`AgentConfigAuditLog` 已经以字段级 diff 的形式记录了所有历史变更（`field_name`, `old_value`, `new_value`），但缺少**快照版本**机制和从审计日志快速重建完整 Prompt 快照的能力，目前回滚只能替换 `previous_system_prompt`（即上一版）。

**验收标准**：
- [ ] 新增 `agent_config_versions` 表（或扩展审计日志），存储每次变更后的完整 Prompt 快照
- [ ] Admin API 新增 `GET /admin/agents/{agent_name}/versions` 获取所有历史快照版本
- [ ] Admin 前端新增 Prompt 版本对比（diff）页面
- [ ] 支持回滚到任意历史版本

### 任务 5：优化 System / Human Message 职责边界

**优先级**：P2  
**负责人**：后端 Agent 团队  
**验收标准**：
- [ ] 所有 Agent 的 `_create_messages()` 中，角色定义必须通过 `SystemMessage` 发送
- [ ] 动态上下文（检索结果、记忆、用户问题）通过 `HumanMessage` 发送
- [ ] 新增 `BaseAgent` 的 `_build_system_prompt()` 和 `_build_user_prompt()` 方法，规范拆分逻辑
- [ ] 修复 `ProductAgent` 中直接拼接 prompt 到 `HumanMessage` 的问题

### 任务 6：RAG Prompt 幻觉抑制专项

**优先级**：P1  
**负责人**：RAG + Agent 团队  
**验收标准**：
- [ ] `PolicyAgent` System Prompt 增加 "引用标注" 要求
- [ ] 在检索结果注入前增加相关性过滤（score < 0.5 的 chunk 不注入）
- [ ] 引入 Self-RAG 模式：LLM 先判断检索结果是否充分，再决定生成或拒绝回答
- [ ] 评估：RAG 回答幻觉率从当前估计的 ~10% 降至 ≤ 5%

### 任务 7：建立 Prompt 效果评估体系

**优先级**：P2  
**负责人**：算法 + 数据团队  
**验收标准**：
- [ ] 每次 Prompt 变更自动关联 `AgentConfigAuditLog` 与 `GraphExecutionLog`
- [ ] 建立 Prompt 版本 → 置信度分数 → 人工接管率的关联看板
- [ ] 每月输出《Prompt 优化效果报告》，量化评估每次变更的影响

### 任务 8：多意图独立判定的 LLM 辅助

**优先级**：P2  
**负责人**：后端 Agent 团队  
**验收标准**：
- [ ] 在 `multi_intent.py` 中增加 LLM 辅助判定逻辑
- [ ] 当硬编码规则不确定时，调用轻量模型进行独立性判断
- [ ] 记录 LLM 判定结果与人工标注的一致性，持续优化规则

## 时间规划

| 周次 | 重点任务 | 里程碑 |
|------|----------|--------|
| W1-W2 | 任务 1（A/B 实验激活）+ 任务 5（消息边界优化） | Prompt 变体可生效 |
| W3-W4 | 任务 2（模板变量）+ 任务 4（版本 Diff） | Admin 配置中心升级完成 |
| W5-W6 | 任务 3（Few-shot 库）+ 任务 6（Self-RAG） | 意图准确率、RAG 质量提升 |
| W7-W8 | 任务 7（效果评估体系）+ 任务 8（多意图 LLM 辅助）+ 全链路测试 | 评估看板上线上报 |
