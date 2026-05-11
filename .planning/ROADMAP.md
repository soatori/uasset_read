# uasset_read 路线图

**项目：** uasset_read — Unreal Engine .uasset 解析工具
**创建日期：** 2026-04-27
**当前里程碑：** v6.0 模块化重构

## 里程碑概览

- ✅ **v1.0 MVP** — 阶段 1-5（已发布 2026-05-02）— [归档](milestones/v1.0-ROADMAP.md)
- ✅ **v2.0 蓝图图解析** — 阶段 6-10（已发布 2026-05-02，通过 PR #2）— [归档](milestones/v2.0-ROADMAP.md)
- ✅ **v3.x 解析完善+Skill+兼容性** — 阶段 11-17（已发布 2026-05-04，通过 PR #4）— [归档](milestones/v3.x-ROADMAP.md)
- ✅ **v4.0 节点属性深度解析** — 阶段 18-22（已发布 2026-05-05）— [归档](milestones/v4.0-ROADMAP.md)
- ✅ **v5.0 原功能完善及后续重构计划** — 阶段 23-26（已归档 2026-05-06）— [归档](milestones/v5.0-ROADMAP.md)
- ✅ **v5.1 项目结构初始化** — 仅阶段 27（已归档 2026-05-07）— [归档](milestones/v5.1-ROADMAP.md)
- 🔵 **v6.0 模块化重构** — 阶段 28-35（进行中）
- ⬜ **v7.0 深度序列化解析** — 阶段 36-40（已规划）
- ⬜ **v8.0 蓝图完整解析** — 阶段 41-45（已规划）
- ⬜ **v9.0 全资产覆盖与JSON规范化** — 阶段 46-50（已规划）

## 阶段列表

<details>
<summary>✅ v1.0 MVP（阶段 1-5）— 已发布 2026-05-02</summary>

- [x] Phase 1: 核心解析（8 个计划）— 已完成 2026-05-02
- [x] Phase 2: 属性解析（3 个计划）— 已完成 2026-05-02
- [x] Phase 3: 蓝图提取（4 个计划）— 已完成 2026-05-02
- [x] Phase 4: 输出与CLI（5 个计划）— 已完成 2026-05-02
- [x] Phase 5: 优化与安全（5 个计划）— 已完成 2026-05-02

