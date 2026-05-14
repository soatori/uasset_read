# Phase 3: Blueprint Extraction - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-01
**Phase:** 03-blueprint-extraction
**Areas discussed:** 蓝图检测策略, 变量类型命名, 父类解析深度, 默认值处理

---

## 蓝图检测策略

### Q1: 蓝图资产的首要检测方法应该是什么？

| Option | Description | Selected |
|--------|-------------|----------|
| 类名检测（推荐） | 检查ExportMap中导出的ClassIndex指向的类名包含"Blueprint"关键字。简单直接，但可能漏检非标准命名 | ✓ |
| 包路径模式 | 检查包路径是否匹配/Game/Blueprints/...等模式。可能误判或漏检自定义路径结构 | |
| 导出类型检测 | 检查导出对象的ClassName是否为Blueprint、WidgetBlueprint等类型。最准确，但需完整类型列表 | |
| 多重组合检测 | 组合多种方法提高准确度。复杂度高，但覆盖边缘情况更好 | |

**User's choice:** 类名检测（推荐）
**Notes:** 检查ExportMap中导出的ClassIndex指向的类名包含"Blueprint"关键字

---

### Q2: 蓝图检测应该在什么时机触发？

| Option | Description | Selected |
|--------|-------------|----------|
| 按需检测（推荐） | 用户调用parse_blueprint()时才检测蓝图。用户控制，但需手动选择函数 | |
| 自动检测 | parse_uasset()解析后自动检测并提取蓝图元数据。全自动，但可能解析不需要的数据 | ✓ |
| 标志+可选提取 | 解析后返回is_blueprint标志，用户决定是否调用extract_blueprint()。平衡自动和手动控制 | |

**User's choice:** 自动检测
**Notes:** parse_uasset()解析后自动检测并提取蓝图元数据

---

### Q3: 蓝图检测失败时如何处理？

| Option | Description | Selected |
|--------|-------------|----------|
| 静默跳过（推荐） | 检测失败时跳过蓝图提取，返回普通资产解析结果。用户仍能获取基础数据 | |
| 记录警告 | 检测失败时在ParseResult.errors中添加警告信息。用户知道检测尝试失败 | ✓ |
| 抛出异常 | 检测失败时抛出异常。严格模式，但可能阻断正常解析流程 | |

**User's choice:** 记录警告
**Notes:** 检测失败时在ParseResult.errors中添加警告信息

---

### Q4: 蓝图类型识别需要到什么程度？

| Option | Description | Selected |
|--------|-------------|----------|
| 仅蓝图标志（推荐） | 仅识别是否为蓝图，不区分类型。简单，满足基本需求 | ✓ |
| 完整类型分类 | 识别BlueprintType枚举值（Normal、Interface、MacroLibrary等）。完整信息，但增加解析复杂度 | |
| 关键类型区分 | 仅区分普通蓝图和蓝图接口（Interface）。关键类型区分，其他简化 | |

**User's choice:** 仅蓝图标志（推荐）
**Notes:** 仅识别是否为蓝图，不区分BlueprintType（Normal、Interface、MacroLibrary等）

---

## 变量类型命名

### Q1: 变量类型输出使用什么命名风格？

| Option | Description | Selected |
|--------|-------------|----------|
| UE原始名称（推荐） | 使用PinCategory原始值如"Integer"、"Object Reference"。UE源码一致，但名称可能较长 | ✓ |
| 简化技术名 | 简化为"int"、"obj"、"arr"等。简短，但可能与UE术语不一致 | |
| 详细描述格式 | 如"Integer (int32)"、"Object Ref (AActor*)"。详细，但可能过于冗长 | |

**User's choice:** UE原始名称（推荐）
**Notes:** 使用PinCategory原始值如"Integer"、"Object Reference"

---

### Q2: 复合类型（Array、Map、Set）如何表示元素类型？

