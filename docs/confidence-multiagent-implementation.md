# 置信度驱动人工接管 + 多 Agent 协作架构 - 实现总结

## 概述

本项目实现了基于置信度评估的智能人工接管机制，并将单体 Agent 重构为职责分明的多 Agent 协作架构。

## 已完成功能

### 1. 多 Agent 架构 (Tasks 5-10)

#### BaseAgent 抽象类 (`app/agents/base.py`)
- 泛型设计，支持依赖注入
- 统一的 `AgentResult` 返回格式
- 包含响应、状态更新、置信度分数和转人工标志

#### RouterAgent (`app/agents/router.py`)
- 意图识别：ORDER, POLICY, REFUND, OTHER
- 快速意图检查用于直接响应（问候语等）
- 将请求路由到相应的 Specialist Agent

#### PolicyAgent (`app/agents/policy.py`)
- 政策咨询专家
- RAG 检索增强回答
- 运费计算、退货规则查询

#### OrderAgent (`app/agents/order.py`)
- 订单查询和处理
- 退货申请流程
- 退货资格检查

#### SupervisorAgent (`app/agents/supervisor.py`)
- 协调所有 Specialist Agent
- 置信度评估决策
- 人工接管判断

#### 工作流集成 (`app/graph/workflow.py`)
- LangGraph Multi-Agent 工作流
- Supervisor 节点统一协调
- Redis 状态持久化

### 2. 置信度评估系统 (Tasks 2-4)

#### 信号计算 (`app/confidence/signals.py`)
- **RAGSignal**: 基于检索质量（相似度、覆盖率）
- **LLMSignal**: LLM 自我评估，带重试机制
- **EmotionSignal**: 用户情感检测（正面/负面/紧急）
- **ConfidenceSignals**: 统一信号计算和加权

#### 配置管理 (`app/core/config.py`)
- `ConfidenceSettings` 嵌套配置
- 支持环境变量 `CONFIDENCE__THRESHOLD=0.7`
- 可配置的阈值、权重、超时

#### 数据库模型扩展 (`app/models/audit.py`)
- `AuditTriggerType` 枚举：RISK, CONFIDENCE, MANUAL
- `confidence_metadata` JSON 字段
- 触发类型索引

### 3. 管理员 API 扩展 (Task 11)

#### 扩展端点 (`app/api/v1/admin.py`)
- `GET /admin/tasks` - 获取待审核任务列表
- `GET /admin/confidence-tasks` - 获取置信度触发的任务
- `GET /admin/tasks-all` - 获取任务统计
- `POST /admin/resume/{audit_log_id}` - 管理员决策接口

#### 消息卡片扩展 (`app/models/message.py`)
- `CONFIDENCE_CARD` - 置信度信息卡片
- `TRANSFER_CARD` - 转人工信息卡片

### 4. 前端展示支持 (Task 12)

#### Chat API 更新 (`app/api/v1/chat.py`)
- SSE 流式响应包含置信度元数据
- 转人工时发送 transfer_card

#### 工具函数 (`app/api/v1/chat_utils.py`)
- `create_confidence_message()` - 生成置信度卡片
- `create_transfer_message()` - 生成转人工卡片
- `create_stream_metadata_message()` - 生成元数据消息

#### 响应模型 (`app/api/v1/schemas.py`)
- `ChatResponseMetadata` - 完整的响应元数据
- `ConfidenceCardContent` - 置信度卡片内容
- `TransferCardContent` - 转人工卡片内容

### 5. 测试覆盖 (Tasks 13-14)

#### 单元测试
- `test/agents/test_base.py` - BaseAgent 测试 (5 tests)
- `test/agents/test_router.py` - RouterAgent 测试 (6 tests)
- `test/agents/test_policy.py` - PolicyAgent 测试 (5 tests)
- `test/agents/test_order.py` - OrderAgent 测试 (9 tests)
- `test/agents/test_supervisor.py` - SupervisorAgent 测试 (5 tests)
- `tests/test_chat_utils.py` - Chat 工具函数测试 (16 tests)

#### 集成测试
- `test/integration/test_multi_agent.py` - 多 Agent 协作测试 (18 tests)
- `test/integration/test_confidence_workflow.py` - 置信度工作流测试 (16 tests)
- `test/integration/test_chat_api.py` - Chat API 测试 (11 tests)

