# E-commerce Smart Agent v4.0 系统架构图

## 1. 整体架构图

```mermaid
flowchart TB
    subgraph Frontend["🖥️ 前端层 (React + TypeScript)"]
        CUI["👤 Customer App<br/>用户聊天界面<br/>React 18 + Vite"]
        ADM["🛡️ Admin Dashboard<br/>管理员工作台<br/>React 18 + Vite"]
    end

    subgraph APILayer["📡 API 层 (FastAPI)"]
        API["FastAPI Application<br/>Port: 8000"]

        subgraph Routers["🔀 路由模块"]
            AUTH["/auth<br/>登录认证"]
            CHAT["/chat<br/>聊天接口 (SSE)"]
            WS["/ws<br/>WebSocket"]
            ADMIN["/admin<br/>管理员 API"]
            STATUS["/status<br/>状态查询"]
        end
    end

    subgraph CoreLayer["⚙️ 核心层"]
        CONFIG["Config<br/>Pydantic Settings"]
        DB["Database<br/>SQLModel + AsyncPG"]
        SEC["Security<br/>JWT Auth"]
    end

    subgraph AgentLayer["🤖 Agent 层 (LangGraph)"]
        GRAPH["StateGraph<br/>工作流编排"]

        subgraph Nodes["📍 节点定义"]
            INTENT["Intent Router v2.0<br/>IntentRouterAgent<br/>分层意图识别"]
            RETRIEVE["Retrieve<br/>知识检索 (RAG)"]
            QUERY["Query Order<br/>订单查询"]
            REFUND["Handle Refund<br/>退货处理"]
            AUDIT["Check Eligibility<br/>资格审核"]
            GEN["Generate<br/>回复生成"]
        end

        subgraph State["📦 状态定义"]
            AGENT_STATE["AgentState<br/>TypedDict"]
        end
    end

    subgraph ServiceLayer["🛠️ 服务层"]
        REFUND_SVC["Refund Service<br/>退货业务逻辑"]
        RULES["Refund Rules<br/>退货规则引擎"]
    end

    subgraph TaskLayer["⏳ 任务层 (Celery)"]
        CELERY["Celery Worker<br/>异步任务队列"]
        TASKS["Refund Tasks<br/>- 发送短信<br/>- 处理退款<br/>- 通知管理员"]
    end

    subgraph WebSocketLayer["🔌 WebSocket 层"]
        WS_MGR["Connection Manager<br/>连接管理器"]
    end

    subgraph DataLayer["💾 数据层"]
        subgraph PostgreSQL["🐘 PostgreSQL + pgvector"]
            TBL_USERS[(users<br/>用户表)]
            TBL_ORDERS[(orders<br/>订单表)]
            TBL_REFUNDS[(refund_applications<br/>退款申请表)]
            TBL_AUDIT[(audit_logs<br/>审计日志表)]
            TBL_KNOWLEDGE[(knowledge_chunks<br/>知识库表)]
            TBL_MSG[(message_cards<br/>消息卡片表)]
        end

        subgraph Redis["🔴 Redis"]
            REDIS_CACHE["Session Cache<br/>状态缓存"]
            REDIS_CELERY["Celery Broker<br/>任务队列"]
            REDIS_CHECK["LangGraph Checkpoint<br/>检查点"]
        end
    end

    subgraph External["🌐 外部服务"]
        LLM["LLM API<br/>通义千问/Qwen"]
        EMBED["Embedding API<br/>文本嵌入"]
    end

    %% 连接关系
    CUI <-->|"HTTP/SSE"| API
    ADM <-->|"HTTP"| API

    API --> Routers
    Routers --> CoreLayer
    Routers --> AgentLayer
    Routers --> ServiceLayer
    Routers --> WebSocketLayer

    CHAT --> GRAPH
    ADMIN --> REFUND_SVC
    WS --> WS_MGR

    GRAPH --> Nodes
    Nodes --> State
    INTENT --> RETRIEVE & QUERY & REFUND
    REFUND --> AUDIT
    QUERY --> GEN
    RETRIEVE --> GEN
    AUDIT --> GEN

    REFUND_SVC --> RULES
    REFUND_SVC --> DB

    AUDIT -->|"高风险触发"| CELERY
    CELERY --> TASKS
    TASKS --> DB

    Nodes <-->|"Embedding/LLM"| External

    DB --> PostgreSQL
    WS_MGR --> REDIS_CACHE
    CELERY --> REDIS_CELERY
    GRAPH --> REDIS_CHECK
```

