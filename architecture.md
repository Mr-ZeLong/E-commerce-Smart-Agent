# E-commerce Smart Agent v4.1 系统架构图

## 1. 整体架构图

```mermaid
flowchart TB
    subgraph Frontend["🖥️ 前端层 (React + TypeScript)"]
        CUI["👤 Customer App<br/>用户聊天界面<br/>React 19 + Vite"]
        ADM["🛡️ Admin Dashboard<br/>管理员工作台<br/>React 19 + Vite"]
    end

    subgraph APILayer["📡 API 层 (FastAPI)"]
        API["FastAPI Application<br/>Port: 8000"]

        subgraph Routers["🔀 路由模块"]
            AUTH["/api/v1/login<br/>登录认证"]
            CHAT["/api/v1/chat<br/>聊天接口 (SSE)"]
            WS["/api/v1/ws<br/>WebSocket"]
            ADMIN["/api/v1/admin<br/>管理员 API"]
            KB_ADMIN["/admin/knowledge<br/>知识库管理"]
            AGENT_CFG["/admin/agent-config<br/>Agent 配置中心"]
            STATUS["/api/v1/status<br/>状态查询"]
        end
    end

    subgraph CoreLayer["⚙️ 核心层"]
        CONFIG["Config<br/>Pydantic Settings"]
        DB["Database<br/>SQLModel + AsyncPG"]
        SEC["Security<br/>JWT Auth"]
        UTILS["Utils<br/>通用工具函数"]
    end

    subgraph AgentLayer["🤖 Agent 层 (LangGraph)"]
        GRAPH["StateGraph<br/>工作流编排"]

        subgraph Subgraphs["🧩 Agent Subgraphs"]
            SUB_POLICY["policy_agent<br/>Subgraph"]
            SUB_ORDER["order_agent<br/>Subgraph"]
            SUB_PRODUCT["product<br/>Subgraph"]
            SUB_CART["cart<br/>Subgraph"]
            SUB_LOGISTICS["logistics<br/>Subgraph"]
            SUB_ACCOUNT["account<br/>Subgraph"]
            SUB_PAYMENT["payment<br/>Subgraph"]
        end

        subgraph Nodes["📍 节点定义"]
            ROUTER_NODE["router_node<br/>意图路由"]
            MEMORY_NODE["memory_node<br/>记忆加载 / 摘要注入"]
            SUPERVISOR_NODE["supervisor_node<br/>串行/并行调度"]
            SYNTHESIS_NODE["synthesis_node<br/>多 Agent 回复融合"]
            EVALUATOR_NODE["evaluator_node<br/>置信度评估"]
            DECIDER_NODE["decider_node<br/>人工接管决策 / 回复生成 / 记忆抽取触发"]
        end

        subgraph ParallelExec["⚡ 并行执行器"]
            PLAN_DISPATCH["plan_dispatch<br/>独立性判断"]
            BUILD_SENDS["build_parallel_sends<br/>LangGraph Send"]
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
        KB_TASKS["Knowledge Tasks<br/>- 知识库 ETL 同步"]
    end

    subgraph WebSocketLayer["🔌 WebSocket 层"]
        WS_MGR["Connection Manager<br/>连接管理器"]
    end

    subgraph MemoryLayer["🧠 记忆层 (Phase 3)"]
        subgraph MemorySQL["PostgreSQL"]
            TBL_PROFILE[(user_profiles<br/>用户画像)]
            TBL_PREF[(user_preferences<br/>用户偏好)]
            TBL_SUMMARY[(interaction_summaries<br/>交互摘要)]
            TBL_FACT[(user_facts<br/>原子事实)]
            TBL_AGENT_CFG[(agent_configs<br/>Agent 配置)]
            TBL_AGENT_AUDIT[(agent_config_audit_logs<br/>配置审计)]
            TBL_COMPLAINT[(complaint_tickets<br/>投诉工单)]

            TBL_FEEDBACK[(message_feedbacks<br/>用户反馈)]
        end

        subgraph MemoryVec["Qdrant"]
            VEC_CONV[(conversation_memory<br/>对话向量记忆)]
        end

        MEM_MGR["Memory Managers<br/>Structured / Vector / Extractor / Summarizer"]
    end

    subgraph DataLayer["💾 数据层"]
        subgraph PostgreSQL["🐘 PostgreSQL"]
            TBL_USERS[(users<br/>用户表)]
            TBL_ORDERS[(orders<br/>订单表)]
            TBL_REFUNDS[(refund_applications<br/>退款申请表)]
            TBL_AUDIT[(audit_logs<br/>审计日志表)]
            TBL_MSG[(message_cards<br/>消息卡片表)]
            TBL_KB[(knowledge_documents<br/>知识库文档表)]
        end

        subgraph Qdrant["🔷 Qdrant"]
            VEC_KNOWLEDGE[(knowledge_chunks<br/>向量知识库)]
            VEC_PRODUCT[(product_catalog<br/>商品目录向量库)]
        end

        subgraph Redis["🔴 Redis"]
            REDIS_CACHE["Session Cache<br/>状态缓存"]
            REDIS_CART["购物车缓存<br/>cart:{user_id}"]
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
    KB_ADMIN --> KB_TASKS
    AGENT_CFG --> MemoryLayer
    WS --> WS_MGR

    GRAPH --> Nodes
    Nodes --> State
    Nodes --> ParallelExec
    Nodes --> Subgraphs

    ROUTER_NODE --> MEMORY_NODE
    MEMORY_NODE --> SUPERVISOR_NODE
    SUPERVISOR_NODE --> PLAN_DISPATCH
    PLAN_DISPATCH --> BUILD_SENDS
    BUILD_SENDS --> Subgraphs
    Subgraphs --> SYNTHESIS_NODE
    SYNTHESIS_NODE --> EVALUATOR_NODE
    EVALUATOR_NODE --> DECIDER_NODE
    EVALUATOR_NODE -->|"低置信度"| ROUTER_NODE

    REFUND_SVC --> RULES
    REFUND_SVC --> DB

    ServiceLayer -->|"高风险触发"| CELERY
    CELERY --> TASKS
    KB_TASKS --> Qdrant
    TASKS --> DB
    CELERY -->|"记忆抽取"| MEM_MGR

    Nodes <-->|"Embedding/LLM"| External
    MEM_MGR <-->|"Embedding"| External

    DB --> PostgreSQL
    CELERY --> REDIS_CELERY
    GRAPH --> REDIS_CHECK
    REDIS_CART --> Redis
    MEM_MGR --> MemorySQL
    MEM_MGR --> MemoryVec
```

