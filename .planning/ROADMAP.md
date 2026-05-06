# uasset_read 路线图

**项目：** uasset_read — Unreal Engine .uasset 解析工具
**创建日期：** 2026-04-27
**当前状态：** v4.0 规划中

## Milestones

- ✅ **v1.0 MVP** — Phases 1-5 (shipped 2026-05-02) — [Archive](milestones/v1.0-ROADMAP.md)
- ✅ **v2.0 蓝图图解析** — Phases 6-10 (shipped 2026-05-02 via PR #2) — [Archive](milestones/v2.0-ROADMAP.md)
- ✅ **v3.x 解析完善+Skill+兼容性** — Phases 11-17 (shipped 2026-05-04 via PR #4) — [Archive](milestones/v3.x-ROADMAP.md)
- ✅ **v4.0 节点属性深度解析** — Phases 18-22 (shipped 2026-05-05)
- 🔵 **v5.0 架构重构与蓝图编译研究** — Phases 23-26 (active)

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
<summary>🔵 v5.0 架构重构与蓝图编译研究 (Phases 23-26) — ACTIVE</summary>

- [x] Phase 23: 模块化重构 (4 plans) — completed 2026-05-06
- [x] Phase 24: JSON 输出规范化 (4 plans) — completed 2026-05-06
- [x] Phase 25: 蓝图编译流程研究 (4 plans) — completed 2026-05-06
- [~] Phase 26: 蓝图元数据增强 (4 plans) — in progress
  - [ ] 26-01: 增强变量解析（默认值、属性）
  - [ ] 26-02: 增强函数解析（参数、返回值、属性）
  - [x] 26-03: 增强事件解析（自定义、多播、接口） — completed 2026-05-06
  - [ ] 26-04: 添加到 JSON 输出

**关键成就：**
- 模块化重构（src/ 目录结构、核心解析模块、蓝图解析模块）
- JSON 输出规范化（统一 Schema、输出格式化模块、Schema 验证）
- 蓝图编译流程研究（KismetCompiler.cpp 源码分析、蓝图虚拟机、节点到 C++ 映射）
- 事件元数据解析（FunctionParameter、MulticastDelegate、BlueprintEvent 类、函数标志位解析）

</details>

<details>
<summary>📅 v5.1 UnrealBridge 扩展集成 (Phases 27-29) — PLANNED</summary>

- [ ] Phase 27: UnrealBridge 可移植功能分析 (4 plans)
- [ ] Phase 28: 资产查询扩展 (4 plans)
- [ ] Phase 29: DataTable 解析扩展 (4 plans)

</details>

<details>
<summary>📅 v5.2 C++ 代码生成框架 (Phases 30-32) — PLANNED</summary>

- [ ] Phase 30: C++ 代码生成架构设计 (4 plans)
- [ ] Phase 31: 头文件生成 (4 plans)
- [ ] Phase 32: 实现文件生成 (4 plans)

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
**Plans**: 9 plans (Wave 1: 22-01 partial, Wave 2: 22-02 partial, Wave 3: 22-03 partial, Wave 4: 22-04 complete, Wave 5: 22-05 planned, Wave 6: 22-06 partial, Wave 7: 22-07 partial, Wave 8: 22-08 partial, Wave 9: 22-09 planned)

Plans:
- [x] 22-01-PLAN.md — 修复 read_ue_graph_node 跳过 UObject tagged properties (partial: ISSUE-02/03 remaining)
- [x] 22-02-PLAN.md — PinFriendlyName FText 跳过逻辑研究（发现：不适用于当前资产）
- [x] 22-03-PLAN.md — 深入修复 SerializePin 格式和 pins offset 计算 (partial: ISSUE-04/05 remaining)
- [x] 22-04-PLAN.md — 修复图判断和类名解析逻辑（TEST-01/04 通过）
- [x] 22-05-PLAN.md — 动态扫描定位 pins_offset（解决 TEST-02/03 失败）
- [x] 22-06-PLAN.md — 正确定位 pins_offset（FText 枚举值修正 + SourceIndex 位置修正）
- [x] 22-07-PLAN.md — Direction 和 PinType 序列化格式修复
- [x] 22-08-PLAN.md — 回滚 22-06 修改并添加调试输出，找出 Pin 解析失败根因 (partial: TEST-02/03 仍失败)
- [x] 22-09-PLAN.md — 修复 Pin 连接读取失败问题（pins_offset 动态扫描 + LinkedTo 数组读取）

### Phase 23: 模块化重构 ✓ COMPLETE
**Goal**: 将单文件 uasset_read.py 拆分为模块化架构
**Depends on**: Phase 22
**Success Criteria** (what must be TRUE):
  1. src/ 目录结构创建完成 ✓
  2. 核心解析模块提取完成 (core/) ✓
  3. 蓝图解析模块提取完成 (blueprint/) ✓
  4. 所有现有测试通过 ✓
**Plans**: 4 plans
**Completed**: 2026-05-06

Plans:
- [x] 23-01-PLAN.md — 创建项目新结构和 src/__init__.py
- [x] 23-02-PLAN.md — 提取核心解析模块 (core/archive.py, core/models.py, core/constants.py)
- [x] 23-03-PLAN.md — 提取蓝图解析模块 (blueprint/graph.py, blueprint/nodes.py, blueprint/metadata.py)
- [x] 23-04-PLAN.md — 创建兼容性包装和更新导入

### Phase 24: JSON 输出规范化 ✓ COMPLETE
**Goal**: 规范化 JSON 输出格式，为 C++ 代码生成做准备
**Depends on**: Phase 23
**Success Criteria** (what must be TRUE):
  1. 统一 JSON Schema 设计完成 ✓
  2. 输出格式化模块实现完成 ✓
  3. Schema 验证功能实现完成 ✓
  4. C++ 代码生成映射添加完成 ✓
**Plans**: 4 plans
**Completed**: 2026-05-06

Plans:
- [x] 24-01-PLAN.md — 设计统一 JSON Schema
- [x] 24-02-PLAN.md — 实现输出格式化模块
- [x] 24-03-PLAN.md — 更新现有输出接口
- [x] 24-04-PLAN.md — 添加 JSON Schema 验证

### Phase 25: 蓝图编译流程研究 ✓ COMPLETE
**Goal**: 深度研究蓝图如何编译为 C++/字节码
**Depends on**: Phase 24
**Requirements**: COMP-01, COMP-02, COMP-03, COMP-04
**Success Criteria** (what must be TRUE):
  1. 理解蓝图编译器核心流程 ✓
  2. 理解蓝图虚拟机执行模型 ✓
  3. 提取节点到 C++ 的映射关系 ✓
  4. 编写完整研究文档 ✓
**Plans**: 4 plans
**Completed**: 2026-05-06

Plans:
- [x] 25-01-PLAN.md — COMP-01 研究蓝图编译器源码 (KismetCompiler.cpp)
- [x] 25-02-PLAN.md — COMP-02 研究蓝图虚拟机源码
- [x] 25-03-PLAN.md — COMP-03 提取节点到 C++ 的映射关系
- [x] 25-04-PLAN.md — COMP-04 编写研究文档

### Phase 26: 蓝图元数据增强
**Goal**: 增强蓝图变量、函数、事件的解析能力
**Depends on**: Phase 25
**Requirements**: META-01, META-02, META-03, META-04
**Success Criteria** (what must be TRUE):
  1. 变量元数据完整（默认值、属性）
  2. 函数元数据完整（参数、返回值、属性）
  3. 事件元数据完整（自定义、多播、接口）
  4. JSON 输出包含增强元数据
**Plans**: 4 plans

Plans:
- [ ] 26-01-PLAN.md — META-01 增强变量解析（默认值、属性）
- [ ] 26-02-PLAN.md — META-02 增强函数解析（参数、返回值、属性）
- [ ] 26-03-PLAN.md — META-03 增强事件解析（自定义、多播、接口）
- [ ] 26-04-PLAN.md — META-04 添加到 JSON 输出

---

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1-5 | v1.0 MVP | 25 | Complete | 2026-05-02 |
| 6-10 | v2.0 蓝图图解析 | 20 | Complete | 2026-05-02 |
| 11-17 | v3.x 解析完善+Skill | 23 | Complete | 2026-05-04 |
| 18 | Pin序列化解析 | 4 | Complete | 2026-05-04 |
| 19 | 连接关系重建 | 3 | Complete | 2026-05-04 |
| 20 | 整合输出 | 2 | Complete | 2026-05-05 |
| 21 | 验证测试 | 1 | Complete | 2026-05-05 |
| 22 | 节点序列化修复 | 9 | Complete | 2026-05-05 |
| 23 | 模块化重构 | 4 | Complete | 2026-05-06 |
| 24 | JSON 输出规范化 | 4 | Complete | 2026-05-06 |
| 25 | 蓝图编译流程研究 | 4 | Complete | 2026-05-06 |
| 26 | 蓝图元数据增强 | 4 | Planned | - |

**Total:** 32 phases (24 complete, 0 partial, 8 planned)

---

## Backlog

暂无backlog阶段。

---
*最后更新：2026-05-06 — v5.0 Phase 23-24 完成，Phase 25-26 规划中*