# 表字段参考：PostgreSQL 数据表

## users
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | 用户主键 |
| username | string UK | 用户名 |
| password_hash | string | 密码哈希 |
| email | string UK | 邮箱 |
| full_name | string | 全名 |
| phone | string | 手机号 |
| is_admin | boolean | 是否管理员 |
| is_active | boolean | 是否激活 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

## orders
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | 订单主键 |
| order_sn | string UK | 订单号 |
| user_id | int FK | 用户 ID |
| status | string | 订单状态 |
| total_amount | decimal | 总金额 |
| items | json | 商品明细 |
| tracking_number | string | 物流单号 |
| shipping_address | string | 收货地址 |
| delivered_at | datetime | 签收时间 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

## refund_applications
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | 退款申请主键 |
| order_id | int FK | 订单 ID |
| user_id | int FK | 用户 ID |
| status | string | 申请状态 |
| reason_category | string | 原因分类 |
| reason_detail | text | 详细原因 |
| refund_amount | decimal | 退款金额 |
| admin_note | text | 管理员备注 |
| reviewed_by | int | 审核人 ID |
| reviewed_at | datetime | 审核时间 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

## audit_logs
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | 审计日志主键 |
| thread_id | string | 会话 ID |
| order_id | int FK | 订单 ID |
| refund_application_id | int FK | 退款申请 ID |
| user_id | int FK | 用户 ID |
| trigger_reason | text | 触发原因 |
| risk_level | string | 风险等级 |
| audit_level | string | 审计级别 |
| trigger_type | string | 触发类型 |
| action | string | 处理动作 |
| admin_id | int | 管理员 ID |
| admin_comment | text | 管理员评论 |
| context_snapshot | json | 上下文快照 |
| decision_metadata | json | 决策元数据 |
| confidence_metadata | json | 置信度元数据 |
| created_at | datetime | 创建时间 |
| reviewed_at | datetime | 审核时间 |
| updated_at | datetime | 更新时间 |

## message_cards
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | 消息卡片主键 |
| thread_id | string | 会话 ID |
| message_type | string | 消息类型 |
| status | string | 状态 |
| content | json | 内容 |
| meta_data | json | 元数据 |
| sender_type | string | 发送者类型 |
| sender_id | int | 发送者 ID |
| receiver_id | int | 接收者 ID |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

## knowledge_documents
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | 文档主键 |
| filename | string | 文件名 |
| storage_path | string | 存储路径 |
| content_type | string | 内容类型 |
| doc_size_bytes | int | 文件大小 |
| sync_status | string | 同步状态 |
| sync_message | string | 同步消息 |
| last_synced_at | datetime | 最后同步时间 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

## supervisor_decisions
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | 决策记录主键 |
| thread_id | string | 会话 ID |
| primary_intent | string | 主意图 |
| pending_intents | string | 待处理意图 |
| selected_agents | string | 选中的 Agent |
| execution_mode | string | 执行模式 |
| reasoning | text | 推理说明 |
| created_at | datetime | 创建时间 |

## user_profiles
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | 画像主键 |
| user_id | int FK | 用户 ID |
| membership_level | string | 会员等级 |
| preferred_language | string | 偏好语言 |
| timezone | string | 时区 |
| total_orders | int | 总订单数 |
| lifetime_value | float | 生命周期价值 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

## user_preferences
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | 偏好主键 |
| user_id | int FK | 用户 ID |
| preference_key | string | 偏好键 |
| preference_value | string | 偏好值 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

## interaction_summaries
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | 摘要主键 |
| user_id | int FK | 用户 ID |
| thread_id | string | 会话 ID |
| summary_text | text | 摘要文本 |
| resolved_intent | string | 已解决意图 |
| satisfaction_score | float | 满意度评分 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

## user_facts
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | 事实主键 |
| user_id | int FK | 用户 ID |
| fact_type | string | 事实类型 |
| content | text | 内容 |
| confidence | float | 置信度 |
| source_thread_id | string | 来源会话 ID |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

