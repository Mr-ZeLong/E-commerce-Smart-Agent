# E-commerce Smart Agent - 未完成功能点清单

> **生成时间:** 2026-04-16  
> **审核方式:** 代码静态分析 + 并行探索任务  
> **覆盖范围:** 前端、后端、基础设施、测试

---

## 🔴 Critical (必须完成)

### 1. WebSocket 前端集成完全缺失
**状态:** ⚠️ 未实现  
**影响:** 实时通知、任务状态更新、告警推送无法工作  
**涉及文件:**
- `frontend/src/hooks/useNotifications.ts` - 只有本地状态,无WebSocket连接
- `frontend/src/apps/admin/components/NotificationToast.tsx` - UI完整但无数据源
- `frontend/src/apps/customer/App.tsx` - 无WebSocket连接
- `frontend/src/apps/admin/App.tsx` - 无WebSocket连接

**具体缺失:**
```typescript
// 当前 useNotifications.ts 只有:
const [notifications, setNotifications] = useState<Notification[]>([])
// 完全没有WebSocket客户端代码,没有API轮询,没有SSE连接
```

**后端状态:** ✅ 已提供 WebSocket 端点
- `app/api/v1/websocket.py` - 用户和管理员WebSocket端点已完整实现
- `app/websocket/manager.py` - ConnectionManager已完整实现,包含广播功能

**需要实现:**
1. 创建 `frontend/src/hooks/useWebSocket.ts` - WebSocket连接管理
2. 修改 `useNotifications.ts` - 集成WebSocket消息接收
3. 修改 `Dashboard.tsx` - 添加WebSocket连接初始化
4. 修改 `NotificationToast.tsx` - 连接真实数据源

---

### 2. 自动告警系统 WebSocket 推送缺失
**状态:** ⚠️ TODO标记  
**文件:** `app/tasks/notifications.py:91`  
**代码:**
```python
# TODO: broadcast WebSocket alert to admin dashboards when manager is available
```

**影响:** 告警系统仅发送邮件,无法实时推送到管理后台  
**依赖:** 需要 WebSocket manager 在 Celery 上下文中可用

**需要实现:**
1. 在 Celery 任务中访问 WebSocket manager
2. 调用 `broadcast_to_admins()` 方法推送告警
3. 前端接收并显示告警通知

---

### 3. RAG Precision 评估指标 LLM Judge 未实现
**状态:** ⚠️ 仅回退实现  
**文件:** `app/evaluation/metrics.py:72`  
**代码:**
```python
if llm_judge:
    logger.warning("LLM judge for RAG precision is not implemented; falling back to heuristic.")
```

**当前实现:** 仅基于字符串匹配的启发式算法  
**缺失:** LLM-as-judge 的高质量评估逻辑

**需要实现:**
1. 使用 LLM 评估检索片段与问题的相关性
2. 实现评分 Prompt
3. 支持 batch 评估提高效率

---

### 4. 关键后端模块缺少测试
**状态:** ❌ 无测试文件  

| 模块 | 文件 | 说明 |
|------|------|------|
| ComplaintAgent | `app/agents/complaint.py` | **完全无测试** |
| IntentRouterAgent | `app/agents/router.py` | **完全无测试** |
| ConfidenceEvaluator | `app/agents/evaluator.py` | **完全无测试** |
| ConfigLoader | `app/agents/config_loader.py` | **完全无测试** |

---

### 5. Admin 子路由 API 测试缺失
**状态:** ❌ 无测试覆盖  
**目录:** `tests/admin/`  

**现状:**
- `tests/admin/` 仅包含 `test_agent_config_api.py`
- `test_admin_api.py` 覆盖了核心端点 (`/tasks`, `/decisions`, `/conversations`)
- **以下子路由完全无 API 测试:**
  - `/api/v1/admin/feedback` - 反馈列表、导出、CSAT、质量评分
  - `/api/v1/admin/complaints` - 投诉工单 CRUD
  - `/api/v1/admin/experiments` - 实验管理 CRUD
  - `/api/v1/admin/analytics` - 分析数据端点
  - `/api/v1/admin/evaluation/*` - 评估数据集/运行
  - `/api/v1/admin/metrics/*` - 性能指标
  - `/api/v1/admin/confidence-tasks` - 置信度任务

