# 路线图：uasset_read

**创建日期：** 2026-04-27
**项目：** Python .uasset 解析器（面向 AI agent）
**总阶段数：** 5
**粒度：** 标准（5-8 阶段，均衡规模）

## 阶段概览

| # | 阶段 | 目标 | 需求 | 成功标准 |
|---|------|------|------|----------|
| 1 | 核心解析 | 解析 .uasset 文件头、名称表和映射表；检测资产结构 | CORE-01 至 CORE-08 | 4 条标准 |
| 2 | 属性解析 | 从导出读取并提取属性值 | PROP-01 至 PROP-09 | 4 条标准 |
| 3 | 蓝图提取 | 提取蓝图特定元数据（变量、父类） | BLUE-01 至 BLUE-06 | 4 条标准 |
| 4 | 输出与 CLI | JSON/文本输出格式，命令行接口 | OUT-01 至 OUT-06, CLI-01 至 CLI-06 | 4 条标准 |
| 5 | 优化与安全 | 性能优化，错误处理，安全检查 | SAFE-01 至 SAFE-05 | 3 条标准 |

---

## 阶段 1：核心解析

**目标：** 解析 .uasset 文件头、名称表、导入表和导出表；识别资产结构和类型。

**需求：** CORE-01, CORE-02, CORE-03, CORE-04, CORE-05, CORE-06, CORE-07, CORE-08

**工期估算：** 中等（基础层，为后续所有工作奠定基础）

**计划：** 1 个计划，Wave 1
**状态：** ✓ 已验证（2026-04-28）

计划列表：
- [x] 01-01-PLAN.md — 核心解析器实现（FArchive、dataclasses、解析函数、测试） ✓ 13 测试通过

### 成功标准

1. **给定**任意有效 .uasset 文件，**当**解析器读取文件头，**则**PackageFileSummary 包含正确的魔术标签、版本号和偏移。
2. **给定**带有交换字节序魔术标签的文件，**当**解析器检测到它，**则**启用字节交换，后续所有读取正确。
3. **给定**有效 .uasset 文件，**当**解析器读取名称表和映射表，**则**NameMap、ImportMap 和 ExportMap 包含所有条目及正确值。
4. **给定**不支持的版本 .uasset，**当**解析器检测版本，**则**返回清晰错误信息而不崩溃。

### 主要工作

- FArchive 基类及读取方法（u8、u32、u64、f32、fstring）
- 字节交换检测与处理（PACKAGE_FILE_TAG vs PACKAGE_FILE_TAG_SWAPPED）
- PackageFileSummary 解析（所有文件头字段）
- 名称表提取（NameOffset、NameCount、FString 条目）
- 导入表解析（FObjectImport 结构）
- 导出表解析（FObjectExport 结构）
- 从 ClassIndex 识别资产类
- 版本处理（UE4/UE5/自定义版本）
- 错误处理框架（自定义异常）

### 依赖

无 —— 基础阶段。

### 风险

- **字节序边缘情况：** 不同平台保存的文件可能有意外的字节顺序
- **版本复杂性：** UE 版本系统多层（UE4、UE5、自定义、遗留）
- **偏移算术：** 混用绝对与相对偏移导致读取错误

### UE 源码参考

- `PackageFileSummary.h` —— 文件头结构
- `ObjectResource.h` —— 导入/导出结构
- `Archive.h` —— FArchive 模式
- `PackageFileSummary.cpp` —— Summary 序列化

---

## 阶段 2：属性解析

**目标：** 解析 PropertyTag 并提取基本属性值（int、float、bool、string、name、object、array）。

**需求：** PROP-01, PROP-02, PROP-03, PROP-04, PROP-05, PROP-06, PROP-07, PROP-08, PROP-09

**工期估算：** 中等（属性类型多样，需系统性处理）

**计划：** 待规划

### 成功标准

