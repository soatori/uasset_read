# Phase 10: 依赖分析 - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning

<domain>
## Phase Boundary

构建 ImportMap + SoftObjectPaths 依赖图，检测循环依赖。此阶段交付依赖关系分析和输出格式化，不包含导出表依赖数组解析（Phase 6 推迟但超出当前 ROADMAP 范围）。

**交付能力：**
- ImportMap 依赖列表构建（{class, package, object} 对象格式）
- SoftObjectPaths 软引用依赖列表（{asset_path, sub_path} 对象格式）
- 循环依赖检测（DFS 图遍历，跨包循环）
- JSON 输出依赖图结构（imports、soft_references、circular_deps）

**Requirements:** DEPS-01, DEPS-02, DEPS-03, DEPS-04

**固定范围（来自 ROADMAP.md）：**
- 解析器能从 ImportMap 构建依赖列表（包路径、类名、对象名）
- 解析器能从 SoftObjectPaths 构建软引用依赖列表（AssetReference）
- 解析器能检测循环依赖（ImportMap 中的相互引用）
- JSON 输出包含依赖图结构（imports、soft_references、circular_deps）

**依赖：** Phase 7（蓝图图核心解析）—— ParseResult 已扩展 graphs 字段，顶层字段设计模式已确立

</domain>

<decisions>
## Implementation Decisions

### ImportMap 依赖格式
- **D-10-01:** `{class, package, object}` 对象格式 —— 每个 import 条目为 {"class": "ClassName", "package": "PackageName", "object": "ObjectName"}
  - **原因:** 结构清晰，便于 AI agent 理解引用来源；与 Phase 4 D-02 的顶层字段设计一致
- **D-10-02:** 统一处理，不区分类型 —— 所有 ImportMap 条目统一处理，不区分类引用 vs 对象引用
  - **原因:** 简单实现，满足 DEPS-01 需求；ObjectImport 结构统一
- **D-10-03:** 原始顺序 —— 按 ImportMap 原始顺序输出依赖列表
  - **原因:** 保持与 UE 文件一致的顺序；便于追踪引用来源
- **D-10-04:** 合并重复依赖 —— 相同 {class, package, object} 的条目合并为单一条目
  - **原因:** 减少输出冗余；用户选择简洁输出
- **D-10-05:** 顶层 `imports` 字段 —— imports 字段放在 ParseResult 顶层，与 graphs/blueprint 同级，始终输出（即使为空数组）
  - **原因:** 统一结构；非蓝图资产也有依赖信息；与 Phase 4 D-04 顶层字段设计一致

### SoftObjectPaths 解析
- **D-10-06:** 实现完整解析 —— 实现 `read_soft_object_paths()` 函数，从 soft_object_paths_offset 读取 FSoftObjectPath 数组
  - **原因:** 满足 DEPS-02；soft_object_paths_count/offset 已读取，需解析数据
- **D-10-07:** `{asset_path, sub_path}` 对象格式 —— 每个 SoftObjectPath 为 {"asset_path": "/Game/Path.Asset", "sub_path": ""}
  - **原因:** 与 UE FSoftObjectPath 结构一致；AssetPath + SubPathString 字段
- **D-10-08:** 顶层 `soft_references` 字段 —— soft_references 字段放在 ParseResult 顶层，与 imports/graphs 同级
  - **原因:** 统一结构；与 imports 字段同级便于对比
- **D-10-09:** 仅 UE5 >= 1008 —— 仅在 file_version_ue5 >= UE5_ADD_SOFTOBJECTPATH_LIST (1008) 时解析，UE4 文件返回空数组
  - **原因:** 满足 DEPS-02 版本条件；UE4 文件无 SoftObjectPaths 数据

### 循环依赖检测
- **D-10-10:** DFS 图遍历 —— 使用深度优先搜索检测 ImportMap 中的循环路径
  - **原因:** 标准图算法；满足 DEPS-03
- **D-10-11:** 跨包循环检测 —— 检测 ImportMap 中相同 class_package 的相互引用
  - **原因:** ImportMap 仅包含跨包引用；同一包内引用在 ExportMap 中
- **D-10-12:** 路径数组格式 —— 每个循环路径为 ["A.Package", "B.Package", "A.Package"] 字符列表
  - **原因:** 满足 DEPS-04 示例；清晰展示循环路径
- **D-10-13:** 顶层 `circular_deps` 字段 —— circular_deps 字段放在 ParseResult 顶层，与 imports/soft_references 同级
  - **原因:** 满足 DEPS-04 JSON 结构；便于查看循环依赖

### 依赖数组处理
- **D-10-14:** 不处理导出依赖数组 —— FirstExportDependency + 4 个依赖数组不在此阶段实现
  - **原因:** 满足 ROADMAP 范围；Phase 6 D-06 推迟但超出当前需求；DEPS-01~04 仅涉及 ImportMap 和 SoftObjectPaths
