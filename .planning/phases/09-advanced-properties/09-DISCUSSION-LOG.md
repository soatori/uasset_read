# Phase 9: 高级属性类型 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-02
**Phase:** 09-advanced-properties
**Areas discussed:** StructProperty 解析策略、MapProperty 键类型范围、SetProperty 处理方式、EnumProperty 值格式、TextProperty 本地化处理、DelegateProperty 函数引用、数据类设计、版本支持、失败处理策略、性能考量、JSON 输出位置、测试资产来源

---

## StructProperty 解析策略

| Option | Description | Selected |
|--------|-------------|----------|
| 递归解析 (推荐) | 结构体字段作为嵌套 dict 返回，递归解析深度限制 5 层（ROADMAP ADVP-01 指定） | ✓ |
| 延迟引用 | 返回原始字节位置 + 结构体类型名，由下游 agent 或 Phase 10 解析 | |
| 混合模式 | 常见结构体（Vector、Rotator、Color）预定义解析器，其他延迟处理 | |

**User's choice:** 递归解析 (推荐)
**Notes:** 深度限制 5 层满足常见结构体嵌套需求

---

## MapProperty 键类型范围

| Option | Description | Selected |
|--------|-------------|----------|
| 基本类型键 (推荐) | IntProperty、StrProperty、NameProperty 作为键（Phase 2 已支持的基本类型） | ✓ |
| 枚举类型键 | EnumProperty 值作为键（需 ADVP-04 先完成） | ✓ |
| StructProperty 键 | 简单结构体（如 Vector）作为键 — 实现复杂度较高 | ✓ |
| ObjectProperty 键 | ObjectProperty 引用作为键 | ✓ |

**User's choice:** 全选 — 支持所有四种键类型
**Notes:** 用户选择扩展键类型支持范围，实现复杂度较高但功能完整

---

## SetProperty 处理方式

| Option | Description | Selected |
|--------|-------------|----------|
| 不验证唯一性 (推荐) | 解析为 List，不检查唯一性 — 实现简单，与 ArrayProperty 输出格式一致 | ✓ |
| 验证 + 警告 | 解析时验证元素唯一性，发现重复时记录警告，返回 List | |
| 自动去重 | 使用 Python set 类型存储，自动去重 — 但失去顺序信息 | |

**User's choice:** 不验证唯一性 (推荐)
**Notes:** 与 ArrayProperty 格式一致，简化实现

---

## EnumProperty 值格式

| Option | Description | Selected |
|--------|-------------|----------|
| 枚举值名 (推荐) | 返回枚举值名称字符串（如 'EWalletState::Active'），便于 AI agent 理解语义 | ✓ |
| 整数值 + 类型 | 返回整数值 + 类型名，由下游 agent 根据枚举定义映射 | |
| 两者都返回 | 同时返回值名和整数值，最完整但输出体积大 | |

**User's choice:** 枚举值名 (推荐)
**Notes:** 值名便于 AI agent 理解语义，无需额外枚举定义映射

---

## TextProperty 本地化处理

| Option | Description | Selected |
|--------|-------------|----------|
| 完整结构 (推荐) | 返回 Namespace、Key、SourceString 三个字段，保留完整本地化信息 | ✓ |
| 仅文本内容 | 仅返回 SourceString，忽略本地化元数据 | |
| 简化结构 | 返回 SourceString + 指示是否本地化的标志 | |

**User's choice:** 完整结构 (推荐)
**Notes:** 保留完整本地化信息，SourceString 仅返回丢失本地化元数据

---

## DelegateProperty 函数引用

| Option | Description | Selected |
|--------|-------------|----------|
| 原始引用 (推荐) | 返回 {ObjectRef: FPackageIndex, FunctionName: str}，对象引用延迟解析到 Phase 10 | ✓ |
| 解析对象名 | 尝试解析 ObjectRef 为对象名（需 ImportMap/ExportMap 查询），失败时返回原始索引 | |
| 仅函数名 | 仅返回函数名字符串，忽略对象引用（简化输出） | |

**User's choice:** 原始引用 (推荐)
**Notes:** 原始引用避免 ImportMap/ExportMap 查询复杂度，延迟解析保持解析器职责单一

---

## 失败处理策略