## 2. LangGraph 工作流详解

```mermaid
flowchart LR
    START([START]) --> INTENT["🎯 Intent Router<br/>意图识别"]

    INTENT -->|"ORDER"| QUERY["📦 Query Order<br/>订单查询"]
    INTENT -->|"POLICY"| RETRIEVE["📚 Retrieve<br/>知识检索"]
    INTENT -->|"REFUND"| REFUND_NODE["🔄 Handle Refund<br/>退货处理"]
    INTENT -->|"OTHER"| GENERATE["💬 Generate<br/>生成回复"]

    QUERY --> GENERATE
    RETRIEVE --> GENERATE

    REFUND_NODE --> CHECK["⚖️ Check Eligibility<br/>资格审核"]

    CHECK -->|"自动通过<br/>低风险"| GENERATE
    CHECK -->|"需要审核<br/>中高风险"| END_AUDIT([END<br/>等待人工审核])

    GENERATE --> END_NORMAL([END])

    style CHECK fill:#ffeb3b,stroke:#f57f17
    style END_AUDIT fill:#ff9800,stroke:#e65100
```

## 3. 数据模型关系图

```mermaid
erDiagram
    users ||--o{ orders : "拥有"
    users ||--o{ refund_applications : "申请"
    users ||--o{ audit_logs : "触发"
    orders ||--o{ refund_applications : "关联"
    orders ||--o{ audit_logs : "关联"
    refund_applications ||--o{ audit_logs : "触发"

    users {
        int id PK
        string username UK
        string password_hash
        string email UK
        string full_name
        string phone
        boolean is_admin
        boolean is_active
        datetime created_at
        datetime updated_at
    }

    orders {
        int id PK
        string order_sn UK
        int user_id FK
        string status
        decimal total_amount
        json items
        string tracking_number
        string shipping_address
        datetime created_at
        datetime updated_at
    }

    refund_applications {
        int id PK
        int order_id FK
        int user_id FK
        string status
        string reason_category
        text reason_detail
        decimal refund_amount
        text admin_note
        int reviewed_by
        datetime reviewed_at
        datetime created_at
        datetime updated_at
    }

    audit_logs {
        int id PK
        string thread_id
        int order_id FK
        int refund_application_id FK
        int user_id FK
        text trigger_reason
        string risk_level
        string action
        int admin_id
        text admin_comment
        json context_snapshot
        json decision_metadata
        datetime created_at
        datetime reviewed_at
        datetime updated_at
    }

    knowledge_chunks {
        int id PK
        string source
        text content
        vector embedding
        boolean is_active
        datetime created_at
    }

    message_cards {
        int id PK
        string thread_id
        string message_type
        string status
        json content
        string sender_type
        int sender_id
        int receiver_id
        datetime created_at
    }
```

## 4. 系统交互流程图

### 4.1 订单查询流程

```mermaid
sequenceDiagram
    actor User
    participant CUI as Customer UI
    participant API as FastAPI
    participant Graph as LangGraph
    participant Node as Query Node
    participant DB as PostgreSQL
    participant LLM as Qwen LLM

    User->>CUI: "查询我的订单"
    CUI->>API: POST /chat (SSE)
    API->>Graph: astream_events()
    Graph->>Graph: intent_router()
    Graph->>Node: query_order()
    Node->>DB: SELECT orders
    DB-->>Node: Order Data
    Node-->>Graph: {order_data, context}
    Graph->>Graph: generate()
    Graph->>LLM: 生成回复
    LLM-->>Graph: 流式响应
    Graph-->>API: SSE Events
    API-->>CUI: 流式显示
    CUI-->>User: 订单信息
```

