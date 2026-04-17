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
├── 📄 celery_worker.py             # Celery Worker 启动脚本
│
├── 📁 app/                         # 主应用目录
│   ├── 📄 main.py                  # FastAPI 应用入口
│   ├── 📄 celery_app.py            # Celery 配置
│   ├── 📁 api/v1/                  # API 路由层
│   ├── 📁 core/                    # 核心基础设施
│   ├── 📁 observability/           # 可观测性基础设施
│   ├── 📁 models/                  # 数据库模型 (SQLModel)
│   ├── 📁 memory/                  # 记忆系统
│   ├── 📁 graph/                   # LangGraph 核心逻辑
│   ├── 📁 agents/                  # Agent 实现层
│   ├── 📁 tools/                   # Agent Tool 层
│   ├── 📁 confidence/              # 置信度信号模块
│   ├── 📁 context/                 # 上下文优化（Token 预算、观察掩码）
│   ├── 📁 utils/                   # 通用工具函数
│   ├── 📁 intent/                  # 意图识别模块
│   ├── 📁 retrieval/               # RAG 检索层
│   ├── 📁 services/                # 业务服务层
│   ├── 📁 schemas/                 # 共享 Schema
│   ├── 📁 tasks/                   # Celery 异步任务
│   └── 📁 websocket/               # WebSocket 服务
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
