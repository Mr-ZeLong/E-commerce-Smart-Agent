# E-commerce Smart Agent

E-commerce Smart Agent 是一个先进的全栈智能客服系统，旨在通过结合大型语言模型（LLM）和人工审核流程，为电商平台提供高效、精准、安全的客户服务。

## 主要特性

- **智能问答**：订单查询、政策咨询、商品查询、购物车管理
- **Supervisor 多 Agent 编排**：基于 LangGraph 的串行/并行智能调度
- **结构化记忆系统**：PostgreSQL 用户画像/偏好/事实 + Qdrant 向量对话记忆
- **Agent 配置中心**：B 端热重载、路由规则、审计日志与 A/B 实验
- **智能风控与人工审核**：按金额分级风控，自动转交高风险请求
- **知识库管理**：支持 PDF/Markdown 上传、Embedding 检索与同步
- **可观测性**：OpenTelemetry 全链路追踪

## 快速开始

```bash
./start.sh
```

启动后访问：
- API: http://localhost:8000
- API 文档: http://localhost:8000/docs
- C端用户界面: http://localhost:8000/app
- B端管理后台: http://localhost:8000/admin

## 文档

- [快速开始](./docs/tutorials/quickstart.md)
- [系统架构](./docs/explanation/architecture/)
- [Prompt Engineering 指南](./docs/explanation/prompt-engineering/)
- [Context Engineering 指南](./docs/explanation/context-engineering/)
- [环境变量参考](./docs/reference/environment-variables.md)
- [常用命令速查表](./docs/reference/command-cheatsheet.md)

## 截图

### 订单查询
<img src="assets/image/order_query.png" width="600" alt="订单查询" />

### 退货申请
<img src="assets/image/refund_apply.png" width="600" alt="退货申请" />

### 政策咨询
<img src="assets/image/policy_ask.png" width="600" alt="政策咨询" />

### 意图识别
<img src="assets/image/intent_detect.png" width="600" alt="意图识别" />

### 非法查询他人订单
<img src="assets/image/illegal_query.png" width="600" alt="非法查询" />
