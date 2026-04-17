# 常见反模式与避免方法

| 反模式 | 表现 | 避免方法 |
|--------|------|----------|
| **Prompt 稀释（Prompt Dilution）** | System Prompt 过长或用户请求被大量上下文淹没 | 控制 Prompt 长度，使用摘要和检索 |
| **模糊指令（Vague Instructions）** | "写得好一点"、"分析一下" | 使用可衡量的标准（字数、格式、角度） |
| **示例不一致（Inconsistent Examples）** | Few-shot 示例的输出格式不统一 | 建立示例模板，严格校验一致性 |
| **过度假设（Over-assumption）** | 假设模型知道专有名词或内部背景 | 在 Prompt 中提供必要的定义和上下文 |
| **幻觉诱导（Hallucination Induction）** | 要求模型回答超出其知识边界的问题而不提供检索 | 明确允许模型说"不知道"，结合 RAG |
| **角色越狱风险（Jailbreak Vulnerability）** | 用户通过角色扮演绕过安全限制 | 在 System Prompt 中强化核心安全策略 |
| **忽视 Token 限制** | 输入超过 Context Window 导致截断 | 监控 Token 使用量，设计分段处理策略 |
| **没有错误处理** | 假设模型每次都能输出完美 JSON | 始终对结构化输出做校验和重试 |
| **链式调用无边界** | Agent 无限循环调用工具 | 设置最大步数、超时、人工介入机制 |
| **System/User 边界模糊** | 将角色定义塞入 HumanMessage | 严格分离 SystemMessage 和 HumanMessage 职责 |
