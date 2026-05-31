# 贡献指南

## 开发环境

```bash
poetry install --with dev
pre-commit install
```

## 代码规范

- ruff lint + format
- mypy strict 类型检查
- 单元测试覆盖率 ≥80%

## PR 流程

1. Fork & Clone
2. 创建 feature 分支
3. 编写代码 + 测试
4. `make lint typecheck test`
5. 提交 PR
