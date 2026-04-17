# Qdrant Collections

## knowledge_chunks
| 字段 | 类型 | 说明 |
|------|------|------|
| content | text | 文档内容 |
| source | string | 来源文档 |
| meta_data | json | 元数据 |
| embedding | vector | 向量嵌入 |

## product_catalog
| 字段 | 类型 | 说明 |
|------|------|------|
| name | string | 商品名称 |
| description | text | 商品描述 |
| price | float | 价格 |
| category | string | 分类 |
| sku | string | SKU |
| in_stock | boolean | 是否有货 |
| attributes | json | 属性 |
| embedding | vector | 向量嵌入 |

## conversation_memory
| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | int | 用户 ID |
| thread_id | string | 会话 ID |
| message_role | string | 消息角色 |
| content | text | 内容 |
| timestamp | datetime | 时间戳 |
| intent | string | 意图 |
| embedding | vector | 向量嵌入 |