## 2. LangGraph 工作流详解

Phase 2 重构了 Agent 层的编排方式，引入 **Supervisor-based Graph**；Phase 3 进一步在工作流中嵌入 **记忆层** (`memory_node`)，实现长期上下文增强：

- `router_node` 负责意图识别与澄清，将结果写入 `AgentState`。
- `memory_node` 加载结构化记忆（`UserProfile`、`UserPreference`、`UserFact`、`InteractionSummary`）和向量对话记忆（`conversation_memory` 语义检索），生成 `memory_context` 并注入后续 Agent Prompt。
- `supervisor_node` 基于 `intent_result` 中的主意图和 `pending_intents`，通过 `plan_dispatch` 判断多个意图之间是否独立，决定**串行**或**并行**调度。
- 若为并行，通过 `build_parallel_sends` 生成多个 `LangGraph Send`，同时分发到不同的 `Agent Subgraph`。
- 各 `Agent Subgraph` 执行完毕后统一收敛到 `synthesis_node`，将多个专家回复融合为一段连贯回答。
- 之后进入 `evaluator_node` 进行置信度评估，低置信度时回到 `router_node` 重试。
- `decider_node` 在最终决策（人工接管/直接回复）后，触发 Celery 异步任务进行会话摘要与事实抽取。

```mermaid
flowchart LR
    START([START]) --> ROUTER["🎯 router_node\n意图路由"]

    ROUTER -->|"主意图 / slots"| MEMORY["🧠 memory_node\n记忆加载 / 摘要注入"]

    MEMORY -->|"memory_context"| SUPERVISOR["🧠 supervisor_node\n串行/并行调度"]

    SUPERVISOR -->|"串行"| POLICY["📚 policy_agent\nSubgraph"]
    SUPERVISOR -->|"串行"| ORDER["📦 order_agent\nSubgraph"]
    SUPERVISOR -->|"并行 Send"| PRODUCT["🛍️ product\nSubgraph"]
    SUPERVISOR -->|"并行 Send"| CART["🛒 cart\nSubgraph"]
    SUPERVISOR -->|"串行"| LOGISTICS["🚚 logistics\nSubgraph"]
    SUPERVISOR -->|"串行"| ACCOUNT["👤 account\nSubgraph"]
    SUPERVISOR -->|"串行"| PAYMENT["💳 payment\nSubgraph"]

    POLICY --> SYNTHESIS["🔄 synthesis_node\n多 Agent 回复融合"]
    ORDER --> SYNTHESIS
    PRODUCT --> SYNTHESIS
    CART --> SYNTHESIS
    LOGISTICS --> SYNTHESIS
    ACCOUNT --> SYNTHESIS
    PAYMENT --> SYNTHESIS

    SYNTHESIS --> EVAL["⚖️ evaluator_node\n置信度评估"]
    EVAL -->|"低置信度"| ROUTER
    EVAL -->|"通过"| DECIDER["🔀 decider_node\n人工接管决策 / 回复生成 / 记忆抽取触发"]

    DECIDER -->|"无需接管"| END_NORMAL([END])
    DECIDER -->|"需要审核"| END_AUDIT([END\n等待人工审核])

    style MEMORY fill:#e1bee7,stroke:#7b1fa2
    style SUPERVISOR fill:#bbdefb,stroke:#1565c0
    style EVAL fill:#ffeb3b,stroke:#f57f17
    style END_AUDIT fill:#ff9800,stroke:#e65100
```

## 3. 数据模型关系图

