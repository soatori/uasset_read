# 路线图

## 里程碑

版本命名: `{env}-{major}.{minor}.{patch}` — 详见 `VERSIONING.md`

| 版本 | 语义版本 | 范围 | 日期 | 状态 |
|------|---------|------|------|------|
| v1.0–v6.0 | — | MVP → 模块化重构 | 2026-04-28 ~ 05-13 | 已归档 |
| v7.0 | — | UE FLinkerLoad 对象图重建 | 2026-05-14 | 已归档 |
| v8.0 | — | BP-to-CPP JSON 可翻译性 (P47-51) | 2026-05-17 | 已归档 |
| v9.0 | — | 函数调用链解析 (P52-55) | 2026-05-17 | 已归档 |
| v10.0 | — | Blueprint-to-C++ 代码生成参考 (P56-60) | 2026-05-18 | [已归档](milestones/v10.0-ROADMAP.md) |
| v11.0 | — | Kismet 字节码反编译器 + 图解析修复 + Agent 翻译管线 (P61-66) | 2026-05-20 | [已归档](milestones/v11.0-ROADMAP.md) |
| v12.0 | — | 序列化修复 + N2C 中间格式 + 节点分类体系 + 处理器架构 (P67-71) | 2026-05-21~22 | [已归档](milestones/v12.0-ROADMAP.md) |
| v13.0 | — | Pin 连接修复 + Kismet 字节码导航 + FName/FString 区分 (P72-75) | 2026-05-23 ~ 05-26 | [已归档](archive/v13.0-phases/) |
| **v14.0** | `dev-0.3.0` | **CUE4Parse 核心对齐 — FArchive/Pak/IoStore/格式对齐 (P76-80)** | 2026-05-26 ~ | 执行中 |

历史详情：`.planning/archive/`

## v14.0 — CUE4Parse 核心对齐 (P76-80)

**参考设计:** CUE4Parse — FArchive/PackageSummary/Import/Export/PropertyTag / PakFileReader / IoStoreReader / Aes.cs / CompressionFlags / IFileProvider

**目标:** 实现 CUE4Parse 核心解析能力对齐，包括 FArchive 层补齐、Pak/IoStore 解析、AES 加密、压缩分派、以及 JSON 输出格式 PascalCase 对齐。

### Phase 76: FArchive 层补齐 + PackageSummary 源码索引 + COR 修复

**需求:** COR-01, COR-02
**范围:** StructProperty 深度解析、FAssetArchive 封装管线集成、FCustomVersion 体系（GUID→Version 映射）、VersionContainer 统一管理
**验收:** `if (Ar.Ver >= EUEVersion.UE4_23)` 版本分支语法，CustomVersion 按 GUID 查询，StructProperty 内部字段完整提取

### Phase 77: Pak 解析 + 压缩系统 + AES 加密 ✅

**需求:** PAK-01, PAK-02, PAK-03
**范围:** FPakInfo/PakEntry 解析、Zlib/LZ4/Zstd/Oodle 压缩分派、AES-ECB/CBC 解密 + CustomEncryption 委托接口
**验收:** 解包真实 .pak 文件，Entries 完整可提取，Oodle 不可用时优雅降级
**完成日期:** 2026-05-26 | 62 tests passed, UAT 8/8

### Phase 78: UObject 继承树 + PackageLinker 重构

**需求:** COR-03, COR-04
**范围:** UObject → UField → UEnum/UStruct/UClass/UFunction 层次结构、link/linker.py 重构为 FAssetArchive 模式、preload() 管线集成
**验收:** 连续 parse_uasset 无缓存串扰，SuperField 链返回完整父类列表

### Phase 79: IoStore (.utoc/.ucas) 解析

**需求:** PAK-04, PAK-05
**范围:** FIoStoreTocResource 解析（Chunk ID 表、偏移量、压缩块信息）、.ucas 数据段提取、DefaultFileProvider 路径扫描
**验收:** 解析 .utoc/.ucas 对，提取有效 Container 条目

### Phase 80: 输出格式 PascalCase 对齐

**需求:** FMT-01, FMT-02, FMT-03
**范围:** format_json_cue4parse()（PascalCase 字段名、ExportTypes 结构）、format_text_full() 重构（dict→统一文本渲染）、BlueprintText 统一到 Schema
**验收:** JSON 输出与 CUE4Parse 字段名一一对应，无 snake_case 残留

---

## 历史里程碑摘要

v1.0-v13.0 的详细 Phase 规划与执行记录已归档至 `.planning/archive/` 和 `.planning/milestones/`。以下为核心交付摘要：

| 里程碑 | 核心交付 | Phase 范围 | 测试 |
|--------|---------|-----------|------|
| v7.0 | PackageLinker / UObjectInstance / 两阶段链接 | P41-46 | — |
| v8.0 | BP→C++ JSON 可翻译性 | P47-51 | — |
| v9.0 | 函数调用链解析 / function_graphs | P52-55 | — |
| v10.0 | Blueprint-to-C++ 代码生成参考 | P56-60 | 1021 |
| v11.0 | Kismet 反编译器 + Agent 翻译管线 | P61-66 | 1271 |
| v12.0 | UE5.4+ PropertyTag / N2CStruct JSON Schema / 执行流链式表达 | P67-71 | 1435 |
| v13.0 | Pin 连接修复 / BPGC 字节码 / LinkedTo 恢复 / EventGraph 字段对齐 | P72-75 | 1339 |

v13.0 关键修复回顾：
- **P72-A/B:** history_type signed 转换 + ParentPin 条件读取，LinkedTo 从 0→24 refs
- **P72-C:** BPGC bytecode extraction module (295 lines)
- **P72-D:** FString null termination 验证替代 null_ratio 启发式
- **P72-G/I:** StructProperty 深度解析 + BP_FirstPersonCharacter 全量对比修复
- **P73:** Pin 序列化边界对齐，LinkedTo 24→48 refs，29 专项测试
- **P74/75:** PinReference 主路径 + EventGraph 节点字段级对齐

---

*Updated: 2026-05-26 (v1.0-v13.0 archived, v14.0 active, version naming rule `dev-0.3.0` applied)*
