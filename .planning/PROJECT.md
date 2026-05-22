# uasset_read

Python 工具读取 Unreal Engine .uasset 文件（未烘焙蓝图），让 AI agent 直接解析内容。

**技术栈**: Python 3.10+，零运行时依赖 | **架构**: `.uasset → FArchive → 序列化 → 数据模型 → 属性解析 → 蓝图图 → 格式化输出 → PackageLinker → Kismet 字节码反编译 → Agent 翻译管线 → N2C 中间格式`

**源码参考**: `E:\Develop\lib\UnrealEngine` (UE 5.7，只读)

## 里程碑

| 版本 | 范围 | 状态 |
|------|------|------|
| v1.0–v6.0 | MVP → 模块化重构 | 已归档 |
| v7.0 | UE FLinkerLoad 对象图重建 | 已归档 |
| v8.0 | BP-to-CPP JSON 可翻译性 (P47-51) | 已归档 |
| v9.0 | 函数调用链解析 (P52-55) | 已归档 |
| v10.0 | Blueprint-to-C++ 代码生成参考 (P56-60) | 已归档 |
| v11.0 | Kismet 字节码反编译器 + 图解析修复 + Agent 翻译管线 (P61-66) | 已归档 |
| **v12.0** | **N2C 中间格式 + 节点分类体系 + 处理器架构 (P67-71)** | 已归档 |
| **v13.0** | **Pin 连接修复 + Kismet 字节码导航 + FName/FString 区分 (P72)** | 活跃 |

详情：`.planning/milestones/` | 路线图：`.planning/ROADMAP.md`

## 当前状态

**当前开发**: v13.0 — Pin 连接修复 + Kismet 字节码导航 + FName/FString 区分 (P72)

Phase 72-A（Pin 连接二进制诊断）已完成，定位 2 个独立 bug：
1. `history_type` 无符号/有符号不匹配（`read_u8()` 返回 255，UE 意图是 -1）
2. ParentPin 条件读取错误（`null != 0` 时多读 16B GUID）

Phase 72-B（Pin 连接修复）待执行。

**已归档**: v12.0 — N2C 中间格式 (2026-05-22)

完成 N2C 中间格式完整架构：序列化修复（6 类错误清零）、N2CNodeTypeRegistry（126 种 K2Node 类型）、节点处理器架构（9 个 Processor）、N2CStruct JSON Schema（72.6% token 压缩）、执行流链式表达（`N1->N2->N3`）。1290 tests。

## Out of Scope

导出纹理/模型 | 修改 .uasset | Cooked 资产 | MCP Server

~~蓝图字节码反编译~~ → v11.0 已实现（KismetExpression → C++）
~~Agent 翻译管线~~ → v11.0 已实现（AgentTranslationPipeline + CppFileWriter）
~~C++ 代码生成~~ → v10.0 已实现参考级输出

## 关键决策

零依赖 ✓ | 参考 UE 源码 ✓ | JSON 优先 ✓ | FArchive 管道模式 ✓ | v7.0 增量采用 ✓ | v8.0 按 gap 分 phase ✓ | v11.0 参考 CUE4Parse 设计（Python 化）✓ | v12.0 N2C 中间格式架构 ✓

## Evolution

This document evolves at phase transitions and milestone boundaries.
Full update rules in the original template.

---

*Last updated: 2026-05-23 after v12.0 milestone archived, v13.0 active*
