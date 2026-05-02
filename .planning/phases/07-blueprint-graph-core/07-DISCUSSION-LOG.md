# Phase 7: 蓝图图核心解析 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 07-blueprint-graph-core
**Areas discussed:** 引脚连接解析策略, 节点类型识别范围, 图数据解析深度, 图输出层级设计

---

## 引脚连接解析策略

| Option | Description | Selected |
|--------|-------------|----------|
| 名称索引 + 解析后映射 | LinkedTo 为 FString 名称，通过 pin_name 查找目标引脚，解析后生成连接映射 | |
| FPackageIndex 指针 | LinkedTo 为 int32 指针，直接指向导出表中的目标节点/引脚对象 | |
| 混合格式检测 | 先检测 FString，失败则尝试 FPackageIndex，两种格式兼容 | |
| 延迟到 Phase 8 | 仅记录原始 LinkedTo 数据，Phase 8 输出时处理连接映射 | ✓ |

**User's choice:** 延迟到 Phase 8
**Notes:** 降低 Phase 7 复杂度，连接映射逻辑集中在输出阶段处理

---

## 节点类型识别范围

| Option | Description | Selected |
|--------|-------------|----------|
| 类字段 + 类型名 | 仅解析基类字段（NodeGuid、Pos、Comment、Pins）和类型名称，不解析子类特有字段 | |
| 基类 + 需求类型 | 基类字段 + 5种需求节点类型特有字段（FunctionReference、EventReference 等） | ✓ |
| 全面解析所有类型 | 基类字段 + 所有遇到类型的特有字段，未知类型记录警告 | |
| 仅类型识别无字段 | 基类字段 + 类型名 + ClassIndex，不解析任何子类特有字段 | |

**User's choice:** 基类 + 需求类型 (Recommended)
**Notes:** 满足 ROADMAP 需求 GRAPH-05~09，避免过度扩展范围

---

## 图数据解析深度

| Option | Description | Selected |
|--------|-------------|----------|
| 完整解析 Graph→Node→Pin | 检测 EdGraph → 提取 Graph 基本信息 → 解析所有 Node → 解析所有 Pin | ✓ |
| 仅 Graph 基本信息 | 检测 EdGraph → 仅提取 Schema、Guid、节点数，不解析 Node/Pin | |
| Graph→Node 不含 Pin | 检测 EdGraph → 解析 Node 基类字段，不解析 Pin | |
| 动态深度控制 | 根据 SerialSize 决定解析深度，小图完整解析，大图仅基本信息 | |

**User's choice:** 完整解析 Graph→Node→Pin (Recommended)
**Notes:** 满足 ROADMAP 成功标准，Phase 7 交付完整图数据

---

## 图输出层级设计

| Option | Description | Selected |
|--------|-------------|----------|
| 顶层 graphs 字段 | graphs 数组与 blueprint 同级，每个导出的图数据汇总到顶层 | ✓ |
| 嵌入 export.graph_data | 图数据嵌入 export 对象内，保持 Package→Exports 层级 | |
| 嵌入 blueprint.metadata.graphs | 图数据仅蓝图资产有，嵌入 blueprint.metadata | |
| 延迟到 Phase 8 | Phase 7 不设计输出格式，仅定义图数据类和解析逻辑 | |

**User's choice:** 顶层 graphs 字段 (Recommended)
**Notes:** 便于快速访问图数据，与 Phase 4 D-02 的顶层字段设计一致

---

## Claude's Discretion

以下区域由 Claude 在规划/实现时自行决定：
- 节点类型特有字段的具体解析顺序（需研究 UE 源码确定）
- LinkedTo 原始数据的存储格式（List[str] vs List[dict]）
- PinId 生成格式（UE GUID hex vs 自定义 ID）
- 节点/引脚解析失败的错误上下文字段设计
- 单元测试组织

---

## Deferred Ideas

推迟到后续阶段的实现：

### Phase 8
- 引脚连接映射构建
- graphs 字段 JSON 输出格式化
- --graph CLI 标志
- 执行流路径输出
- 图结构摘要文本输出

### Phase 9+
- 更多 K2Node 子类解析
- 自定义节点类型扩展机制

---

*Phase: 07-blueprint-graph-core*
*Discussion log generated: 2026-05-02*