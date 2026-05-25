---
gsd_state_version: 1.0
milestone: v14.0
milestone_name: CUE4Parse 核心对齐 — 修复 + Pak/IoStore + 输出格式
status: Active — Phase 76-80 planned, index-driven execution
last_updated: "2026-05-26"
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# v14.0 — CUE4Parse 核心对齐 — 修复 + Pak/IoStore + 输出格式

**Started:** 2026-05-26
**Status:** Active — Roadmap defined, Phase 76 ready to discuss/plan

## 索引驱动模式

每 Phase 开头先产出 `docs/reference/` 源码对照索引文档（CUE4Parse C# ↔ UE C++ ↔ uasset_read Python），后续 agent 直接引用索引执行。贯穿整个里程碑。

## Phase 分解

| Phase | 索引文档 | 实现目标 | Requirements | Status |
|-------|---------|---------|--------------|--------|
| 76 | FArchive + PackageSummary + FPropertyTag | COR-01/02 修复 | COR-01, COR-02 | ⬜ |
| 77 | PakFile | .pak parser + compression + AES | PAK-01~03 | ⬜ |
| 78 | UObject + PackageLinker | 继承树 + Linker 重构 | COR-03, COR-04 | ⬜ |
| 79 | IoStore | .utoc/.ucas + IFileProvider | PAK-04, PAK-05 | ⬜ |
| 80 | KismetExpression | 输出格式 PascalCase 对齐 | FMT-01~03 | ⬜ |

## 当前状态

**当前阶段:** Phase 76 — 核心序列化层源码索引 + FArchive 补齐 (待 discuss/plan)
**并行机会:** P76 和 P77 可并行（无共享依赖）
**遗留评估:** v13.0 Phase 75 里程碑末尾评估

## 索引文档清单

| 文档 | Phase | 状态 |
|------|-------|------|
| `docs/reference/FArchive-对照详解.md` | 76 | ⬜ |
| `docs/reference/PackageSummary-对照详解.md` | 76 | ⬜ |
| `docs/reference/FPropertyTag-对照详解.md` | 76 | ⬜ |
| `docs/reference/PakFile-对照详解.md` | 77 | ⬜ |
| `docs/reference/UObject-对照详解.md` | 78 | ⬜ |
| `docs/reference/PackageLinker-对照详解.md` | 78 | ⬜ |
| `docs/reference/IoStore-对照详解.md` | 79 | ⬜ |
| `docs/reference/Kismet-对照详解.md` | 80 | ⬜ |

## 下一步行动

1. **Phase 76 discuss:** `/gsd:discuss-phase 76` — 核心序列化层源码索引 + FArchive 补齐
2. **Phase 77 parallel:** `/gsd:discuss-phase 77` — Pak 文件索引 + 解析 + 压缩 + AES

---

*Updated: 2026-05-26 (v14.0 milestone initialized, index-driven roadmap)*
