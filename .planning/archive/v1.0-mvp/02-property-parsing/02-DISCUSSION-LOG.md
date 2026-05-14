# Phase 2: 属性解析 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-01
**Phase:** 02-property-parsing
**Areas discussed:** 属性发现, 导出结构, 属性类型处理, 未知类型处理, 值表示, 数组格式, 版本处理, 测试资产, 错误策略, 版本覆盖, ObjectProperty, 嵌套深度, 蓝图属性, PropertyGuid, BoolProperty, Extensions

---

## 属性发现

| Option | Description | Selected |
|--------|-------------|----------|
| Tagged Property 循环 | 从 ExportMap 的 serial_offset 定位，循环读取 PropertyTag 直到 Name == "None" | |
| Export 解析器 | 创建专门的 ExportReader 类，先读取导出对象头，再进入属性循环 | ✓ |

**User's choice:** Export 解析器
**Notes:** 用户希望创建专门的解析器类，而非直接进入属性循环

---

## 导出结构

| Option | Description | Selected |
|--------|-------------|----------|
| 直接属性循环 | 导出序列化数据直接是属性循环，无需读取额外头信息 | |
| 带 UObject 头 | 先读取 UObject 序列化头（ClassIndex、SuperIndex 等），再进入属性循环 | ✓ |
| 按资产类型分支 | 不同资产类型有不同的导出结构 | |

**User's choice:** 带 UObject 头 → 统一头结构
**Notes:** 用户确认所有导出统一读取固定头（ObjectFlags、ClassRef 等），再进入属性循环

---

## 属性类型处理

| Option | Description | Selected |
|--------|-------------|----------|
| 函数分派 | 为每种类型创建独立解析函数。清晰易测试，匹配 UE 源码结构 | ✓ |
| 字典注册表 | 用字典映射类型名到解析器，便于扩展新类型 | |

**User's choice:** 函数分派（推荐）
**Notes:** 用户认可推荐方案

---

## 未知类型处理

| Option | Description | Selected |
|--------|-------------|----------|
| 跳过并继续 | 读取 Size 字段后跳过该字节数，继续下一个属性 | |
| 存储原始数据 | 记录类型名和原始字节，供后续分析 | |
| 停止解析 | 遇到未知类型立即停止该导出的属性解析 | |

**User's choice:** 参考UE编辑器源码加载方式，记录简短标记，然后跳过并继续
**Notes:** 用户强调不建议直接使用字节读取法，要参考 UE 编辑器源码中的加载方式

---

## 值表示

| Option | Description | Selected |
|--------|-------------|----------|
| Python 原生类型 | int、float、str、list 等原生类型。简单，JSON 输出直接支持 | ✓ |
| Typed dataclasses | IntPropertyValue、FloatPropertyValue 等包装类 | |
| Union/容器类型 | 用 Union 类型或通用 PropertyValue 容器 | |

**User's choice:** Python 原生类型（推荐）
**Notes:** 用户认可推荐方案

---

## 数组格式

| Option | Description | Selected |
|--------|-------------|----------|
| Count + 循环读取 | 先读取元素数量，再循环读取各元素值 | ✓ |
| Size 推算 | 数组大小由 PropertyTag.Size 计算 | |

**User's choice:** Count + 循环读取
**Notes:** 用户确认数组格式为元素数量 + 循环读取

---

## NameProperty

| Option | Description | Selected |
|--------|-------------|----------|
| FName 格式 | NameMap 索引 + 实例编号 | |
| FString 格式 | 直接字符串，不需要索引解析 | |

**User's choice:** 评估后再决定 → FName 格式（从 UE 源码确认）
**Notes:** UE 源码确认 NameProperty 值为 int32 NameIndex + int32 Number，使用现有 read_name() 方法

---

## 版本处理

| Option | Description | Selected |
|--------|-------------|----------|
| 版本分支 | 使用 PROPERTY_TAG_COMPLETE_TYPE_NAME 版本检查，新版本用完整 TypeName | ✓ |
| 仅 UE5 新格式 | 仅支持 UE5 最新版本格式，简化实现 | |
| 尝试-回退 | 先尝试新格式，失败则回退旧格式 | |

**User's choice:** 版本分支（推荐）
**Notes:** 用户选择版本分支，需支持 UE4/UE5 格式差异

---

## 测试资产来源

| Option | Description | Selected |
|--------|-------------|----------|
| Lyra 示例 | 从 LyraStarterGame/ 目录选择测试资产 | |
| UE 源码示例 | 从 UE 源码示例项目复制资产到 tests/fixtures/ | |
| 混合来源 | Lyra + UE 源码示例，覆盖多种资产类型和版本 | |

