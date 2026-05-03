# uasset_read 路线图

**项目：** uasset_read — Unreal Engine .uasset 解析工具
**创建日期：** 2026-04-27
**当前状态：** v3.0 Phase 13规划完成，准备执行

## Milestones

- ✅ **v1.0 MVP** — Phases 1-5 (shipped 2026-05-02) — [Archive](milestones/v1.0-ROADMAP.md)
- ✅ **v2.0 蓝图图解析** — Phases 6-10 (shipped 2026-05-02 via PR #2) — [Archive](milestones/v2.0-ROADMAP.md)
- 🚀 **v3.0 解析完善 + Skill打包** — Phases 11-15 (planning 13/15, 13-01/13-03 complete)

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

**关键成就：**
- 修复导出表FObjectExport结构缺失字段
- 实现蓝图图三层解析（Graph → Node → Pin）
- 支持六种高级属性类型
- 构建ImportMap+SoftObjectPaths依赖图

</details>

### 🚀 v3.0 解析完善 + Skill打包 (Phases 11-15) — PLANNING IN PROGRESS

**目标：** 补齐缺失数值解析，输出可用结果，打包成Claude Code skill

- [x] **Phase 11: ExportMap属性值提取** — 从ExportMap提取组件属性值、变量默认值、输入动作引用（gap closure已完成）
- [x] **Phase 12: BlueprintVariables完整提取** — 提取蓝图变量完整信息，区分组件变量和普通变量（规划完成）
- [x] **Phase 13: 组件变换属性解析** — 解析组件的Location/Rotation/Scale变换属性（规划完成）
- [ ] **Phase 14: 输出格式优化并冻结** — 优化JSON输出格式，添加status字段、摘要模式、Markdown格式
- [ ] **Phase 15: Claude Code skill封装** — 创建SKILL.md、知识库、示例文件，封装成Claude Code skill

---

## Phase Details

### Phase 11: ExportMap属性值提取

**Goal:** 用户可以从ExportMap中提取完整的组件属性值、变量默认值和输入动作引用

**Depends on:** Phase 10 (依赖分析已完成，ParseResult数据结构稳定)

**Requirements:** EXTR-01

**Success Criteria** (what must be TRUE):
  1. 用户可以从ParseResult中读取ExportMap条目的属性值（组件属性如SkeletalMesh、AnimBlueprint等）
  2. 用户可以获取变量的默认值，且值与UE编辑器中显示一致
  3. 用户可以解析EnhancedInputAction引用，获取引用的输入动作名称
  4. 用户可以通过JSON输出查看完整的属性值层次结构（Package→Exports→Properties）

**Plans:** 6 plans (4 standard + 2 gap closure)

Plans:
- [x] 11-01-PLAN.md — 集成ExportMap属性解析 (Wave 1, completed)
- [x] 11-02-PLAN.md — 增强ObjectProperty解析 (Wave 2, completed)
- [x] 11-03-PLAN.md — 新增SoftObjectProperty解析器 (Wave 2, completed)
- [x] 11-04-PLAN.md — 创建完整测试覆盖 (Wave 3, completed)
- [x] 11-05-GAP-PLAN.md — 修复ScriptSerialization读取条件 (Wave 1, gap closure, completed)
- [x] 11-06-GAP-PLAN.md — 验证属性解析功能完整 (Wave 2, gap closure, completed)

**Gap Resolution:** UE5/UE4版本常量修正，ExportMap解析恢复正常

### Phase 12: BlueprintVariables完整提取

**Goal:** 用户可以获取蓝图变量的完整信息（名称、类型、默认值、元数据）并区分组件变量和普通变量

**Depends on:** Phase 11 (ExportMap属性值提取能力已建立)

**Requirements:** EXTR-02, EXTR-03, EXTR-05

**Success Criteria** (what must be TRUE):
  1. 用户可以从ParseResult.blueprint.variables中读取变量名称、类型和默认值
  2. 用户可以通过is_component字段区分组件变量（如SkeletalMeshComponent）和普通变量
  3. 用户可以读取变量元数据，包括Category、BlueprintReadWrite、EditAnywhere等标签
  4. 用户可以看到变量的类型完整显示（包括泛型参数，如TArray<UObject*>）
  5. 变量默认值正确处理多种类型（数值、字符串、布尔、向量、对象引用）

**Plans:** 3 plans

Plans:
- [x] 12-01-PLAN.md — BlueprintVariable数据模型增强 (Wave 1)
- [x] 12-02-PLAN.md — 变量解析函数增强 (Wave 2, depends on 12-01)
- [x] 12-03-PLAN.md — 测试和验证 (Wave 3, depends on 12-01, 12-02)

### Phase 13: 组件变换属性解析

**Goal:** 用户可以准确解析组件的位置、旋转、缩放变换属性

**Depends on:** Phase 12 (变量提取能力完整，组件变量可识别)

**Requirements:** EXTR-04

**Success Criteria** (what must be TRUE):
  1. 用户可以从组件属性中解析RelativeLocation（X/Y/Z坐标）
  2. 用户可以从组件属性中解析RelativeRotation（Roll/Pitch/Yaw角度）
  3. 用户可以从组件属性中解析RelativeScale3D（X/Y/Z缩放因子）
  4. 变换值使用正确的浮点精度（Location整数优先/3位，Rotation 3位，Scale 4位）
  5. FRotator角度保持UE度数格式（RotatorValue.unit='degrees'标注）

**Plans:** 3 plans

Plans:
- [x] 13-01-PLAN.md — Transform dataclass创建和精度处理 (Wave 1)
- [x] 13-02-PLAN.md — StructValue转换和组件变换提取 (Wave 2)
- [x] 13-03-PLAN.md — 测试和验证 (Wave 3)

### Phase 14: 输出格式优化并冻结

**Goal:** 输出格式对AI友好，包含status字段、摘要模式、Markdown格式，API稳定供skill使用

**Depends on:** Phase 13 (所有数据提取能力完整)

**Requirements:** OUT-01, OUT-02, OUT-03, OUT-04, OUT-05, OUT-06

**Success Criteria** (what must be TRUE):
  1. 用户可以在JSON输出中看到status字段（success/fail/error），一眼判断解析结果状态
  2. 用户可以通过--summary标志获取精简摘要，输出token减少70%以上
  3. 用户可以通过--markdown标志获取Markdown格式输出，同时友好人类和AI阅读
  4. 用户可以在顶层graphs_summary字段中看到execution_flows概览，无需深入graphs数组
  5. 用户可以看到关键字段（parent_class、variables等）的语义注释，理解字段含义
  6. 输出格式冻结后保持稳定，后续skill封装依赖此API不变

**Plans:** TBD

### Phase 15: Claude Code skill封装

**Goal:** 用户可以通过Claude Code直接调用uasset_read skill解析蓝图，skill提供完整知识库和示例

**Depends on:** Phase 14 (输出格式冻结，API稳定)

**Requirements:** SKILL-01, SKILL-02, SKILL-03, SKILL-04

**Success Criteria** (what must be TRUE):
  1. 用户可以在.claude/skills/uasset-read/目录中找到SKILL.md主文件，包含触发词和能力范围说明
  2. 用户可以在knowledge/目录中找到5-6个知识文件（blueprint-semantics.md、node-types.md、pin-type-mapping.md、cpp-conversion.md、common-patterns.md、troubleshooting.md）
  3. 用户可以在examples/目录中找到3-4个示例文件（basic-usage.md、blueprint-analysis.md、cpp-conversion.md）
  4. Claude Code可以通过触发词自动调用parse_uasset() API并正确解读输出结果
  5. 集成测试验证skill触发、API调用、输出解读三个环节正确工作

**Plans:** TBD

---

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1. 核心解析 | v1.0 | 8/8 | Complete | 2026-05-02 |
| 2. 属性解析 | v1.0 | 3/3 | Complete | 2026-05-02 |
| 3. 蓝图提取 | v1.0 | 4/4 | Complete | 2026-05-02 |
| 4. 输出与CLI | v1.0 | 5/5 | Complete | 2026-05-02 |
| 5. 优化与安全 | v1.0 | 5/5 | Complete | 2026-05-02 |
| 6. 导出表修复 | v2.0 | 2/2 | Complete | 2026-05-02 |
| 7. 蓝图图核心 | v2.0 | 3/3 | Complete | 2026-05-02 |
| 8. 蓝图图输出 | v2.0 | 4/4 | Complete | 2026-05-02 |
| 9. 高级属性 | v2.0 | 3/3 | Complete | 2026-05-02 |
| 10. 依赖分析 | v2.0 | 6/6 | Complete | 2026-05-02 |
| 11. ExportMap属性值提取 | v3.0 | 6/6 | Complete | 2026-05-03 |
| 12. BlueprintVariables完整提取 | v3.0 | 3/3 | Planning complete | - |
| 13. 组件变换属性解析 | v3.0 | 3/3 | Planning complete | - |
| 14. 输出格式优化并冻结 | v3.0 | 0/1 | Not started | - |
| 15. Claude Code skill封装 | v3.0 | 0/1 | Not started | - |

---

## Coverage Map

| Requirement | Phase | Status |
|-------------|-------|--------|
| EXTR-01 | Phase 11 | Complete |
| EXTR-02 | Phase 12 | Planning complete |
| EXTR-03 | Phase 12 | Planning complete |
| EXTR-04 | Phase 13 | Planning complete |
| EXTR-05 | Phase 12 | Planning complete |
| OUT-01 | Phase 14 | Pending |
| OUT-02 | Phase 14 | Pending |
| OUT-03 | Phase 14 | Pending |
| OUT-04 | Phase 14 | Pending |
| OUT-05 | Phase 14 | Pending |
| OUT-06 | Phase 14 | Pending |
| SKILL-01 | Phase 15 | Pending |
| SKILL-02 | Phase 15 | Pending |
| SKILL-03 | Phase 15 | Pending |
| SKILL-04 | Phase 15 | Pending |

**Coverage:** 15/15 requirements mapped ✓

---

## Backlog

暂无backlog阶段。

---

*最后更新：2026-05-03 — Phase 13规划完成，3 plans created*