```mermaid
erDiagram
    users ||--o{ orders : "拥有"
    users ||--o{ refund_applications : "申请"
    users ||--o{ audit_logs : "触发"
    users ||--o{ user_profiles : "拥有"
    users ||--o{ user_preferences : "拥有"
    users ||--o{ interaction_summaries : "拥有"
    users ||--o{ user_facts : "拥有"
    users ||--o{ complaint_tickets : "提交"
    users ||--o{ message_feedbacks : "提交"
    orders ||--o{ refund_applications : "关联"
    orders ||--o{ audit_logs : "关联"
    orders ||--o{ complaint_tickets : "关联"
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
        string audit_level
        string trigger_type
        string action
        int admin_id
        text admin_comment
        json context_snapshot
        json decision_metadata
        json confidence_metadata
        datetime created_at
        datetime reviewed_at
        datetime updated_at
    }

    message_cards {
        int id PK
        string thread_id
        string message_type
        string status
        json content
        json meta_data
        string sender_type
        int sender_id
        int receiver_id
        datetime created_at
        datetime updated_at
    }

    knowledge_documents {
        int id PK
        string filename
        string storage_path
        string doc_type
        int chunk_count
        string status
        datetime created_at
        datetime updated_at
    }

    supervisor_decisions {
        int id PK
        string thread_id
        string primary_intent
        string pending_intents
        string selected_agents
        string execution_mode
        text reasoning
        datetime created_at
    }

    user_profiles {
        int id PK
        int user_id FK
        string membership_level
        string preferred_language
        string timezone
        int total_orders
        float lifetime_value
        datetime created_at
        datetime updated_at
    }

    user_preferences {
        int id PK
        int user_id FK
        string preference_key
        string preference_value
        datetime created_at
        datetime updated_at
    }

    interaction_summaries {
        int id PK
        int user_id FK
        string thread_id
        text summary_text
        string resolved_intent
        float satisfaction_score
        datetime created_at
        datetime updated_at
    }

    user_facts {
        int id PK
        int user_id FK
        string fact_type
        text content
        float confidence
        string source_thread_id
        datetime created_at
        datetime updated_at
    }

    agent_configs {
        int id PK
        string agent_name UK
        text system_prompt
        text previous_system_prompt
        float confidence_threshold
        int max_retries
        boolean enabled
        datetime updated_at
    }

    agent_config_audit_logs {
        int id PK
        string agent_name
        int changed_by
        string field_name
        text old_value
        text new_value
        datetime created_at
    }

    complaint_tickets {
        int id PK
        int user_id FK
        string thread_id
        string order_sn
        string category
        string urgency
        string status
        text description
        text expected_resolution
        text resolution_notes
        int assigned_to FK
        datetime created_at
        datetime updated_at
    }

    message_feedbacks {
        int id PK
        string thread_id
        int message_index
        string sentiment
        text comment
        int user_id FK
        datetime created_at
    }

    quality_scores {
        int id PK
        string thread_id
        float coherence
        float helpfulness
        float safety
        float overall
        text reasoning
        datetime created_at
    }

    knowledge_chunks[Qdrant Collection: knowledge_chunks] {
        string source
        text content
        vector embedding
        boolean is_active
        datetime created_at
    }

    product_catalog[Qdrant Collection: product_catalog] {
        string source
        text content
        vector embedding
        json meta_data
        datetime created_at
    }

    conversation_memory[Qdrant Collection: conversation_memory] {
        string thread_id
        string message_id
        string role
        text content
        vector embedding
        json meta_data
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
    participant Node as order_agent
    participant DB as PostgreSQL
    participant LLM as Qwen LLM

    User->>CUI: "查询我的订单"
    CUI->>API: POST /api/v1/chat (SSE)
    API->>Graph: astream_events()
    Graph->>Graph: router_node
    Graph->>Node: order_agent()
    Node->>DB: SELECT orders
    DB-->>Node: Order Data
    Node-->>Graph: {order_data, context}
    Node->>Node: _format_order_response
    Node-->>Graph: {response_text}
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
    participant Service as OrderService
    participant AdminSvc as AdminService
    participant DB as PostgreSQL
    participant Celery as Celery Worker
    participant WS as WebSocket Manager

    User->>CUI: "我要退货 订单SN20240003"
    CUI->>API: POST /api/v1/chat
    API->>Graph: 启动工作流
    Graph->>Graph: router_node → AFTER_SALES
    Graph->>Graph: order_agent()
    Graph->>Service: handle_refund_request (OrderService)

    alt 低风险 (< ¥500)
        Service-->>Graph: 无需审计
        Graph-->>API: 返回处理结果
        API-->>CUI: 已提交，保持 PENDING
    else 中高风险 (≥ ¥500)
        Service->>DB: INSERT audit_logs
        Service->>Celery: notify_admin_audit
        Service-->>Graph: 需人工审核
        Graph-->>API: 返回处理结果
        API-->>CUI: 等待人工审核

        Admin->>ADM: 查看任务队列
        ADM->>API: GET /api/v1/admin/tasks
        API-->>ADM: 待审核列表

        Admin->>ADM: 点击"批准"
        ADM->>API: POST /api/v1/admin/resume/{id}
        API->>AdminSvc: process_admin_decision()
        AdminSvc->>DB: UPDATE audit_logs
        AdminSvc->>DB: UPDATE refund_applications
        AdminSvc->>Celery: process_refund_payment
        AdminSvc->>Celery: send_refund_sms
        AdminSvc->>WS: 通知状态变更
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
    participant VecDB as Qdrant
    participant LLM as Qwen LLM

    User->>CUI: "内衣可以退货吗？"
    CUI->>API: POST /api/v1/chat
    API->>Graph: 启动工作流
    Graph->>Graph: router_node → POLICY
    Graph->>Graph: policy_agent()（内含 retrieve）
    Graph->>Embed: aembed_query()
    Embed->>Embed: 生成查询向量
    Embed-->>Graph: query_vector
    Graph->>VecDB: 混合检索 (dense + sparse)
    VecDB-->>Graph: 相似文档片段
    Graph->>Graph: Rerank(TopK)
    Graph->>LLM: Prompt + Context + Question
    LLM-->>Graph: 流式响应
    Graph-->>API: SSE Events
    API-->>CUI: 逐字显示回复
    CUI-->>User: 政策解答
```

### 4.4 商品查询流程

```mermaid
sequenceDiagram
    actor User
    participant CUI as Customer UI
    participant API as FastAPI
    participant Graph as LangGraph
    participant Supervisor as supervisor_node
    participant Node as product (Subgraph)
    participant Tool as ProductTool
    participant VecDB as Qdrant product_catalog
    participant LLM as Qwen LLM

    User->>CUI: "智能手机 Pro 屏幕多大？"
    CUI->>API: POST /api/v1/chat (SSE)
    API->>Graph: astream_events()
    Graph->>Graph: router_node → PRODUCT
    Graph->>Supervisor: 调度 product
    Supervisor-->>Graph: Send(product)
    Graph->>Node: product Subgraph
    Node->>Tool: process()
    Tool->>VecDB: semantic_search(using="dense")
    VecDB-->>Tool: 匹配商品元数据
    alt 属性命中直接回答
        Tool-->>Node: direct_answer
    else 属性未命中 / 需要推理
        Node->>LLM: 基于检索描述推理
        LLM-->>Node: LLM 回答
    end
    Node-->>Graph: sub_answers
    Graph->>Graph: synthesis_node
    Graph-->>API: SSE Events
    API-->>CUI: 流式显示回复
    CUI-->>User: 商品信息
```

### 4.5 购物车管理流程

