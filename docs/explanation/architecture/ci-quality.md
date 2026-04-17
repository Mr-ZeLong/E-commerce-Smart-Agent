# CI 与代码质量

## 质量工具链

| 工具 | 用途 | 配置位置 |
|---|---|---|
| ruff | Lint + Format | `.pre-commit-config.yaml`, `pyproject.toml` |
| ty | 类型检查 | `.pre-commit-config.yaml` |
| pytest | 单元/集成测试 | `pyproject.toml` |
| GitHub Actions | CI 流水线 | `.github/workflows/ci.yml` |

## CI 流程

1. 检出代码
2. 设置 Python 3.12 + uv 0.6.5
3. 创建 test database
4. Cache uv dependencies (`actions/cache@v4`)
5. `uv sync` 安装依赖
6. `uv run ruff check app tests`
7. `uv run ty check --error-on-warning app tests`
8. `uv run pytest tests/evaluation/ -v -s`
9. `uv run pytest --cov=app --cov-fail-under=75`

## 本地质量检查

```bash
# 安装 pre-commit hook
pre-commit install

# 手动检查
uv run ruff check app tests --fix
uv run ruff format app tests
uv run ty check --error-on-warning app tests
```

> 前端代码质量检查请参考 [常用命令速查表](../../reference/command-cheatsheet.md)。
