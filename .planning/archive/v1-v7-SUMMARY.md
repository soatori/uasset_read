# v1.0 – v7.0 归档摘要

> 原始 541 个 Markdown 文件已压缩为此摘要。完整历史文件在 git 中可恢复：
> `git checkout <commit> -- .planning/archive/v1.0-mvp/` 等。

## v1.0 MVP (2026-04-28) — 91 文件 → 摘要

**核心成就**: 建立 `.uasset` 文件解析基础管道
- FArchive 二进制读取器（字节交换/mmap）
- PackageFileSummary/Import/Export 序列化
- 基础属性解析器（NameProperty, IntProperty, 等）
- CLI 入口 (`uasset-read`)

**关键决策**:
- 零运行时依赖，Python 3.10+
- `from uasset_read import *` 公共 API 约定
- FArchive 流式解析模式（非原始字节读取）

## v2.0 – v5.1 (2026-05-02 ~ 2026-05-07) — 含在 v6.0 archive 中

**演进路径**:
- v2.0: 蓝图图解析（UEdGraph/Node/Pin 数据模型）
- v3.0: 14 种属性类型解析器
- v5.1: src layout + pyproject.toml 迁移

## v6.0 模块化重构 (2026-05-13) — 405 文件 → 摘要

**核心成就**: 将单体解析器拆分为模块化架构
- `serializers/` — PackageSummary/Import/Export/PropertyTag
- `models/` — UEdGraph/Node/Pin + 属性数据类
- `parsers/` — 14 种属性类型 + 分派器
- `blueprint/` — 变量/组件/元数据提取
- `formatters/` — JSON/Text/Markdown/Mermaid 输出
- `graph/` — 执行流/数据流/连接映射
- 测试: 432 tests, 0 failures

**关键调试记录**:
- Pin 偏移对齐问题（UE5 头部结构差异）
- ExportMap 序列化偏移异常
- 方向标志 fname 漂移

**技术债**: Phase 44a-c 在 v7.0 中清理

## v7.0 UE FLinkerLoad 对象图重建 (2026-05-14) — 44 文件 → 摘要

**核心成就**: 两阶段对象图重建
- `link/` 模块 — PackageLinker / UObjectInstance
- 从 ImportMap/ExportMap 创建外壳 → 按需反序列化属性
- GraphSerializer linker 变体
- PackageIndex 类型安全索引

**关键决策**:
- UE FLinkerLoad 模式对齐（非自定义链接器）
- 增量采用（v6.0 模块逐步接入）
- 技术债清理：移除 UE4 兼容代码、替换直接字节读取

---

*此摘要生成于 2026-05-18，v10.0 发布后深度清理。*
*完整文件可通过 git 历史恢复。*