1. **给定**带属性的导出，**当**解析器读取 PropertyTag，**则**标签包含正确的名称、类型、大小和标志。
2. **给定**基本类型属性（Int、Float、Bool、String、Name），**当**解析器提取值，**则**值与预期内容匹配。
3. **给定**ArrayProperty，**当**解析器读取元素，**则**所有元素正确解析。
4. **给定**带 HasPropertyGuid 标志的 PropertyTag，**当**解析器读取完整标签，**则**GUID 字段正确提取。

### 主要工作

- PropertyTag 解析（名称、类型、数组索引、大小、标志、GUID、扩展）
- IntProperty 解析（int32、int64）
- FloatProperty 解析（float、double）
- BoolProperty 解析（内联 bool 字节）
- StrProperty 解析（带长度前缀的 FString）
- NameProperty 解析（从 NameMap 解析的 FName）
- ObjectProperty 解析（FPackageIndex 引用）
- ArrayProperty 解析（计数 + 元素循环）
- PropertyTag 标志处理（HasPropertyGuid、HasPropertyExtensions）

### 依赖

- 阶段 1（需要 PackageFileSummary、NameMap、ExportMap、FArchive）

### 风险

- **PropertyTag演进：** 标志和字段在 UE 版本间有差异
- **FString 编码：** UTF-8 vs UTF-16 取决于版本
- **数组嵌套：** 嵌套数组或复杂类型数组增加复杂度

### UE 源码参考

- `PropertyTag.h` —— 属性标签结构
- `PropertyTag.cpp` —— 序列化
- `UnrealString.h` —— FString 格式

---

## 阶段 3：蓝图提取

**目标：** 检测蓝图资产并提取蓝图特定元数据（变量、父类、蓝图类型）。

**需求：** BLUE-01, BLUE-02, BLUE-03, BLUE-04, BLUE-05, BLUE-06

**工期估算：** 中等（蓝图结构已知，提取需谨慎）

**计划：** 待规划

### 成功标准

1. **给定**蓝图 .uasset 文件，**当**解析器检测资产类型，**则**资产被识别为蓝图并带正确蓝图类型。
2. **给定**蓝图导出，**当**解析器读取 ParentClass，**则**父类名称正确解析。
3. **给定**带变量的蓝图，**当**解析器提取 NewVariables，**则**所有变量具有正确的名称、类型和默认值。
4. **给定**变量类型，**当**解析器读取 FEdGraphPinType，**则**类型字符串人类可读（如 "Integer"、"Object Reference"）。

### 主要工作

- 蓝图类型检测（类名包含 "Blueprint" 或包路径模式）
- 父类解析（ParentClass FPackageIndex → ImportMap 或 ExportMap）
- 蓝图类型提取（BlueprintType 枚举）
- 变量定义解析（FBPVariableDescription 数组）
- FEdGraphPinType 解释（PinCategory、PinSubCategory、ContainerType）
- 变量元数据提取（Category、PropertyFlags、MetaDataArray）

### 依赖

- 阶段 1（需要 PackageFileSummary、NameMap、ExportMap、ImportMap）
- 阶段 2（需要属性解析来获取变量值）

### 风险

- **蓝图序列化变体：** 不同蓝图类型可能有不同结构
- **变量类型复杂性：** FEdGraphPinType 有多种变体（Array、Map、Set、Reference、Const）
- **默认值解析：** DefaultValue 存储为字符串，可能需要转换

### UE 源码参考

- `Blueprint.h` —— 蓝图结构
- `EdGraphPin.h` —— FEdGraphPinType
- `K2Node.h` —— 节点层次（用于类型检测）

---

## 阶段 4：输出与 CLI

**目标：** 生成 JSON 和文本输出格式；实现命令行接口用于工具执行。

**需求：** OUT-01, OUT-02, OUT-03, OUT-04, OUT-05, CLI-01, CLI-02, CLI-03, CLI-04, CLI-05, CLI-06

**工期估算：** 中等（输出格式设计，CLI 参数处理）

**计划：** 待规划

### 成功标准