- **D-10-15:** 不处理 preload_dependencies —— preload_dependency_count/offset 仅作为 PackageFileSummary 元信息保留
  - **原因:** 满足 ROADMAP 范围；preload_dependencies 与 ImportMap 功能重叠

### Claude's Discretion
- ImportMap 合并重复的具体实现（去重算法选择）
- DFS 循环检测的具体实现细节（节点标识、路径记录）
- soft_references 数组的解析函数实现细节
- 单元测试组织
- 错误处理和边界情况（空 ImportMap、无循环依赖）

</decisions>

<canonical_refs>
## Canonical References

**下游 agent 必须在规划或实现前阅读这些。**

### UE 源码参考（SoftObjectPaths）
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Private/UObject/PackageFileSummary.cpp` 第 282-285 行 —— SoftObjectPaths 序列化
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/Core/Public/UObject/SoftObjectPath.h` —— FSoftObjectPath 结构定义

### UE 源码参考（ImportMap）
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Private/UObject/ObjectResource.cpp` 第 40-85 行 —— FObjectImport 序列化
- `D:/Program Files/Epic Games/Engine/UE_5.7/Engine/Source/Runtime/CoreUObject/Public/UObject/ObjectResource.h` 第 75-120 行 —— FObjectImport 结构定义

### 项目现有代码
- `uasset_read.py` 第 646-657 行 —— ObjectImport dataclass（已完整实现）
- `uasset_read.py` 第 1422-1461 行 —— read_import_map() 函数（已完整实现）
- `uasset_read.py` 第 1066-1070 行 —— soft_object_paths_count/offset 读取（PackageFileSummary）
- `uasset_read.py` 第 942 行 —— ParseResult.import_map 字段（已存在）
- `uasset_read.py` 第 2856-2999 行 —— format_json_full(), format_json_summary()（Phase 4 已实现，需扩展）
- `uasset_read.py` 第 3208-3302 行 —— create_parser(), main() CLI 实现（Phase 4 已实现）

### 项目规划文档
- `.planning/PROJECT.md` —— 项目核心价值、约束（零运行时依赖）
- `.planning/REQUIREMENTS.md` —— DEPS-01, DEPS-02, DEPS-03, DEPS-04 需求定义
- `.planning/ROADMAP.md` —— Phase 10 成功标准
- `.planning/phases/06-export-table-fix/06-CONTEXT.md` —— Phase 6 D-06（依赖数组推迟）
- `.planning/phases/07-blueprint-graph-core/07-CONTEXT.md` —— Phase 7 D-04（顶层 graphs 字段）
- `.planning/phases/04-output-and-cli/04-CONTEXT.md` —— Phase 4 D-01~D-27（JSON 结构、顶层字段设计）

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **ObjectImport dataclass:** 已完整实现（class_package, class_name, object_name），可直接遍历构建 imports 输出
- **read_import_map() 函数:** 已完整实现，返回 List[ObjectImport]
- **ParseResult.import_map:** 已存在顶层字段，可直接访问
- **soft_object_paths_count/offset:** 已在 PackageFileSummary 中读取，需实现 read_soft_object_paths()
- **format_json_full():** Phase 4 已实现，需扩展添加 imports/soft_references/circular_deps 字段
- **create_parser():** Phase 4 已实现，可考虑添加 --dependencies 标志（可选）

### Established Patterns
- **顶层字段设计:** graphs/blueprint 同级模式（Phase 7 D-04, Phase 4 D-04）
- **dataclasses + asdict():** JSON 输出直接兼容（Phase 1 D-06）
- **版本条件读取:** read_package_summary() 中大量版本检查模式可复用
- **合并重复:** Python set 或 dict 去重模式

### Integration Points
- ParseResult: 需扩展添加 soft_references, circular_deps 字段
- read_soft_object_paths(): 新函数，从 soft_object_paths_offset 读取数据
- build_dependency_graph(): 新函数，从 ImportMap 构建依赖列表
- detect_circular_deps(): 新函数，DFS 循环检测
- format_json_full(): 需扩展添加依赖字段输出

</code_context>

<specifics>
## Specific Ideas

- "{class, package, object} 对象格式" —— 用户确认结构清晰优先
- "合并重复依赖" —— 用户选择简洁输出，不记录引用次数
- "顶层 imports/soft_references/circular_deps 字段" —— 统一结构设计
- "仅 UE5 >= 1008" —— 严格版本条件，不尝试所有版本

</specifics>

<deferred>
## Deferred Ideas

推迟到后续阶段的实现：

### v3（高级依赖分析）
- FirstExportDependency + 4 个导出依赖数组解析
- preload_dependencies 解析（PackageFileSummary 中的 preload_dependency_count/offset）
- 导出条目依赖关系分析（ExportMap 内部依赖）
- 依赖关系可视化输出（DOT/SVG 格式）
- 更复杂的循环依赖检测（包含 ExportMap 内部引用）

None — discussion stayed within phase scope

</deferred>

---

*Phase: 10-dependency-analysis*
*Context gathered: 2026-05-02*