## agent_configs
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | 配置主键 |
| agent_name | string UK | Agent 名称 |
| system_prompt | text | 系统提示词 |
| previous_system_prompt | text | 上一版提示词 |
| confidence_threshold | float | 置信度阈值 |
| max_retries | int | 最大重试次数 |
| enabled | boolean | 是否启用 |
| updated_at | datetime | 更新时间 |

## agent_config_audit_logs
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | 审计主键 |
| agent_name | string | Agent 名称 |
| changed_by | int | 修改人 ID |
| field_name | string | 字段名 |
| old_value | text | 旧值 |
| new_value | text | 新值 |
| created_at | datetime | 创建时间 |

## complaint_tickets
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | 工单主键 |
| user_id | int FK | 用户 ID |
| thread_id | string | 会话 ID |
| order_sn | string | 订单号 |
| category | string | 投诉类别 |
| urgency | string | 紧急程度 |
| status | string | 工单状态 |
| description | text | 投诉描述 |
| expected_resolution | string | 期望解决方式 |
| assigned_to | int FK | 分配处理人 ID |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

## message_feedbacks
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | 反馈主键 |
| user_id | int FK | 用户 ID |
| thread_id | string | 会话 ID |
| message_index | int | 消息索引 |
| score | int | 评分 |
| comment | text | 评论 |
| created_at | datetime | 创建时间 |

## quality_scores
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | 质量评分主键 |
| score_date | date | 评分日期 |
| score_type | string | 评分类型 |
| total_sessions | int | 总会话数 |
| human_transfer_rate | float | 人工转接率 |
| avg_confidence | float | 平均置信度 |
| avg_turns | float | 平均轮数 |
| implicit_satisfaction_rate | float | 隐式满意度 |
| explicit_upvotes | int | 点赞数 |
| explicit_downvotes | int | 点踩数 |
| immediate_transfer_count | int | 立即转接数 |
| contradictory_followup_count | int | 矛盾跟进数 |
| low_confidence_retry_count | int | 低置信度重试数 |
| intent_breakdown | json | 意图分布 |
| top_degraded_intents | json |  top 退化意图 |
| sample_trace_ids | json | 样本 Trace ID |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

## graph_execution_logs
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | 执行日志主键 |
| thread_id | string | 会话 ID |
| user_id | int FK | 用户 ID |
| intent_category | string | 意图分类 |
| final_agent | string | 最终 Agent |
| confidence_score | float | 置信度分数 |
| needs_human_transfer | boolean | 是否需要人工 |
| langsmith_run_url | text | LangSmith 链接 |
| total_latency_ms | int | 总延迟(ms) |
| created_at | datetime | 创建时间 |

## graph_node_logs
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | 节点日志主键 |
| execution_id | int FK | 执行日志 ID |
| node_name | string | 节点名称 |
| latency_ms | int | 节点延迟(ms) |
| created_at | datetime | 创建时间 |

## experiments
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | 实验主键 |
| name | string | 实验名称 |
| description | text | 实验描述 |
| status | string | 实验状态 |
| target_dimensions | json | 目标维度 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

## experiment_variants
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | 变体主键 |
| experiment_id | int FK | 实验 ID |
| name | string | 变体名称 |
| weight | int | 权重 |
| system_prompt | text | 系统提示词 |
| llm_model | string | LLM 模型 |
| retriever_top_k | int | 检索 TopK |
| reranker_enabled | boolean | 是否启用重排序 |
| extra_config | json | 额外配置 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

## experiment_assignments
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | 分配主键 |
| experiment_id | int FK | 实验 ID |
| variant_id | int FK | 变体 ID |
| user_id | int FK | 用户 ID |
| created_at | datetime | 创建时间 |

## routing_rules
| 字段 | 类型 | 说明 |
|------|------|------|
| id | int PK | 规则主键 |
| intent_category | string | 意图分类 |
| target_agent | string | 目标 Agent |
| priority | int | 优先级 |
| condition_json | json | 条件 JSON |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |
