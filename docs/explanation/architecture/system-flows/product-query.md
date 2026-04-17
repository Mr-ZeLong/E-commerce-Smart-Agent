# 商品查询流程

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
