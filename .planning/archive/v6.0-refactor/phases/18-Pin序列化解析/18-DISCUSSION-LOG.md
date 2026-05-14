# Phase 18: Pin序列化解析 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-04
**Phase:** 18-Pin序列化解析
**Areas discussed:** LinkedTo解析顺序, Flags bit位解析, 缺失字段处理, JSON输出整理

---

## LinkedTo解析顺序

### 如何修正LinkedTo解析以获取节点名引用？

| Option | Description | Selected |
|--------|-------------|----------|
| 修正解析顺序（推荐） | 先读OwningNode引用，再读PinId。能获取完整节点+Pin连接信息。需修改read_ue_graph_pin()逻辑。 | ✓ |
| 后处理反推节点 | 保持现有PinId解析，在Phase 19通过PinId查找表反推节点名。简化实现但依赖后处理。 | |
| 验证现状再决定 | 根据现有测试资产验证，若LinkedTo能正确构建连接则不改解析逻辑。 | |

**Decision:** D-18-01

### LinkedTo输出应使用哪种格式？

| Option | Description | Selected |
|--------|-------------|----------|
| 结构化对象（推荐） | 符合REQUIREMENTS.md PIN-04规范，易于AI理解节点连接关系。 | ✓ |
| UE文本格式字符串 | 格式："NodeName GUID"。与UE文本格式一致，便于对照验证。 | |
| 双字段输出 | 保持linked_to_raw存GUID，linked_to存结构化，两者并存。 | |

**Decision:** D-18-02

### LinkedTo引用解析失败时应如何处理？

| Option | Description | Selected |
|--------|-------------|----------|
| 输出原始索引+警告 | FPackageIndex可能引用无效节点。输出时存储原始索引+警告。 | ✓ |
| 跳过无效连接 | 引用无效时跳过该连接，记录warning到ParseResult.errors。 | |
| 中断解析 | 解析失败时中断该Pin解析，返回错误。 | |

**Decision:** D-18-08

### SubPins数组应如何解析和输出？

| Option | Description | Selected |
|--------|-------------|----------|
| 修正解析顺序 | 与LinkedTo相同处理：先读ParentNode引用再读PinId。输出结构化对象。 | ✓ |
| 保持现有解析 | SubPins是子Pin列表，已存储PinId GUID列表。保持现有解析。 | |
| 延后处理 | SubPins解析延后到Phase 19/20，当前仅存储原始数据。 | |

**Decision:** D-18-09

### ParentPin引用应如何处理？

| Option | Description | Selected |
|--------|-------------|----------|
| 添加节点引用 | 现有实现正确：has_parent bool + PinId。但需添加节点引用。输出结构化对象。 | ✓ |
| 保持现有实现 | ParentPin只需PinId，节点名可通过PinId查找表反推。 | |
| 延后处理 | ParentPin解析延后到Phase 19，当前仅存储PinId。 | |

**Decision:** D-18-10

---

## Flags bit位解析

### Pin flags bitfield应如何处理？

| Option | Description | Selected |
|--------|-------------|----------|
| 解析为命名字段（推荐） | 解析bit位为具体字段名（hidden、not_connectable、advanced_view、orphaned），输出更友好。 | ✓ |
| 双输出：flags+labels | 保留flags整数，同时在JSON中添加flags_labels数组。 | |
| 延后处理 | 保持现有flags整数输出，后续Phase 20整合时再处理。 | |

**Decision:** D-18-03

### Pin flags应解析并输出哪些字段？

| Option | Description | Selected |
|--------|-------------|----------|
| hidden, not_connectable, advanced_view, orphaned | REQUIREMENTS PIN-05要求的核心属性。 | ✓ |
| 添加所有flags | 包含DefaultValueReadOnly/DefaultValueIgnored，完整输出。 | ✓ |
| 仅输出需求定义 | 仅输出REQUIREMENTS定义的5个，其他存内部但不输出。 | |

**Decision:** D-18-11 — 输出所有flags字段

---

## 缺失字段处理

### 缺失字段（PinToolTip、DefaultObject、DefaultTextValue）应如何处理？