| Option | Description | Selected |
|--------|-------------|----------|
| 仅容器类型名 | Array返回"Array"，Map返回"Map"。简单，但无元素类型信息 | |
| 容器+元素类型（推荐） | Array[Int]表示整数数组，Map[Str,Obj]表示字符串到对象映射。元素类型信息完整 | ✓ |
| 分离字段结构 | 分离输出container_type和element_type字段。JSON友好，但需额外字段 | |

**User's choice:** 容器+元素类型（推荐）
**Notes:** Array[Int]表示整数数组，Map[Str,Obj]表示字符串到对象映射

---

### Q3: Object Reference类型应该显示具体类名吗？

| Option | Description | Selected |
|--------|-------------|----------|
| 通用引用类型 | 仅返回"Object Reference"。无具体类信息，但解析简单 | |
| 具体类引用（推荐） | 尝试解析PinSubCategoryObject获取具体类名如"AActor Reference"。完整信息，但需额外解析 | ✓ |
| 引用+原始索引 | 返回"Object Reference"加上class_index字段供后续解析。延迟解析模式 | |

**User's choice:** 具体类引用（推荐）
**Notes:** 尝试解析PinSubCategoryObject获取具体类名如"AActor Reference"

---

### Q4: FEdGraphPinType解析范围？

| Option | Description | Selected |
|--------|-------------|----------|
| 完整结构解析（推荐） | FEdGraphPinType所有字段完整解析。信息完整，但可能解析不需要的字段 | ✓ |
| 仅核心字段 | 仅解析PinCategory和PinSubCategory。核心类型信息，但缺失容器类型等 | |
| 类型相关字段 | 解析类型相关字段，跳过无关字段（如PinId）。平衡完整性和效率 | |

**User's choice:** 完整结构解析（推荐）
**Notes:** FEdGraphPinType所有字段完整解析

---

## 父类解析深度

### Q1: 父类解析应该追溯多少层级？

| Option | Description | Selected |
|--------|-------------|----------|
| 仅直接父类（推荐） | 仅解析ParentClass FPackageIndex指向的直接父类。简单，满足基本继承信息需求 | ✓ |
| 完整继承链 | 递归解析完整继承链直到UObject。完整信息，但复杂度高 | |
| 可选深度参数 | 提供max_depth参数控制解析深度。用户控制，但需额外参数设计 | |

**User's choice:** 仅直接父类（推荐）
**Notes:** 仅解析ParentClass FPackageIndex指向的直接父类

---

### Q2: ParentClass引用如何解析输出？

| Option | Description | Selected |
|--------|-------------|----------|
| 解析为对象名（推荐） | FPackageIndex解析为ImportMap/ExportMap中的对象名。直接可读，但需NameMap支持 | ✓ |
| 保持原始索引 | 仅返回ParentClass的原始FPackageIndex值。延迟解析，但用户需手动解析 | |
| 名称+原始索引 | 返回解析后的名称加原始索引。完整信息，但字段冗余 | |

**User's choice:** 解析为对象名（推荐）
**Notes:** FPackageIndex解析为ImportMap/ExportMap中的对象名

---

### Q3: 父类引用缺失或解析失败时如何处理？

| Option | Description | Selected |
|--------|-------------|----------|
| 返回null | 返回null或空字符串。简单，但用户无法区分"无父类"和"解析失败" | |
| 返回原始索引+警告（推荐） | 返回原始FPackageIndex值加警告。用户有原始数据参考 | ✓ |
| 记录错误 | 在ParseResult.errors中添加错误信息，父类字段返回null。严格模式 | |

**User's choice:** 返回原始索引+警告（推荐）
**Notes:** 返回原始FPackageIndex值加警告，用户有原始数据参考

---

### Q4: 需要处理循环父类引用吗？

| Option | Description | Selected |
|--------|-------------|----------|
| 仅直接父类无循环风险（推荐） | 仅直接父类不存在循环风险。简单解决方案 | ✓ |
| 检查自引用 | 检查父类引用是否指向自己，记录警告。安全检查 | |
| 推迟到v2 | 仅支持直接父类，v2完整继承链时添加循环检测。推迟复杂逻辑 | |

