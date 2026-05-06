# uasset_read 路线图

**项目：** uasset_read — Unreal Engine .uasset 解析工具
**创建日期：** 2026-04-27
**当前里程碑：** v5.1 模块化重构与C++代码生成准备

## Milestones

- ✅ **v1.0 MVP** — Phases 1-5 (shipped 2026-05-02) — [Archive](milestones/v1.0-ROADMAP.md)
- ✅ **v2.0 蓝图图解析** — Phases 6-10 (shipped 2026-05-02 via PR #2) — [Archive](milestones/v2.0-ROADMAP.md)
- ✅ **v3.x 解析完善+Skill+兼容性** — Phases 11-17 (shipped 2026-05-04 via PR #4) — [Archive](milestones/v3.x-ROADMAP.md)
- ✅ **v4.0 节点属性深度解析** — Phases 18-22 (shipped 2026-05-05) — [Archive](milestones/v4.0-ROADMAP.md)
- ✅ **v5.0 原功能完善及后续重构计划** — Phases 23-26 (archived 2026-05-06) — [Archive](milestones/v5.0-ROADMAP.md)
- 🔵 **v5.1 模块化重构与C++代码生成准备** — Phases 27-32 (active)

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

**关键成就：**
- ExportMap属性值提取、BlueprintVariables完整提取
- 输出格式冻结（status字段、Markdown、摘要模式）
- Claude Code skill封装（知识库+示例+35测试）
- Bool序列化修复（1→4 bytes）、属性解析修复（D-01/D-02/D-03)

</details>

<details>
<summary>✅ v4.0 节点属性深度解析 (Phases 18-22) — SHIPPED 2026-05-05</summary>

- [x] Phase 18: Pin序列化解析 (4 plans) — completed 2026-05-04
- [x] Phase 19: 连接关系重建 (3 plans) — completed 2026-05-04
- [x] Phase 20: 整合输出 (2 plans) — completed 2026-05-05
- [x] Phase 21: 验证测试 (1 plan) — completed 2026-05-05
- [x] Phase 22: 节点序列化修复 (9 plans including gap closure) — completed 2026-05-05

详见：[milestones/v4.0-ROADMAP.md](milestones/v4.0-ROADMAP.md)

**关键成就：**
- Pin序列化解析（pin_id、pin_name、direction、pin_type、default_value、linked_to）
- 连接关系重建（connections、execution_flows、data_flows）
- 节点序列化修复（UObject tagged properties 跳过、pins_offset 动态扫描）
- 验证测试通过（节点数量、执行流程、数据流、节点属性）

</details>

<details>
<summary>✅ v5.0 原功能完善及后续重构计划 (Phases 23-26) — SHIPPED 2026-05-06</summary>

- [x] Phase 23: 模块化重构 (4 plans) — ❌ 未实现（技术债务）
- [x] Phase 24: JSON 输出规范化 (4 plans) — ❌ 未实现（技术债务）
- [x] Phase 25: 蓝图编译流程研究 (4 plans) — ✓ 完成 2026-05-06
- [x] Phase 26: 蓝图元数据增强 (4 plans) — ⚠️ 部分完成 2026-05-06

详见：[milestones/v5.0-ROADMAP.md](milestones/v5.0-ROADMAP.md)

**关键成就：**
- 蓝图编译器核心流程研究（BLUEPRINT_COMPILER_FLOW.md）
- 蓝图虚拟机执行模型研究（BLUEPRINT_BYTECODE.md）
- 节点到 C++ 映射关系建立（NODE_TO_CPP_MAPPING.md）
- 元数据解析功能实现（变量、函数、事件）

</details>

<details>
<summary>🔵 v5.1 模块化重构与C++代码生成准备 (Phases 27-32) — IN PROGRESS</summary>

- [ ] Phase 27: 项目结构初始化 (4 requirements) — TBD
- [ ] Phase 28: 核心模块拆分 (3 requirements) — TBD
- [ ] Phase 29: 属性解析模块拆分 (3 requirements) — TBD
- [ ] Phase 30: 架构验证 (2 requirements) — TBD
- [ ] Phase 31: JSON Schema定义 (3 requirements) — TBD
- [ ] Phase 32: 新模块单元测试 (1 requirement) — TBD

**里程碑目标：**
- 模块化重构（src layout，零依赖，分层架构）
- JSON Schema定义（为C++代码生成准备）
- 测试兼容性（所有现有测试通过）

</details>

## Phase Details

### Phase 27: 项目结构初始化
**目标**: 创建src目录结构和配置文件，定义基础常量和异常
**依赖**: 无
**需求**: STRUCT-01, STRUCT-02, MOD-02, MOD-03
**Success Criteria** (what must be TRUE):
  1. 项目具有src/uasset_read/目录结构，符合Python Packaging User Guide的src layout
  2. pyproject.toml配置完成，dependencies = []确保零依赖
  3. 常量模块包含所有版本号、属性类型阈值、边界常量（如PROPERTY_TAG_COMPLETE_TYPE_NAME = 1012）
  4. 异常模块包含所有异常类（UAssetError, VersionError, ParseError, ErrorContext）
**Plans**: TBD

### Phase 28: 核心模块拆分
**目标**: 拆分FArchive、PackageFileSummary、ImportMap/ExportMap到独立模块
**依赖**: Phase 27
**需求**: MOD-01, MOD-04, MOD-05
**Success Criteria** (what must be TRUE):
  1. FArchive类及其所有方法（read_i32, seek, tell等）在archive.py中完整实现
  2. PackageFileSummary及相关类在serializers/package_summary.py中完整实现
  3. ObjectImport、ObjectExport、PackageIndex在serializers/object_resources.py中完整实现
**Plans**: TBD

### Phase 29: 属性解析模块拆分
**目标**: 拆分PropertyTag、属性解析器、核心数据模型到独立模块
**依赖**: Phase 28
**需求**: MOD-06, MOD-07, MOD-08
**Success Criteria** (what must be TRUE):
  1. PropertyTag和parse_property_tag在serializers/property_tags.py中完整实现
  2. 属性解析器（parse_property及所有parse_*_property函数）在parsers/property_parser.py中完整实现
  3. ParseResult、StatusInfo在models/core.py中使用dataclass完整实现
**Plans**: TBD

### Phase 30: 架构验证
**目标**: 验证分层架构，避免循环导入，确保所有现有测试通过
**依赖**: Phase 29
**需求**: MOD-09, TEST-01
**Success Criteria** (what must be TRUE):
  1. 所有模块依赖单向（Output → Models → Parsers → Serializers → FArchive），无循环导入
  2. 所有359+现有测试用例通过，功能性零变更
  3. 使用延迟导入、TYPE_CHECKING、字符串类型注解等策略避免循环依赖
**Plans**: TBD

### Phase 31: JSON Schema定义
**目标**: 定义JSON Schema结构和验证功能，为C++代码生成准备
**依赖**: 无（可并行）
**需求**: SCHEMA-01, SCHEMA-02, SCHEMA-03
**Success Criteria** (what must be TRUE):
  1. JSON Schema定义ParseResult顶层结构、蓝图图结构、节点类型定义
  2. Schema验证功能可以验证输出JSON是否符合Schema定义（使用Python标准库json模块）
  3. Schema文档说明Schema结构、字段语义、C++映射关系
**Plans**: TBD

### Phase 32: 新模块单元测试
**目标**: 为新模块创建单元测试，验证模块接口正确性
**依赖**: Phase 30
**需求**: TEST-02
**Success Criteria** (what must be TRUE):
  1. 为每个新模块创建独立的测试文件（如tests/test_archive.py、tests/test_constants.py等）
  2. 所有新模块单元测试通过
  3. 测试覆盖模块的核心功能和边界情况
**Plans**: TBD

## Progress

| Phase | Milestone | Requirements | Plans Complete | Status | Completed |
|-------|-----------|--------------|----------------|--------|-----------|
| 1-5 | v1.0 MVP | 25 | 25 | Complete | 2026-05-02 |
| 6-10 | v2.0 蓝图图解析 | 20 | 20 | Complete | 2026-05-02 |
| 11-17 | v3.x 解析完善+Skill | 23 | 23 | Complete | 2026-05-04 |
| 18-22 | v4.0 节点属性深度解析 | 14 | 14 | Complete | 2026-05-05 |
| 23-26 | v5.0 原功能完善 | 16 | 8 | Complete | 2026-05-06 |
| 27 | v5.1 模块化重构 | 4 | 0 | Not started | - |
| 28 | v5.1 模块化重构 | 3 | 0 | Not started | - |
| 29 | v5.1 模块化重构 | 3 | 0 | Not started | - |
| 30 | v5.1 模块化重构 | 2 | 0 | Not started | - |
| 31 | v5.1 模块化重构 | 3 | 0 | Not started | - |
| 32 | v5.1 模块化重构 | 1 | 0 | Not started | - |

**Total:** 32 phases (27 complete, 6 not started)

**v5.1 Coverage:** 16/16 requirements mapped (100%)

---

*最后更新：2026-05-06 — v5.1 里程碑开始*