```mermaid
sequenceDiagram
    actor User
    participant CUI as Customer UI
    participant API as FastAPI
    participant Graph as LangGraph
    participant Supervisor as supervisor_node
    participant Node as cart (Subgraph)
    participant Tool as CartTool
    participant Redis as Redis cart:{user_id}

    User->>CUI: "给我加一部智能手机到购物车"
    CUI->>API: POST /api/v1/chat (SSE)
    API->>Graph: astream_events()
    Graph->>Graph: router_node → CART
    Graph->>Supervisor: 调度 cart
    Supervisor-->>Graph: Send(cart)
    Graph->>Node: cart Subgraph
    Node->>Tool: process(action=ADD)
    Tool->>Redis: SET cart:{user_id} (JSON, TTL=86400)
    Redis-->>Tool: OK
    Tool-->>Node: "已添加"
    Node-->>Graph: sub_answers
    Graph->>Graph: synthesis_node
    Graph-->>API: SSE Events
    API-->>CUI: 流式显示回复
    CUI-->>User: 购物车更新结果
```

### 4.6 并行多意图执行流程

```mermaid
sequenceDiagram
    actor User
    participant CUI as Customer UI
    participant API as FastAPI
    participant Graph as LangGraph
    participant Router as router_node
    participant Supervisor as supervisor_node
    participant Plan as plan_dispatch
    participant Product as product (Subgraph)
    participant Logistics as logistics (Subgraph)
    participant Synthesis as synthesis_node

    User->>CUI: "查一下智能手机的价格和物流"
    CUI->>API: POST /api/v1/chat (SSE)
    API->>Graph: astream_events()
    Graph->>Router: 识别意图
    Router-->>Graph: primary=PRODUCT, pending=[LOGISTICS]
    Graph->>Supervisor: 读取意图结果
    Supervisor->>Plan: are_independent(PRODUCT, LOGISTICS)?
    Plan-->>Supervisor: True → parallel
    Supervisor-->>Graph: Send(product) + Send(logistics)
    par 并行执行
        Graph->>Product: product Subgraph
        Product-->>Graph: sub_answer_product
    and
        Graph->>Logistics: logistics Subgraph
        Logistics-->>Graph: sub_answer_logistics
    end
    Graph->>Synthesis: 融合两个回复
    Synthesis-->>Graph: 整合后的连贯回答
    Graph->>Graph: evaluator_node
    Graph-->>API: SSE Events
    API-->>CUI: 流式显示回复
    CUI-->>User: 商品 + 物流信息
```

### 4.7 B端知识库上传与同步流程

```mermaid
sequenceDiagram
    actor Admin
    participant ADM as Admin Dashboard
    participant API as FastAPI
    participant DB as PostgreSQL
    participant Celery as Celery Worker
    participant ETL as etl_qdrant.py
    participant VecDB as Qdrant knowledge_chunks

    Admin->>ADM: 选择 PDF/Markdown 上传
    ADM->>API: POST /admin/knowledge
    API->>API: 保存文件到 uploads/knowledge
    API->>DB: INSERT knowledge_documents
    DB-->>API: doc_id
    API->>Celery: sync_knowledge_document(doc_id)
    API-->>ADM: 返回 task_id

    loop 轮询同步状态
        ADM->>API: GET /admin/knowledge/sync/{task_id}
        API-->>ADM: PENDING / SUCCESS / FAILURE
    end

    Celery->>ETL: 执行 ETL (提取 → Embedding → Upsert)
    ETL->>VecDB: upsert 向量片段
    VecDB-->>ETL: OK
    Celery->>DB: UPDATE knowledge_documents.status=SYNCED
```

### 4.8 记忆系统加载流程

```mermaid
sequenceDiagram
    actor User
    participant CUI as Customer UI
    participant API as FastAPI
    participant Graph as LangGraph
    participant MemoryNode as memory_node
    participant StructMgr as StructuredMemoryManager
    participant VecMgr as VectorMemoryManager
    participant PG as PostgreSQL
    participant Qdrant as Qdrant conversation_memory

    User->>CUI: "我之前问过退货政策"
    CUI->>API: POST /api/v1/chat (SSE)
    API->>Graph: astream_events()
    Graph->>Graph: router_node
    Graph->>MemoryNode: 加载记忆

    par 结构化记忆加载
        MemoryNode->>StructMgr: get_memory_context(user_id)
        StructMgr->>PG: SELECT user_profiles / preferences / facts / summaries
        PG-->>StructMgr: 用户画像 + 偏好 + 事实
        StructMgr-->>MemoryNode: memory_context (文本)
    and 向量记忆召回
        MemoryNode->>VecMgr: retrieve_similar_messages(query, user_id)
        VecMgr->>Qdrant: semantic_search(embedding)
        Qdrant-->>VecMgr: 相关历史消息 TopK
        VecMgr-->>MemoryNode: relevant_history
    end

    MemoryNode-->>Graph: 更新 state.memory_context
    Graph->>Graph: supervisor_node / Agent Subgraphs / synthesis_node
    Graph-->>API: SSE Events
    API-->>CUI: 流式显示（含记忆感知的回复）
    CUI-->>User: 个性化回答
```

### 4.9 Agent 配置中心流程

```mermaid
sequenceDiagram
    actor Admin
    participant ADM as Admin Dashboard
    participant API as FastAPI
    participant Svc as AgentConfigService
    participant DB as PostgreSQL
    participant Cache as Redis Cache
    participant Graph as LangGraph

    Admin->>ADM: 修改 Agent 系统提示词 / 路由规则
    ADM->>API: PUT /api/v1/admin/agent-config/{agent_name}
    API->>Svc: update_agent_config()
    Svc->>DB: UPDATE agent_configs (version ++)
    Svc->>DB: INSERT agent_config_audit_logs
    Svc->>Cache: DEL agent_config:{agent_name}
    Svc-->>API: 配置已更新
    API-->>ADM: 200 OK

    Note over Graph: 60s TTL 过期后
    Graph->>Cache: GET agent_config:order_agent
    Cache-->>Graph: MISS
    Graph->>Svc: load_config("order_agent")
    Svc->>DB: SELECT agent_configs
    DB-->>Svc: 最新配置
    Svc->>Cache: SET agent_config:order_agent (TTL=60s)
    Svc-->>Graph: 热重载配置
```

