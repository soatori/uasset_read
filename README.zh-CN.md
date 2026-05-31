# uasset_read

> **虚幻引擎 .uasset 文件 Python 解析器** — 解析蓝图、提取变量、反编译 Kismet 字节码、生成 C++ 类骨架 — 无需启动 UE 编辑器。

一个零依赖的 Python 解析器，将虚幻引擎 `.uasset` 二进制蓝图数据转换为结构化 JSON、文本和代码。

[English](README.md) | [中文版](README.zh-CN.md)

## 为什么选择 uasset_read？

虚幻引擎的蓝图以二进制 `.uasset` 文件格式存储 — 离开编辑器就无法阅读。uasset_read 填补了这一空白，能够提取：

- **蓝图图结构** — 节点、引脚、执行流、数据依赖
- **变量与元数据** — 类型、默认值、分类、提示信息
- **Kismet 字节码** — 反编译为类 C++ 伪代码
- **组件属性** — 变换、材质、网格体引用
- **依赖关系图** — 导入/导出关系、软对象路径

无论你是审计蓝图依赖、提取类骨架用于 C++ 迁移，还是为游戏开发构建工具链，uasset_read 都能让你在文件级别获得对蓝图数据的结构化访问能力。

## 状态

| 指标 | 值 |
|------|-----|
| 源码 | Python 解析器，用于解析 Unreal Engine .uasset 文件 |
| 测试 | 10 个文件，108 个测试 |

## 功能特性

### 核心解析
- **PackageFileSummary** — 文件头解析
- **NameMap** — 名称表提取
- **ImportMap / ExportMap** — 依赖和导出映射
- **高级属性** — Struct / Map / Set / Enum / Text / Delegate

### 蓝图分析
- **蓝图图解析** — UEdGraph / Node / Pin 结构
- **变量提取** — 变量、函数、事件、元数据，带类型推断
- **组件属性** — Transform/Rotation/Scale + 标量属性
- **执行流/数据流追踪** — Event → CallFunction 链路追踪
- **函数图分析** — FunctionEntry 识别、按函数粒度的调用链

### 高级功能
- **Kismet 字节码反编译** — EExprToken → AST → C++ 伪代码
- **PackageLinker** — 两阶段对象图重建
- **N2C 中间格式** — 结构化 JSON Schema、执行链
- **C++ 骨架提取** — 组件声明、函数签名、UPROPERTY 映射
- **依赖分析** — ImportMap + SoftObjectPaths 依赖图构建
- **循环依赖检测** — 导入映射相互引用检测

### 文件格式支持
- **Pak 文件解析** — FPakInfo、压缩（Zlib/LZ4/Zstd/Oodle）、AES-ECB 解密
- **IoStore 容器** — Chunk ID、偏移/大小结构
- **资产类型解析器** — SkeletalMesh、Texture2D、Material、MaterialInstanceConstant
- **Bulk Data** — BulkData 头部解析

### 多种输出格式
- **JSON** — 完整结构化输出或摘要
- **Text** — 人类可读格式
- **Markdown** — 带表格的格式化文档
- **Mermaid** — 交互式流程图和依赖图
- **Blueprint UE Text** — UE 编辑器风格格式
- **C++ Skeleton** — 可直接使用的类骨架代码

## 安装

```bash
git clone https://github.com/soatori/uasset_read.git
cd uasset_read
pip install -e ".[dev]"
```

核心 `.uasset` 解析零运行时依赖，仅需 Python 3.10+。
如需 PAK 的 AES/LZ4/Zstd 可选支持，请安装：

```bash
pip install -e ".[pak]"
# 或从 PyPI 安装：
pip install "uasset_read[pak]"
```

## 使用

### CLI

```bash
# 基本用法
uasset-read path/to/file.uasset                    # JSON 输出到 stdout
uasset-read path/to/file.uasset --output output.json   # 保存到文件

# 输出模式
uasset-read path/to/file.uasset --summary          # 仅摘要
uasset-read path/to/file.uasset --text             # 可读文本
uasset-read path/to/file.uasset --markdown         # Markdown 输出
uasset-read path/to/file.uasset --blueprint-text   # 蓝图节点文本
uasset-read path/to/file.uasset --blueprint-ue-text # UE 格式文本
uasset-read path/to/file.uasset --cpp-skeleton     # C++ 类骨架
uasset-read path/to/file.uasset --n2c              # N2C 中间格式 JSON

# 批量导出
uasset-read --batch-dir path/to/dir/               # 批量导出目录

# 严格度
uasset-read path/to/file.uasset --strict           # 遇到警告即停止
uasset-read path/to/file.uasset --tolerant         # 容错模式（默认）

# 调试
uasset-read path/to/file.uasset --verbose          # 启用详细日志
```

### Python API

解析函数建议直接从包根导入。如果需要 `uasset_read.parse_uasset`
模块对象，请使用 `importlib.import_module()`，避免与包根同名
`parse_uasset` 函数混淆。

