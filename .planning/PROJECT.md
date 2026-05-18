# uasset_read

Python 工具读取 Unreal Engine .uasset 文件（未烘焙蓝图），让 AI agent 直接解析内容。

**技术栈**: Python 3.10+，零运行时依赖 | **架构**: `.uasset → FArchive → 序列化 → 数据模型 → 属性解析 → 蓝图图 → 格式化输出 → PackageLinker → Kismet 字节码反编译`

**源码参考**: `E:\Develop\lib\UnrealEngine` (UE 5.7，只读)

## 里程碑

| 版本 | 范围 | 状态 |
|------|------|------|
| v1.0–v6.0 | MVP → 模块化重构 | 已归档 |
| v7.0 | UE FLinkerLoad 对象图重建 | 已归档 |
| v8.0 | BP-to-CPP JSON 可翻译性 (P47-51) | 已归档 |
| v9.0 | 函数调用链解析 (P52-55) | 已归档 |
| **v10.0** | **Blueprint-to-C++ 代码生成参考 (P56-60)** | **已发布** |
| **v11.0** | 📋 Kismet 字节码反编译器 (P61-64) | 活跃 |

详情：`.planning/archive/` | 路线图：`.planning/ROADMAP.md`

## 当前状态

**当前开发**: v11.0 — Kismet 字节码反编译器（活跃）

参考 CUE4Parse 设计，实现完整的 Kismet 字节码反编译器：从函数体原始字节流构建表达式树，翻译为可读 C++ 伪代码，覆盖变量/常量/函数调用/控制流/类型转换。

**已归档**: v10.0 — Blueprint-to-C++ 代码生成参考 (2026-05-19)

从蓝图 JSON 输出提取足够信息，使开发者能直接编写等价的 C++ 类实现：组件声明+构造函数数值、函数签名、输入绑定、执行流、函数调用链、数据流标注、函数体逻辑（AST 层面）、组件初始化代码。1021 tests。

**预存在问题**: 26 个测试失败（资产版本 -8 vs -9，pre-existing）

## Out of Scope

导出纹理/模型 | 修改 .uasset | Cooked 资产 | MCP Server

~~蓝图字节码反编译~~ → v11.0 开始实施
*C++ 代码生成~~ → v10.0 已实现参考级输出

## 关键决策

零依赖 ✓ | 参考 UE 源码 ✓ | JSON 优先 ✓ | FArchive 管道模式 ✓ | v7.0 增量采用 ✓ | v8.0 按 gap 分 phase ✓ | v11.0 参考 CUE4Parse 设计（Python 化）✓

## Evolution

This document evolves at phase transitions and milestone boundaries.
Full update rules in the original template.

---

*Last updated: 2026-05-19 after v10.0 milestone archived, v11.0 active*