## 5. 技术栈分层

```mermaid
flowchart TB
    subgraph Layer1["表示层"]
        F1["React 19 + TypeScript<br/>Vite + Tailwind CSS"]
    end

    subgraph Layer2["接入层"]
        A1["FastAPI<br/>Port 8000"]
        A2["WebSocket<br/>实时通信"]
        A3["JWT Auth<br/>身份认证"]
    end

    subgraph Layer3["业务层"]
        B1["LangGraph\nSupervisor-based 工作流引擎 (含 memory_node)"]
        B2["意图识别\nIntent Router + 多意图独立判断"]
        B3["RAG 检索\nDense + Sparse + Rerank + Rewriter"]
        B4["专家 Agent 舰队\nProduct / Cart / Order / Policy / Logistics / Account / Payment"]
        B5["退货服务\nRefund Service"]
        B6["记忆系统\nStructured + Vector + Extractor + Summarizer"]
        B7["Agent 配置中心\n热重载 + 路由规则 + 审计日志"]
    end

    subgraph Layer4["任务层"]
        T1["Celery\n异步任务队列"]
        T2["退款处理\n支付网关"]
        T3["短信通知\nSMS Gateway"]
        T4["知识库同步\nETL → Qdrant"]
        T5["记忆抽取\n会话摘要 + UserFact 提取"]
    end

    subgraph Layer5["数据层"]
        D1["PostgreSQL\n关系型数据 (含 memory / config 表)"]
        D2["Qdrant\n混合向量检索 (knowledge_chunks + product_catalog + conversation_memory)"]
        D3["Redis\n缓存 / 会话 / 购物车 / Checkpoint"]
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
    Layer2 --> Layer3
```

## 6. 项目文件结构

