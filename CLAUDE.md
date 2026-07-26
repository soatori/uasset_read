# CLAUDE.md

本仓库的 Claude Code 项目规范。

## 基本规则

- 所有代码注释、错误消息和文档均使用英文；输出保持专业简洁。
- 项目简介：`uasset_read` 是一个 Python 3.10+ 零运行时依赖的 Unreal `.uasset` 解析器，支持未烘焙/编辑器保存的资产（含完整蓝图数据）。
- Windows 路径使用 `E:/Develop/...` 或双反斜杠；测试样本位于 `tests/samples/`。

## 代码理解

- CodeGraph（`.codegraph/`）仍为代码探索和调用路径追踪的主要工具。
- 代码搜索、跳转定义、查看引用、重构和深度分析时，**优先使用基于 LSP 的插件**（如 `pylsp`、`pyright`、`jedi`），而非原始的 grep/find。

## 约束条件

完整约束见 `.claude/rules/constraints.md`。要点：只读、零运行时依赖、禁止 `pip install`。

## 分支与提交

- `develop` 日常开发；`master` 发布；`wiki/master` Wiki 维护。
- `master` 仅允许 `src/`、CI、README、`CLAUDE.md`、`pytest.ini`、`run.py`、`tests/`、指定的 `docs/`、`.claude/rules/`。
- 提交格式：`<类型>: <简述> (#issue)`，类型：`feat`、`fix`、`refactor`、`test`、`docs`、`chore`、`release`；issue 号可选。

## 文档结构

- `wiki/`：开发者指南
- `docs/formats/uasset/`：UE 格式参考
- `docs/designs/`、`docs/reference/`、`docs/release-notes/`：设计、参考和发布文档
- Issue 跟踪：GitHub Issues（`gh` CLI）；见 `docs/agents/issue-tracker.md`
