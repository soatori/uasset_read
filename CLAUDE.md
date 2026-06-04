# CLAUDE.md

## 行为规则
- 所有对话、代码注释、错误提示、文档统一使用中文
- 输出专业简洁

## 项目概述

**uasset_read** — 虚幻引擎 `.uasset` 文件的 Python 解析器。专注于未烘焙/编辑器保存的资产（含完整蓝图数据）。

- **版本**: 0.4.1-dev | **Python**: 3.10+ | **运行时依赖**: 零依赖
- 构建系统: setuptools（src 布局）
- 详细开发指南（测试、CLI、架构、模块索引）见 [docs/dev-guide.md](docs/dev-guide.md)

## CodeGraph

优先使用 `codegraph_*` 工具回答结构化问题（符号定义、调用链、影响范围）。详细规则见全局 CLAUDE.md。

## 关键约束

- **仅支持未烘焙/编辑器保存的资产** — Cooked 资产的图数据已被剥离
- **只读** — 仅解析，不支持修改或写入
- **零运行时依赖** — 不向 `dependencies` 添加第三方包（PAK 可选依赖在 `optional-dependencies` 中）
- **必须参考 UE 源码** — 格式理解必须追溯到 UE C++ 源码，禁止猜测二进制
- **GUID 格式统一** — Pin GUID 在源头标准化为 32 位小写 hex（无 dashes），比较前统一格式
- **FText 偏移安全网** — 图序列化器包含 safety net 检测偏移错位，遇到时自动校正
- **临时文件放 `temp/`** — 脚本、中间输出、调试日志、测试产物一律放在项目根目录 `temp/` 子目录

## 测试要点

- 位置: `tests/`（824+ 用例，40+ 集成测试）
- 要求: ≥ 800 单元测试，100% 通过率，≥ 12 种资产类型
- 稳定资产必须在 strict 和 tolerant 双模式下通过
- 详细规范见 [docs/dev-guide.md](docs/dev-guide.md) 的"测试"章节
