# E-commerce Smart Agent 文档

## 目录

- [开发指南](./development.md) — 本地开发环境搭建、调试、测试
- [API 文档](./api.md) — REST API 端点说明
- [部署指南](./deployment.md) — Docker / K8s 部署
- [架构决策记录](./adr.md) — 关键设计决策

## 项目简介

E-commerce Smart Agent 是一个面向电商场景的智能客服系统，基于 FastAPI + LangGraph 构建，支持多意图识别、知识库检索、实时 WebSocket 通知、管理员后台等功能。

## 快速开始

```bash
# 一键启动（基础设施 + 后端 + 前端构建）
./start.sh

# 手动启动后端
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 手动启动前端
cd frontend && npm run dev
```

## 技术栈

- **后端**: Python 3.12, FastAPI, SQLModel, LangGraph, Celery
- **前端**: React 19, TypeScript, Vite, Tailwind CSS, shadcn/ui
- **基础设施**: PostgreSQL, Redis, Qdrant
