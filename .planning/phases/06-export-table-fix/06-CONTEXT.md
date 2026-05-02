# Phase 6: 导出表修复 - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning

<domain>
## Phase Boundary

修复 v1.0 导出表解析的完整 FObjectExport 结构序列化。当前 `read_export_map()` 缺失多个字段导致偏移错位，影响后续蓝图图解析（Phase 7）。此阶段实现完整的导出表解析，确保所有字段正确读取。

**交付能力：**
- TemplateIndex 字段读取（条件：file_version_ue4 >= 506）
- bool flags 读取（bForcedExport, bNotForClient, bNotForServer）
- PackageGuid 读取（条件：UE5 < REMOVE_OBJECT_EXPORT_PACKAGE_GUID）
- bIsInheritedInstance 读取（条件：UE5 >= TRACK_OBJECT_EXPORT_IS_INHERITED）
- PackageFlags 读取（导出条目的）
- 其他 bool flags 读取（条件版本检查）
- ScriptSerializationOffset 正确命名和位置
- 错误上下文增强（导出表解析阶段信息）

**Requirements:** BUG-01, BUG-02, BUG-03

**固定范围（来自 ROADMAP.md）：**
- 解析器正确读取 FObjectExport.TemplateIndex 字段（UE4 >= 506）
- 解析器正确读取 FObjectExport.OuterIndex 字段（修复偏移错位）
- 导出表解析失败时返回清晰错误信息（包含偏移、期望值、实际值）

</domain>

<decisions>
## Implementation Decisions

### TemplateIndex 读取条件
- **D-01:** 统一版本检查 —— 所有文件检查 `file_version_ue4 >= 506`（VER_UE4_TemplateIndex_IN_COOKED_EXPORTS）
- **D-02:** 读取位置 —— TemplateIndex 在 SuperIndex 之后、OuterIndex 之前读取
- **D-03:** UE5 文件处理 —— UE5 文件的 FileVersionUE4 通常 >= 522，自动满足条件
- **原因:** FPackageFileVersion.operator>= 仅比较 FileVersionUE4；UE5 文件也有有效的 FileVersionUE4 值

### FObjectExport 完整结构
- **D-04:** 完整修复 —— 实现所有缺失字段（不仅仅是 TemplateIndex）
- **D-05:** 序列化顺序 —— 严格按 ObjectResource.cpp 第 130-217 行顺序：
  1. ClassIndex → 2. SuperIndex → 3. TemplateIndex (条件) → 4. OuterIndex → 5. ObjectName →
  6. ObjectFlags → 7-8. SerialSize/Offset → 9-11. bool flags → 12. PackageGuid (条件) →
  13. bIsInheritedInstance (条件) → 14. PackageFlags → 15-17. 其他 bool flags → 18. 依赖数组 (跳过) →
  19-20. ScriptSerializationStartOffset/EndOffset (条件)
- **D-06:** 依赖数组推迟 —— FirstExportDependency + 4 个依赖数组推迟到 Phase 10（依赖分析阶段）
- **原因:** 用户选择完整修复；依赖数组与 Phase 10 的依赖图功能直接相关

### bool flags 处理
- **D-07:** 位字段读取 —— bForcedExport, bNotForClient, bNotForServer 各读取 1 byte（bool）
- **D-08:** 条件 flags —— bIsInheritedInstance（UE5 >= 1011）、bNotAlwaysLoadedForEditorGame（UE4 >= ?）、bIsAsset（UE4 >= ?）、bGeneratePublicHash（UE5 >= 1015）
- **D-09:** ObjectFlags 处理 —— 仅保留 RF_Load 标志（参考 ObjectResource.cpp 第 141-147 行）
- **原因:** UE 源码明确 bool 序列化为单字节；条件读取避免旧版本文件偏移错位

### PackageGuid 处理
- **D-10:** 条件读取 —— 仅 UE5 < REMOVE_OBJECT_EXPORT_PACKAGE_GUID 时读取（16 bytes FGuid）
- **D-11:** 跳过策略 —— 读取但不存储（DummyPackageGuid），不影响解析结果
- **原因:** PackageGuid 在 UE5 >= 1010 已移除；读取是为了保持偏移正确

### 错误上下文增强（BUG-03）
- **D-12:** 导出表解析阶段信息 —— 当前导出索引、期望偏移、实际偏移、字段名
- **D-13:** 版本检查失败信息 —— 版本号、阈值、字段名（TemplateIndex 条件失败）
- **D-14:** 偏移验证失败信息 —— 字段名、期望位置、实际位置、剩余字节
- **D-15:** 使用 ErrorContext —— 扩展 Phase 5 D-18 的 ErrorContext 结构
- **原因:** 用户选择全面的错误上下文；便于定位导出表解析问题