详见：[milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

<details>
<summary>✅ v2.0 蓝图图解析（阶段 6-10）— 已发布 2026-05-02，通过 PR #2</summary>

- [x] Phase 6: 导出表修复（2 个计划）— 已完成 2026-05-02
- [x] Phase 7: 蓝图图核心解析（3 个计划）— 已完成 2026-05-02
- [x] Phase 8: 蓝图图输出增强（4 个计划）— 已完成 2026-05-02
- [x] Phase 9: 高级属性类型（3 个计划）— 已完成 2026-05-02
- [x] Phase 10: 依赖分析（6 个计划，含缺口补全）— 已完成 2026-05-02

详见：[milestones/v2.0-ROADMAP.md](milestones/v2.0-ROADMAP.md)

</details>

<details>
<summary>✅ v3.x 解析完善+Skill+兼容性（阶段 11-17）— 已发布 2026-05-04，通过 PR #4</summary>

- [x] Phase 11: ExportMap属性值提取（6 个计划）— 已完成 2026-05-03
- [x] Phase 12: BlueprintVariables完整提取（3 个计划）— 已完成 2026-05-03
- [x] Phase 13: 组件变换属性解析（3 个计划）— 已完成 2026-05-03
- [x] Phase 14: 输出格式优化并冻结（4 个计划）— 已完成 2026-05-03
- [x] Phase 15: Claude Code skill封装（3 个计划）— 已完成 2026-05-03
- [x] Phase 16: Bool序列化修复（1 个计划）— 已完成 2026-05-03
- [x] Phase 17: 属性解析修复（3 个计划）— 已完成 2026-05-04

详见：[milestones/v3.x-ROADMAP.md](milestones/v3.x-ROADMAP.md)

</details>

<details>
<summary>✅ v4.0 节点属性深度解析（阶段 18-22）— 已发布 2026-05-05</summary>

- [x] Phase 18: Pin序列化解析（4 个计划）— 已完成 2026-05-04
- [x] Phase 19: 连接关系重建（3 个计划）— 已完成 2026-05-04
- [x] Phase 20: 整合输出（2 个计划）— 已完成 2026-05-05
- [x] Phase 21: 验证测试（1 个计划）— 已完成 2026-05-05
- [x] Phase 22: 节点序列化修复（9 个计划，含缺口补全）— 已完成 2026-05-05

详见：[milestones/v4.0-ROADMAP.md](milestones/v4.0-ROADMAP.md)

</details>

<details>
<summary>✅ v5.0 原功能完善及后续重构计划（阶段 23-26）— 已发布 2026-05-06</summary>

- [x] Phase 23: 模块化重构（4 个计划）— ❌ 未实现（技术债务，已纳入 v6.0）
- [x] Phase 24: JSON 输出规范化（4 个计划）— ❌ 未实现（技术债务，已纳入 v9.0）
- [x] Phase 25: 蓝图编译流程研究（4 个计划）— ✓ 完成 2026-05-06
- [x] Phase 26: 蓝图元数据增强（4 个计划）— ⚠️ 部分完成 2026-05-06

详见：[milestones/v5.0-ROADMAP.md](milestones/v5.0-ROADMAP.md)

</details>

<details>
<summary>✅ v5.1 项目结构初始化（仅阶段 27）— 已归档 2026-05-07</summary>

- [x] Phase 27: 项目结构初始化 — constants.py + exceptions.py ✓ 已完成 2026-05-07

详见：[milestones/v5.1-ROADMAP.md](milestones/v5.1-ROADMAP.md)

</details>

<details>
<summary>🔵 v6.0 模块化重构（阶段 28-35）— 进行中</summary>

**设计原则：** 等价迁移现有 uasset_read.py 功能，不新增能力。零兼容包袱。

- [x] Phase 27: 项目结构初始化 (constants.py, exceptions.py) — 已完成
- [x] Phase 28: 核心序列化模块 (FArchive, PackageFileSummary, ImportMap/ExportMap) — 已完成 2026-05-11
- [x] Phase 28a: 测试基线修复 (7个已知失败修复 + stash关键bug合并) — 已完成 2026-05-11
- [x] Phase 29: 核心数据模型 (UEdGraph, UEdGraphNode, UEdGraphPin, ParseResult dataclasses) — 已完成 2026-05-11
- [x] Phase 29b: 属性与图数据模型 (PropertyTag, FunctionReference, 图连接数据结构) — 已合并到 Phase 30 一并实现
- [x] Phase 30: 属性解析模块 (PropertyTag, 属性解析器, 蓝图变量提取) — 已完成 2026-05-11
- [ ] Phase 31: 蓝图图解析模块 (图解析, 节点读取, 连接关系构建) — 等价迁移 Phase 7/18-22
- [ ] Phase 32: 输出格式化模块 (JSON/Text/Markdown 输出) — 等价迁移 Phase 14/20
- [ ] Phase 33: 入口与测试适配 (CLI, __init__.py, 测试更新, 删除旧文件)
- [ ] Phase 34: 等价验证 (新旧输出逐字段对比，零回归)

**里程碑目标：**
- 将 7,957 行单文件重写为 ~15 个模块
- 所有测试适配并通过（修复 7 个已知失败）
- 等价迁移：JSON/Text/Markdown 输出与旧版完全一致

**范围边界（v6.0 不包含）：**
- ❌ BulkData 内容解析 → v7.0
- ❌ UberGraph/事件分发图增强 → v8.0
- ❌ UBlueprintGeneratedClass 字节码反编译 → v8.0
- ❌ .umap/World 资产解析 → v9.0

</details>

<details>
<summary>⬜ v7.0 深度序列化解析（阶段 36-40）— 已规划</summary>

**UE 对应阶段：** Object Serialization (FLinkerLoad Tick/LoadAllObjects)

- [ ] Phase 36: 导出体数据解析 (ExportBody 完整反序列化)
- [ ] Phase 37: Preload 数据解析 (Preload 依赖链)
- [ ] Phase 38: 对象引用图构建 (跨对象引用关系)
- [ ] Phase 39: BulkData 元数据解析 (批量数据头/偏移/大小)
- [ ] Phase 40: 版本化序列化支持 (UE 版本兼容性矩阵)

</details>

<details>
<summary>⬜ v8.0 蓝图完整解析（阶段 41-45）— 已规划</summary>

**UE 对应阶段：** FinalizeCreation + UClass/UBlueprint 生成

- [ ] Phase 41: UBlueprintGeneratedClass 深度解析 (生成类结构)
- [ ] Phase 42: UberGraph 解析 (完整 UberGraph 数据)
- [ ] Phase 43: 事件分发图解析 (EventDispatcher 完整链路)
- [ ] Phase 44: 蓝图字节码反编译 (Kismet bytecode 参考解析)
- [ ] Phase 45: 蓝图 JSON 输出完整性验证

</details>

<details>
<summary>⬜ v9.0 全资产覆盖与JSON规范化（阶段 46-50）— 已规划</summary>

- [ ] Phase 46: .umap/World 资产解析
- [ ] Phase 47: AssetRegistry 标签解析
- [ ] Phase 48: JSON Schema 定义与验证
- [ ] Phase 49: 性能优化 (mmap, 并行解析, 缓存)
- [ ] Phase 50: 生产级验证 (压力测试, 边界资产覆盖)

</details>

## 阶段详情

### Phase 27: 项目结构初始化 ✅
**目标**: 创建src目录结构和配置文件，定义基础常量和异常
**依赖**: 无
**需求**: STRUCT-01, STRUCT-02, MOD-02, MOD-03
**成功标准**（必须满足）：
  1. 项目具有src/uasset_read/目录结构，符合Python Packaging User Guide的src layout
  2. pyproject.toml配置完成，dependencies = []确保零依赖
  3. 常量模块包含所有版本号、属性类型阈值、边界常量
  4. 异常模块包含所有异常类（UAssetError, VersionError, ParseError, ErrorContext）

- [x] 27-01-PLAN.md — 创建src目录结构和pyproject.toml ✓
- [x] 27-02-PLAN.md — 提取常量和异常到独立模块 ✓

### Phase 28: 核心序列化模块 ✅
**目标**: 提取 FArchive、PackageFileSummary、ImportMap/ExportMap 到独立模块
**依赖**: Phase 27
**需求**: MOD-01, MOD-04, MOD-05
**成功标准**（必须满足）：
  1. FArchive类在 archive.py 中完整实现
  2. PackageFileSummary及相关类在 serializers/package_summary.py 中完整实现
  3. ObjectImport、ObjectExport、PackageIndex在 serializers/object_resources.py 中完整实现
**计划**: 28-01 至 28-04（UAT 9/9 通过）

### Phase 28a: 测试基线修复 ✅
**目标**: 修复 7 个已知测试失败 + 合并 stash 中的关键 bug
**依赖**: Phase 28
**成功标准**（必须满足）：
  1. 修复 `build_graphs_summary()` 返回键名 `"graph_name"` → `"graph"` (2个测试)
  2. 修复 `build_execution_flows()` function_name 为空的问题 (1个测试)
  3. 合并 stash: peek_i32() 方法、ETextHistoryType 枚举修复、pin 读取容错 (4个测试)
  4. 所有 458 个测试中失败数从 7 降至 0，跳过数从 48 降至 ≤48

**计划**: 5 个 UAT 测试（全部通过）

**已知失败分类：**
| 测试文件 | 根因 | 修复方向 |
|------|------|----------|
| test_output_formatting.py:1315 | `graph_name` vs `graph` 键名不匹配 | 统一为 `graph` |
| test_phase14_output_formats.py:132 | 同上 | 同上 |
| test_phase21_verification.py:130 | Jump 函数调用节点未找到 | stash: pin 读取容错 |
| test_phase21_verification.py:163 | StopJumping 函数调用节点未找到 | 同上 |
| test_phase21_verification.py:224 | Move graph 数据流连接缺失 | stash: pin 读取修复 |
| test_phase21_verification.py:304 | function_reference 为 None | stash: 改进 FText 跳过逻辑 |
| test_skill_integration.py:186 | function_name 为空字符串 | 修复 execution_flows 提取 |

### Phase 29: 核心数据模型 ✅
**目标**: 提取 UEdGraph, UEdGraphNode, UEdGraphPin, ParseResult 等 core dataclass 到独立模块
**依赖**: Phase 28a
**需求**: MOD-06, MOD-07
**成功标准**（必须满足）：
  1. UEdGraph/Node/Pin dataclass 在 models/core.py 中定义
  2. ParseResult 在 models/result.py 中定义
  3. asdict() 输出格式与旧版完全一致
  4. JSON 序列化兼容性保持不变
**计划**: 29-01 至 29-03（全部完成于 2026-05-11）
- [x] 29-01-PLAN.md — 核心数据类（FEdGraphPinType, UEdGraphPin, UEdGraphNode, UEdGraph, FMemberReference）+ 模块导出 ✓
- [x] 29-02-PLAN.md — 节点类型子类（K2NodeCallFunction, K2NodeEvent, K2NodeKnot, EdGraphNodeComment, K2NodeEnhancedInputAction）继承 UEdGraphNode ✓
- [x] 29-03-PLAN.md — ParseResult, StatusInfo, BlueprintMetadata 辅助类 + 完整导出 ✓

### Phase 29b: 属性与图数据模型 ✅ (已合并到 Phase 30)
**目标**: 提取 PropertyTag, FunctionReference, 图连接数据结构到独立模块
**依赖**: Phase 29
**需求**: MOD-08
**成功标准**（必须满足）：
  1. PropertyTag/PropertyValue dataclass 在 models/properties.py 中定义
  2. FunctionReference/EventReference 在 models/references.py 中定义
  3. 图连接数据结构 (ExecutionFlow, DataFlow) 在 models/graph.py 中定义
  4. 所有模型类可从 uasset_read.models 导入
**状态**: 本 phase 未独立执行，PropertyTag/PropertyValue 等数据模型已在 Phase 30 (30-01-PLAN.md) 中一并实现完成。FunctionReference/EventReference 和图连接数据结构尚未实现，待 Phase 31 蓝图图解析时补充。

### Phase 30: 属性解析模块 ✅
**目标**: 提取所有属性解析逻辑（PropertyTag + 类型解析 + 蓝图变量提取）
**依赖**: Phase 29（Phase 29b 已合并入本 phase）
**需求**: MOD-06, MOD-07, MOD-09, MOD-10, MOD-11, TEST-01
**成功标准**（必须满足）：
  1. 所有属性类型解析正确
  2. 蓝图变量、函数、事件元数据提取正常
  3. 组件变换属性解析正常
**计划**: 30-01 至 30-03（3 个计划，全部完成）
- [x] 30-01-PLAN.md — PropertyTag/PropertyValue dataclasses + read_property_tag serializer + use_complete_type_name ✓
- [x] 30-02-PLAN.md — 14 parse_*_property functions + dispatcher + export loop ✓
- [x] 30-03-PLAN.md — blueprint/ module (variable extraction + component transform) + test verification ✓

### Phase 31: 蓝图图解析模块 🔵
**目标**: 提取图解析、节点读取、连接关系构建到独立模块（等价迁移 Phase 7/18-22 功能）
**依赖**: Phase 30
**成功标准**（必须满足）：
  1. 图解析节点数量、连接数据与旧版一致
  2. 执行流追踪正确
  3. 数据流追踪正确
  4. ⚠️ 范围：仅等价迁移现有功能，不包含 UberGraph/事件分发图增强
**计划**: 待制定

### Phase 32: 输出格式化模块 🔵
**目标**: 提取所有 JSON/Text/Markdown 输出格式化到独立模块（等价迁移 Phase 14/20 功能）
**依赖**: Phase 31
**成功标准**（必须满足）：
  1. JSON 输出格式与旧版一致
  2. Markdown/Text 输出正常
  3. 增强元数据输出正常
**计划**: 待制定

### Phase 33: 入口与测试适配 🔵
**目标**: CLI 入口、__init__.py 公共 API、测试更新、删除旧文件
**依赖**: Phase 28-32
**成功标准**（必须满足）：
  1. `python -m uasset_read file.uasset` 正常工作（通过 pyproject.toml 入口）
  2. 旧 uasset_read.py 已删除
  3. 所有测试适配并通过
  4. pyproject.toml 配置正确
**计划**: 待制定

### Phase 34: 等价验证 🔵
**目标**: 新旧输出逐字段对比，确保零回归
**依赖**: Phase 33
**成功标准**（必须满足）：
  1. 同一 .uasset 文件，新旧版本 JSON 输出 diff 为空
  2. 同一 .uasset 文件，新旧版本 Text/Markdown 输出 diff 为空
  3. 所有测试资产覆盖验证通过
**计划**: 待制定

## 进度总览

| Phase | 里程碑 | 需求数 | 计划完成数 | 状态 | 完成日期 |
|-------|-----------|--------------|----------------|--------|-----------|
| 1-5 | v1.0 MVP | 25 | 25 | 已完成 | 2026-05-02 |
| 6-10 | v2.0 蓝图图解析 | 20 | 20 | 已完成 | 2026-05-02 |
| 11-17 | v3.x 解析完善+Skill | 23 | 23 | 已完成 | 2026-05-04 |
| 18-22 | v4.0 节点属性深度解析 | 14 | 14 | 已完成 | 2026-05-05 |
| 23-26 | v5.0 原功能完善 | 16 | 8 | 已完成 | 2026-05-06 |
| 27 | v5.1 项目结构初始化 | 4 | 2 | 已完成 | 2026-05-07 |
| 28 | v6.0 模块化重构 | 3 | 4 | 已完成 | 2026-05-11 |
| 28a | v6.0 测试基线修复 | 5 | 5 | 已完成 | 2026-05-11 |
| 29 | v6.0 核心数据模型 | 2 | 3 | 已完成 | 2026-05-11 |
| 29b | v6.0 属性与图数据模型 | 1 | 0 | 已合并→30 | 2026-05-11 |
| 30 | v6.0 属性解析 | 6 | 3 | 已完成 | 2026-05-11 |
| 31 | v6.0 蓝图图解析 | 3 | 0 | 未开始 | - |
| 32 | v6.0 输出格式化 | 3 | 0 | 未开始 | - |
| 33 | v6.0 入口与测试适配 | 2 | 0 | 未开始 | - |
| 34 | v6.0 等价验证 | 2 | 0 | 未开始 | - |
| 36-40 | v7.0 深度序列化 | 15 | 0 | 已规划 | - |
| 41-45 | v8.0 蓝图完整解析 | 15 | 0 | 已规划 | - |
| 46-50 | v9.0 全资产+JSON规范化 | 15 | 0 | 已规划 | - |

**总计:** 50 个阶段（30 已完成，20 待执行）

**v6.0 需求覆盖:** 17/17 需求已映射（100%）+ 3 新增（测试基线/拆分模型/等价验证）

---

*最后更新：2026-05-12 — Phase 28a 测试基线修复完成，Phase 29 核心数据模型完成（3 个计划），Phase 29b 已合并到 Phase 30*
