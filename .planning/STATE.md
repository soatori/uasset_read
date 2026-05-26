---
gsd_state_version: 1.0
version: dev-0.3.0
milestone: v14.0
milestone_name: — CUE4Parse 核心对齐
status: Active — Phase 74 ✅, 75 ✅, 77 ✅ (Pak parser + AES-ECB + compression + index 解析), Phase 76/78/79/80 待启动
last_updated: "2026-05-27"
progress:
  total_phases: 5
  completed_phases: 0
  total_plans: 5
  completed_plans: 1
  percent: 0
---

# v14.0 — CUE4Parse 核心对齐 (P76-80)

**参考设计:** CUE4Parse — FArchive/Pak/IoStore/Compression/Aes.cs/IFileProvider
**Started:** 2026-05-26
**Scope:** COR（核心修复）+ PAK（Pak/IoStore）+ FMT（输出格式 PascalCase 对齐）

## Phase 分解

| Phase | Name | Goal | Requirements | Status |
|-------|------|------|--------------|--------|
| 76 | FArchive 补齐 + PackageSummary + COR 修复 | FCustomVersion 体系、StructProperty 深度解析、FAssetArchive | COR-01/02 | ⬜ Next |
| 77 | Pak 解析 + 压缩 + AES | FPakInfo/Entry、Zlib/LZ4/Zstd/Oodle、AES-ECB/CBC | PAK-01/02/03 | ✅ Complete |
| 78 | UObject 继承树 + PackageLinker 重构 | UObject→UField 层次、FAssetArchive 模式、Provider/跨包解析收敛 | COR-03/04 | ⬜ Pending |
| 79 | IoStore (.utoc/.ucas) + 文件发现 | FIoStoreTocResource、DefaultFileProvider | PAK-04/05 | ⬜ Pending |
| 80 | 输出格式 PascalCase 对齐 | format_json_cue4parse、text_schema 化 | FMT-01/02/03 | ⬜ Pending |

### Phase 78 计划索引

- [78-01](./phases/phase-78/78-01-PLAN.md) — UObject 继承树 Python 化（COR-03）
- [78-02](./phases/phase-78/78-02-PLAN.md) — 独立 archive + preload 隔离（COR-04 / Wave 2）
- [78-03](./phases/phase-78/78-03-PLAN.md) — CUE4Parse 架构收敛：Provider、跨包解析、graph 单一路径（COR-04 / Wave 3）
- [INDEX](./phases/phase-78/INDEX.md) — Phase 78 总索引与依赖顺序

## Phase 74: PinReference null/non-null 主路径对齐 ✅

**完成日期:** 2026-05-26
**描述:** v13.0 遗留 phase，Pin 序列化主路径对齐

## Phase 75: EventGraph 节点字段级对齐 ✅

**完成日期:** 2026-05-26
**描述:** v13.0 遗留 phase，EventGraph 节点字段级对齐

## Phase 77: Pak 解析 + 压缩 + AES ✅

**完成日期:** 2026-05-26
**范围:** PAK-01 (PakEntry 解析) + PAK-02 (压缩分派) + PAK-03 (AES 加密)
**交付物:**

- `src/uasset_read/pak/` — FPakInfo/PakEntry/FPakDirectoryEntry 数据结构 + 序列化
- `src/uasset_read/pak/reader.py` — PakFileReader（open/extract/get_entry/context manager）
- `src/uasset_read/compression/dispatch.py` — Zlib/LZ4/Zstd/Oodle 分派 + 优雅降级
- `src/uasset_read/crypto/aes_ecb.py` — AES-ECB 解密 + CustomEncryption 委托
- `src/uasset_read/pak/index.py` — Legacy flat index + v10+ PathHashIndex/DirectoryIndex 解析
- `tests/test_pak_*.py` — 62 tests, 1 skipped

**UAT:** 8/8 通过

## 历史里程碑归档（v1.0-v13.0）

| 版本 | 范围 | 日期 | 测试 | 归档 |
|------|------|------|------|------|
| v1.0–v6.0 | MVP → 模块化重构 | 04-28 ~ 05-13 | — | `.planning/archive/v1-v7-SUMMARY.md` |
| v7.0 | UE FLinkerLoad 对象图重建 | 05-14 | — | `.planning/archive/v8.0/` |
| v8.0 | BP→C++ JSON 可翻译性 (P47-51) | 05-17 | — | `.planning/archive/v8.0/` |
| v9.0 | 函数调用链解析 (P52-55) | 05-17 | — | `.planning/archive/v9.0/` |
| v10.0 | BP→C++ 代码生成参考 (P56-60) | 05-18 | 1021 | `.planning/milestones/v10.0-ROADMAP.md` |
| v11.0 | Kismet 反编译器 + Agent 管线 (P61-66) | 05-20 | 1271 | `.planning/milestones/v11.0-ROADMAP.md` |
| v12.0 | 序列化修复 + N2C + 节点分类 (P67-71) | 05-21~22 | 1435 | `.planning/milestones/v12.0-TEST-REPORT.md` |
| v13.0 | Pin 修复 + Kismet 导航 (P72-75) | 05-23~26 | 1339 | `.planning/archive/v13.0-phases/` |

**详细记录:** `.planning/MILESTONES.md` + `.planning/ROADMAP.md` 里程碑表

---

*Updated: 2026-05-27 (v14.0 active, Phase 78 plan index expanded)*
