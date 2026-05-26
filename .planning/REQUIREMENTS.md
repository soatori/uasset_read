# v14.0 Requirements — CUE4Parse 核心对齐

**Milestone:** v14.0 | **Date:** 2026-05-26 | **Status:** Active

## Scope

COR（核心修复）+ PAK（Pak/IoStore 解析）+ FMT（输出格式对齐）。EXP/GAM/ENH 归入 v15.0。

---

## COR — 核心修复层

- [ ] **COR-01**: 对照 Wiki 驱动修复
  - **What:** 按 docs/CUE4Parse-对照索引.md 中标记 🔧 的 2 项（StructProperty 深度解析、FAssetArchive 封装）逐一修复
  - **Verify:** StructProperty 内部字段（FVector/FRotator/FBodyInstance）完整提取，FAssetArchive 装饰器集成到 parse_uasset 管线
  - **Deps:** None

- [ ] **COR-02**: FArchive 层补齐
  - **What:** 新增 `FCustomVersion` 体系（GUID→Version 映射表），建立 `VersionContainer` 统一版本管理（EGame 枚举 + FPackageFileVersion + CustomVersionContainer）
  - **Verify:** 支持 `if (Ar.Ver >= EUEVersion.UE4_23)` 版本分支语法，CustomVersion 按 GUID 字符串键查询
  - **Deps:** None

- [ ] **COR-03**: UObject 继承树 Python 化
  - **What:** 新增 `models/uobject.py` → UObject → UField → UEnum/UStruct/UClass/UFunction 层次结构，BPGC SuperField 链解析
  - **Verify:** `UObject.Class` / `UObject.Outer` / `UObject.Template` 可解析，SuperField 链返回完整父类列表
  - **Deps:** COR-02 (需要版本感知序列化)

- [ ] **COR-04**: PackageLinker CUE4Parse 对齐
  - **What:** 重构 `link/linker.py` 为 CUE4Parse 风格的 Package-centered 模式：独立 archive + 位置安全 `preload()` + graph/linker 单一路径 + provider/resolver 接口；为跨包 import 解析、`/Script/` 占位符、Phase 79 的 `IFileProvider` / IoStore 接入铺路
  - **Verify:** 连续 `parse_uasset(file_A)` + `parse_uasset(file_B)` 无缓存串扰；graph/pin/blueprint metadata 统一走 linker-aware 主路径；本包 `FPackageIndex` 解析稳定，跨包 import 通过 provider 接口可扩展，`/Script/` import 不触发真实包加载
  - **Deps:** COR-03 (需要 UObject 继承树)

---

## PAK — Pak/IoStore 解析层

- [ ] **PAK-01**: .pak 文件解析
  - **What:** 新建 `src/uasset_read/pak/` 模块 — `FPakInfo` 解析（Magic 0x5A6F12E1，版本 1~12），Entry 表解析（FPakEntry），按偏移+大小提取条目
  - **Verify:** 解包至少 1 个真实 .pak 文件，Entries 列表完整，条目二进制可提取
  - **Deps:** None

- [ ] **PAK-02**: 压缩系统
  - **What:** 新建 `src/uasset_read/compression.py` — `ECompressionFlags` 枚举，Zlib(内置) / LZ4 / Zstd / Oodle 分派，Oodle 通过 `python_oodle` CTypes wrapper 调用（不可用时降级跳过 + 警告）
  - **Verify:** 每种压缩算法能正确解压已知数据，Oodle 不可用时优雅降级
  - **Deps:** PAK-01

- [ ] **PAK-03**: AES 加密
  - **What:** 新建 `src/uasset_read/encryption.py` — `AESKey` 类，ECB/CBC 模式解密，`CustomEncryption` 委托接口（游戏特定密钥注入）
  - **Verify:** AES-ECB 解密已知 Pak index，游戏密钥注入后正确解密
  - **Deps:** PAK-01

- [ ] **PAK-04**: IoStore (.utoc/.ucas) 解析
  - **What:** 新建 `src/uasset_read/iostore/` 模块 — `FIoStoreTocResource` 解析（Chunk ID 表、偏移量、压缩块信息、容器完美哈希索引），`.ucas` 数据段提取
  - **Verify:** 解析至少 1 个 .utoc/.ucas 对，提取有效 Container 条目
  - **Deps:** PAK-01, PAK-02

