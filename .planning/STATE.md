---
gsd_state_version: 1.0
milestone: v10.0
milestone_name: Blueprint-to-C++ 代码生成参考
status: in_progress
last_updated: "2026-05-18T02:02:00Z"
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 13
  completed_plans: 1
  percent: 7
---

# v10.0 — Blueprint-to-C++ 代码生成参考

## Phase 分解

| Phase | Name | Goal | Requirements | Status |
|-------|------|------|--------------|--------|
| 56 | C++ 类骨架提取 | 从 PackageSummary/ExportMap/组件列表导出完整 C++ 类声明骨架 | CPP-01, CPP-02, CPP-03 | In progress (1/3) |
| 57 | 函数签名映射 | 从函数图节点提取完整函数签名，输出 C++ 函数声明 | FUNC-01, FUNC-02, FUNC-03 | Not started |
| 58 | 函数体逻辑翻译 | 从执行流+数据流生成等价 C++ 语句序列 | BODY-01, BODY-02, BODY-03, BODY-04 | Not started |
| 59 | 组件初始化代码 | 从组件层次和属性生成构造函数初始化代码 | COMP-01, COMP-02 | Not started |
| 60 | 验证与测试 | 基于真实资产验证端到端 C++ 参考输出 | TEST-01, TEST-02, TEST-03 | Not started |

## 依赖关系

```
Phase 56 (类骨架) ──→ Phase 57 (函数签名) ──→ Phase 58 (函数体逻辑)
     │                                              │
     └──────────────────────────────────────────────┘
                                  │
Phase 59 (组件初始化) ─────────────┘
                                  │
                         Phase 60 (验证与测试)
```

- Phase 56 是基础，无依赖
- Phase 57 依赖 Phase 56（类声明完成后才能添加函数声明）
- Phase 58 依赖 Phase 57（函数签名完成后才能填充函数体）
- Phase 59 依赖 Phase 56（组件 UPROPERTY 声明完成后才能生成初始化代码）
- Phase 60 依赖 Phase 58 和 Phase 59（需要完整的类骨架+函数+组件初始化才能端到端验证）

## 目标

从蓝图 JSON 输出提取足够信息，使开发者能直接编写等价的 C++ 类实现。

## 当前状态

**Milestone 状态:** 执行中

**最近完成的计划:**
- 56-01: C++ Type Mapping Engine (2026-05-18, 2 commits)

## 上下文

- v9.0 已完成：执行流追踪、数据流追踪、function_graphs 输出
- 参考数据：`reference/蓝图节点文本参考.md`（BP_FirstPersonCharacter 真实导出）
- 测试基础：517 passed / 107 skipped（554 total，含 37 pre-existing failures）
- 技术栈：Python 3.10+，零运行时依赖
- 架构管道：`.uasset → FArchive → Serializers → Models → Parsers → Graph → Formatters`

## 覆盖验证

| Requirement | Phase | Status |
|-------------|-------|--------|
| CPP-01 | Phase 56 | Completed (56-01) |
| CPP-02 | Phase 56 | Completed (56-01) |
| CPP-03 | Phase 56 | Pending |
| FUNC-01 | Phase 57 | Pending |
| FUNC-02 | Phase 57 | Pending |
| FUNC-03 | Phase 57 | Pending |
| BODY-01 | Phase 58 | Pending |
| BODY-02 | Phase 58 | Pending |
| BODY-03 | Phase 58 | Pending |
| BODY-04 | Phase 58 | Pending |
| COMP-01 | Phase 59 | Pending |
| COMP-02 | Phase 59 | Pending |
| TEST-01 | Phase 60 | Pending |
| TEST-02 | Phase 60 | Pending |
| TEST-03 | Phase 60 | Pending |

**Coverage: 15/15 requirements mapped**

---
*Started: 2026-05-18*
*ROADMAP created: 2026-05-18*
