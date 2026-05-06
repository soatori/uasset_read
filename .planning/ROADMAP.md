# uasset_read 路线图

**项目：** uasset_read — Unreal Engine .uasset 解析工具
**创建日期：** 2026-04-27
**当前状态：** v5.0 归档准备中

## Milestones

- ✅ **v1.0 MVP** — Phases 1-5 (shipped 2026-05-02) — [Archive](milestones/v1.0-ROADMAP.md)
- ✅ **v2.0 蓝图图解析** — Phases 6-10 (shipped 2026-05-02 via PR #2) — [Archive](milestones/v2.0-ROADMAP.md)
- ✅ **v3.x 解析完善+Skill+兼容性** — Phases 11-17 (shipped 2026-05-04 via PR #4) — [Archive](milestones/v3.x-ROADMAP.md)
- ✅ **v4.0 节点属性深度解析** — Phases 18-22 (shipped 2026-05-05) — [Archive](milestones/v4.0-ROADMAP.md)
- 🔵 **v5.0 原功能完善及后续重构计划** — Phases 23-26 (准备归档，部分完成)

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
<summary>🔵 v5.0 原功能完善及后续重构计划 (Phases 23-26) — 部分完成</summary>

- [ ] Phase 23: 模块化重构 (4 plans) — ❌ 未实现（技术债务）
- [ ] Phase 24: JSON 输出规范化 (4 plans) — ❌ 未实现（技术债务）
- [x] Phase 25: 蓝图编译流程研究 (4 plans) — ✓ 完成 2026-05-06
- [x] Phase 26: 蓝图元数据增强 (4 plans) — ⚠️ 部分完成 2026-05-06

**关键成就：**
- 蓝图编译器核心流程研究（BLUEPRINT_COMPILER_FLOW.md）
- 蓝图虚拟机执行模型研究（BLUEPRINT_BYTECODE.md）
- 节点到 C++ 映射关系建立（NODE_TO_CPP_MAPPING.md）
- 元数据解析功能实现（变量、函数、事件）

**已知技术债务：**
- 模块化架构缺失（单文件 ~295KB）
- JSON 输出规范化缺失
- 部分功能受限（META-04 依赖 Phase 24）

详见：[milestones/v5.0-ROADMAP.md](milestones/v5.0-ROADMAP.md)

</details>

## Progress

| Phase | Milestone | Plans | Status | Completed |
|-------|-----------|-------|--------|-----------|
| 1-5 | v1.0 MVP | 25 | Complete | 2026-05-02 |
| 6-10 | v2.0 蓝图图解析 | 20 | Complete | 2026-05-02 |
| 11-17 | v3.x 解析完善+Skill | 23 | Complete | 2026-05-04 |
| 18-22 | v4.0 节点属性深度解析 | 14 | Complete | 2026-05-05 |
| 23 | v5.0 原功能完善 | 4 | Unimplemented | - |
| 24 | v5.0 原功能完善 | 4 | Unimplemented | - |
| 25 | v5.0 原功能完善 | 4 | Complete | 2026-05-06 |
| 26 | v5.0 原功能完善 | 4 | Partial | 2026-05-06 |

**Total:** 32 phases (27 complete, 1 partial, 2 unimplemented, 2 planned)

---

## Backlog

暂无 backlog 阶段。

---

*最后更新：2026-05-06 — v5.0 重新定位为"原功能完善及后续重构计划"，准备归档*