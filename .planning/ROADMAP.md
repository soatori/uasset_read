---
gsd_state_version: 1.0
milestone: null
milestone_name: null
status: planning_next
last_updated: "2026-05-02T23:50:00Z"
progress:
  total_phases: 0
  completed_phases: 0
  active_phase: null
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# uasset_read 路线图

**项目：** uasset_read — Unreal Engine .uasset 解析工具
**创建日期：** 2026-04-27
**当前状态：** v2.0 已发布，规划下一里程碑

## Milestones

- ✅ **v1.0 MVP** — Phases 1-5 (shipped 2026-05-02) — [Archive](milestones/v1.0-ROADMAP.md)
- ✅ **v2.0 蓝图图解析** — Phases 6-10 (shipped 2026-05-02 via PR #2) — [Archive](milestones/v2.0-ROADMAP.md)
- 📋 **v3.0 TBD** — 未来里程碑（规划中）

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

### 📋 v3.0 TBD (Planned)

下一里程碑规划中，待需求定义。

运行 `/gsd-new-milestone` 开始规划。

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

---

## Backlog

暂无backlog阶段。下一里程碑规划启动后添加。

---

*最后更新：2026-05-02 — v2.0 里程碑完成归档*