| Option | Description | Selected |
|--------|-------------|----------|
| 完整实现 | 按UE源码完整实现所有字段。PinToolTip用于用户提示，DefaultObject/DefaultTextValue用于特定默认值类型。 | ✓ |
| 仅实现需求定义 | 仅实现REQUIREMENTS.md明确要求的字段，其他延后。 | |
| 部分输出 | 完整实现但仅PinToolTip输出到JSON，其他存raw_data不输出。 | |

**Decision:** D-18-04

### PinToolTip字段应如何处理空值？

| Option | Description | Selected |
|--------|-------------|----------|
| 直接输出字符串 | PinToolTip是FString，直接输出字符串内容。空字符串时省略字段。 | |
| 空值输出null | 当tooltip为空时输出null而非省略，明确表示无tooltip。 | ✓ |

**Decision:** D-18-12

### DefaultObject引用应如何输出？

| Option | Description | Selected |
|--------|-------------|----------|
| 解析为对象名 | DefaultObject是UObject引用，解析为对象名。输出语义化名称。 | |
| 保留索引+名称 | 保留FPackageIndex整数，同时添加object_name字段。原始值+解析结果。 | ✓ |
| 仅输出对象名 | 仅输出解析后的对象名，不暴露索引细节。 | |

**Decision:** D-18-13

### DefaultTextValue (FText)应如何输出？

| Option | Description | Selected |
|--------|-------------|----------|
| 解析为字符串 | FText解析为字符串内容，输出text_value字段。空值时输出null。 | ✓ |
| 完整FText结构 | FText完整解析：text、namespace、flags等字段。 | |
| 仅输出文本内容 | 仅输出解析后的字符串内容，不保留FText结构细节。 | |

**Decision:** D-18-14

---

## JSON输出整理

### Pin JSON输出应如何清理内部字段？

| Option | Description | Selected |
|--------|-------------|----------|
| 清理内部字段（推荐） | 清理linked_to_raw、auto_default_value、flags等内部字段，仅输出结构化信息。 | ✓ |
| 保留双输出 | 同时输出内部字段和结构化字段，便于调试和验证。 | |
| 前缀标记 | 输出所有解析字段，但用前缀标记字节细节。 | |

**Decision:** D-18-05

### PinType JSON结构是否需要调整？

| Option | Description | Selected |
|--------|-------------|----------|
| 保持现有结构 | 按REQUIREMENTS PIN-02规范，使用语义化名称：category、sub_category等。当前已实现。 | ✓ |
| 添加原名映射注释 | 添加UE原名映射注释，如pin_category→PinCategory。 | |

**Decision:** D-18-06

### Pin direction字段应如何输出？

| Option | Description | Selected |
|--------|-------------|----------|
| 字符串 "input/output" | 转换为语义化字符串，便于AI理解。符合REQUIREMENTS设计原则。 | ✓ |
| 整数+label双输出 | 保留uint8整数，添加direction_label字段解释。 | |
| 保持整数 | 保留uint8整数，简单直接。 | |

**Decision:** D-18-07

### Pin JSON输出结构应如何组织？

| Option | Description | Selected |
|--------|-------------|----------|
| 按决策顺序输出 | 完整结构按讨论顺序输出所有字段。 | |
| 分组结构输出 | 分组输出：基础信息+类型信息+默认值+连接+显示属性。 | ✓ |
| 仅输出非空字段 | 仅输出非空字段，空值/null字段省略。 | ✓ |

**Decision:** D-18-15 — 分组结构 + 仅输出非空字段

### PinId GUID应使用哪种输出格式？

| Option | Description | Selected |
|--------|-------------|----------|
| 32字符hex | PinId是FGuid(16字节)，输出32字符hex字符串。 | |
| 带分隔符GUID | UE标准GUID格式："13FD260E-4EE1-8FD0-AA5F-7085F9B509D6"。 | ✓ |

**Decision:** D-18-16

---

## Claude's Discretion

- 确切分组字段顺序
- 非空字段判断阈值
- 警告信息格式

## Deferred Ideas

None — discussion stayed within phase scope.

---

*Phase: 18-Pin序列化解析*
*Discussion completed: 2026-05-04*