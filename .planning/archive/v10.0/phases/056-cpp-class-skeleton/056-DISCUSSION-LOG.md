# Phase 56 Discussion Log

**Date:** 2026-05-18
**Phase:** 56 - C++ 类骨架提取

## Areas Discussed

### Area 1: 输出格式设计
**Options presented:** 中间 JSON IR 再格式化 / 直接 .h 文本生成 / 两步都提供
**Decision:** JSON IR 中间表示
**Rationale:** 保持与现有架构一致 `extract → models → format`，后续 phase 57-59 消费同结构逐步填充

### Area 2: 继承链推导策略
**Options presented:** 直接查 ImportMap/ExportMap ClassParent / 需要外部 UE 源码映射 / 混合策略
**Decision:** 混合策略 — 包内 ClassParent 追溯 + UE 引擎类映射兜底
**Rationale:** PackageLinker 已有 ImportMap 解析能力，遇到引擎原生类时用内置映射表转换路径到 C++ 类名

### Area 3: 类型映射方式
**Options presented:** 硬编码类型字典 / 从 UE 头文件自动生成 / 混合
**Decision:** 核心类型硬编码 + 从 UE 头文件生成的扩展脚本
**Rationale:** 核心类型高度稳定（float/bool/FVector 等），扩展脚本覆盖不常见类型

### Area 4: UPROPERTY 标记推断
**Options presented:** CPF 标志直接映射 / 启发式规则推断 / CPF + 属性来源组合判断
**Decision:** CPF 标志直接映射
**Rationale:** v9.0 已有完整 CPF 标志常量，CPF 就是 UPROPERTY 的底层表示，最可靠

### Area A: 头文件 include/前缀宏组织
**Options presented:** 完整 UE 头文件模板 / 最小骨架 / 分层输出
**Decision:** 完整 UE 模板 + JSON IR 结构化字段
**Rationale:** 产出文件可直接用于 UE 项目，同时保持 JSON IR 灵活性

### Area B: 输出 JSON 结构层级
**Options presented:** 扁平结构 / 嵌套结构 / 模块化子结构
**Decision:** 模块化子结构（header_meta, properties, methods, constructor）
**Rationale:** 每个 phase 独立填充一个子对象，结构清晰且解耦

### Area C: 测试用例基础
**Options presented:** BP_FirstPersonCharacter + mock JSON / 仅 BP_FirstPersonCharacter / 多个真实资产
**Decision:** BP_FirstPersonCharacter + mock JSON 补充边界情况
**Rationale:** 真实资产覆盖 golden path，mock 覆盖极端情况