**User's choice:** FirstPerson + FirstPersonC（BP vs C++对照）→ UE源码示例 → Lyra
**Notes:** 用户指定测试顺序：先 BP/C++对照，再 UE 源码示例验证，最后 Lyra

---

## 错误策略

| Option | Description | Selected |
|--------|-------------|----------|
| 跳过并继续 | 单个属性失败时跳过并继续，记录错误信息 | ✓ |
| 停止导出解析 | 单个属性失败立即停止该导出的解析 | |
| 整体失败 | 单属性失败导致整个文件解析失败 | |

**User's choice:** 记录简短标记，然后跳过并继续
**Notes:** 匹配阶段 1 D-15 部分结果模式

---

## 版本覆盖

| Option | Description | Selected |
|--------|-------------|----------|
| 边界版本测试 | 测试覆盖 UE4/UE5 边界版本：4.20、4.26、5.0、5.1 | ✓ |
| 仅 UE5 最新 | 仅测试 UE 5.x 最新版本格式 | |
| 测试当前版本 | 测试遇到的第一个有效资产版本 | |

**User's choice:** 边界版本测试
**Notes:** 需覆盖 UE4/UE5 关键版本差异

---

## ObjectProperty

| Option | Description | Selected |
|--------|-------------|----------|
| 原始索引 | 读取 FPackageIndex，返回原始索引 | ✓ |
| 即时解析名称 | 即时解析为对象名 | |
| 索引 + 名称 | 存储索引和解析后的名称 | |

**User's choice:** 原始索引（推荐）
**Notes:** 阶段 3/4 再解析为对象名

---

## 嵌套深度

| Option | Description | Selected |
|--------|-------------|----------|
| 限制深度 | 设置最大嵌套深度（如 10 层），超出时跳过并标记 | ✓ |
| 不限制 | 不限制深度，信任资产结构正常 | |
| Size 验证 | 通过 Size 字段控制嵌套属性大小 | |

**User's choice:** 限制深度（推荐）
**Notes:** 防止无限递归

---

## 蓝图属性

| Option | Description | Selected |
|--------|-------------|----------|
| 作为普通属性 | 解析蓝图特定属性作为普通属性处理 | |
| 特殊处理蓝图 | 特殊处理蓝图属性：ParentClass 解析为父类名 | |
| 推迟到阶段 3 | 蓝图结构推迟到阶段 3 | ✓ |

**User's choice:** 推迟到阶段 3
**Notes:** 阶段 2 仅解析基本类型属性

---

## PropertyGuid

| Option | Description | Selected |
|--------|-------------|----------|
| 读取但不使用 | 读取 PropertyGuid 字段，阶段 3 可能使用 | ✓ |
| 跳过不读 | 跳过 PropertyGuid 字段 | |
| 用于属性匹配 | 使用 PropertyGuid 匹配蓝图重命名属性 | |

**User's choice:** 读取但不使用
**Notes:** 存储供阶段 3 使用

---

## BoolProperty

| Option | Description | Selected |
|--------|-------------|----------|
| 从 Tag.BoolVal | 从 PropertyTag.BoolVal 读取（标志位 BoolTrue），无额外数据读取 | ✓ |
| 可能需要读取 | Tag.BoolVal = 0 时仍需读取 1 byte 数据值 | |
| 始终读取数据 | 始终读取 1 byte bool 数据，忽略 Tag.BoolVal | |

**User's choice:** 从 Tag.BoolVal（推荐）
**Notes:** 匹配 UE 源码 PropertyTag.cpp

---

## Extensions

| Option | Description | Selected |
|--------|-------------|----------|
| 跳过扩展 | 跳过扩展数据 | |
| 读取并存储 | 读取并存储扩展数据 | |
| 仅记录存在 | 仅记录扩展标志存在 | |

**User's choice:** 推迟到阶段3
**Notes:** HasPropertyExtensions 数据推迟到阶段 3

---

## Claude's Discretion

- 具体 PropertyTag 字段解析顺序
- 嵌套深度限制实现方式（计数器或 Size 验证）
- 错误标记格式和详细程度
- 单元测试组织

---

## Deferred Ideas

- ParentClass 解析为父类名 → 阶段 3
- NewVariables 提取变量定义 → 阶段 3
- FunctionGraphs 解析 → 阶段 3
- HasPropertyExtensions 数据解析 → 阶段 3
- PropertyGuid 用于蓝图重命名属性匹配 → 阶段 3
- ObjectProperty 索引解析为对象名 → 阶段 4
- StructProperty、MapProperty、SetProperty、EnumProperty、TextProperty → v2