**影响:** 这些端点涉及权限校验和业务逻辑,缺少回归测试保障

---

## 🟠 High (重要但非阻塞)

### 6. 前端 CI/CD 完全缺失
**状态:** ❌ 未配置  
**文件:** `.github/workflows/ci.yml`  

**当前状态:** CI 只包含后端测试
```yaml
# 现有步骤:
- Lint with ruff
- Type check with ty
- Run evaluation tests
- Run tests with coverage
# 缺失:
# - 前端 build
# - 前端 lint
# - 前端 type check
# - E2E 测试
```

**需要实现:**
1. 添加 Node.js 安装步骤
2. 添加 `cd frontend && npm ci`
3. 添加 `cd frontend && npm run build`
4. 添加 `cd frontend && npm run lint`
5. 添加 `cd frontend && npm run test:e2e`

---

### 7. 文档严重不足
**状态:** ⚠️ 仅1个文档文件  
**目录:** `docs/`  

**当前文件:**
- `docs/resume-guide.md` - 与项目无关的个人简历指南

**缺失文档:**
| 文档 | 优先级 | 内容 |
|------|--------|------|
| API 文档 | High | 所有 REST API 端点说明 |
| 部署指南 | High | Docker 部署、K8s 部署 |
| 开发指南 | High | 本地开发、调试、测试 |
| 架构决策记录 | Medium | ADR 文档 |
| 操作手册 | Medium | 运维、监控、故障排查 |
| 用户手册 | Medium | 管理员后台使用指南 |

---

### 8. Admin Feedback 管理界面完全缺失
**状态:** ❌ 未实现  
**影响:** 后端 Feedback API 完整,但前端无任何入口查看反馈数据

**后端状态:** ✅ 完整实现
- `app/api/v1/admin/feedback.py` 提供 4 个端点:
  - `GET /admin/feedback` - 反馈列表
  - `GET /admin/feedback/export` - CSV 导出
  - `GET /admin/feedback/csat` - CSAT 趋势
  - `POST /admin/feedback/quality-score/run` - 质量评分

**前端状态:** ❌ 完全缺失
- 无 `useFeedback.ts` hook
- `Dashboard.tsx` 无 Feedback tab
- 无反馈列表/导出/CSAT 组件

**这是真实的前后端能力不匹配,优先级应高于页面 stub。**

---

### 9. 后端模块测试覆盖率过低
**状态:** ⚠️ 低于 40% 覆盖率  

| 模块 | 覆盖率 | 文件路径 |
|------|--------|----------|
| `email.py` | 25% | `app/core/email.py` |
| `experiment_assigner.py` | 22% | `app/services/experiment_assigner.py` |
| `experiment.py` | 27% | `app/services/experiment.py` |
| `online_eval.py` | 36% | `app/services/online_eval.py` |
| `notifications.py` | 29% | `app/tasks/notifications.py` |
| `knowledge_tasks.py` | 31% | `app/tasks/knowledge_tasks.py` |
| `complaint_tool.py` | 32% | `app/tools/complaint_tool.py` |
| `reranker.py` | 45% | `app/retrieval/reranker.py` |
| `manager.py` | 46% | `app/websocket/manager.py` |

---

## 🟡 Medium (建议完成)

### 10. 通知铃铛不可点击
**状态:** ⚠️ UI 不完整  
**文件:** `frontend/src/apps/admin/pages/Dashboard.tsx:61-68`  

**当前:** 铃铛图标显示未读数量,但点击无反应  
**期望:** 点击显示通知下拉列表

---

### 11. 易碎测试 (Flaky Test)
**状态:** ⚠️ 在完整测试套件中失败,单独运行通过  
**文件:** `tests/test_auth_rate_limit.py`  
**测试:** `test_register_allows_five_requests_per_minute`  
**问题:** 测试隔离问题,可能影响 CI 稳定性

---

## 🟢 Low (可选优化)

### 12. 前端 Admin 页面缺失
**状态:** ❌ 页面文件不存在  
**目录:** `frontend/src/apps/admin/pages/`  

**缺失页面:**
- `Feedback.tsx` - 反馈管理页面 (真正缺失,后端 API 已存在)

