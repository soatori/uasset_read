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

- **版本**: 0.3.8-dev（分支 `0.3.8-dev`）
- **Python**: 3.10+（使用 `match/case`、类型注解）
- **运行时依赖**: 零依赖（PAK AES/LZ4/Zstd 为可选依赖）
- **构建系统**: setuptools（src 布局）

## CodeGraph

本项目使用 CodeGraph MCP 服务器进行代码智能检索。`codegraph_*` 工具提供基于 tree-sitter AST 的结构化查询。

**优先使用 codegraph 而非原生搜索的场景：**

| 问题 | 工具 |
|------|------|
| "X 在哪里定义？" | `codegraph_search` |
| "谁调用了 Y？" | `codegraph_callers` |
| "Y 调用了什么？" | `codegraph_callees` |
| "X 如何到达 Y？/ 追踪调用链" | `codegraph_trace` |
| "改了 Z 会影响什么？" | `codegraph_impact` |
| "看 Y 的签名/源码" | `codegraph_node` |
| "一次性看多个相关符号" | `codegraph_explore`（避免循环调用 codegraph_node） |
| "获取某任务/区域的上下文" | `codegraph_context` |

**使用原则：**
- 回答结构化问题先用 `codegraph_context`，再用 ONE 次 `codegraph_explore` 获取源码
- 追踪调用链用 `codegraph_trace`（一次调用返回完整路径，包括动态分发跳转）
- 不要对已确认的 codegraph 结果再用 grep 验证
- 索引延迟时读具体文件而非猜测，codegraph 响应中会标注未同步文件

## 测试

- 测试位于 `tests/`（12+ 个测试文件，218+ 个测试）
- 集成测试使用 `@pytest.mark.integration` 标记
- `pyproject.toml` 中配置了 pytest 选项

## 开发命令

