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
| 序列化 | `serializers/` | Summary/Import/Export/PropertyTag/图 |
| 解析器 | `parsers/` | 40+ 种属性类型解析器 |
| 数据模型 | `models/` | UEdGraph/Node/Pin、属性值、蓝图 |
| 蓝图 | `blueprint/` | 变量/变换/组件/元数据提取 |
| 图分析 | `graph/` | 执行流/数据流/链构建器 |
| Kismet | `kismet/` | 字节码提取、AST、C++ 翻译 |
| 链接器 | `link/` | PackageLinker 对象图重建 |
| C++ 生成 | `cpp_gen/` | C++ 骨架/函数提取、IR 格式化 |
| N2C 格式 | `n2c/` | 中间格式、JSON Schema、验证器 |
| 输出 | `formatters/` / `exporter/` | 多格式输出 + 导出系统 |

> [!TIP]
> **相关章节**: [[FArchive]] · [[解析管线]]