```
E-commerce-Smart-Agent/
├── 📄 README.md                    # 项目文档
├── 📄 architecture.md              # 系统架构文档
├── 📄 .env.example                 # 环境变量模板
├── 📄 alembic.ini                  # Alembic 迁移配置
├── 📄 pyproject.toml               # Python 项目配置 (uv)
├── 📄 uv.lock                      # uv 依赖锁定文件
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
│   │   ├── 📄 chat_utils.py        # SSE 流式响应工具
│   │   ├── 📄 admin.py             # 管理员接口 (含知识库 CRUD + 同步)
│   │   ├── 📁 admin/
│   │   │   ├── 📄 agent_config.py  # Agent 配置中心 API (路由规则 / 提示词 / 审计日志)
│   │   │   ├── 📄 complaints.py    # 投诉工单管理 API (Phase 4)

│   │   │   ├── 📄 feedback.py      # 用户反馈与质量评估 API (Phase 4)
│   │   │   └── 📄 analytics.py     # 高级分析 API (Phase 4)
│   │   ├── 📄 status.py            # 状态查询接口
│   │   ├── 📄 websocket.py         # WebSocket 端点
│   │   └── 📄 schemas.py           # Pydantic 数据模型
│   │
│   ├── 📁 core/                    # 核心基础设施
│   │   ├── 📄 config.py            # 配置管理 (Pydantic Settings)
│   │   ├── 📄 database.py          # 数据库连接 (SQLModel)
│   │   ├── 📄 redis.py             # 统一 Redis 客户端
│   │   ├── 📄 security.py          # JWT 认证
│   │   ├── 📄 limiter.py           # API 限流 (slowapi)
│   │   ├── 📄 llm_factory.py       # LLM 实例工厂
│   │   ├── 📄 logging.py           # 结构化日志 (correlation_id)
│   │   └── 📄 utils.py             # 工具函数（utc_now 等）
│   │
│   ├── 📁 models/                  # 数据库模型 (SQLModel)
│   │   ├── 📄 user.py              # 用户表
│   │   ├── 📄 order.py             # 订单表
│   │   ├── 📄 refund.py            # 退款申请表
│   │   ├── 📄 audit.py             # 审计日志表
│   │   ├── 📄 message.py           # 消息卡片表
│   │   ├── 📄 knowledge_document.py # 知识库文档表
│   │   ├── 📄 observability.py     # 可观测性模型
│   │   ├── 📄 memory.py            # 记忆模型 (UserProfile / UserPreference / InteractionSummary / UserFact / AgentConfig / AuditLog)
│   │   ├── 📄 complaint.py         # 投诉工单模型 (Phase 4)

│   │   ├── 📄 evaluation.py        # 在线评估模型 (Phase 4)
│   │   └── 📄 state.py             # AgentState TypedDict
│   │
│   ├── 📁 memory/                  # 记忆系统 (Phase 3)
│   │   ├── 📄 __init__.py
│   │   ├── 📄 structured_manager.py # 结构化记忆管理器 (PostgreSQL)
│   │   ├── 📄 vector_manager.py    # 向量对话记忆管理器 (Qdrant conversation_memory)
│   │   ├── 📄 extractor.py         # 事实抽取器 (FactExtractor)
│   │   └── 📄 summarizer.py        # 会话摘要器 (SessionSummarizer)
│   │
│   ├── 📁 graph/                   # LangGraph 核心逻辑
│   │   ├── 📄 workflow.py          # 工作流定义 (含 Supervisor 模式与兼容模式)
│   │   ├── 📄 nodes.py             # 节点定义 (router / supervisor / synthesis / evaluator / decider)
│   │   ├── 📄 subgraphs.py         # Agent Subgraph 标准化封装
│   │   └── 📄 parallel.py          # 并行多意图调度 (plan_dispatch + build_parallel_sends)
│   │
│   ├── 📁 agents/                  # Agent 实现层
│   │   ├── 📄 base.py              # Agent 基类
│   │   ├── 📄 router.py            # IntentRouterAgent
│   │   ├── 📄 supervisor.py        # SupervisorAgent (串行/并行调度)
│   │   ├── 📄 order.py             # 订单 Agent
│   │   ├── 📄 policy.py            # 政策 Agent
│   │   ├── 📄 product.py           # 商品 Agent (ProductAgent)
│   │   ├── 📄 cart.py              # 购物车 Agent (CartAgent)
│   │   ├── 📄 logistics.py         # 物流 Agent
│   │   ├── 📄 account.py           # 账户 Agent
│   │   ├── 📄 payment.py           # 支付 Agent
│   │   ├── 📄 complaint.py         # 投诉 Agent (ComplaintAgent, Phase 4)
│   │   └── 📄 evaluator.py         # ConfidenceEvaluator
│   │
│   ├── 📁 tools/                   # Agent Tool 层
│   │   ├── 📄 __init__.py
│   │   ├── 📄 product_tool.py      # 商品检索 Tool (Qdrant product_catalog)
│   │   ├── 📄 cart_tool.py         # 购物车操作 Tool (Redis)
│   │   ├── 📄 logistics_tool.py    # 物流查询 Tool
│   │   ├── 📄 account_tool.py      # 账户查询 Tool
│   │   ├── 📄 payment_tool.py      # 支付查询 Tool
│   │   └── 📄 complaint_tool.py    # 投诉工单创建 Tool (Phase 4)
│   │
│   ├── 📁 confidence/              # 置信度信号模块
│   │   ├── 📄 __init__.py
│   │   └── 📄 signals.py           # 置信度评估信号计算
│   │
│   ├── 📁 utils/                   # 通用工具函数
│   │   └── 📄 order_utils.py       # 订单相关工具
│   │
│   ├── 📁 intent/                  # 意图识别模块
│   │   ├── 📄 service.py           # IntentRecognitionService (Redis 会话/缓存)
│   │   ├── 📄 models.py            # 意图/槽位/澄清状态数据模型
│   │   ├── 📄 config.py            # 意图识别配置
│   │   ├── 📄 classifier.py        # 意图分类器
│   │   ├── 📄 clarification.py     # 澄清引擎
│   │   ├── 📄 slot_validator.py    # 槽位验证器
│   │   ├── 📄 topic_switch.py      # 话题切换检测
│   │   ├── 📄 multi_intent.py      # 多意图处理器 (含独立性判断)
│   │   └── 📄 safety.py            # 安全过滤器
│   │
│   ├── 📁 retrieval/               # RAG 检索层
│   │   ├── 📄 client.py            # 检索客户端
│   │   ├── 📄 embeddings.py        # 向量嵌入
│   │   ├── 📄 retriever.py         # 检索器
│   │   ├── 📄 reranker.py          # 精排器
│   │   ├── 📄 rewriter.py          # 查询重写器
│   │   └── 📄 sparse_embedder.py   # 稀疏嵌入
│   │
│   ├── 📁 services/                # 业务服务层
│   │   ├── 📄 refund_service.py    # 退货业务逻辑
│   │   ├── 📄 status_service.py    # 状态服务
│   │   ├── 📄 order_service.py     # 订单服务
│   │   ├── 📄 admin_service.py     # 管理员服务
│   │   ├── 📄 auth_service.py      # 认证服务
│   │   ├── 📄 experiment.py        # A/B 实验服务 (Phase 4)

│   │   └── 📄 online_eval.py       # 在线评估服务 (Phase 4)
│   │
│   ├── 📁 schemas/                 # 共享 Schema
│   │   ├── 📄 auth.py
│   │   ├── 📄 admin.py
│   │   └── 📄 status.py
│   │
│   ├── 📁 tasks/                   # Celery 异步任务
│   │   ├── 📄 __init__.py
│   │   ├── 📄 refund_tasks.py      # 退款相关任务
│   │   ├── 📄 knowledge_tasks.py   # 知识库同步任务
│   │   ├── 📄 memory_tasks.py      # 记忆抽取与同步任务
│   │   └── 📄 notifications.py     # 告警通知任务 (Phase 4)
│   │
│   ├── 📁 websocket/               # WebSocket 服务
│   │   └── 📄 manager.py           # 连接管理器
│   │
│
├── 📁 frontend/                    # React 前端 (Vite + TypeScript)
│   ├── 📄 package.json             # npm 依赖配置
│   ├── 📄 package-lock.json        # npm 锁定文件
│   ├── 📄 vite.config.ts           # Vite 多页面配置
│   ├── 📄 tailwind.config.ts       # Tailwind CSS 配置
│   ├── 📄 tsconfig.json            # TypeScript 配置
│   ├── 📄 tsconfig.node.json       # Vite Node 类型配置
│   ├── 📄 components.json          # shadn/ui 组件注册表
│   ├── 📄 postcss.config.mjs       # PostCSS 配置
│   ├── 📄 eslint.config.js         # ESLint 配置
│   ├── 📄 playwright.config.ts     # Playwright E2E 配置
│   ├── 📄 index.html               # C端入口
│   ├── 📄 admin.html               # B端入口
│   │
│   └── 📁 src/
│       ├── 📁 apps/
│       │   ├── 📁 customer/        # C端用户应用
│       │   │   ├── 📄 App.tsx
│       │   │   ├── 📄 main.tsx
│       │   │   ├── 📁 hooks/
│       │   │   │   └── 📄 useChat.ts
│       │   │   └── 📁 components/
│       │   │       ├── 📄 ChatMessageList.tsx
│       │   │       └── 📄 ChatInput.tsx
│       │   │
│       │   └── 📁 admin/           # B端管理后台
│       │       ├── 📄 App.tsx
│       │       ├── 📄 main.tsx
│       │       ├── 📁 pages/
│       │       │   ├── 📄 Login.tsx
│       │       │   ├── 📄 Dashboard.tsx
│       │       │   ├── 📄 KnowledgeBase.tsx      # 知识库管理页面
│       │       │   └── 📄 AgentConfig.tsx        # Agent 配置中心页面
│       │       └── 📁 components/
│       │           ├── 📄 DecisionPanel.tsx
│       │           ├── 📄 NotificationToast.tsx
│       │           ├── 📄 TaskDetail.tsx
│       │           ├── 📄 TaskList.tsx
│       │           ├── 📄 ConversationLogs.tsx
│       │           ├── 📄 EvaluationViewer.tsx
│       │           ├── 📄 Performance.tsx
│       │           ├── 📄 KnowledgeBaseManager.tsx  # 知识库上传/同步组件
│       │           ├── 📄 AgentConfigEditor.tsx     # Agent 配置编辑器组件
│       │           ├── 📄 ComplaintQueue.tsx        # 投诉工单管理 (Phase 4)

│       │           └── 📄 AnalyticsV2.tsx           # 高级分析面板 (Phase 4)
│       │
│       ├── 📁 components/
│       │   ├── 📁 ui/              # shadcn/ui 组件
│       │   │   ├── 📄 accordion.tsx
│       │   │   ├── 📄 alert.tsx
│       │   │   ├── 📄 avatar.tsx
│       │   │   ├── 📄 badge.tsx
│       │   │   ├── 📄 button.tsx
│       │   │   ├── 📄 card.tsx
│       │   │   ├── 📄 input.tsx
│       │   │   ├── 📄 label.tsx
│       │   │   ├── 📄 radio-group.tsx
│       │   │   ├── 📄 scroll-area.tsx
│       │   │   ├── 📄 separator.tsx
│       │   │   ├── 📄 sheet.tsx
│       │   │   ├── 📄 skeleton.tsx
│       │   │   └── 📄 textarea.tsx
│       │
│       ├── 📁 assets/              # 前端静态资源
│       ├── 📁 lib/                 # 共享基础设施
│       │   ├── 📄 api.ts           # 统一 API 客户端
│       │   ├── 📄 risk.ts          # 风险等级配置
│       │   ├── 📄 query-client.ts  # Query Client 配置
│       │   └── 📄 utils.ts         # 前端工具函数
│       ├── 📁 stores/              # Zustand 状态管理
│       │   └── 📄 auth.ts          # 认证状态
│       ├── 📁 hooks/               # 自定义 React Hooks
│       │   ├── 📄 useAuth.ts
│       │   ├── 📄 useNotifications.ts
│       │   ├── 📄 useTasks.ts
│       │   ├── 📄 useKnowledgeBase.ts  # 知识库管理 Hooks
│       │   ├── 📄 useAgentConfig.ts    # Agent 配置管理 Hooks
│       │   ├── 📄 useComplaints.ts     # 投诉工单 Hooks (Phase 4)

│       │   └── 📄 useAnalytics.ts      # 高级分析 Hooks (Phase 4)
│       ├── 📁 types/               # TypeScript 类型定义
│       │   └── 📄 index.ts         # 统一类型导出
│
├── 📄 start.sh                     # 本地一键启动脚本
├── 📄 start_worker.sh              # 单独启动 Celery Worker
├── 📄 Dockerfile                   # 容器构建配置
├── 📄 alembic.ini                  # Alembic 迁移配置
│
├── 📁 scripts/                     # 辅助脚本
│   ├── 📄 __init__.py
│   ├── 📄 seed_data.py             # 数据库初始化数据
│   ├── 📄 seed_large_data.py       # 大批量测试数据
│   ├── 📄 seed_product_catalog.py  # 商品目录种子数据 (→ Qdrant product_catalog)
│   ├── 📄 etl_qdrant.py            # 知识库 ETL (PDF/Markdown → Qdrant)
│   └── 📄 verify_db.py             # 数据库验证脚本
│
├── 📁 migrations/                  # Alembic 数据库迁移
│   ├── 📄 env.py
│   └── 📁 versions/
│       └── 📄 *.py                 # 迁移脚本
│
├── 📁 assets/                      # 截图与静态资源
│
├── 📁 data/                        # 静态数据
│   ├── 📄 shipping_policy.md       # 示例政策文档
│   ├── 📄 return_policy.md         # 退货政策文档
│   └── 📄 products.json            # 商品目录种子数据
│
├── 📁 docs/                        # 项目文档
│   └── 📄 resume-guide.md          # 简历写作指南
│
├── 📁 .github/                     # GitHub Actions 工作流
│   └── 📁 workflows/
│       └── 📄 ci.yml               # CI 配置
│
└── 📁 tests/                       # 测试文件
    ├── 📄 conftest.py              # pytest 全局 fixtures
    ├── 📄 _db_config.py            # 测试数据库配置
    ├── 📄 test_auth_api.py         # 认证 API 测试
    ├── 📄 test_chat_api.py         # 聊天 API 测试
    ├── 📄 test_admin_api.py        # 管理员 API 测试
    ├── 📄 test_websocket.py        # WebSocket 测试
    ├── 📄 test_auth_rate_limit.py  # 认证限流测试
    ├── 📄 test_order_service.py    # 订单服务测试
    ├── 📄 test_refund_service.py   # 退款服务测试
    ├── 📄 test_admin_service.py    # 管理员服务测试
    ├── 📄 test_auth_service.py     # 认证服务测试
    ├── 📄 test_status_service.py   # 状态服务测试
    ├── 📄 test_security.py         # 安全测试
    ├── 📄 test_main_security.py    # 主应用安全测试
    ├── 📄 test_logging.py          # 日志测试
    ├── 📄 test_chat_utils.py       # 聊天工具测试
    ├── 📄 test_refund_tasks.py     # 退款任务测试
    ├── 📄 test_knowledge_admin.py  # 知识库管理 API 测试
    ├── 📄 test_users.py            # 用户模型测试
    ├── 📄 test_confidence_signals.py # 置信度信号测试
    ├── 📁 agents/                  # Agent 单元测试
    ├── 📁 tools/                   # Tool 单元测试 (product_tool / cart_tool)
    ├── 📁 graph/                   # LangGraph 测试
    ├── 📁 intent/                  # 意图模块测试
    ├── 📁 retrieval/               # RAG 检索测试
    └── 📁 integration/             # 集成测试
```