```bash
# 安装（含开发依赖）
pip install -e ".[dev]"

# PAK 可选依赖（AES 解密、LZ4/Zstd 压缩）
pip install -e ".[pak]"

# 运行所有测试
python -m pytest tests/ -v

# 运行测试并生成覆盖率报告
python -m pytest tests/ -v --cov=uasset_read

# 运行单个测试文件
python -m pytest tests/test_pak_handling.py -v

# 仅运行集成测试
python -m pytest tests/ -v -m integration

# CLI 入口
uasset-read path/to/file.uasset              # JSON 输出（默认）
uasset-read path/to/file.uasset --output out.json   # 保存到文件
uasset-read path/to/file.uasset --summary      # 仅摘要
uasset-read path/to/file.uasset --text       # 人类可读文本
uasset-read path/to/file.uasset --markdown   # Markdown + Mermaid 图表
uasset-read path/to/file.uasset --blueprint-text   # 蓝图节点文本
uasset-read path/to/file.uasset --blueprint-ue-text  # UE 格式文本
uasset-read path/to/file.uasset --cpp-skeleton       # C++ 类骨架
uasset-read path/to/file.uasset --n2c          # N2C 中间格式 JSON
uasset-read path/to/file.uasset --strict     # 遇到警告时停止
uasset-read path/to/file.uasset --tolerant   # 容错模式（默认）
uasset-read path/to/file.uasset --verbose    # 启用调试日志
```

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
| 常量 | `constants.py` | 版本号、属性类型阈值、CPF/PropertyTag 标志 |
| 异常 | `exceptions.py` | `UAssetError`、`VersionError`、`ParseError`、`ErrorContext` |
| 主解析器 | `parse_uasset.py` | `parse_package()`、`parse_uasset()` 和 `parse_uasset_with_linker()` 入口 |
| 包管理 | `package.py` | `PackageBundle`、`PackageProvider`（文件系统/Pak/IoStore） |
| 原始文件 | `raw.py` | JSON/INI/LocRes/LocMeta/Audio 等非 uasset 文件解析 |
| CLI | `cli.py` | argparse 入口（`uasset-read`），支持 `--n2c`、`--batch`、`--validate` |
| 导出器 | `exporter/` | `IExporter` 接口、注册表、批量导出 |
| 版本管理 | `versioning.py` | `VersionContainer`、`build_version_container`、`EUEVersion` |
| 映射 | `mappings.py` | UE 类型映射（`.usmap`/`.jmap` 解析） |
| **序列化** | `serializers/` | `PackageFileSummary`、`ImportMap`、`ExportMap`、`PropertyTag`、图序列化器、对象资源 |
| **数据模型** | `models/` | `UEdGraph/Node/Pin`、属性值模型、`ParseResult`、变换、蓝图模型、节点类型 |
| **属性解析器** | `parsers/` | 40+ 种属性类型解析器 + 分发器 + 自定义属性注册表 + 类特定跳过机制 |
| ├ 资产类型 | `parsers/asset_types/` | (已废弃，0.4.0 移除) SkeletalMesh、Texture2D、Material、MaterialInstanceConstant 专用解析器 |
| **蓝图** | `blueprint/` | 变量/变换/组件/元数据提取 |
| **图分析** | `graph/` | 执行流/数据流追踪、链构建器、Pin 追踪报告 |
| **Kismet** | `kismet/` | 字节码提取器、`EExprToken` → AST → C++ 翻译器、BPGC 回退、结构化控制流 |
| ├ 表达式 | `kismet/expressions/` | 16 种表达式类型（赋值、控制流、函数调用、字面量等） |
| **链接器** | `link/` | `PackageLinker` 两阶段对象图重建、`UObjectInstance` |
| **C++ 生成** | `cpp_gen/` | C++ 骨架/函数提取、IR 格式化器、类型映射、UPROPERTY 映射 |
| **Agent** | `agent/` | `AgentTranslationPipeline` + `CppFileWriter`（蓝图→C++） |
| **N2C** | `n2c/` | 中间格式：`N2CStruct/Graph/Node/Pin`、JSON Schema、验证器、57 种节点处理器 |
| **Pak** | `pak/` | `FPakInfo/PakEntry/FPakDirectoryEntry`、`PakFileReader`、索引解析、压缩分发、AES 解密 |
| **IoStore** | `iostore/` | IoStore 容器读取器、Chunk ID、偏移/大小结构 |
| **Bulk Data** | `bulk/` | BulkData 头部解析、标志定义 |
| **UObject** | `objects/` | (已废弃，0.4.0 移除) UObject 类型体系、类型注册表、导出类型（StaticMesh/SkeletalMesh/Texture2D/Material） |
| **格式化器** | `formatters/` | JSON/Text/Markdown/Mermaid/蓝图翻译文本/UE 格式文本输出生成器 |

### 公共 API

所有公共符号在 `src/uasset_read/__init__.py` 中通过 `__all__` 导出。以该文件为权威 API 参考。

## 外部参考

- `docs/uasset-format/` — UE .uasset 格式文档（60+ 个 Markdown 文件，覆盖资产类型、序列化、Cooked 格式、版本兼容）。`Index.md` 为主索引。
- `external/CUE4Parse/` — 参考 C# 实现，用于交叉验证解析逻辑。
- `docs/reference/` — 蓝图节点文本参考、UE 加载流程、CUE4Parse 对照索引、蓝图转 C++ 指南。
- `docs/asset_type_index.md` — 60+ 种 UE 资产类型综合索引，含命名规范和示例文件路径。


## 关键约束

- **仅支持未烘焙/编辑器保存的资产**: Cooked 资产的图数据已被剥离
- **只读**: 仅解析，不支持修改或写入
- **零运行时依赖**: 不要向 `pyproject.toml` 的 `dependencies` 添加第三方包（PAK 可选依赖在 `optional-dependencies` 中）
- **必须参考 UE 源码**: 格式理解必须追溯到 UE C++ 源码，禁止猜测二进制（参见 `docs/uasset-format/Index.md`）
- **临时文件一律放在 `temp/` 目录**: 任何运行脚本、中间输出、调试日志、测试产物等临时文件必须创建在项目根目录的 `temp/` 子目录下，禁止放在项目根目录

## 工作规范

- **临时文件一律放在 `temp/` 目录**: 任何运行脚本、中间输出、调试日志、测试产物等临时文件必须创建在项目根目录的 `temp/` 子目录下，禁止放在项目根目录。根目录只保留项目源码、配置文件和文档。
