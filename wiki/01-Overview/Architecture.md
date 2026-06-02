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
        ↓ 分析处理
JSON    Text    Markdown    C++ Generator    N2C
```

## 解析管线

```
open_package_bundle → read_package_summary → build_version_container → read_name_table
```

```
read_import_map → read_export_map → parse_properties → post_process
```

## 模块结构

| 层级 | 路径 | 职责 |
|------|------|------|
| 核心层 | `archive.py` / `constants.py` / `exceptions.py` | 二进制读取、常量、异常体系 |
| 包管理 | `package.py` / `parse_uasset.py` | 包捆绑、Provider 抽象、解析管线 |
| 版本管理 | `versioning.py` | VersionContainer、build_version_container、EUEVersion |
| 类型映射 | `mappings.py` | UE 类型映射（.usmap/.jmap 解析） |
| 原始文件 | `raw.py` | JSON/INI/LocRes/LocMeta/Audio 非 uasset 文件解析 |
| 序列化 | `serializers/` | Summary/Import/Export/PropertyTag/图序列化 |
| 解析器 | `parsers/` | 40+ 种属性类型解析器 + 分发器 + 自定义属性注册表 |
| ├ 资产类型 | `parsers/asset_types/` | StaticMesh/SkeletalMesh/Texture2D/Material/MIC 专用解析器 |
| 数据模型 | `models/` | UEdGraph/Node/Pin、属性值、变换、蓝图模型、ParseResult |
| 蓝图 | `blueprint/` | 变量/变换/组件/元数据提取 |
| 图分析 | `graph/` | 执行流/数据流/链构建器、Pin 追踪报告 |
| Kismet | `kismet/` | 字节码提取、EExprToken → AST → C++ 翻译、BPGC 回退 |
| ├ 表达式 | `kismet/expressions/` | 16 种表达式类型（赋值、控制流、函数调用、字面量等） |
| 链接器 | `link/` | PackageLinker 两阶段对象图重建、UObjectInstance |
| C++ 生成 | `cpp_gen/` | C++ 骨架/函数提取、IR 格式化器、类型映射、UPROPERTY 映射 |
| Agent | `agent/` | AgentTranslationPipeline + CppFileWriter（蓝图→C++ 翻译） |
| N2C 格式 | `n2c/` | 中间格式、JSON Schema、验证器、57 种节点处理器 |
| Pak | `pak/` | FPakInfo/PakEntry/FPakDirectoryEntry、PakFileReader、索引、压缩、AES 解密 |
| IoStore | `iostore/` | IoStore 容器读取器、Chunk ID、偏移/大小结构 |
| Bulk Data | `bulk/` | BulkData 头部解析、标志定义 |
| UObject | `objects/` | UObject 类型体系、类型注册表、导出类型 |
| 输出 | `formatters/` / `exporter/` | 多格式输出（JSON/Text/Markdown/Mermaid/UE 格式）+ 导出系统 |
| CLI | `cli.py` | argparse 入口（uasset-read），支持 --n2c、--batch、--validate |

> [!TIP]
> **相关章节**: [[FArchive]] · [[解析管线]]