| Option | Description | Selected |
|--------|-------------|----------|
| 跳过继续 (推荐) | Phase 2 D-25 模式：记录简短标记 + 跳过并继续下一个属性 | ✓ |
| 中止导出 | 中止当前导出的属性解析，尝试下一个导出（Phase 5 D-19 智能继续策略） | |
| 部分结果 | 返回原始字节位置 + 已解析字段，保留部分结果 | |

**User's choice:** 跳过继续 (推荐)
**Notes:** 与 Phase 2 策略一致，最大化数据提取

---

## 测试资产来源

| Option | Description | Selected |
|--------|-------------|----------|
| Lyra 资产 | 搜索包含 Struct/Map/Set/Enum/Text/Delegate 的蓝图资产 | ✓ |
| 合成测试 | 创建包含高级属性的测试 .uasset 文件（需 UE 编辑器） | |
| UE 示例项目 | 使用 UnrealEngine/Samples 中的 BP 示例资产 | ✓ |
| 纯单元测试 | 编写 Python 合成测试文件，模拟高级属性二进制格式 | |

**User's choice:** Lyra 资产 + UE 示例项目
**Notes:** Lyra 资产覆盖真实游戏场景，UE 示例项目提供多种版本对照

---

## 数据类设计

| Option | Description | Selected |
|--------|-------------|----------|
| 专用 dataclass (推荐) | 为每种高级属性创建专用 dataclass（StructValue、MapValue、EnumValue 等），结构清晰 | ✓ |
| Python dict | 统一使用 Python dict 存储，简化输出但类型信息不明确 | |
| 扩展 PropertyValue | 扩展 PropertyValue dataclass，添加 type_specific_data 字段 | |

**User's choice:** 专用 dataclass (推荐)
**Notes:** 结构清晰，类型信息明确，便于 JSON 输出序列化

---

## 版本支持

| Option | Description | Selected |
|--------|-------------|----------|
| 仅 UE5 (推荐) | 仅支持 UE5 格式（PROJECT.md 约束：专注于 UE 5.x），UE4 格式记录警告并跳过 | |
| UE4 + UE5 双支持 | 同时支持 UE4 和 UE5 格式，版本检查分支（Phase 2 D-05/D-06 模式） | ✓ |
| 尝试解析 + 跳过 | 尝试解析任何版本，失败时跳过并记录原始数据位置 | |

**User's choice:** UE4 + UE5 双支持
**Notes:** 用户选择扩展版本支持范围，使用 Phase 2 D-05/D-06 版本检查模式

---

## 性能考量

| Option | Description | Selected |
|--------|-------------|----------|
| 复用 Phase 5 (推荐) | 与 Phase 5 SAFE-03 一致：>50MB 自动 mmap，无需额外处理 | ✓ |
| 深度 + 字段数限制 | 添加结构体深度 + 字段数限制，超过时中止并返回部分结果 | |
| 超时保护 | 结构体解析超时保护，防止复杂结构体解析卡死 | |

**User's choice:** 复用 Phase 5 (推荐)
**Notes:** Phase 5 mmap 机制已验证，嵌套深度限制 5 层已覆盖常见结构体

---

## JSON 输出位置

| Option | Description | Selected |
|--------|-------------|----------|
| 替换原始值 (推荐) | 高级属性解析结果直接替换原始字符串值，保持属性列表格式不变 | ✓ |
| 新字段分隔 | 新增 advanced_properties 字段，与 properties 分开存储 | |
| 统一 + parsed 标志 | 所有属性统一放在 properties，高级属性添加 parsed 标志区分 | |

**User's choice:** 替换原始值 (推荐)
**Notes:** Phase 8 OUT2-02 指定替换原始值，保持属性列表格式不变

---

## Claude's Discretion

- 具体结构体类型字段解析顺序（需研究 UE 源码确定）
- EnumProperty 枚举值名生成格式（是否包含类型名前缀）
- TextProperty 空字段处理（Namespace/Key 为空时的默认值）
- 单元测试组织
- 具体测试资产文件选择

---

## Deferred Ideas

推迟到后续阶段的实现：

- DelegateProperty ObjectRef 解析为对象名 — Phase 10 依赖分析
- ObjectProperty 键值解析为对象名 — Phase 10 依赖分析
- 自定义结构体类型注册机制 — v3 高级功能
- 结构体类型缓存 — v3 高级功能
- 枚举定义提取 — v3 高级功能

---

*Phase: 09-advanced-properties*
*Discussion log generated: 2026-05-02*