**已在 Dashboard tabs 中实现,无需独立页面:**
- `Notifications` - 已作为 `NotificationToast` 组件在 Dashboard 中
- `Tasks` - 已作为 `TaskList`/`TaskDetail` 组件在 Dashboard 中

**注意:** `KnowledgeBase.tsx` 当前是 stub,仅包装 `KnowledgeBaseManager` 组件

---

### 13. Dockerfile 缺少辅助文件
**状态:** ⚠️ 技术负债  
**文件:** `Dockerfile`  

**缺失项:**
- `start.sh` 未复制
- `start_worker.sh` 未复制
- `scripts/` 目录未复制

**说明:** `docker-compose.yaml` 直接覆盖了启动命令,所以这不影响当前部署方式。但在纯 Docker 运行时会有问题。

---

### 14. 代码样式统一
**状态:** ⚠️ 存在 pass 空语句  
**文件:**
- `app/services/admin_service.py:20,24` - Exception 类定义后的 pass
- `app/retrieval/rewriter.py:183` - 方法末尾的 pass
- `app/api/v1/websocket.py:79,139` - except WebSocketDisconnect 后的 pass
- `app/agents/base.py:37` - 抽象方法后的 pass
- `app/observability/otel_setup.py:22` - except 后的 pass
- `app/tools/base.py:20` - 抽象方法后的 pass
- `app/intent/multi_intent.py:14` - 抽象方法后的 pass

**注意:** 这些是合法的 Python 语法,不是bug,只是代码风格问题

---

### 15. 前端测试覆盖
**状态:** ⚠️ E2E 测试可能不完整  
**目录:** `frontend/`  

**状态:** Playwright 配置存在,仅有 2 个 E2E 测试文件,无前端单元测试
- `frontend/e2e/customer-chat.spec.ts`
- `frontend/e2e/admin-dashboard.spec.ts`

---

## 📊 按模块统计

| 模块 | Critical | High | Medium | Low | 总计 |
|------|----------|------|--------|-----|------|
| **前端** | 1 (WebSocket) | 2 (CI+Feedback) | 1 | 2 | 6 |
| **后端** | 2 (告警+RAG) | 0 | 0 | 1 | 3 |
| **基础设施** | 0 | 1 (文档) | 0 | 1 | 2 |
| **测试** | 2 (缺失测试) | 1 (低覆盖率) | 1 (易碎) | 0 | 4 |
| **总计** | **5** | **4** | **2** | **4** | **15** |

---

## 🎯 推荐优先级