### 4.2 退货申请 + 风控审核流程

```mermaid
sequenceDiagram
    actor User
    actor Admin
    participant CUI as Customer UI
    participant ADM as Admin Dashboard
    participant API as FastAPI
    participant Graph as LangGraph
    participant Celery as Celery Worker
    participant WS as WebSocket
    participant DB as PostgreSQL

    User->>CUI: "我要退货 订单SN20240003"
    CUI->>API: POST /chat
    API->>Graph: 启动工作流
    Graph->>Graph: intent_router → REFUND
    Graph->>Graph: handle_refund()
    Graph->>Graph: check_refund_eligibility()

    alt 低风险 (< ¥500)
        Graph->>DB: UPDATE status=APPROVED
        Graph-->>CUI: 自动审核通过
    else 中高风险 (≥ ¥500)
        Graph->>DB: INSERT audit_logs
        Graph->>Celery: notify_admin_audit
        Graph->>WS: 实时通知用户
        WS-->>CUI: 显示审核中状态
        Graph-->>CUI: 等待人工审核

        Celery->>ADM: 推送任务通知
        Admin->>ADM: 查看任务队列
        ADM->>API: GET /admin/tasks
        API-->>ADM: 待审核列表

        Admin->>ADM: 点击"批准"
        ADM->>API: POST /admin/resume/{id}
        API->>DB: UPDATE audit_logs
        API->>DB: UPDATE refund_applications
        API->>Celery: process_refund_payment
        API->>Celery: send_refund_sms
        API->>WS: 通知状态变更
        WS-->>CUI: 审核结果通知
        CUI-->>User: 显示审核通过
    end
```

### 4.3 政策咨询 (RAG) 流程

```mermaid
sequenceDiagram
    actor User
    participant CUI as Customer UI
    participant API as FastAPI
    participant Graph as LangGraph
    participant Embed as Embedding Model
    participant DB as PostgreSQL
    participant LLM as Qwen LLM

    User->>CUI: "内衣可以退货吗？"
    CUI->>API: POST /chat
    API->>Graph: 启动工作流
    Graph->>Graph: intent_router → POLICY
    Graph->>Graph: retrieve()
    Graph->>Embed: aembed_query()
    Embed->>Embed: 生成查询向量
    Embed-->>Graph: query_vector
    Graph->>DB: SELECT ... ORDER BY distance
    DB-->>Graph: 相似文档片段
    Graph->>Graph: 过滤 (distance < 0.5)
    Graph->>Graph: generate()
    Graph->>LLM: Prompt + Context + Question
    LLM-->>Graph: 流式响应
    Graph-->>API: SSE Events
    API-->>CUI: 逐字显示回复
    CUI-->>User: 政策解答
```

## 5. 技术栈分层

```mermaid
flowchart TB
    subgraph Layer1["表示层"]
        F1["React 18 + TypeScript<br/>Vite + Tailwind CSS"]
    end

    subgraph Layer2["接入层"]
        A1["FastAPI<br/>Port 8000"]
        A2["WebSocket<br/>实时通信"]
        A3["JWT Auth<br/>身份认证"]
    end

    subgraph Layer3["业务层"]
        B1["LangGraph<br/>工作流引擎"]
        B2["意图识别<br/>Intent Router"]
        B3["RAG 检索<br/>语义搜索"]
        B4["退货服务<br/>Refund Service"]
    end

    subgraph Layer4["任务层"]
        T1["Celery<br/>异步任务队列"]
        T2["退款处理<br/>支付网关"]
        T3["短信通知<br/>SMS Gateway"]
    end

    subgraph Layer5["数据层"]
        D1["PostgreSQL<br/>关系型数据"]
        D2["pgvector<br/>向量检索"]
        D3["Redis<br/>缓存/会话"]
    end

    subgraph Layer6["外部层"]
        E1["通义千问<br/>Qwen LLM"]
        E2["Embedding<br/>文本向量化"]
    end

    Layer1 --> Layer2
    Layer2 --> Layer3
    Layer3 --> Layer4
    Layer3 --> Layer5
    Layer4 --> Layer5
    Layer3 --> Layer6
```