1. **给定**解析后的资产数据，**当**输出格式器生成 JSON，**则**JSON 有效、分层且包含所有解析数据。
2. **给定**解析后的资产数据，**当**输出格式器生成文本，**则**文本人类可读并带语义描述。
3. **给定**蓝图数据，**当**生成 JSON 输出，**则**结构遵循 Package → Exports → Properties → Variables 层级。
4. **给定**CLI 参数，**当**工具带 --json 标志运行，**则**JSON 输出写入 stdout。

### 主要工作

- JSON 输出格式器（dataclasses.asdict + json.dumps）
- 文本输出格式器（语义描述，非原始数据）
- 概要输出格式器（精简概览）
- 层级结构设计（Package → Exports → Properties）
- 输出中的引用解析（FPackageIndex → 解析后的名称）
- CLI 参数解析（argparse）
- 输出格式标志（--json、--text、--summary）
- 错误处理与退出码
- 单文件执行支持

### 依赖

- 阶段 1（需要 PackageFileSummary、NameMap、ExportMap）
- 阶段 2（需要属性数据）
- 阶段 3（需要蓝图数据）

### 风险

- **输出大小：** 大资产可能产生巨大 JSON；需要概要格式
- **缺失数据处理：** 未解析引用需要 null 标记
- **CLI 易用性：** 需清晰帮助文本和错误信息

---

## 阶段 5：优化与安全

**目标：** 大文件性能优化，添加全面错误处理，实现安全检查。

**需求：** SAFE-01, SAFE-02, SAFE-03, SAFE-04, SAFE-05

**工期估算：** 中等（性能调优，边缘情况处理）

**计划：** 待规划

### 成功标准

1. **给定**超过 50MB 的 .uasset 文件，**当**解析器读取文件，**则**内存使用受限（使用 mmap，非全量读取）。
2. **给定**带无效偏移的文件，**当**解析器尝试定位，**则**错误被捕获并返回部分结果。
3. **给定**损坏/截断文件，**当**解析器读取，**则**解析器返回错误而不挂起或崩溃。

### 主要工作

- 内存映射归档（大文件用 FMappedArchive）
- 读取偏移前验证文件大小
- 定位前检查偏移边界
- 可恢复错误时返回部分结果
- 超时或大小限制保障安全
- 全面错误信息
- 边缘情况处理（截断文件、损坏区块）

### 依赖

- 阶段 1（需要 FArchive 基类）
- 阶段 2（需要属性解析）
- 阶段 3（需要蓝图提取）
- 阶段 4（需要输出处理）

### 风险

- **内存限制边缘情况：** mmap 在超大文件或特定平台可能失败
- **错误恢复复杂性：** 许多边缘情况需特定处理
- **性能与正确性：** mmap 快但需谨慎位置跟踪

---

## 里程碑概要

| 里程碑 | 阶段 | 交付物 |
|--------|------|--------|
| **v1.0** | 1-5 | 完整 Python .uasset 解析器，含蓝图提取、JSON/文本输出、CLI |

---

## 需求覆盖

| 类别 | 总数 | 阶段 1 | 阶段 2 | 阶段 3 | 阶段 4 | 阶段 5 |
|------|------|--------|--------|--------|--------|--------|
| 核心解析 | 8 | 8 | - | - | - | - |
| 属性解析 | 9 | - | 9 | - | - | - |
| 蓝图提取 | 6 | - | - | 6 | - | - |
| 输出格式 | 5 | - | - | - | 5 | - |
| CLI 与执行 | 6 | - | - | - | 6 | - |
| 性能与安全 | 5 | - | - | - | - | 5 |
| **合计** | 37 | 8 | 9 | 6 | 11 | 5 |

---

## 备注

- `.planning/research/` 中的研究文件为各阶段提供详细背景
- UE 5.7 源码位于 `D:/Program Files/Epic Games/Engine/UE_5.7`，为权威参考
- 专注于未 cooked/编辑器保存的资产（cooked 资产已剥离编辑器数据）
- 蓝图图提取（研究中的阶段 4）因复杂性推迟到 v2

---
*路线图创建日期：2026-04-27*
*最后更新：2026-04-28 Phase 1 计划创建*