# Prompt 评估与测试方法论

Prompt Engineering 不是一次性写作任务，而是需要**持续度量、回归测试和版本控制**的工程实践。参考 OpenAI Evals、Anthropic 内部测试协议以及 Google Cloud 的生成式 AI 评估指南，建议建立以下评估体系：

## 建立 Golden Dataset（基准测试集）

- 为每个核心 Agent 维护 50~200 条覆盖典型场景和边界 case 的测试用例
- 测试集应包含：用户输入、期望意图/槽位、期望回答模式、禁止行为清单
- 每次 Prompt 变更前，必须在 Golden Dataset 上运行回归测试，确保无退化

## LLM-as-Judge 自动评分

- 使用独立的轻量模型（如 `qwen-turbo`）作为评判器，对 Agent 输出进行多维度评分
- 评分维度示例：
  - **准确性（Accuracy）**：回答是否与事实/检索结果一致
  - **遵循度（Instruction Following）**：是否严格遵守 System Prompt 中的格式和规则
  - **安全性（Safety）**：是否泄露敏感信息或产生有害内容
  - **语气一致性（Tone）**：是否符合电商客服的专业友好标准
- 推荐使用结构化输出绑定评分 Schema，实现可批量运行的自动化评判

## A/B 实验与指标关联

- 每个 Prompt 变体必须关联明确的北极星指标：意图准确率、RAG 幻觉率、CSAT、人工接管率
- 实验周期至少 7 天或 500 次对话，确保统计显著性
- 实验结果需记录到 `Experiment` + `GraphExecutionLog` 中，支持按 Prompt 版本追溯指标变化

## 人工抽检与反馈闭环

- 每周从生产环境中抽检 5% 的对话记录，由业务专家标注质量等级
- 建立"差评/低置信度对话 → Prompt 根因分析 → 测试用例补充 → Prompt 迭代"的闭环
- 将人工标注结果反向注入 Golden Dataset，持续扩充边界 case
