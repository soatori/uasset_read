# uasset_read 路线图

**项目：** uasset_read — Unreal Engine .uasset 解析工具
**创建日期：** 2026-04-27
**当前里程碑：** v6.0 模块化重构

## Milestones

- ✅ **v1.0 MVP** — Phases 1-5 (shipped 2026-05-02) — [Archive](milestones/v1.0-ROADMAP.md)
- ✅ **v2.0 蓝图图解析** — Phases 6-10 (shipped 2026-05-02 via PR #2) — [Archive](milestones/v2.0-ROADMAP.md)
- ✅ **v3.x 解析完善+Skill+兼容性** — Phases 11-17 (shipped 2026-05-04 via PR #4) — [Archive](milestones/v3.x-ROADMAP.md)
- ✅ **v4.0 节点属性深度解析** — Phases 18-22 (shipped 2026-05-05) — [Archive](milestones/v4.0-ROADMAP.md)
- ✅ **v5.0 原功能完善及后续重构计划** — Phases 23-26 (archived 2026-05-06) — [Archive](milestones/v5.0-ROADMAP.md)
- ✅ **v5.1 项目结构初始化** — Phase 27 only (archived 2026-05-07) — [Archive](milestones/v5.1-ROADMAP.md)
- 🔵 **v6.0 模块化重构** — Phases 28-33 (active)
- ⬜ **v7.0 深度序列化解析** — Phases 34-38 (planned)
- ⬜ **v8.0 蓝图完整解析** — Phases 39-43 (planned)
- ⬜ **v9.0 全资产覆盖与JSON规范化** — Phases 44-48 (planned)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-5) — SHIPPED 2026-05-02</summary>

- [x] Phase 1: 核心解析 (8 plans) — completed 2026-05-02
- [x] Phase 2: 属性解析 (3 plans) — completed 2026-05-02
- [x] Phase 3: 蓝图提取 (4 plans) — completed 2026-05-02
- [x] Phase 4: 输出与CLI (5 plans) — completed 2026-05-02
- [x] Phase 5: 优化与安全 (5 plans) — completed 2026-05-02

详见：[milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

<details>
<summary>✅ v2.0 蓝图图解析 (Phases 6-10) — SHIPPED 2026-05-02 via PR #2</summary>

- [x] Phase 6: 导出表修复 (2 plans) — completed 2026-05-02
- [x] Phase 7: 蓝图图核心解析 (3 plans) — completed 2026-05-02
- [x] Phase 8: 蓝图图输出增强 (4 plans) — completed 2026-05-02
- [x] Phase 9: 高级属性类型 (3 plans) — completed 2026-05-02
- [x] Phase 10: 依赖分析 (6 plans including gap closure) — completed 2026-05-02

详见：[milestones/v2.0-ROADMAP.md](milestones/v2.0-ROADMAP.md)

</details>

<details>
<summary>✅ v3.x 解析完善+Skill+兼容性 (Phases 11-17) — SHIPPED 2026-05-04 via PR #4</summary>

- [x] Phase 11: ExportMap属性值提取 (6 plans) — completed 2026-05-03
- [x] Phase 12: BlueprintVariables完整提取 (3 plans) — completed 2026-05-03
- [x] Phase 13: 组件变换属性解析 (3 plans) — completed 2026-05-03
- [x] Phase 14: 输出格式优化并冻结 (4 plans) — completed 2026-05-03
- [x] Phase 15: Claude Code skill封装 (3 plans) — completed 2026-05-03
- [x] Phase 16: Bool序列化修复 (1 plan) — completed 2026-05-03
- [x] Phase 17: 属性解析修复 (3 plans) — completed 2026-05-04

详见：[milestones/v3.x-ROADMAP.md](milestones/v3.x-ROADMAP.md)

</details>

<details>
<summary>✅ v4.0 节点属性深度解析 (Phases 18-22) — SHIPPED 2026-05-05</summary>

- [x] Phase 18: Pin序列化解析 (4 plans) — completed 2026-05-04
- [x] Phase 19: 连接关系重建 (3 plans) — completed 2026-05-04
- [x] Phase 20: 整合输出 (2 plans) — completed 2026-05-05
- [x] Phase 21: 验证测试 (1 plan) — completed 2026-05-05
- [x] Phase 22: 节点序列化修复 (9 plans including gap closure) — completed 2026-05-05

详见：[milestones/v4.0-ROADMAP.md](milestones/v4.0-ROADMAP.md)

</details>

<details>
<summary>✅ v5.0 原功能完善及后续重构计划 (Phases 23-26) — SHIPPED 2026-05-06</summary>

- [x] Phase 23: 模块化重构 (4 plans) — ❌ 未实现（技术债务，已纳入 v6.0）
- [x] Phase 24: JSON 输出规范化 (4 plans) — ❌ 未实现（技术债务，已纳入 v9.0）
- [x] Phase 25: 蓝图编译流程研究 (4 plans) — ✓ 完成 2026-05-06
- [x] Phase 26: 蓝图元数据增强 (4 plans) — ⚠️ 部分完成 2026-05-06

详见：[milestones/v5.0-ROADMAP.md](milestones/v5.0-ROADMAP.md)

</details>

<details>
<summary>✅ v5.1 项目结构初始化 (Phase 27 only) — ARCHIVED 2026-05-07</summary>

- [x] Phase 27: 项目结构初始化 — constants.py + exceptions.py ✓ Complete 2026-05-07

详见：[milestones/v5.1-ROADMAP.md](milestones/v5.1-ROADMAP.md)

</details>

<details>
<summary>🔵 v6.0 模块化重构 (Phases 28-33) — IN PROGRESS</summary>

**设计原则：** 允许清理旧代码和技术栈，不保留向后兼容层。

- [x] Phase 27: 项目结构初始化 (constants.py, exceptions.py) — Complete
- [x] Phase 28: 核心序列化模块 (FArchive, PackageFileSummary, ImportMap/ExportMap) — Complete 2026-05-11
- [ ] Phase 29: 数据模型模块 (所有 dataclass 模型和属性类型类)
- [ ] Phase 29: 数据模型模块 (所有 dataclass 模型和属性类型类)
- [ ] Phase 30: 属性解析模块 (PropertyTag, 属性解析器, 蓝图变量提取)
- [ ] Phase 31: 蓝图图解析模块 (图解析, 节点读取, 连接关系构建)
- [ ] Phase 32: 输出格式化模块 (JSON/Text/Markdown 输出)
- [ ] Phase 33: 入口与测试适配 (CLI, __init__.py, 测试更新, 删除旧文件)

**里程碑目标：**
- 将 7,957 行单文件重写为 ~12 个模块
- 所有测试更新适配并通过
- 零兼容包袱，直接清理技术债

</details>

<details>
<summary>⬜ v7.0 深度序列化解析 (Phases 34-38) — PLANNED</summary>

**UE 对应阶段：** Object Serialization (FLinkerLoad Tick/LoadAllObjects)

- [ ] Phase 34: 导出体数据解析
- [ ] Phase 35: Preload 数据解析
- [ ] Phase 36: 对象引用图构建
- [ ] Phase 37: BulkData 元数据解析
- [ ] Phase 38: 版本化序列化支持

</details>

<details>
<summary>⬜ v8.0 蓝图完整解析 (Phases 39-43) — PLANNED</summary>

**UE 对应阶段：** FinalizeCreation + UClass/UBlueprint 生成

- [ ] Phase 39: UBlueprintGeneratedClass 深度解析
- [ ] Phase 40: UberGraph 解析
- [ ] Phase 41: 事件分发图解析
- [ ] Phase 42: 生成类元数据
- [ ] Phase 43: 蓝图 JSON 输出完整性验证

</details>

<details>
<summary>⬜ v9.0 全资产覆盖与JSON规范化 (Phases 44-48) — PLANNED</summary>

- [ ] Phase 44: .umap/World 资产解析
- [ ] Phase 45: AssetRegistry 标签解析
- [ ] Phase 46: JSON Schema 定义与验证
- [ ] Phase 47: 性能优化
- [ ] Phase 48: 生产级验证

</details>

## Phase Details

### Phase 27: 项目结构初始化 ✅
**目标**: 创建src目录结构和配置文件，定义基础常量和异常
**依赖**: 无
**需求**: STRUCT-01, STRUCT-02, MOD-02, MOD-03
**Success Criteria** (what must be TRUE):
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
**Success Criteria** (what must be TRUE):
  1. FArchive类在 archive.py 中完整实现
  2. PackageFileSummary及相关类在 serializers/package_summary.py 中完整实现
  3. ObjectImport、ObjectExport、PackageIndex在 serializers/object_resources.py 中完整实现
**Plans**: 28-01 to 28-04 (UAT 9/9 pass)

### Phase 29: 数据模型模块 🔵
**目标**: 提取所有 dataclass 模型和属性类型类到独立模块
**依赖**: Phase 28
**需求**: MOD-06, MOD-07, MOD-08
**Success Criteria** (what must be TRUE):
  1. 所有模型类可从 uasset_read.models 导入
  2. asdict() 输出格式不变
  3. JSON 序列化兼容性保持不变
**Plans**: TBD

### Phase 30: 属性解析模块 🔵
**目标**: 提取所有属性解析逻辑（PropertyTag + 类型解析 + 蓝图变量提取）
**依赖**: Phase 29
**需求**: MOD-09, MOD-10, MOD-11
**Success Criteria** (what must be TRUE):
  1. 所有属性类型解析正确
  2. 蓝图变量、函数、事件元数据提取正常
  3. 组件变换属性解析正常
**Plans**: TBD

### Phase 31: 蓝图图解析模块 🔵
**目标**: 提取图解析、节点读取、连接关系构建到独立模块
**依赖**: Phase 30
**Success Criteria** (what must be TRUE):
  1. 图解析节点数量、连接数据与旧版一致
  2. 执行流追踪正确
  3. 数据流追踪正确
**Plans**: TBD

### Phase 32: 输出格式化模块 🔵
**目标**: 提取所有 JSON/Text/Markdown 输出格式化到独立模块
**依赖**: Phase 31
**Success Criteria** (what must be TRUE):
  1. JSON 输出格式与旧版一致
  2. Markdown/Text 输出正常
  3. 增强元数据输出正常
**Plans**: TBD

### Phase 33: 入口与测试适配 🔵
**目标**: CLI 入口、__init__.py 公共 API、测试更新、删除旧文件
**依赖**: Phase 28-32
**Success Criteria** (what must be TRUE):
  1. `python uasset_read.py file.uasset` 正常工作（通过 pyproject.toml 入口）
  2. 旧 uasset_read.py 已删除
  3. 所有测试适配并通过（修复 7 个失败，处理 48 个跳过）
  4. pyproject.toml 配置正确
**Plans**: TBD

## Progress

| Phase | Milestone | Requirements | Plans Complete | Status | Completed |
|-------|-----------|--------------|----------------|--------|-----------|
| 1-5 | v1.0 MVP | 25 | 25 | Complete | 2026-05-02 |
| 6-10 | v2.0 蓝图图解析 | 20 | 20 | Complete | 2026-05-02 |
| 11-17 | v3.x 解析完善+Skill | 23 | 23 | Complete | 2026-05-04 |
| 18-22 | v4.0 节点属性深度解析 | 14 | 14 | Complete | 2026-05-05 |
| 23-26 | v5.0 原功能完善 | 16 | 8 | Complete | 2026-05-06 |
| 27 | v5.1 项目结构初始化 | 4 | 2 | Complete | 2026-05-07 |
| 28 | v6.0 模块化重构 | 3 | 4 | Complete | 2026-05-11 |
| 29 | v6.0 模块化重构 | 3 | 0 | Not started | - |
| 30 | v6.0 模块化重构 | 3 | 0 | Not started | - |
| 31 | v6.0 模块化重构 | 3 | 0 | Not started | - |
| 32 | v6.0 模块化重构 | 3 | 0 | Not started | - |
| 33 | v6.0 模块化重构 | 2 | 0 | Not started | - |
| 34-38 | v7.0 深度序列化 | 15 | 0 | Planned | - |
| 39-43 | v8.0 蓝图完整解析 | 15 | 0 | Planned | - |
| 44-48 | v9.0 全资产+JSON规范化 | 15 | 0 | Planned | - |

**Total:** 48 phases (28 complete, 20 remaining)

**v6.0 Coverage:** 17/17 requirements mapped (100%)

---

*最后更新：2026-05-11 — Phase 28 核心序列化模块完成，准备开始 Phase 29 数据模型模块*