**User's choice:** 仅直接父类无循环风险（推荐）
**Notes:** 仅直接父类不存在循环风险，简单解决方案

---

## 默认值处理

### Q1: DefaultValue字符串应该解析为Python类型吗？

| Option | Description | Selected |
|--------|-------------|----------|
| 保持原始字符串 | 不解析，直接输出原始字符串。简单，但AI agent理解困难 | |
| 解析为Python类型（推荐） | 尝试解析为Python原生类型（int、float、bool、str）。AI agent直接理解，但可能失败 | ✓ |
| 部分解析 | 解析成功输出Python值，失败输出原始字符串。安全，但输出不统一 | |

**User's choice:** 解析为Python类型（推荐）
**Notes:** 尝试解析为Python原生类型（int、float、bool、str）

---

### Q2: 类型解析失败时如何输出？

| Option | Description | Selected |
|--------|-------------|----------|
| 返回原始字符串（推荐） | 解析失败时输出原始字符串值。fallback策略，用户有原始数据 | ✓ |
| 错误标记结构 | 返回{"raw": "...", "parse_error": true}结构。明确标记失败，但结构复杂 | |
| 返回null | 解析失败时返回null。简洁，但丢失原始数据 | |

**User's choice:** 返回原始字符串（推荐）
**Notes:** 解析失败时输出原始字符串值，用户有原始数据

---

### Q3: 应该尝试解析哪些类型的默认值？

| Option | Description | Selected |
|--------|-------------|----------|
| 基本类型解析（推荐） | 仅解析基本类型（int、float、bool、string）。简单安全，覆盖常见情况 | ✓ |
| 全类型解析 | 尝试解析所有类型包括数组、对象引用。完整，但复杂度高易失败 | |
| 极简解析 | 仅解析int和bool。最保守，其他类型保持字符串 | |

**User's choice:** 基本类型解析（推荐）
**Notes:** 仅解析基本类型（int、float、bool、string），不尝试复杂类型

---

### Q4: 向量类型默认值（如Vector、Rotator）如何处理？

| Option | Description | Selected |
|--------|-------------|----------|
| 保持原始字符串（推荐） | 向量字符串如"(X=1.0,Y=2.0,Z=3.0)"保持原样。复杂格式暂不解析 | ✓ |
| 解析为列表 | 解析为Python列表[1.0, 2.0, 3.0]。结构化输出，但需格式识别 | |
| 解析为字典 | 解析为{"x": 1.0, "y": 2.0, "z": 3.0}字典。字段命名，但更复杂 | |

**User's choice:** 保持原始字符串（推荐）
**Notes:** 向量字符串如"(X=1.0,Y=2.0,Z=3.0)"保持原样，复杂格式暂不解析

---

## Claude's Discretion

以下区域由 Claude 自行决定具体实现细节：

- 具体蓝图检测的类名匹配逻辑（包含 "Blueprint" 还是精确匹配）
- FEdGraphPinType 各字段的具体解析顺序和数据类型
- DefaultValue 字符串解析的正则表达式或解析器实现
- 变量元数据（Category、PropertyFlags）的输出格式
- 单元测试组织和测试资产选择

---

## Deferred Ideas

讨论中提出的推迟到后续阶段的实现：

### 阶段 4（输出与 CLI）
- BlueprintMetadata JSON 输出格式化
- 蓝图数据文本摘要格式

### v2（蓝图高级功能）
- BlueprintType 完整分类（Normal、Interface、MacroLibrary、FunctionLibrary）
- 完整继承链解析（递归到 UObject）
- 循环引用检测
- 蓝图图提取（UEdGraph、Nodes、Pins）
- 复杂默认值解析（数组、向量、对象引用）
- 变量元数据完整提取（MetaDataArray 详细解析）

---