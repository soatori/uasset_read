---
gsd_state_version: 1.0
milestone: v14.0
milestone_name: CUE4Parse 核心对齐 — 修复 + Pak/IoStore + 输出格式
status: Active — Phase 76-80 planned
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
**Status:** Active — Roadmap defined, Phase 76-80 ready to discuss/plan

## Phase 分解

| Phase | Name | Goal | Requirements | Status |
|-------|------|------|--------------|--------|
| 76 | 对照 Wiki 修复 + FArchive 补齐 | 修复 🔧 标记项 + FCustomVersion + VersionContainer | COR-01, COR-02 | ⬜ Not Started |
| 77 | Pak 基础 + 压缩 + AES | .pak 解析 → Zlib/LZ4/Zstd/Oodle → AES 解密 | PAK-01, PAK-02, PAK-03 | ⬜ Not Started |
| 78 | UObject 继承树 + Linker 重构 | UObject hierarchy + FAssetArchive 模式重构 | COR-03, COR-04 | ⬜ Not Started |
| 79 | IoStore + IFileProvider | .utoc/.ucas 解析 + 文件发现 | PAK-04, PAK-05 | ⬜ Not Started |
| 80 | 输出格式 CUE4Parse 对齐 | PascalCase JSON + 文本 Schema 化 + BlueprintText 统一 | FMT-01, FMT-02, FMT-03 | ⬜ Not Started |

## 当前状态

**当前阶段:** Phase 76 — 对照 Wiki 修复 + FArchive 补齐 (待 discuss/plan)
**并行机会:** P76 和 P77 可并行（无共享依赖）
**遗留评估:** v13.0 Phase 75（EventGraph 字段级对齐）将在本里程碑末尾评估是否需要修复

## v14.0 完成度

| Phase | 范围 | 日期 | 状态 |
|-------|------|------|------|
| v14.0 P76 | 对照 Wiki 修复 + FArchive 补齐 | — | ⬜ Not Started |
| v14.0 P77 | Pak 基础 + 压缩 + AES | — | ⬜ Not Started |
| v14.0 P78 | UObject 继承树 + Linker 重构 | — | ⬜ Not Started |
| v14.0 P79 | IoStore + IFileProvider | — | ⬜ Not Started |
| v14.0 P80 | 输出格式对齐 | — | ⬜ Not Started |

## 交付物清单

| 交付物 | 位置 | 状态 |
|--------|------|------|
| 对照 Wiki | `docs/CUE4Parse-对照索引.md` | ✅ Complete |
| 研究 — Stack | `.planning/research/STACK.md` | ✅ Complete |
| 研究 — Features | `.planning/research/FEATURES.md` | ✅ Complete |
| 需求 | `.planning/REQUIREMENTS.md` | ✅ Complete |
| 路线图 | `.planning/ROADMAP.md` | ✅ Complete |
| 项目文档 | `.planning/PROJECT.md` | ✅ Updated |

## 下一步行动

1. **Phase 76 discuss/plan:** `/gsd:discuss-phase 76` — 对照 Wiki 修复 + FArchive 补齐
2. **Phase 77 parallel discuss/plan:** `/gsd:discuss-phase 77` — Pak 基础 + 压缩 + AES

---

*Updated: 2026-05-26 (v14.0 milestone initialized)*
