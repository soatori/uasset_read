# CLAUDE.md

## 行为规则

- 所有对话、代码注释、错误提示、文档统一使用中文
- 输出专业简洁

## 项目概述

**uasset_read** — 虚幻引擎 `.uasset` 文件的 Python 解析器。专注于未烘焙/编辑器保存的资产（含完整蓝图数据）。

- **版本**: 0.4.4-dev | **Python**: 3.10+ | **运行时依赖**: 零依赖
- 构建系统: 直接脚本运行（src 布局）
- 详细开发指南（测试、CLI、架构、模块索引）见 [docs/guides/dev-guide.md](docs/guides/dev-guide.md)
- 参考UE虚幻引擎源码 "E:\Develop\lib\UnrealEngine"

## 关键约束

见 [.claude/rules/constraints.md](.claude/rules/constraints.md)

## 测试要点

- 位置: `tests/`（994 用例通过，2 xfail，40+ 集成测试）
- 要求: ≥ 800 单元测试，100% 通过率，≥ 12 种资产类型
- 稳定资产必须在 strict 和 tolerant 双模式下通过
- 详细规范见 [docs/guides/dev-guide.md](docs/guides/dev-guide.md) 的"测试"章节

## 文档结构

```
docs/
├── guides/          ← 开发规范（活跃参考）
│   ├── dev-guide.md         开发指南（架构、模块、CLI、测试）
│   ├── development-scope.md  开发范围及限制（IN/OUT OF SCOPE）
│   └── testing-requirements.md  测试要求规范
├── formats/uasset/  ← UE .uasset 格式参考
│   ├── Index.md             主索引，文档导航入口
│   ├── assets/              资产类型详解（50+ 文件）
│   ├── serialization/       序列化机制（PropertyTag、BulkData 等）
│   ├── cooked/              Cooked 格式（Pak、IoStore）
│   └── version/             版本演进（UE4/UE5 历史、迁移指南）
├── designs/         ← 永久设计规格
│   ├── real-asset-test-suite-design.md
│   ├── development-scope-refined-design.md
│   └── output-format-ir-design.md
├── reference/       ← 技术参考资料（蓝图节点参考、UE 加载流程、C++ 转换指南等）
├── reports/         ← 技术报告
└── release-notes/   ← 版本发布说明

wiki/                ← 代码指南（独立维护，wiki 镜像）
temp/                ← 临时文件、脚本、中间产物、session 归档
```

## Agent skills

### Issue tracker

使用 GitHub Issues 跟踪任务（gh CLI）。详见 `docs/agents/issue-tracker.md`。

### Triage labels

五个标准角色标签：needs-triage, needs-info, ready-for-agent, ready-for-human, wontfix。详见 `docs/agents/triage-labels.md`。

### Domain docs

单上下文布局。详见 `docs/agents/domain.md`。
