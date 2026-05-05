# uasset_read 路线图

**项目：** uasset_read — Unreal Engine .uasset 解析工具
**创建日期：** 2026-04-27
**当前状态：** v4.0 规划中

## Milestones

- ✅ **v1.0 MVP** — Phases 1-5 (shipped 2026-05-02) — [Archive](milestones/v1.0-ROADMAP.md)
- ✅ **v2.0 蓝图图解析** — Phases 6-10 (shipped 2026-05-02 via PR #2) — [Archive](milestones/v2.0-ROADMAP.md)
- ✅ **v3.x 解析完善+Skill+兼容性** — Phases 11-17 (shipped 2026-05-04 via PR #4) — [Archive](milestones/v3.x-ROADMAP.md)
- 🔵 **v4.0 节点属性深度解析** — Phases 18-21 (active)

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
<summary>🔵 v4.0 节点属性深度解析 (Phases 18-21) — ACTIVE</summary>

- [x] Phase 18: Pin序列化解析 (4 plans) — completed 2026-05-04
- [x] Phase 19: 连接关系重建 (3 plans) — completed 2026-05-04
- [ ] Phase 20: 整合输出 (2 plans planned)
- [ ] Phase 21: 验证测试 (1 plan planned)

</details>

---

## Phase Details

### Phase 18: Pin序列化解析 ✓ COMPLETE
**Goal**: 用户可以在JSON中看到每个Pin的完整信息，不包含字节细节
**Depends on**: Phase 17
**Requirements**: PIN-01, PIN-02, PIN-03, PIN-04, PIN-05
**Success Criteria** (what must be TRUE):
  1. 用户可以在JSON中看到每个Pin的pin_id、pin_name、direction字段 ✓
  2. 用户可以在JSON中看到每个Pin的pin_type结构（category、sub_category、container_type、is_reference、is_const） ✓
  3. 用户可以在JSON中看到每个Pin的default_value（非空时） ✓
  4. 用户可以在JSON中看到每个Pin的linked_to数组，包含连接的节点和Pin引用 ✓
  5. 用户不会在JSON中看到offset、size、raw_bytes等底层字节细节 ✓
**Plans**: 4 plans
**Completed**: 2026-05-04

Plans:
- [x] 18-01-PLAN.md — CustomVersion常量 + UEdGraphPin dataclass扩展
- [x] 18-02-PLAN.md — Pin引用解析辅助函数 (read_pin_reference/read_pin_array)
- [x] 18-03-PLAN.md — 重写read_ue_graph_pin()核心函数
- [x] 18-04-PLAN.md — 修复read_ed_graph_pin_type()版本检查

### Phase 19: 连接关系重建 ✓ COMPLETE
**Goal**: 用户可以查看节点间的执行流和数据流关系
**Depends on**: Phase 18
**Requirements**: LINK-01, LINK-02, LINK-03
**Success Criteria** (what must be TRUE):
  1. 用户可以在JSON的connections数组中看到所有节点连接（from/to节点+Pin） ✓
  2. 用户可以在execution_flows中看到从Event节点开始的执行链路 ✓
  3. 用户可以在data_flows中看到Pin之间的数据传递关系 ✓
**Plans**: 3 plans
**Completed**: 2026-05-04

Plans:
- [x] 19-01-PLAN.md — LINK-01 connections数组构建（name模式支持，format_pin_ref()格式转换函数）
- [x] 19-02-PLAN.md — LINK-02 execution_flows起点扩展（4种起点类型 + branch_type字段）
- [x] 19-03-PLAN.md — LINK-03 data_flows构建（非exec pins数据流，扁平数组输出）

### Phase 20: 整合输出
**Goal**: 用户可以获得完整的节点、图、蓝图JSON结构
**Depends on**: Phase 19
**Requirements**: OUT-01, OUT-02, OUT-03
**Success Criteria** (what must be TRUE):
  1. 用户可以在JSON中看到每个节点的完整信息（node_name、node_type、node_guid、position、pins、function_reference等）
  2. 用户可以在JSON中看到每个Graph的完整信息（graph_name、graph_type、nodes、execution_flows、data_flows）
  3. 用户可以在JSON中看到蓝图的完整信息（blueprint_name、parent_class、graphs、variables）
**Plans**: 2 plans

Plans:
- [ ] 20-01-PLAN.md — OUT-01/02 节点和Graph输出结构重组（node_name派生、position嵌套、graph_type语义化映射）
- [ ] 20-02-PLAN.md — OUT-03 蓝图结构重组（单一blueprint对象、graphs移入内部、output_version升级到4.0）

### Phase 21: 验证测试
**Goal**: 验证JSON输出与UE编辑器信息一致，确保正确性
**Depends on**: Phase 20
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04
**Success Criteria** (what must be TRUE):
  1. 测试可以验证JSON中的节点数量与导出表一致
  2. 测试可以验证Jump执行流程（IA_Jump → Jump → StopJumping）正确构建
  3. 测试可以验证数据流（ActionValue_X/Y → 参数）正确解析
  4. 测试可以验证节点属性（FunctionReference.MemberName、NodeGuid）正确提取
**Plans**: 1 plan

Plans:
- [ ] 21-01-PLAN.md — TEST-01~04 验证测试实现（节点数量、执行流程、数据流、节点属性，使用真实资产集成测试）

### Phase 22: 节点序列化修复
**Goal**: 修复 Phase 21 发现的节点序列化问题，使 TEST-02/03/04 通过
**Depends on**: Phase 21 (gap closure)
**Requirements**: FIX-01 (修复 read_ue_graph_node 跳过 UObject properties), NODE-FIX-02 (PinFriendlyName FText 跳过), NODE-FIX-03 (K2Node 数量验证), FIX-04 (extract_blueprint_graphs 确确匹配), FIX-05 (resolve_class_name object_name), FIX-06 (动态扫描 pins_offset)
**Success Criteria** (what must be TRUE):
  1. execution_flows 包含 IA_Jump → Jump → StopJumping 链路 ✓
  2. data_flows 包含 ActionValue_X/Y 连接 ✓
  3. function_reference.MemberName 正确提取 ✓
  4. node_guid 非空（非 fallback 值） ✓
**Plans**: 8 plans (Wave 1: 22-01 partial, Wave 2: 22-02 partial, Wave 3: 22-03 partial, Wave 4: 22-04 complete, Wave 5: 22-05 planned, Wave 6: 22-06 partial, Wave 7: 22-07 partial, Wave 8: 22-08 planned)

Plans:
- [x] 22-01-PLAN.md — 修复 read_ue_graph_node 跳过 UObject tagged properties (partial: ISSUE-02/03 remaining)
- [x] 22-02-PLAN.md — PinFriendlyName FText 跳过逻辑研究（发现：不适用于当前资产）
- [x] 22-03-PLAN.md — 深入修复 SerializePin 格式和 pins offset 计算 (partial: ISSUE-04/05 remaining)
- [x] 22-04-PLAN.md — 修复图判断和类名解析逻辑（TEST-01/04 通过）
- [ ] 22-05-PLAN.md — 动态扫描定位 pins_offset（解决 TEST-02/03 失败）
- [x] 22-06-PLAN.md — 正确定位 pins_offset（FText 枚举值修正 + SourceIndex 位置修正）
- [x] 22-07-PLAN.md — Direction 和 PinType 序列化格式修复
- [x] 22-08-PLAN.md — 回滚 22-06 修改并添加调试输出，找出 Pin 解析失败根因 (partial: TEST-02/03 仍失败)

---

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1-5 | v1.0 MVP | 25 | Complete | 2026-05-02 |
| 6-10 | v2.0 蓝图图解析 | 20 | Complete | 2026-05-02 |
| 11-17 | v3.x 解析完善+Skill | 23 | Complete | 2026-05-04 |
| 18 | Pin序列化解析 | 4 | Complete | 2026-05-04 |
| 19 | 连接关系重建 | 3 | Complete | 2026-05-04 |
| 20 | 整合输出 | 2 | Planned | - |
| 21 | 验证测试 | 1 | Planned | - |
| 22 | 节点序列化修复 | 8 | Partial (8/8) | 2026-05-05 |

**Total:** 22 phases (19 complete, 3 partial, 0 planned)

---

## Backlog

暂无backlog阶段。

---
*最后更新：2026-05-05 — Phase 22-08 规划完成（回滚 22-06 修改并添加调试输出）*