**总计: 86 个测试通过**

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        Client (Frontend)                     │
└───────────────────────┬─────────────────────────────────────┘
                        │ SSE Stream
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                      Chat API (FastAPI)                      │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  POST /chat  ->  event_generator()                   │  │
│  │  - Returns tokens stream                             │  │
│  │  - Ends with metadata (confidence, transfer info)    │  │
│  └───────────────────────────────────────────────────────┘  │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              LangGraph Workflow (Multi-Agent)                │
│                                                              │
│   ┌──────────────┐    ┌─────────────────────────────────┐   │
│   │   START      │───▶│     Supervisor Node             │   │
│   └──────────────┘    │  - Route Intent                 │   │
│                       │  - Delegate to Agent            │   │
│                       │  - Evaluate Confidence          │   │
│                       │  - Determine Human Transfer     │   │
│                       └──────────────┬────────────────────┘   │
│                                      │                       │
│         ┌────────────────────────────┼───────────────────┐   │
│         │                            │                   │   │
│         ▼                            ▼                   ▼   │
│   ┌──────────┐               ┌──────────┐        ┌──────────┐│
│   │  Order   │               │  Policy  │        │  Router  ││
│   │  Agent   │               │  Agent   │        │  Agent   ││
│   └──────────┘               └──────────┘        └──────────┘│
│                                                              │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              Confidence Evaluation System                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  RAG Signal │  │  LLM Signal │  │  Emotion Signal     │  │
│  │  - Quality  │  │  - Self-eval│  │  - Sentiment        │  │
│  │  - Coverage │  │  - Retries  │  │  - Urgency          │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                     │             │
│         └────────────────┼─────────────────────┘             │
│                          ▼                                   │
│               ┌─────────────────────┐                        │
│               │   Weighted Score    │                        │
│               │   + Audit Level     │                        │
│               └─────────────────────┘                        │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              Admin API + Audit System                        │
│  - Confidence-triggered audit tasks                         │
│  - Manual review interface                                   │
│  - WebSocket status updates                                  │
└─────────────────────────────────────────────────────────────┘
```

## 配置说明

### 环境变量

```bash
# 置信度阈值配置
CONFIDENCE__THRESHOLD=0.7
CONFIDENCE__HIGH_THRESHOLD=0.8
CONFIDENCE__MEDIUM_THRESHOLD=0.5
CONFIDENCE__LOW_THRESHOLD=0.3

# 信号权重配置
CONFIDENCE__RAG_WEIGHT=0.3
CONFIDENCE__LLM_WEIGHT=0.5
CONFIDENCE__EMOTION_WEIGHT=0.2

# 超时和重试
CONFIDENCE__CALCULATION_TIMEOUT_SECONDS=3.0
CONFIDENCE__LLM_PARSE_MAX_RETRIES=3

# 成本优化
CONFIDENCE__EVALUATION_MODEL=qwen-turbo
CONFIDENCE__ENABLE_CACHE=true
```

## API 使用示例

### 聊天请求 (SSE 流)

```bash
curl -N -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "订单 SN20240001 状态", "thread_id": "thread_001"}' \
  http://localhost:8000/api/v1/chat
```

响应流：
```
data: {"token": "订单"}
data: {"token": "状态"}
data: {"token": "：已发货"}
data: {"type": "metadata", "confidence_score": 0.85, "confidence_level": "high", "needs_human_transfer": false}
data: [DONE]
```

### 获取待审核任务

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/v1/admin/confidence-tasks
```

## 后续优化建议

1. **前端组件开发**
   - 置信度展示组件（进度条形式）
   - 转人工提示卡片
   - 实时审核状态显示

2. **监控与日志**
   - 置信度分数分布统计
   - 人工接管原因分析
   - Agent 响应时间监控

3. **模型优化**
   - 基于历史数据的权重调优
   - LLM 评估 prompt 优化
   - 情感词典扩展

## 文件清单

### 核心实现
- `app/agents/base.py`
- `app/agents/router.py`
- `app/agents/policy.py`
- `app/agents/order.py`
- `app/agents/supervisor.py`
- `app/confidence/signals.py`
- `app/graph/workflow.py`
- `app/api/v1/chat.py`
- `app/api/v1/chat_utils.py`
- `app/api/v1/admin.py`
- `app/api/v1/schemas.py`

### 测试
- `test/agents/test_*.py` (5 files, 25 tests)
- `test/integration/test_*.py` (3 files, 45 tests)
- `tests/test_chat_utils.py` (16 tests)

---

*实现完成日期: 2025-01-17*
*总测试数: 86 个通过*