### ObjectExport dataclass 扩展
- **D-16:** 新增字段 —— template_index: PackageIndex、b_forced_export: bool、b_not_for_client: bool、b_not_for_server: bool、package_flags: int、b_is_inherited_instance: bool (可选)
- **D-17:** 条件字段标注 —— 使用 Optional 或默认值表示条件字段
- **原因:** dataclass 需反映完整结构；JSON 输出应包含所有解析字段

### 测试验证策略
- **D-18:** OuterIndex 值对比 —— 修复前后 OuterIndex 值变化验证偏移错位修复
- **D-19:** TemplateIndex 非零验证 —— 检查 TemplateIndex 是否正确读取（非零值表示成功）
- **D-20:** UE 编辑器文件验证 —— 使用 UE 编辑器导出的文件进行验证
- **D-21:** Lyra 资产对比 —— 对比 Lyra 资产修复前后 JSON 输出
- **原因:** 多角度验证确保修复正确性

### Claude's Discretion
- 版本常量命名（VER_UE4_TemplateIndex_IN_COOKED_EXPORTS = 506）
- bool flags 的 Python 命名风格（b_forced_export vs bForcedExport）
- 条件字段的默认值选择
- 错误消息格式和详细程度
- 单元测试组织

</decisions>

<canonical_refs>
## Canonical References

**下游 agent 必须在规划或实现前阅读这些。**

### UE 源码参考（核心）
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Private/UObject/ObjectResource.cpp` 第 125-225 行 —— FObjectExport 序列化实现（完整顺序和条件）
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Public/UObject/ObjectResource.h` 第 226-350 行 —— FObjectExport 结构定义
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/Core/Public/UObject/ObjectVersion.h` 第 711 行 —— VER_UE4_TemplateIndex_IN_COOKED_EXPORTS = 506
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/Core/Public/UObject/ObjectVersion.h` 第 761-839 行 —— FPackageFileVersion 结构和 operator>= 实现

### 项目现有代码
- `uasset_read.py` 第 1267-1330 行 —— read_export_map() 当前实现（需修复）
- `uasset_read.py` 第 636-656 行 —— ObjectExport dataclass（需扩展）
- `uasset_read.py` 第 112-131 行 —— ErrorContext 结构（Phase 5 D-18，需扩展）
- `uasset_read.py` 第 448-512 行 —— PackageIndex 验证函数

### 项目规划文档
- `.planning/PROJECT.md` —— 项目核心价值、约束
- `.planning/REQUIREMENTS.md` —— BUG-01, BUG-02, BUG-03 需求定义
- `.planning/ROADMAP.md` —— Phase 6 成功标准
- `.planning/phases/05-optimization-security/05-CONTEXT.md` —— Phase 5 决策（ErrorContext D-18）

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **FArchive 类:** 所有读取方法已实现（read_i32, read_i64, read_u8, read_name 等）
- **PackageIndex dataclass:** 已有完整的索引解析和验证逻辑
- **ErrorContext dataclass:** Phase 5 D-18 已定义基础结构（offset, phase, operation, context_name）
- **版本常量:** UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS = 505 已定义

### Established Patterns
- **版本条件读取:** read_package_summary() 中大量使用，可复用模式
- **dataclass + field(default):** 条件字段使用默认值模式
- **边界验证:** validate_offset, validate_size 已实现

### Integration Points
- read_export_map(): 需重构添加缺失字段
- ObjectExport dataclass: 需扩展添加新字段
- ErrorContext: 需扩展添加导出表特定字段
- JSON 输出: 需更新 format_exports_list() 包含新字段

</code_context>

<specifics>
## Specific Ideas

- "完整修复所有缺失字段" —— 用户明确选择完整实现
- "依赖数组推迟到 Phase 10" —— 与依赖图功能对应
- "统一版本检查 file_version_ue4 >= 506" —— 不区分 UE4/UE5 文件
- "OuterIndex 值对比验证" —— 直接验证偏移错位修复效果

</specifics>

<deferred>
## Deferred Ideas

推迟到后续阶段的实现：

### Phase 10（依赖分析）
- FirstExportDependency 字段解析
- SerializationBeforeSerializationDependencies 数组解析
- CreateBeforeSerializationDependencies 数组解析
- SerializationBeforeCreateDependencies 数组解析
- CreateBeforeCreateDependencies 数组解析

### v3（高级功能）
- 导出表哈希验证
- 导出条目完整性检查

None — discussion stayed within phase scope

</deferred>

---

*Phase: 06-export-table-fix*
*Context gathered: 2026-05-02*