# 项目文件结构

```text
E-commerce-Smart-Agent/
├── 📄 README.md                    # 项目文档
├── 📄 AGENTS.md                    # AI Agent 开发规范
├── 📄 .env.example                 # 环境变量模板
├── 📄 .gitignore                   # Git 忽略规则
├── 📄 alembic.ini                  # Alembic 迁移配置
├── 📄 pyproject.toml               # Python 项目配置 (uv)
├── 📄 uv.lock                      # uv 依赖锁定文件
├── 📄 docker-compose.yaml          # 容器编排配置
├── 📄 start_worker.sh              # 推荐：Celery Worker 启动脚本（含健康检查）
├── 📄 celery_worker.py             # Celery Worker Python 入口
│
├── 📁 app/                         # 主应用目录
│   ├── 📄 main.py                  # FastAPI 应用入口
│   ├── 📄 celery_app.py            # Celery 配置
│   ├── 📁 api/v1/                  # API 路由层
│   │   └── 📁 admin/               # B 端管理后台 API（Agent 配置、投诉、分析、反馈、实验、指标、告警、审核队列、Token 用量）
│   ├── 📁 core/                    # 核心基础设施（配置、安全、数据库、Redis、LLM 工厂、缓存、结构化日志）
│   ├── 📁 observability/           # 可观测性基础设施（追踪、指标、告警规则、Token 追踪）
│   ├── 📁 models/                  # 数据库模型 (SQLModel)
│   ├── 📁 memory/                  # 记忆系统（结构化记忆、事实提取、摘要、向量管理）
│   ├── 📁 graph/                   # LangGraph 核心逻辑（工作流编译器、检查点、子图、并行调度）
│   ├── 📁 agents/                  # Agent 实现层
│   ├── 📁 tools/                   # Agent Tool 层
│   ├── 📁 evaluation/              # 离线评估框架
│   ├── 📁 confidence/              # 置信度信号模块
│   ├── 📁 context/                 # 上下文优化（Token 预算、观察掩码、PII 过滤）
│   ├── 📁 utils/                   # 通用工具函数
│   ├── 📁 intent/                  # 意图识别模块（分类器、安全过滤、少样本加载）
│   ├── 📁 retrieval/               # RAG 检索层（稠密+稀疏向量、重排序、查询重写）
│   ├── 📁 services/                # 业务服务层（告警、审核队列、在线评估）
│   ├── 📁 schemas/                 # 共享 Schema
│   ├── 📁 tasks/                   # Celery 异步任务（内存、通知、退款、评估、自动恢复、检查点清理）
│   ├── 📁 websocket/               # WebSocket 服务
│   └── 📁 safety/                  # 输出内容安全审核
│
├── 📁 frontend/                    # React + TypeScript 前端
│   ├── 📄 package.json             # npm 依赖配置
│   ├── 📄 vite.config.ts           # Vite 多页面配置
│   ├── 📄 tailwind.config.ts       # Tailwind CSS 配置
│   ├── 📄 tsconfig.json            # TypeScript 配置
│   ├── 📄 index.html               # C端入口
│   ├── 📄 admin.html               # B端入口
│   └── 📁 src/
│       ├── 📁 apps/                # C端/B端应用
│       ├── 📁 components/          # 共享组件
│       ├── 📁 assets/              # 静态资源
│       ├── 📁 lib/                 # 共享基础设施
│       ├── 📁 stores/              # Zustand 状态管理
│       ├── 📁 hooks/               # 自定义 Hooks
│       └── 📁 types/               # TypeScript 类型定义
│
├── 📁 scripts/                     # 辅助脚本
│   ├── 📄 seed_data.py             # 数据库初始化数据
│   ├── 📄 seed_large_data.py       # 大批量测试数据
│   ├── 📄 seed_product_catalog.py  # 商品目录种子数据
│   ├── 📄 etl_qdrant.py            # 知识库 ETL
│   ├── 📄 run_evaluation.py        # 离线评估脚本
│   ├── 📄 adversarial_run.py       # 对抗测试脚本
│   ├── 📄 generate_golden_v2.py    # 生成 Golden Dataset v2
│   └── 📄 verify_db.py             # 数据库验证脚本
│
├── 📁 migrations/                  # Alembic 数据库迁移
├── 📁 assets/                      # 截图与静态资源
├── 📁 data/                        # 静态数据
├── 📁 docs/                        # 项目文档 (Diátaxis 结构)
│   ├── 📁 tutorials/               # 教程
│   ├── 📁 how-to-guides/           # 操作指南
│   ├── 📁 explanation/             # 解释说明
│   │   ├── 📁 architecture/        # 系统架构
│   │   ├── 📁 prompt-engineering/  # Prompt 工程
│   │   └── 📁 context-engineering/ # 上下文工程
│   └── 📁 reference/               # 参考资料
├── 📁 .github/                     # GitHub Actions 工作流
└── 📁 tests/                       # 测试文件
```

> 完整目录树及各文件详细说明，请参考源码仓库。