## 6. 项目文件结构

```
E-commerce-Smart-Agent/
├── 📄 README.md                    # 项目文档
├── 📄 pyproject.toml               # Python 项目配置 (uv)
├── 📄 docker-compose.yaml          # 容器编排配置
├── 📄 celery_worker.py             # Celery Worker 启动脚本
│
├── 📁 app/                         # 主应用目录
│   ├── 📄 main.py                  # FastAPI 应用入口
│   ├── 📄 celery_app.py            # Celery 配置
│   │
│   ├── 📁 api/v1/                  # API 路由层
│   │   ├── 📄 auth.py              # 认证接口 (登录)
│   │   ├── 📄 chat.py              # 聊天接口 (SSE 流式)
│   │   ├── 📄 admin.py             # 管理员接口
│   │   ├── 📄 status.py            # 状态查询接口
│   │   ├── 📄 websocket.py         # WebSocket 端点
│   │   └── 📄 schemas.py           # Pydantic 数据模型
│   │
│   ├── 📁 core/                    # 核心基础设施
│   │   ├── 📄 config.py            # 配置管理 (Pydantic Settings)
│   │   ├── 📄 database.py          # 数据库连接 (SQLModel)
│   │   └── 📄 security.py          # JWT 认证
│   │
│   ├── 📁 models/                  # 数据库模型 (SQLModel)
│   │   ├── 📄 user.py              # 用户表
│   │   ├── 📄 order.py             # 订单表
│   │   ├── 📄 refund.py            # 退款申请表
│   │   ├── 📄 audit.py             # 审计日志表
│   │   ├── 📄 knowledge.py         # 知识库表
│   │   └── 📄 message.py           # 消息卡片表
│   │
│   ├── 📁 graph/                   # LangGraph 核心逻辑
│   │   ├── 📄 workflow.py          # 工作流定义与编译
│   │   ├── 📄 state.py             # 状态定义 (TypedDict)
│   │   ├── 📄 nodes.py             # 节点函数 (6个节点)
│   │   └── 📄 tools.py             # 工具函数 (3个工具)
│   │
│   ├── 📁 agents/                  # Agent 实现层
│   │   ├── 📄 base.py              # Agent 基类与 AgentResult
│   │   ├── 📄 router.py            # IntentRouterAgent (v2.0) + RouterAgent 兼容别名
│   │   ├── 📄 order.py             # 订单 Agent
│   │   ├── 📄 policy.py            # 政策 Agent
│   │   └── 📄 supervisor.py        # 监督 Agent
│   │
│   ├── 📁 intent/                  # 意图识别模块
│   │   ├── 📄 service.py           # IntentRecognitionService (Redis 会话/缓存)
│   │   ├── 📄 models.py            # 意图/槽位/澄清状态数据模型
│   │   ├── 📄 classifier.py        # 意图分类器
│   │   ├── 📄 clarification.py     # 澄清引擎
│   │   ├── 📄 slot_validator.py    # 槽位验证器
│   │   ├── 📄 topic_switch.py      # 话题切换检测
│   │   ├── 📄 multi_intent.py      # 多意图处理器
│   │   └── 📄 safety.py            # 安全过滤器
│   │
│   ├── 📁 services/                # 业务服务层
│   │   └── 📄 refund_service.py    # 退货业务逻辑
│   │
│   ├── 📁 tasks/                   # Celery 异步任务
│   │   └── 📄 refund_tasks.py      # 退款相关任务
│   │
│   ├── 📁 websocket/               # WebSocket 服务
│   │   └── 📄 manager.py           # 连接管理器
│   │
│
├── 📁 frontend/                    # React 前端 (Vite + TypeScript)
│   ├── 📄 package.json             # npm 依赖配置
│   ├── 📄 vite.config.ts           # Vite 多页面配置
│   ├── 📄 tailwind.config.ts       # Tailwind CSS 配置
│   ├── 📄 tsconfig.json            # TypeScript 配置
│   ├── 📄 index.html               # C端入口
│   ├── 📄 admin.html               # B端入口
│   │
│   └── 📁 src/
│       ├── 📁 apps/
│       │   ├── 📁 customer/        # C端用户应用
│       │   │   ├── 📄 App.tsx
│       │   │   ├── 📄 main.tsx
│       │   │   └── 📁 pages/
│       │   │       ├── 📄 Login.tsx
│       │   │       └── 📄 Chat.tsx
│       │   │
│       │   └── 📁 admin/           # B端管理后台
│       │       ├── 📄 App.tsx
│       │       ├── 📄 main.tsx
│       │       └── 📁 pages/
│       │           ├── 📄 Login.tsx
│       │           └── 📄 Dashboard.tsx
│       │
│       ├── 📁 components/
│       │   ├── 📁 ui/              # shadcn/ui 组件
│       │   └── 📁 common/          # 业务共享组件
│       │
│       ├── 📁 api/                 # API 客户端
│       ├── 📁 stores/              # Zustand 状态管理
│       ├── 📁 hooks/               # 自定义 React Hooks
│       └── 📁 types/               # TypeScript 类型定义
│
├── 📁 scripts/                     # 辅助脚本
│   ├── 📄 seed_data.py             # 数据库初始化数据
│   ├── 📄 seed_large_data.py       # 大批量测试数据
│   ├── 📄 etl_policy.py            # 知识库 ETL (PDF/Markdown)
│   └── 📄 verify_db.py             # 数据库验证脚本
│
├── 📁 migrations/                  # Alembic 数据库迁移
│   ├── 📄 env.py
│   └── 📁 versions/
│       └── 📄 *.py                 # 迁移脚本
│
├── 📁 data/                        # 静态数据
│   └── 📄 shipping_policy.md       # 示例政策文档
│
└── 📁 test/                        # 测试文件
    └── 📄 test_*.py                # 单元测试/集成测试
```