## 7. 核心特性

| 特性 | 描述 | 技术实现 |
|------|------|----------|
| **智能问答** | 基于 LLM 的订单查询、政策咨询、商品查询和购物车管理 | LangChain + LangGraph |
| **结构化记忆系统** | PostgreSQL 存储用户画像、偏好、交互摘要、原子事实；通过 `memory_context` 自动注入 Agent Prompt | `app/memory/structured_manager.py` + `app/models/memory.py` |
| **向量对话记忆** | Qdrant `conversation_memory` 集合存储对话消息向量，支持语义检索历史上下文 | `app/memory/vector_manager.py` |
| **记忆抽取 Pipeline** | `decider_node` 后 Celery 异步任务调用轻量 LLM，提取结构化 `UserFact` 并落盘 | `app/memory/extractor.py` + `app/tasks/memory_tasks.py` |
| **Agent 配置中心** | B 端 Admin 支持热重载 Agent 路由规则、系统提示词、启用/禁用 Agent；支持审计日志与版本回滚 | `app/api/v1/admin/agent_config.py` + `frontend/src/apps/admin/pages/AgentConfig.tsx` |
| **Supervisor 多 Agent 编排** | `SupervisorAgent` 基于意图独立性判断，决定串行或并行调度；通过 `Send` 实现多 Agent 并行执行 | `app/graph/parallel.py` + Agent Subgraphs |
| **Agent Subgraph 标准** | 每个专家 Agent 封装为独立 `StateGraph` Subgraph，标准化消费 `AgentState` 子集并输出 `AgentProcessResult` | `app/graph/subgraphs.py` |
| **多意图并行执行** | 独立意图通过 `build_parallel_sends` 同时分发到多个 Subgraph，结果汇聚至 `synthesis_node` 融合 | `plan_dispatch` + `Send` APIs |
| **商品问答** | `ProductAgent` 基于 Qdrant `product_catalog` 语义搜索；参数命中时直接回答，否则 LLM 推理回退 | `ProductTool` + Embedding Search |
| **购物车管理** | `CartAgent` 通过 Redis 支持增删改查，24h TTL 保持会话一致性 | `CartTool` + Redis JSON |
| **意图识别** | 分层意图识别（一级业务域 / 二级动作 / 三级子意图）+ 槽位提取与澄清机制 + 多意图独立性判断 | `IntentRecognitionService` + `multi_intent.py` |
| **RAG 检索** | 基于 Qdrant 的混合语义检索（Dense + BM25 Sparse + Rerank） | Embedding + 向量数据库 |
| **查询重写与精排** | RAG 流程中先重写查询，再混合检索，最后 Rerank | `retrieval/` 模块 |
| **B 端知识库管理** | Admin 后台支持 PDF/Markdown 上传、删除、手动同步到 Qdrant；同步状态通过 Celery 异步追踪 | `KnowledgeBaseManager` + `knowledge_tasks.py` |
| **API 限流** | 防止暴力破解和滥用 | `slowapi` |
| **结构化日志** | 全链路 correlation_id 追踪 | `app/core/logging.py` |
| **pre-commit 质量门禁** | 提交前自动格式化、类型检查 | `ruff` + `ty` |
| **退货流程** | 多步骤退货申请流程 | LangGraph 状态机 |
| **智能风控** | 按金额分级风控 (¥500/¥2000 阈值) | 规则引擎 |
| **人工审核** | 高风险订单转人工审核 | 审计日志 + 管理后台 |
| **实时通知** | WebSocket 状态同步 | ConnectionManager |
| **异步任务** | 退款支付、短信通知、知识库 ETL 同步异步处理 | Celery + Redis |
| **多租户隔离** | 用户只能访问自己的订单和购物车 | JWT + 数据隔离 |
| **智能投诉处理** | `ComplaintAgent` 自动识别投诉意图并分类，支持工单创建与分配 | `app/agents/complaint.py` + `ComplaintTicket` |

