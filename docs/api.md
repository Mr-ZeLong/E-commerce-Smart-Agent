# API 文档

## 认证

所有 API 端点（除登录注册外）需要携带 JWT Token：

```http
Authorization: Bearer <token>
```

## 认证端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/login` | 用户登录 |
| POST | `/api/v1/register` | 用户注册 |
| GET | `/api/v1/me` | 获取当前用户信息 |

## 聊天端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/chat` | 流式对话（SSE） |

## 管理员端点

### 任务与决策

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/admin/tasks` | 待审核任务列表 |
| GET | `/api/v1/admin/tasks-all` | 所有任务统计 |
| GET | `/api/v1/admin/confidence-tasks` | 置信度触发任务 |
| POST | `/api/v1/admin/resume/{audit_log_id}` | 管理员决策 |

### 反馈管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/admin/feedback` | 反馈列表 |
| GET | `/api/v1/admin/feedback/export` | CSV 导出 |
| GET | `/api/v1/admin/feedback/csat` | CSAT 趋势 |
| POST | `/api/v1/admin/feedback/quality-score/run` | 运行质量评分 |

### 投诉工单

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/admin/complaints` | 投诉列表 |
| GET | `/api/v1/admin/complaints/{id}` | 投诉详情 |
| PATCH | `/api/v1/admin/complaints/{id}/assign` | 分配工单 |
| PATCH | `/api/v1/admin/complaints/{id}/status` | 更新状态 |
| PATCH | `/api/v1/admin/complaints/{id}/resolve` | 解决工单 |

### 实验管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/admin/experiments` | 创建实验 |
| GET | `/api/v1/admin/experiments` | 实验列表 |
| GET | `/api/v1/admin/experiments/{id}` | 实验详情 |
| POST | `/api/v1/admin/experiments/{id}/start` | 启动实验 |
| POST | `/api/v1/admin/experiments/{id}/pause` | 暂停实验 |
| POST | `/api/v1/admin/experiments/{id}/archive` | 归档实验 |
| GET | `/api/v1/admin/experiments/{id}/results` | 实验结果 |

### 分析数据

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/admin/analytics/csat` | CSAT 分析 |
| GET | `/api/v1/admin/analytics/complaint-root-causes` | 投诉根因 |
| GET | `/api/v1/admin/analytics/agent-comparison` | Agent 对比 |
| GET | `/api/v1/admin/analytics/traces` | 调用链路 |

### 评估与指标

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/admin/evaluation/dataset` | 评估数据集 |
| POST | `/api/v1/admin/evaluation/run` | 运行离线评估 |
| GET | `/api/v1/admin/metrics/sessions` | 会话统计 |
| GET | `/api/v1/admin/metrics/transfers` | 转接率 |
| GET | `/api/v1/admin/metrics/confidence` | 置信度指标 |
| GET | `/api/v1/admin/metrics/latency` | P99 延迟 |

### 知识库

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/admin/knowledge` | 文档列表 |
| POST | `/api/v1/admin/knowledge` | 上传文档 |
| DELETE | `/api/v1/admin/knowledge/{doc_id}` | 删除文档 |
| POST | `/api/v1/admin/knowledge/{doc_id}/sync` | 同步文档 |
| GET | `/api/v1/admin/knowledge/sync/{task_id}` | 同步状态 |

## WebSocket

| 路径 | 说明 |
|------|------|
| `/api/v1/ws/{thread_id}` | 用户端实时通知 |
| `/api/v1/ws/admin/{admin_id}` | 管理员端实时通知 |

消息格式为 JSON，类型包括 `status_change`、`alert` 等。
