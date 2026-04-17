# 附录：参考与资源

## 关键文件清单

### Prompt 核心管理

| 文件 | 说明 |
|------|------|
| `app/agents/base.py` | Agent 基类，含 `_load_config()`、记忆注入 |
| `app/agents/config_loader.py` | Prompt 配置加载器（Redis + DB） |
| `app/models/memory.py` | `AgentConfig`、`AgentConfigAuditLog` 模型 |
| `app/api/v1/admin/agent_config.py` | Prompt 管理 API |

### Agent Prompt 定义

| 文件 | 说明 |
|------|------|
| `app/agents/order.py` | `ORDER_SYSTEM_PROMPT` |
| `app/agents/policy.py` | `POLICY_SYSTEM_PROMPT` |
| `app/agents/product.py` | `PRODUCT_SYSTEM_PROMPT` |
| `app/agents/cart.py` | `CART_SYSTEM_PROMPT` |
| `app/agents/logistics.py` | `LOGISTICS_SYSTEM_PROMPT` |
| `app/agents/account.py` | `ACCOUNT_SYSTEM_PROMPT` |
| `app/agents/payment.py` | `PAYMENT_SYSTEM_PROMPT` |
| `app/agents/complaint.py` | `COMPLAINT_SYSTEM_PROMPT`（Structured JSON） |

### Prompt 工程组件

| 文件 | 说明 |
|------|------|
| `app/intent/classifier.py` | 意图分类 Prompt + Function Calling |
| `app/retrieval/rewriter.py` | 查询重写 / 多查询扩展 Prompt |
| `app/confidence/signals.py` | LLM 置信度自评估 Prompt |
| `app/memory/extractor.py` | 事实抽取 Prompt |
| `app/memory/summarizer.py` | 会话摘要 Prompt |
| `app/graph/nodes.py` | `synthesis_node` 融合 Prompt |

### 实验系统

| 文件 | 说明 |
|------|------|
| `app/models/experiment.py` | `ExperimentVariant.system_prompt` |
| `app/services/experiment_assigner.py` | 确定性流量分配器 |
| `app/api/v1/admin/experiments.py` | 实验管理 API |

## 推荐学习资源

### 官方文档

| 资源 | 链接 | 说明 |
|------|------|------|
| OpenAI Prompt Engineering Guide | https://platform.openai.com/docs/guides/prompt-engineering | OpenAI 官方提示工程指南 |
| OpenAI Structured Outputs | https://platform.openai.com/docs/guides/structured-outputs | JSON Mode / Function Calling 官方文档 |
| Anthropic Prompt Engineering | https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering | Claude 官方提示工程最佳实践 |
| Anthropic Interactive Tutorial | https://github.com/anthropics/prompt-eng-interactive-tutorial | 交互式 Prompt Engineering 教程 |
| Google Cloud Prompt Engineering | https://cloud.google.com/discover/what-is-prompt-engineering | Google Cloud 权威定义与原则 |

### 综合学习资源

| 资源 | 链接 | 说明 |
|------|------|------|
| PromptingGuide.ai (DAIR.AI) | https://www.promptingguide.ai | 最全面的开源 Prompt Engineering 指南 |
| Learn Prompting | https://learnprompting.org | 免费的 Prompt Engineering 课程 |
| OpenAI Cookbook | https://github.com/openai/openai-cookbook | 大量实战代码示例 |
| LangChain Prompt Templates | https://python.langchain.com/docs/concepts/prompt_templates/ | 工程化 Prompt 管理 |

### 学术论文

- **Chain-of-Thought Prompting Elicits Reasoning in LLMs** (Wei et al., 2022)
- **ReAct: Synergizing Reasoning and Acting in Language Models** (Yao et al., 2023)
- **Tree of Thoughts: Deliberate Problem Solving with Large Language Models** (Yao et al., 2023)

## 引用来源

- [^1]: Google Cloud. "What is prompt engineering?" https://cloud.google.com/discover/what-is-prompt-engineering
- [^2]: OpenAI. "Prompt engineering." https://platform.openai.com/docs/guides/prompt-engineering
- [^3]: Anthropic. "Prompt engineering overview." https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering
- [^4]: DAIR.AI. "PromptingGuide.ai." https://www.promptingguide.ai
- [^5]: Wei, J., et al. "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models." NeurIPS 2022.
- [^6]: Yao, S., et al. "ReAct: Synergizing Reasoning and Acting in Language Models." ICLR 2023.
- [^7]: Kojima, T., et al. "Large Language Models are Zero-Shot Reasoners." NeurIPS 2022.