| **在线评估** | 用户反馈收集 (👍/👎)、CSAT 计算、LLM 自动质量评分 | `app/services/online_eval.py` + `MessageFeedback` |
| **自动告警** | 定时检测服务质量下降，邮件/WebSocket 通知管理员 | `app/tasks/notifications.py` + Celery Beat |
| **高级分析** | CSAT 趋势、投诉根因、Agent 对比、LangSmith Trace | `AnalyticsV2` + `app/api/v1/admin/analytics.py` |

## 8. 启动流程

```mermaid
flowchart LR
    A[docker-compose up] --> B[PostgreSQL]
    A --> C[Redis]
    A --> Q[Qdrant]
    B --> D[FastAPI App]
    C --> D
    Q --> D
    C --> E[Celery Worker]
    D --> F[初始化数据库]
    D --> G[编译 LangGraph]
    F --> H[系统就绪]
    G --> H
```

## 9. 代码质量与 CI

| 工具 | 用途 | 配置位置 |
|---|---|---|
| ruff | Lint + Format | `.pre-commit-config.yaml`, `pyproject.toml` |
| ty | 类型检查 | `.pre-commit-config.yaml` |
| pytest | 单元/集成测试 | `pyproject.toml` |
| GitHub Actions | CI 流水线 | `.github/workflows/ci.yml` |

CI 流程：
1. 检出代码
2. 设置 Python 3.12 + uv 0.6.5
3. 创建 test database
4. Cache uv dependencies (`actions/cache@v4`)
5. `uv sync` 安装依赖
6. `uv run ruff check app tests`
7. `uv run pytest --cov=app --cov-fail-under=75`
