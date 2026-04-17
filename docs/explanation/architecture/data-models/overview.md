# 数据模型概览

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
    users ||--o{ graph_execution_logs : "执行"
    orders ||--o{ refund_applications : "关联"
    orders ||--o{ audit_logs : "关联"
    orders ||--o{ complaint_tickets : "关联"
    refund_applications ||--o{ audit_logs : "触发"
    graph_execution_logs ||--o{ graph_node_logs : "包含"
    experiments ||--o{ experiment_variants : "包含"
    experiments ||--o{ experiment_assignments : "分配"
    experiment_variants ||--o{ experiment_assignments : "拥有"
    users ||--o{ experiment_assignments : "参与"
    agent_configs ||--o{ agent_config_versions : "版本快照"
    agent_config_versions ||--o{ prompt_effect_reports : "效果报告"

    users {
        int id PK
        string username UK
        string password_hash
        string email UK
        boolean is_admin
        datetime created_at
    }

    orders {
        int id PK
        string order_sn UK
        int user_id FK
        string status
        decimal total_amount
        json items
        datetime created_at
    }

    refund_applications {
        int id PK
        int order_id FK
        int user_id FK
        string status
        string reason_category
        decimal refund_amount
        datetime created_at
    }

    audit_logs {
        int id PK
        string thread_id
        int order_id FK
        int refund_application_id FK
        int user_id FK
        string risk_level
        string action
        datetime created_at
    }

    message_cards {
        int id PK
        string thread_id
        string message_type
        json content
        datetime created_at
    }

    knowledge_documents {
        int id PK
        string filename
        string sync_status
        datetime created_at
    }

    supervisor_decisions {
        int id PK
        string thread_id
        string primary_intent
        string execution_mode
        datetime created_at
    }

    user_profiles {
        int id PK
        int user_id FK
        string membership_level
        int total_orders
        datetime created_at
    }

    user_preferences {
        int id PK
        int user_id FK
        string preference_key
        string preference_value
    }

    interaction_summaries {
        int id PK
        int user_id FK
        string thread_id
        text summary_text
        float satisfaction_score
    }

    user_facts {
        int id PK
        int user_id FK
        string fact_type
        text content
        float confidence
    }

    agent_configs {
        int id PK
        string agent_name UK
        text system_prompt
        float confidence_threshold
        boolean enabled
    }

    agent_config_audit_logs {
        int id PK
        string agent_name
        string field_name
        text old_value
        text new_value
    }

    complaint_tickets {
        int id PK
        int user_id FK
        string category
        string urgency
        string status
    }

    message_feedbacks {
        int id PK
        int user_id FK
        int score
        text comment
    }

    quality_scores {
        int id PK
        date score_date
        float human_transfer_rate
        float avg_confidence
    }

    graph_execution_logs {
        int id PK
        string thread_id
        float confidence_score
        boolean needs_human_transfer
    }

    graph_node_logs {
        int id PK
        int execution_id FK
        string node_name
        int latency_ms
    }

    experiments {
        int id PK
        string name
        string status
    }

    experiment_variants {
        int id PK
        int experiment_id FK
        string name
        text system_prompt
    }

    experiment_assignments {
        int id PK
        int experiment_id FK
        int variant_id FK
        int user_id FK
    }

    routing_rules {
        int id PK
        string intent_category
        string target_agent
        int priority
    }

    agent_config_versions {
        int id PK
        string agent_name
        int changed_by FK
        text system_prompt
        float confidence_threshold
    }

    prompt_effect_reports {
        int id PK
        string report_month
        string agent_name
        int version_id FK
        int total_sessions
        float avg_confidence
    }

    multi_intent_decision_logs {
        int id PK
        text query
        string intent_a
        string intent_b
        boolean llm_result
        boolean human_label
    }

    knowledge_chunks[Qdrant Collection] {
        text content
        vector embedding
    }

    product_catalog[Qdrant Collection] {
        string name
        float price
        vector embedding
    }

    conversation_memory[Qdrant Collection] {
        int user_id
        text content
        vector embedding
    }
```

## 架构说明

系统数据层采用 **PostgreSQL + Qdrant** 的混合存储架构：

- **PostgreSQL**：存储所有结构化业务数据（用户、订单、退款、审计日志、记忆、配置等）
- **Qdrant**：存储向量数据，支持语义检索（知识库片段、商品目录、对话记忆）

核心实体关系：
- `users` 是中心实体，与订单、退款、审计日志、记忆、投诉工单等一对多关联
- `orders` 与 `refund_applications`、`audit_logs`、`complaint_tickets` 相关联
- `experiments` 与 `experiment_variants`、`experiment_assignments` 构成实验系统
- `graph_execution_logs` 记录每次图执行的元数据，`graph_node_logs` 记录各节点耗时

> 各表字段的详细说明请参考 [PostgreSQL 表字段参考](./tables-reference.md) 和 [Qdrant Collections](./qdrant-collections.md)。