- [ ] **PAK-05**: IFileProvider 文件发现
  - **What:** 新建 `src/uasset_read/file_provider/` 模块 — `IFileProvider` 抽象接口，`DefaultFileProvider` 本地目录扫描实现，路径映射、包加载
  - **Verify:** `DefaultFileProvider("C:/GameDir")` 发现所有 .pak/.uasset 文件，正确映射路径
  - **Deps:** PAK-01

---

## FMT — 输出格式对齐

- [ ] **FMT-01**: CUE4Parse 对齐 JSON 模式
  - **What:** 新增 `format_json_cue4parse()` 输出器 — PascalCase 字段名（`ObjectName`, `Class`, `Super`, `Outer`, `Serialize`），`ExportTypes` 结构，ExportMap 完整信息（含 ImportMap 引用解析）
  - **Verify:** JSON 输出字段名与 CUE4Parse 对应，ExportTypes 数组完整，无 snake_case 残留
  - **Deps:** COR-03

- [ ] **FMT-02**: 文本输出 Schema 化
  - **What:** 重构 `format_text_full()` — 替换 ad-hoc YAML 拼接为结构化 dict → 统一文本渲染器，支持缩进深度/节点详细程度可配置
  - **Verify:** 文本输出与 JSON 输出字段一一对应，可配置详细程度（summary/normal/full）
  - **Deps:** FMT-01

- [ ] **FMT-03**: BlueprintText 集成到统一 Schema
  - **What:** 合并 `blueprint_text_formatter.py` 到统一格式化体系，输出遵循 FMT-01 定义的结构，去除 ad-hoc 命名规则
  - **Verify:** `format_blueprint_translation_text()` 输出字段与 FMT-01 JSON 模式对齐，PascalCase 命名
  - **Deps:** FMT-01

---

## Out of Scope (→ v15.0)

| Category | Items |
|----------|-------|
| **EXP** | 纹理导出（BC1-7/DXT/ASTC→PNG）、静态/骨骼网格导出（psk/glb）、音频导出（WAV/OGG） |
| **GAM** | VersionContainer 游戏适配（EGame 枚举 + 70+ 游戏覆盖）、游戏加密/Pak版本覆盖框架 |
| **ENH** | Kismet 表达式补齐（60+→100+ 种）、N2CEnum 枚举提取、FExpressionEvaluator 求值器 |

---

## Dependency Graph

```
COR-01 ─┐
COR-02 ─┤
         ├─→ COR-03 ──→ COR-04 ──┐
         │                        │
PAK-01 ──┼─→ PAK-02 ──→ PAK-04   │
         │                        │
         └─→ PAK-03               │
                                  │
         PAK-01 ──→ PAK-05        │
                                  │
                            COR-03 ──→ FMT-01 ──→ FMT-02
                                                 └─→ FMT-03
```

## Phase Mapping

| REQ Group | Phase | Reasoning |
|-----------|-------|-----------|
| COR-01, COR-02 | **Phase 76** | 基础修复无外部依赖 |
| PAK-01, PAK-02, PAK-03 | **Phase 77** | Pak 基础 + 压缩 + 加密可并行 |
| COR-03, COR-04 | **Phase 78** | 依赖 COR-02 版本管理 |
| PAK-04, PAK-05 | **Phase 79** | 依赖 PAK-01~03 |
| FMT-01, FMT-02, FMT-03 | **Phase 80** | 依赖 COR-03/04 |

## Traceability

| REQ-ID | Phase | Category | Source | Priority |
|--------|-------|----------|--------|----------|
| COR-01 | 76 | Core Fix | 对照 Wiki 🔧 标记 | P0 |
| COR-02 | 76 | Core Fix | CUE4Parse VersionContainer | P0 |
| COR-03 | 78 | Core Fix | CUE4Parse UObject hierarchy | P1 |
| COR-04 | 78 | Core Fix | CUE4Parse FAssetArchive | P1 |
| PAK-01 | 77 | Pak/IoStore | CUE4Parse PakFileReader | P0 |
| PAK-02 | 77 | Pak/IoStore | CUE4Parse Compression | P1 |
| PAK-03 | 77 | Pak/IoStore | CUE4Parse Aes.cs | P1 |
| PAK-04 | 79 | Pak/IoStore | CUE4Parse IoStoreReader | P1 |
| PAK-05 | 79 | Pak/IoStore | CUE4Parse IFileProvider | P2 |
| FMT-01 | 80 | Format | User requirement "输出格式不够规范" | P0 |
| FMT-02 | 80 | Format | User requirement "文本 Schema 化" | P2 |
| FMT-03 | 80 | Format | 统一 formatter 体系 | P2 |

---

*Created: 2026-05-26*
