# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Language
使用中文回复
输出专业简洁
1.所有对话和文档都使用中文
2.代码注释使用中文
3.错误提示使用中文
4.文档统一使用中文Markdown格式

## 项目概述

**uasset_read** — 虚幻引擎 `.uasset` 文件的 Python 解析器，使 AI 代理无需 UE 编辑器即可读取蓝图内容。专注于未烘焙/编辑器保存的资产（包含完整蓝图数据）。

- **版本**: 6.0.0（分支 `0.3.0-dev`）
- **Python**: 3.10+（使用 `match/case`、类型注解）
- **运行时依赖**: 零依赖
- **构建系统**: setuptools（src 布局）

## 开发命令

```bash
# 安装（含开发依赖）
pip install -e ".[dev]"

# 运行所有测试
python -m pytest tests/ -v

# 运行测试并生成覆盖率报告
python -m pytest tests/ -v --cov=uasset_read

# 运行单个测试文件
python -m pytest tests/test_cli_regressions.py -v

# 仅运行集成测试
python -m pytest tests/ -v -m integration

# CLI 入口
uasset-read path/to/file.uasset              # JSON 输出（默认）
uasset-read path/to/file.uasset --text       # 人类可读文本
uasset-read path/to/file.uasset --markdown   # Markdown + Mermaid 图表
uasset-read path/to/file.uasset --blueprint-text   # 蓝图节点文本
uasset-read path/to/file.uasset --cpp-skeleton       # C++ 类骨架
uasset-read path/to/file.uasset --strict     # 遇到警告时停止
uasset-read path/to/file.uasset --verbose    # 启用调试日志
```

## CodeGraph

本项目使用 CodeGraph 进行代码分析和可视化。CodeGraph 能够帮助理解代码结构、依赖关系和调用流程，对于复杂模块的分析和重构非常有用。

## 架构

解析器镜像 UE 内部的 `FArchive` 序列化管线：

```
.uasset → FArchive → Deserializer → Models → Formatters → Output
                ↓
          GraphParser · BlueprintParser · DependencyGraphBuilder
          PackageLinker · KismetDecompiler · N2C Format · PakFileReader
```

### 模块结构 (`src/uasset_read/`)

| 模块 | 路径 | 职责 |
|------|------|------|
| **核心** | | |
| FArchive | `archive.py` | 二进制读取器，支持字节交换、mmap |
| 常量 | `constants.py` | 版本号、属性类型阈值、CPF 标志 |
| 异常 | `exceptions.py` | `UAssetError`、`VersionError`、`ParseError`、`ErrorContext` |
| 主解析器 | `parse_uasset.py` | `parse_uasset()` 和 `parse_uasset_with_linker()` 入口 |
| CLI | `cli.py` | argparse 入口（`uasset-read`） |
| 导出器 | `exporter/` | `IExporter` 接口、注册表、批量导出 |
| 版本管理 | `versioning/` | `VersionContainer`、`build_version_container`、`EUEVersion` |
| **序列化** | `serializers/` | `PackageFileSummary`、`ImportMap`、`ExportMap`、`PropertyTag`、图序列化器 |
| **数据模型** | `models/` | `UEdGraph/Node/Pin`、属性值模型、`ParseResult`、变换 |
| **属性解析器** | `parsers/` | 14 种属性类型解析器 + 分发器（`parse_property_value` 等） |
| **蓝图** | `blueprint/` | 变量/变换/组件/元数据提取 |
| **图分析** | `graph/` | 执行流/数据流追踪、链构建器、Pin 追踪报告 |
| **Kismet** | `kismet/` | 字节码提取器、`EExprToken` → AST → C++ 翻译器、BPGC 回退 |
| **链接器** | `link/` | `PackageLinker` 两阶段对象图重建、`UObjectInstance` |
| **C++ 生成** | `cpp_gen/` | C++ 骨架/函数提取、IR 格式化器 |
| **Agent** | `agent/` | `AgentTranslationPipeline` + `CppFileWriter`（蓝图→C++） |
| **N2C** | `n2c/` | 中间格式：`N2CStruct/Graph/Node/Pin`、JSON Schema、验证器 |
| **Pak** | `pak/` | `FPakInfo/PakEntry/FPakDirectoryEntry`、`PakFileReader`、索引解析 |
| **压缩** | `compression/` | Zlib/LZ4/Zstd/Oodle 分发，优雅降级 |
| **加密** | `crypto/` | AES-ECB 解密、`CustomEncryption` 委托 |
| **格式化器** | `formatters/` | JSON/Text/Markdown/Mermaid 输出生成器 |

### 公共 API

所有公共符号在 `src/uasset_read/__init__.py` 中通过 `__all__` 导出。以该文件为权威 API 参考。

## 外部参考

- `external/uasset-format/` — UE .uasset 格式文档（60+ 个 Markdown 文件，覆盖资产类型、序列化、Cooked 格式、版本兼容）。`SKILL.md` 为主索引。
- `external/CUE4Parse/` — 参考 C# 实现，用于交叉验证解析逻辑。
- `docs/reference/` — 蓝图节点文本参考、UE 加载流程、CUE4Parse 对照索引、蓝图转 C++ 指南。
- `docs/asset_type_index.md` — 60+ 种 UE 资产类型综合索引，含命名规范和示例文件路径。

## 测试

- 测试位于 `tests/`（5 个测试文件，21 个测试）
- `conftest.py` 定义了 `sample_result` fixture，解析真实 UE 蓝图资产（需要外部样本位于 `E:\Develop\lib\UnrealEngine\Samples\`）
- 缺少样本资产的测试会通过 `pytest.skip()` 跳过
- 集成测试使用 `@pytest.mark.integration` 标记

## 关键约束

- **仅支持未烘焙/编辑器保存的资产**: Cooked 资产的图数据已被剥离
- **只读**: 仅解析，不支持修改或写入
- **零运行时依赖**: 不要向 `pyproject.toml` 的 `dependencies` 添加第三方包
- **必须参考 UE 源码**: 格式理解必须追溯到 UE C++ 源码，禁止猜测二进制（参见 `external/uasset-format/SKILL.md`）