```python
import importlib

from uasset_read import (
    # 数据模型
    UEdGraph, UEdGraphNode, UEdGraphPin,
    ParseResult, BlueprintMetadata, BlueprintVariable,

    # 解析器
    parse_property_value, parse_properties_from_export,

    # 蓝图
    extract_blueprint_variables, extract_blueprint_metadata,
    parse_component_transform, extract_component_transforms,

    # 流追踪
    build_execution_flow_entries, build_data_flows, build_connections_map,
    build_execution_chains,

    # 格式化
    format_json_full, format_json_summary,
    format_text_full, format_markdown,

    # 链接器
    parse_uasset_with_linker, PackageLinker, UObjectInstance,

    # Kismet
    decompile_uasset, KismetDecompiledResult,
    KismetTranslator, to_function_body,

    # N2C
    N2CStruct, N2CGraph, to_n2c_json, from_n2c_json,

    # Agent 翻译
    AgentTranslationPipeline, translate_blueprint_to_cpp,
    CppFileWriter, write_cpp_class_files,

    # 常量 & 异常
    PACKAGE_FILE_TAG, MMAP_THRESHOLD,
    UAssetError, ParseError, VersionError,
)

# 解析 .uasset 文件
result = parse_uasset('BP_FirstPersonCharacter.uasset')

# 输出 JSON
json_output = format_json_full(result)

parse_module = importlib.import_module("uasset_read.parse_uasset")
```

完整 API 列表见 `src/uasset_read/__init__.py`。

## 架构

采用镜像 UE 的 FArchive 管道模式：

```
.uasset → FArchive → Deserializer → Models → Formatters → Output
                ↓
          GraphParser
          BlueprintParser
          DependencyGraphBuilder
          PackageLinker
          KismetDecompiler
          N2C Format
          PakFileReader
```

### 模块结构 (`src/uasset_read/`)

| 模块 | 路径 | 说明 |
|------|------|------|
| **核心** | | |
| FArchive | `archive.py` | 二进制读取器，支持字节交换、mmap |
| 常量 | `constants.py` | 版本号、属性类型阈值、CPF/PropertyTag 标志 |
| 异常 | `exceptions.py` | UAssetError, VersionError, ParseError, ErrorContext |
| 主解析器 | `parse_uasset.py` | `parse_package()`, `parse_uasset()`, `parse_uasset_with_linker()` |
| 包管理 | `package.py` | `PackageBundle`, `PackageProvider`（文件系统/Pak/IoStore） |
| 原始文件 | `raw.py` | JSON/INI/LocRes/LocMeta/Audio 非 uasset 解析 |
| CLI | `cli.py` | argparse 入口 (`uasset-read`) |
| Exporter | `exporter/` | IExporter 接口、注册表、批量导出 |
| 版本管理 | `versioning.py` | `VersionContainer`, `build_version_container`, `EUEVersion` |
| 映射 | `mappings.py` | UE 类型映射（`.usmap`/`.jmap` 解析） |
| **序列化** | `serializers/` | PackageSummary, Import/ExportMap, PropertyTag, Graph |
| **数据模型** | `models/` | UEdGraph/Node/Pin, Properties, Transforms, ParseResult |
| **解析器** | `parsers/` | 40+ 种属性类型解析器 + 分派器 + 自定义属性注册表 |
| **资产类型** | `parsers/asset_types/` | SkeletalMesh、Texture2D、Material、MaterialInstanceConstant |
| **蓝图** | `blueprint/` | 变量/变换/组件/元数据提取 |
| **图** | `graph/` | 执行流/数据流追踪、链构建器 |
| **Kismet** | `kismet/` | 字节码提取器, EExprToken → AST, C++ 翻译器, BPGC 回退 |
| **链接器** | `link/` | PackageLinker, UObjectInstance |
| **CPP Gen** | `cpp_gen/` | C++ 骨架/函数提取, IR 格式化器 |
| **Agent** | `agent/` | AgentTranslationPipeline + CppFileWriter |
| **N2C** | `n2c/` | N2CStruct/Graph/Node/Pin 模型, JSON Schema |
| **Pak** | `pak/` | FPakInfo/PakEntry/目录条目, PakFileReader |
| **压缩** | `pak/decompress.py` | Zlib/LZ4/Zstd/Oodle 分派 + 优雅降级 |
| **加密** | `pak/crypto.py` | AES-ECB 解密辅助函数 |
| **格式化器** | `formatters/` | JSON/Text/Markdown/Mermaid 输出 |

## 测试

```bash
python -m pytest tests/ -v           # 运行所有测试
python -m pytest tests/ -v --cov=uasset_read  # 带覆盖率
```

## 技术栈

- **语言**: Python 3.10+（match/case，类型提示）
- **依赖**: 零运行时依赖
- **构建**: setuptools（src layout），pyproject.toml
- **测试**: pytest

## 文档

| 文档 | 路径 |
|------|------|
| 快速开始 | [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md) |
| 架构设计 | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| 开发指南 | [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) |
| 参考资料 | [docs/reference/](docs/reference/) |

## 应用场景

| 场景 | uasset_read 的帮助 |
|------|-------------------|
| **蓝图程序化分析** | 解析蓝图数据 → 提取结构 → 自动化检查 |
| **蓝图 → C++ 迁移** | 提取类结构、变量、函数 → 生成 C++ 骨架代码 |
| **依赖审计** | 构建导入/导出图 → 检测循环引用 → 发现孤立资产 |
| **Mod 开发** | 从 `.pak` 文件读取蓝图变量 → 无需源码即可理解 Mod 行为 |
| **资产管线自动化** | 批量解析数千个 `.uasset` 文件 → 提取元数据 → 构建可搜索索引 |
| **技术债务分析** | 追踪执行流 → 识别深层嵌套逻辑 → 发现死代码 |

## 限制

- **仅支持未烘焙/编辑器保存的资产**: Cooked 资产已剥离图数据
- **字节码反编译有限**: Kismet EExprToken→AST→C++ 仅覆盖已知类型
- **不输出资源文件**: 纹理、模型等二进制数据过大，仅提取元数据
- **只读**: 仅支持解析，不支持修改
- **依赖 UE 源码参考**: .uasset 格式无官方文档，需 UE 源码作为参考

---
