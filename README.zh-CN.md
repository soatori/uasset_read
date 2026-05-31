# uasset_read

解析 Unreal Engine `.uasset` 文件的 Python 工具，使 AI 代理能够在不依赖 UE 编辑器的情况下读取蓝图内容。专注于未烘焙/编辑器保存的资产（包含完整蓝图数据）。

[English](README.md) | [中文版](README.zh-CN.md)

## 状态

| 指标 | 值 |
|------|-----|
| 源码 | Python 解析器，用于解析 Unreal Engine .uasset 文件 |
| 测试 | 115 个测试 |

## 功能

- **PackageFileSummary** — 文件头解析
- **NameMap** — 名称表提取
- **ImportMap / ExportMap** — 依赖和导出映射
- **蓝图图解析** — UEdGraph / Node / Pin 结构
- **高级属性** — Struct / Map / Set / Enum / Text / Delegate
- **蓝图变量提取** — 变量、函数、事件、元数据
- **组件属性解析** — Transform/Rotation/Scale + 标量属性
- **依赖分析** — ImportMap + SoftObjectPaths 依赖图构建
- **循环依赖检测** — ImportMap 相互引用检测
- **执行流/数据流追踪** — Event → CallFunction 链路追踪
- **函数图分析** — FunctionEntry 识别、按函数粒度的调用链
- **PackageLinker** — 两阶段对象图重建
- **Kismet 字节码反编译** — EExprToken → AST → C++ 伪代码
- **N2C 中间格式** — Agent 优化的 JSON Schema、执行链
- **C++ 骨架提取** — 组件声明、函数签名
- **Pak 文件解析** — FPakInfo、压缩（Zlib/LZ4/Zstd/Oodle）、AES-ECB
- **资产类型解析器** — SkeletalMesh、Texture2D、Material、MaterialInstanceConstant 属性提取
- **多种输出格式** — JSON、Text、Markdown、Mermaid 流程图

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
| 常量 | `constants.py` | 版本号、属性类型阈值、CPF 标志 |
| 异常 | `exceptions.py` | UAssetError, VersionError, ParseError |
| 主解析器 | `parse_uasset.py` | 顶层 `parse_uasset()` 和 `parse_uasset_with_linker()` |
| CLI | `cli.py` | argparse 入口 (`uasset-read`) |
| Exporter | `exporter/` | IExporter 接口和注册表 |
| **序列化** | `serializers/` | PackageSummary, Import/ExportMap, PropertyTag, Graph |
| **数据模型** | `models/` | UEdGraph/Node/Pin, Properties, Transforms, ParseResult |
| **解析器** | `parsers/` | 14 种属性类型解析器 + 分派器 |
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

## 限制

- **仅支持未烘焙/编辑器保存的资产**: Cooked 资产已剥离图数据
- **字节码反编译有限**: Kismet EExprToken→AST→C++ 仅覆盖已知类型
- **不输出资源文件**: 纹理、模型等二进制数据过大，仅提取元数据
- **只读**: 仅支持解析，不支持修改
- **依赖 UE 源码参考**: .uasset 格式无官方文档，需 UE 源码作为参考

---
