---
title: 架构设计
section: architecture
---

# 架构设计

## 整体架构

```
.uasset / .umap    .pak    .iostore
        ↓ 文件来源
PackageBundle    PackageArchive    FArchive
        ↓ 二进制读取
PackageFileSummary    NameTable    ImportMap    ExportMap
        ↓ 序列化
PropertyTag    PropertyParser    TypeMappings
        ↓ 属性解析
BlueprintParser    GraphParser    PackageLinker    KismetDecompiler
        ↓ IR 构建
PackageIR → ExportIR → GraphIR → NodeIR → PinIR
        ↓ 渲染
JSON    Text    Markdown    BlueprintText    BlueprintUE
```

## 解析管线

```
open_package_bundle → read_package_summary → build_version_container → read_name_table
```

```
read_import_map → read_export_map → link() → preload(idx) × N → post_load()
→ parse_properties → post_process → build_package_ir → renderers
```

> **v0.4.5 变更**: 加载生命周期现在遵循 UE 风格：`link() → preload(idx) × N → post_load()`。
> `post_load()` 在所有 export 预加载之后调用，确保 ObjectProperty 引用能正确解析。

## 模块结构

| 层级 | 路径 | 职责 |
|------|------|------|
| 核心层 | `archive.py` / `constants.py` / `exceptions.py` | 二进制读取、常量、异常体系 |
| 包管理 | `package.py` / `parse_uasset/` | 包捆绑、Provider 抽象、解析管线 |
| 版本管理 | `versioning.py` | VersionContainer、build_version_container、EUEVersion |
| 类型映射 | `mappings.py` | UE 类型映射（.usmap/.jmap 解析） |
| 原始文件 | `raw.py` | JSON/INI/LocRes/LocMeta/Audio 非 uasset 文件解析 |
| Core API | `core.py` | parse_single / parse_batch / list_formats 纯函数入口 |
| IR 模型 | `models/ir.py` | PackageIR、ExportIR、GraphIR、NodeIR、PinIR 等中间表示 |
| IR 构建器 | `ir_builder.py` | build_package_ir：从 ParseResult 构建 PackageIR |
| 渲染器 | `renderers/` | JSON/Markdown 渲染器，自动注册到 RENDERER_REGISTRY |
| 序列化 | `serializers/` | Summary/Import/Export/PropertyTag/图序列化 |
| 解析器 | `parsers/` | 40+ 种属性类型解析器 + 分发器 + 自定义属性注册表 |
| ├ 资产类型 | `parsers/asset_types/` | StaticMesh/SkeletalMesh/Texture2D/Material/MIC 专用解析器 |
| 数据模型 | `models/` | UEdGraph/Node/Pin、属性值、变换、蓝图模型、ParseResult |
| 蓝图 | `blueprint/` | 变量/变换/组件/元数据提取 |
| 图分析 | `graph/` | 执行流/数据流/链构建器、Pin 追踪报告 |
| Kismet | `kismet/` | 字节码提取、EExprToken → AST → C++ 翻译、BPGC 回退、结构化控制流 |
| ├ 表达式 | `kismet/expressions/` | 16 种表达式类型（赋值、控制流、函数调用、字面量等） |
| 链接器 | `link/` | PackageLinker 两阶段对象图重建、UObjectInstance |
| Pak | `pak/` | FPakInfo/PakEntry/FPakDirectoryEntry、PakFileReader、索引、压缩、AES 解密 |
| IoStore | `iostore/` | IoStore 容器读取器、Chunk ID、偏移/大小结构 |
| CLI | `cli.py` | argparse 入口，委托 core.py 核心 API |

## 独立管线（已移除）

> [!WARNING]
> **`cpp_skeleton` 渲染器已移除（v0.4.5）**：C++ 骨架生成功能已从项目中移除。
> 原本独立于 PackageIR 管线的 `CppSkeletonRenderer` 不再可用。
>
> **相关章节**: [[FArchive]] · [[解析管线]] · [[渲染器系统]] · [[IR 中间表示]]
