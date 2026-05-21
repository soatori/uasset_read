# uasset_read

Python 工具读取 Unreal Engine .uasset 文件（未烘焙蓝图），让 AI agent 直接解析内容。

**技术栈**: Python 3.10+，零运行时依赖 | **架构**: `.uasset → FArchive → 序列化 → 数据模型 → 属性解析 → 蓝图图 → 格式化输出 → PackageLinker → Kismet 字节码反编译 → Agent 翻译管线`

**源码参考**: `E:\Develop\lib\UnrealEngine` (UE 5.7，只读)

## 里程碑

| 版本 | 范围 | 状态 |
|------|------|------|
| v1.0–v6.0 | MVP → 模块化重构 | 已归档 |
| v7.0 | UE FLinkerLoad 对象图重建 | 已归档 |
| v8.0 | BP-to-CPP JSON 可翻译性 (P47-51) | 已归档 |
| v9.0 | 函数调用链解析 (P52-55) | 已归档 |
| v10.0 | Blueprint-to-C++ 代码生成参考 (P56-60) | 已归档 |
| **v11.0** | **Kismet 字节码反编译器 + 图解析修复 + Agent 翻译管线 (P61-66)** | **已归档** |
| **v12.0** | 📋 N2C 中间格式 + 节点分类体系 + 处理器架构 (P67-70) | 活跃 |

详情：`.planning/milestones/` | 路线图：`.planning/ROADMAP.md`

## 当前状态

**当前开发**: v12.0 — N2C 中间格式（活跃）

将 NodeToCode 的核心架构模式移植到 Python：N2CNodeTypeRegistry（100+ K2Node 类型映射）、节点处理器架构（Processor 模式）、N2CStruct JSON Schema（LLM 优化中间格式）、执行流链式表达。

**已归档**: v11.0 — Kismet 字节码反编译器 (2026-05-20)

实现完整字节码反编译管线：EExprToken → KismetExpression AST → C++ 伪代码，集成到 Agent 翻译管线输出 .h/.cpp 文件。修复图解析关键差距（FMemberReference、Pin 连接、Struct 映射）。1271 tests。

**预存在问题**: 26 个测试失败（资产版本 -8 vs -9，pre-existing）

## Out of Scope

导出纹理/模型 | 修改 .uasset | Cooked 资产 | MCP Server

~~蓝图字节码反编译~~ → v11.0 已实现（KismetExpression → C++）
~~Agent 翻译管线~~ → v11.0 已实现（AgentTranslationPipeline + CppFileWriter）
~~C++ 代码生成~~ → v10.0 已实现参考级输出

## 关键决策

零依赖 ✓ | 参考 UE 源码 ✓ | JSON 优先 ✓ | FArchive 管道模式 ✓ | v7.0 增量采用 ✓ | v8.0 按 gap 分 phase ✓ | v11.0 参考 CUE4Parse 设计（Python 化）✓

## Evolution

This document evolves at phase transitions and milestone boundaries.
Full update rules in the original template.

---

*Last updated: 2026-05-19 after v10.0 milestone archived, v11.0 active*