## 7. 核心特性

| 特性 | 描述 | 技术实现 |
|------|------|----------|
| **智能问答** | 基于 LLM 的订单查询和政策咨询 | LangChain + LangGraph |
| **意图识别** | 分层意图识别（一级业务域 / 二级动作 / 三级子意图）+ 槽位提取与澄清机制 | IntentRecognitionService + Redis |
| **RAG 检索** | 基于 pgvector 的语义知识检索 | Embedding + 向量数据库 |
| **退货流程** | 多步骤退货申请流程 | LangGraph 状态机 |
| **智能风控** | 按金额分级风控 (¥500/¥2000 阈值) | 规则引擎 |
| **人工审核** | 高风险订单转人工审核 | 审计日志 + 管理后台 |
| **实时通知** | WebSocket 状态同步 | ConnectionManager |
| **异步任务** | 退款支付、短信通知异步处理 | Celery + Redis |
| **多租户隔离** | 用户只能访问自己的订单 | JWT + 数据库查询过滤 |

## 8. 启动流程

```mermaid
flowchart LR
    A[docker-compose up] --> B[PostgreSQL]
    A --> C[Redis]
    B --> D[FastAPI App]
    C --> D
    C --> E[Celery Worker]
    D --> F[初始化数据库]
    D --> G[编译 LangGraph]
    F --> H[系统就绪]
    G --> H
```