### Sprint 1 (立即开始) - 核心功能
1. **WebSocket 前端集成** (#1) - 影响实时通知核心功能
2. **告警系统 WebSocket 推送** (#2) - 配合#1完成实时告警
3. **关键后端模块缺少测试** (#4) - ComplaintAgent, IntentRouterAgent, ConfidenceEvaluator, ConfigLoader
4. **Admin 子路由 API 测试** (#5) - feedback/complaints/experiments/analytics
5. **Admin Feedback 管理界面** (#8) - 后端 API 完整但前端完全缺失

### Sprint 2 (下个迭代) - 质量提升
6. **RAG Precision LLM Judge** (#3) - 提升评估质量
7. **前端 CI/CD** (#6) - 防止前端代码质量问题
8. **修复易碎测试** (#11) - `test_register_allows_five_requests_per_minute`
9. **提升低覆盖率模块** (#9) - 优先 email.py (25%), experiment_assigner.py (22%)

### Sprint 3 (后续优化)
10. **文档补充** (#7) - API文档、部署指南
11. **通知铃铛交互** (#10) - 添加下拉列表
12. **前端页面完善** (#12) - 独立 Feedback.tsx 页面
13. **Dockerfile 优化** (#13) - 复制 start.sh 和 scripts/ 目录
14. **代码样式统一** (#14) - 清理冗余 pass 语句
15. **前端测试覆盖** (#15) - 补充 E2E/单元测试

---

## 📈 测试基线

**运行结果 (验证时):**
- `pytest --cov=app`: **528 passed**, 0 failed
- 总覆盖率: **~76%** (满足 75% CI 门限)
- **注意**: `test_register_allows_five_requests_per_minute` 在完整套件中偶发失败(易碎测试),单独运行可通过。

---

## ✅ 已验证完成的模块

以下功能已确认完整实现,无需额外工作:

### 后端 API (全部完整)
- ✅ `app/api/v1/admin/__init__.py` - 管理员核心 API
- ✅ `app/api/v1/admin/agent_config.py` - Agent 配置中心 (294行)
- ✅ `app/api/v1/admin/analytics.py` - 高级分析 (201行)
- ✅ `app/api/v1/admin/complaints.py` - 投诉工单管理 (188行)
- ✅ `app/api/v1/admin/experiments.py` - A/B 实验管理 (181行)
- ✅ `app/api/v1/admin/feedback.py` - 反馈评估 (116行)
- ✅ `app/api/v1/websocket.py` - WebSocket 端点 (143行)

### 后端服务 (全部完整)
- ✅ `app/services/admin_service.py` - 管理员服务
- ✅ `app/services/online_eval.py` - 在线评估
- ✅ `app/services/experiment.py` - 实验服务
- ✅ `app/services/experiment_assigner.py` - 实验流量分配
- ✅ `app/memory/extractor.py` - 事实抽取器
- ✅ `app/memory/summarizer.py` - 会话摘要器
- ✅ `app/websocket/manager.py` - WebSocket 连接管理器

### 评估与脚本 (全部完整)
- ✅ `app/evaluation/pipeline.py` - 离线评估流水线
- ✅ `app/evaluation/metrics.py` - 评估指标 (LLM Judge 待实现除外)
- ✅ `scripts/run_evaluation.py` - 评估执行脚本
- ✅ `tests/evaluation/golden_dataset_v1.jsonl` - 138条记录
- ✅ `scripts/seed_data.py` - 数据初始化
- ✅ `scripts/etl_qdrant.py` - 知识库 ETL
- ✅ `scripts/verify_db.py` - 数据库验证

### 前端组件 (全部完整)
- ✅ `Dashboard.tsx` - 管理后台仪表盘
- ✅ `KnowledgeBaseManager.tsx` - 知识库管理
- ✅ `AgentConfigEditor.tsx` - Agent 配置编辑器
- ✅ `ComplaintQueue.tsx` - 投诉队列 (539行)
- ✅ `ExperimentManager.tsx` - 实验管理 (443行)
- ✅ `AnalyticsV2.tsx` - 高级分析 (311行)
- ✅ `DecisionPanel.tsx` - 决策面板
- ✅ `TaskList.tsx` / `TaskDetail.tsx` - 任务管理
- ✅ `ConversationLogs.tsx` - 会话日志
- ✅ `EvaluationViewer.tsx` - 评估查看器
- ✅ `Performance.tsx` - 性能指标

### 前端 Hooks (全部完整且被使用)
- ✅ `useAuth.ts`
- ✅ `useTasks.ts`
- ✅ `useKnowledgeBase.ts`
- ✅ `useAgentConfig.ts`
- ✅ `useComplaints.ts`
- ✅ `useEvaluation.ts`
- ✅ `useMetrics.ts`
- ✅ `useAnalytics.ts`
- ✅ `useConversations.ts`
- ✅ `useExperiments.ts`
- ✅ `useChat.ts` (功能完整,已正确使用 `apiFetch`)

---

## 📝 备注

### 关于 README 中提到的"待实现"

根据代码审查,README 中提到的以下"待实现"项实际上**已完成**:

| README 描述 | 实际状态 | 证据 |
|------------|---------|------|
| "前端 WebSocket 集成待实现" | ⚠️ 确实未完成 | 前端无 WebSocket 代码 |
| "自动告警系统 WebSocket 推送待实现" | ⚠️ 确实未完成 | notifications.py:91 有 TODO |
| "前端实时通知待实现" | ⚠️ 确实未完成 | 依赖 WebSocket |
| Agent 配置中心 | ✅ 已完成 | agent_config.py 294行完整实现 |
| 投诉工单管理 | ✅ 已完成 | complaints.py 188行完整实现 |
| A/B 实验管理 | ✅ 已完成 | experiments.py 181行完整实现 |
| 高级分析面板 | ✅ 已完成 | AnalyticsV2.tsx 完整实现 |

---

**文档生成者:** Sisyphus Agent  
**审核状态:** 基于静态代码分析,建议开发团队review确认
