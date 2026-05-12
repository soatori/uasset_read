# uasset_read - 项目指导文档

## 项目概览

**uasset_read** 是一个 Python 工具，用于解析 Unreal Engine 的 `.uasset` 文件格式。它的核心价值是让 AI 代理能够直接读取蓝图内容（尤其是编辑器保存的未烘焙资产），无需依赖 UE 编辑器的人工介入。

- **当前版本**: v6.0（模块化重构中，Phase 35 进行中）
- **测试状态**: 397 tests passed, 71 skipped, 0 failed
- **架构**: 分层 FArchive 管道模式（镜像 UE 内部结构）
- **依赖**: 零运行时依赖（仅使用 Python 标准库）

## 核心特性

- **PackageFileSummary** — 文件头解析（版本号、包标志、GUID等）
- **NameMap** — 名称表提取与解压
- **ImportMap** — 依赖映射（导入类/资产引用）
- **ExportMap** — 导出映射（导出对象元数据）
- **蓝图图解析** — UEdGraph/Node/Pin 三层结构（Phase 7）
- **高级属性类型** — Struct/Map/Set/Enum/Text/Delegate（Phase 9）
- **蓝图变量提取** — 变量、函数、事件、元数据（Phase 12）
- **组件变换解析** — Transform/Rotation/Scale（Phase 13）
- **依赖分析** — ImportMap + SoftObjectPaths 依赖图构建（Phase 10）
- **循环依赖检测** — ImportMap 相互引用检测（Phase 28）

## 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.10+（使用 match/case、类型提示） |
| 依赖 | 零运行时依赖（struct、mmap、dataclasses、json、argparse） |
| 构建 | setuptools + pyproject.toml（src layout） |
| 测试 | pytest（可选 dev 依赖） |
| 状态管理 | GSD workflow（.planning/ 目录） |

## 项目结构

```
uasset_read/
├── src/uasset_read/          # 新版模块化包（v6.0重构目标）
│   ├── __init__.py          # 公共 API 导出（50+ 项）
│   ├── archive.py           # FArchive 二进制读取器（mmap、字节交换）
│   ├── constants.py         # 版本号、阈值、边界常量
│   ├── exceptions.py        # 异常类（UAssetError、ParseError等）
│   ├── serialize/           # 序列化模块
│   │   ├── package_summary.py    # PackageFileSummary
│   │   ├── object_resources.py   # ObjectImport/Export
│   │   └── property_tags.py      # PropertyTag / PropertyData
│   ├── models/              # 数据模型
│   │   ├── core.py       # UEdGraph/Node/Pin 核心模型
│   │   ├── node_types.py # 节点类型子类（K2NodeCallFunction等）
│   │   ├── blueprint.py  # 蓝图元数据模型
│   │   ├── result.py     # ParseResult 结果容器
│   │   └── transforms.py # Transform/Rotator/Scale 数据类
│   ├── parsers/             # 属性解析模块
│   │   ├── property_types.py    # 14种属性类型解析函数
│   │   ├── advanced_property.py # 高级属性处理
│   │   └── dispatcher.py        # 类型分派器
│   ├── blueprint/           # 蓝图处理模块
│   │   ├── variable_extractor.py  # 变量提取
│   │   ├── transform_parser.py    # 变换解析
│   │   └── metadata_extractor.py  # 元数据提取
│   ├── graph/               # 图解析模块
│   │   ├── from_archive.py    # 从 FArchive 读取图
│   │   ├── flow_builder.py    # 执行流/数据流构建
│   │   └── summary_builder.py # 图摘要生成
│   ├── formatters/          # 输出格式化模块
│   │   ├── json.py     # JSON 输出（完整/摘要/蓝图）
│   │   ├── text.py     # 纯文本输出
│   │   ├── markdown.py # Markdown 输出（含Mermaid图）
│   │   └── helpers.py  # 辅助函数
│   └── parse_uasset.py      # 主解析管线（Phase 33）
│
├── tests/                   # 测试套件（18个测试文件）
│   ├── test_*.py           # 各功能模块测试
│   └── testdata/           # 测试资产（可选）
│
├── uasset_read.py          # 旧版单文件入口（Phase 33 后删除）
├── cli.py                  # CLI 主入口
├── pyproject.toml          # 项目配置
├── README.md               # 项目说明（英文）
├── README.zh-CN.md         # 项目说明（中文）
├── PROJECT-STRUCTURE.md    # 项目结构详细文档
├── SECURITY.md             # 安全审计文档
├── CLAUDE.md               # Claude Code 指导（可与 QWEN.md 合并）
│
└── .planning/              # GSD 工作流文件
    ├── PROJECT.md          # 项目定义（需求/背景/决策）
    ├── ROADMAP.md          # 路线图（50 phases）
    ├── STATE.md            # 当前里程碑状态
    ├── REQUIREMENTS.md     # 需求追溯表
    ├── MILESTONES.md       # 里程碑历史
    ├── phases/             # 阶段执行记录
    └── schemas/            # 输出格式 schema（JSON/YAML）
```

## 安装与运行

### 安装

```bash
# 克隆仓库
git clone https://github.com/soatori/uasset_read.git
cd uasset_read

# 开发模式安装（推荐）
pip install -e ".[dev]"

# 或仅安装运行时依赖（零依赖）
pip install -e .
```

### CLI 用法

```bash
# 解析单个 .uasset 文件（JSON 输出）
uasset-read path/to/file.uasset

# 导出到文件
uasset-read path/to/file.uasset --output output.json

# 仅输出蓝图图结构
uasset-read path/to/file.uasset --graph

# 输出摘要（不包含完整属性）
uasset-read path/to/file.uasset --summary

# 严格模式（遇到警告即停止）
uasset-read path/to/file.uasset --strict
```

### Python API

**新版模块化 API（推荐）**：

```python
from uasset_read import parse_uasset

# 解析 .uasset 文件
result = parse_uasset('BP_FirstPersonCharacter.uasset')

# 访问解析结果
print(result.name_map)          # 名称表（list[str]）
print(result.import_map)        # 导入依赖（list[ObjectImport]）
print(result.export_map)        # 导出表（list[ObjectExport]）
print(result.blueprint)         # 蓝图元数据（BlueprintMetadata）
print(result.graphs)            # 蓝图图结构（list[UEdGraph]）
print(result.format_json())     # JSON 输出
print(result.format_text())     # 文本输出
print(result.format_markdown()) # Markdown 输出
```

**细粒度控制**：

```python
from uasset_read import (
    # 数据模型
    ParseResult, BlueprintMetadata, BlueprintVariable,
    UEdGraph, UEdGraphNode, UEdGraphPin,
    PropertyTag, PropertyValue, StructValue, MapValue,
    
    # 解析器
    parse_property_value, parse_properties_from_export,
    parse_array_property, parse_struct_property, parse_map_property,
    
    # 蓝图提取
    extract_blueprint_variables, extract_blueprint_metadata,
    parse_component_transform,
    
    # 格式化
    format_json_full, format_json_summary, format_markdown,
    
    # 常量
    PACKAGE_FILE_TAG, MMAP_THRESHOLD,
    
    # 异常
    UAssetError, ParseError, VersionError,
)

# 从 FArchive 开始解析
from uasset_read.archive import FArchive

archive = FArchive('path/to/file.uasset')
summary = read_package_summary(archive)
name_map = read_name_table(archive, summary)
import_map = read_import_map(archive, summary)
export_map = read_export_map(archive, summary)
```

**完整 API 列表**: 见 `src/uasset_read/__init__.py`（`__all__` 导出 50+ 项）

### 测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行单个测试文件
python -m pytest tests/test_graph_parsing.py -v

# 运行单个测试函数
python -m pytest tests/test_graph_parsing.py::test_blueprint_graph_parsed -v

# 运行带覆盖率报告的测试
python -m pytest tests/ --cov=uasset_read --cov-report=html

# 运行特定阶段的测试
python -m pytest tests/test_phase12_blueprint_variables.py -v
```

**测试覆盖**（397 用例）：
- 边界验证（Phase 5）
- 核心解析（Phase 1-2）
- 属性解析（Phase 3）
- 蓝图提取（Phase 12）
- 图解析（Phase 7/18-22）
- 高级属性（Phase 9）
- 依赖分析（Phase 10）
- 格式化输出（Phase 14/20）
- mmap 行为（Phase 24）
- UE5 兼容性（Phase 26/33a）

## 开发流程

### 版本管理

项目采用 GSD（Guided Software Development）工作流：

- **ROADMAP**: `.planning/ROADMAP.md`（50 phases）
- **当前阶段**: `.planning/STATE.md`
- **需求**: `.planning/REQUIREMENTS.md`

**v6.0 模块化重构路线**：

| 阶段 | 名称 | 状态 | 说明 |
|------|------|------|------|
| Phase 27 | 项目结构初始化 | ✅ Complete | constants.py, exceptions.py |
| Phase 28 | 核心序列化模块 | ✅ Complete | FArchive, serializers/ |
| Phase 28a | 测试基线修复 | ✅ Complete | 380 passed, 62 skipped |
| Phase 29 | 核心数据模型 | ✅ Complete | UEdGraph/Node/Pin dataclasses |
| Phase 30 | 属性解析模块 | ✅ Complete | 14 type parsers + property dataclasses |
| Phase 31 | 蓝图图解析模块 | ✅ Complete | 等价迁移 Phase 7/18-22 |
| Phase 32 | 输出格式化模块 | ✅ Complete | JSON/Text/Markdown |
| Phase 33 | 入口与测试适配 | ✅ Complete | 删除旧 uasset_read.py |
| Phase 34 | 等价验证 | ✅ Complete | 新旧输出逐字段对比 |
| Phase 35 | v6.0 里程碑完成 | 🟢 In Progress | Phase 35b Pin 连接修复 |
| Phase 35b | Pin 连接深度调试 | 📋 Planned | 修复 linked_to_raw 根因 |

### 阶段执行

项目使用 GSD 命令管理开发流程（可通过 `/gsd-*` 技能调用）：

| 功能 | GSD 命令 | 说明 |
|------|----------|------|
| 查看状态 | `/gsd-stats` | 显示 phases、plans、progress |
| 切换阶段 | `/gsd-progress` | 前进到下一阶段 |
| 完成里程碑 | `/gsd-complete-milestone` | 归档当前 milestone |
| 创建计划 | `/gsd-plan-phase` | 为阶段创建 PLAN.md |
| 执行计划 | `/gsd-execute-phase` | 并行执行阶段任务 |
| 代码审查 | `/gsd-code-review` | 审查代码质量/安全问题 |
| 安全审计 | `/gsd-secure-phase` | 验证威胁缓解 |
| 验证测试 | `/gsd-validate-phase` | 填补测试覆盖 gaps |

### 开发规范

**代码风格**：

- Python 3.10+（使用 `match/case` 模式匹配）
- 完整类型提示（支持 MyPy）
- 模块化设计（每个模块职责单一）
- 边界验证（所有外部输入验证）
- 零依赖（仅使用标准库）

**模块职责**：

- `archive.py`: 二进制读取（支持 mmap、字节交换、边界检查）
- `constants.py`: 版本号、阈值、边界常量（全局只读）
- `exceptions.py`: 异常类定义（UAssetError、ParseError等）
- `serializers/`: 反序列化 UE 结构（PackageFileSummary、ObjectImport/Export）
- `models/`: 数据模型（dataclasses，用于存储解析结果）
- `parsers/`: 属性解析（14种属性类型 + 分派器）
- `blueprint/`: 蓝图专用解析（变量提取、变换解析、元数据）
- `graph/`: 图结构解析（执行流、数据流、连接图）
- `formatters/`: 输出格式化（JSON、Text、Markdown）

**边界常量**（必须遵守）：

```python
MAX_EXPORT_COUNT        = 1_000_000   # 导出表大小限制
MAX_PINS_PER_NODE       = 1_000       # 单节点引脚数限制
MAX_NODES_PER_GRAPH     = 5_000       # 单图节点数限制
MAX_LINKEDTO_PER_PIN    = 100         # 单引脚连接数限制
MAX_PROPERTY_COUNT      = 10_000      # 属性循环限制
PROPERTY_TAG_COMPLETE_TYPE_NAME = 1012  # UE5 格式切换点
MMAP_THRESHOLD          = # 大文件 mmap 阈值
```

**测试要求**：

- 每个阶段必须通过等价验证（新旧输出逐字段对比）
- 边界验证测试必须覆盖所有边界条件
- UE5 兼容性测试必须覆盖所有版本偏移
- 高级属性测试必须覆盖所有 6 种类型

### 常用开发命令

```bash
# 项目健康检查
python -m pytest tests/ -v --tb=short

# 运行代码质量检查（如添加）
python -m py_compile src/uasset_read/*.py

# 查看模块依赖
python -c "import uasset_read; print(uasset_read.__version__)"

# 解析测试文件并输出 JSON
python -c "from uasset_read import parse_uasset; print(parse_uasset('tests/testdata/test.uasset').format_json())"

# 生成覆盖率报告
python -m pytest tests/ --cov=uasset_read --cov-report=term-missing
```

## 关键架构决策

| 决策 | 理由 | 结果 |
|------|------|------|
| Python 实现 | 易于 AI agent 调用，快速原型开发 | ✅ 佳 |
| 参考 UE 源码 | .uasset 格式无公开文档 | ✅ 佳 |
| 结构化 JSON 优先 | Agent 直接理解 | ✅ 佳 |
| 零运行时依赖 | 减少环境配置复杂度 | ✅ 佳 |
| FArchive 管道模式 | 镜像 UE 架构，易于扩展 | ✅ 佳 |
| Bool 解析：`read_u32()!=0` | UE 源码正确值 | ✅ 佳 |
| 偏移计算：`serial + script_serial_offset` | ObjectResource.h 注释明确 | ✅ 佳 |
| 阈值：`PROPERTY_TAG_COMPLETE_TYPE_NAME=1012` | UE5 格式切换点 | ✅ 佳 |
| Status 三元分类 | JSend 规范，AI 友好 | ✅ 佳 |
| v6.0 等价迁移原则 | 先等价再增强，避免范围蔓延 | ✅ 佳 |
| 测试基线优先 | 修复已知失败后再开始 Phase 29 | ✅ 佳 |

## 已知限制

- **仅支持未烘焙/编辑器保存的资产**: Cooked 资产已剥离图数据，使用不同序列化格式
- **不支持字节码反编译**: 编译蓝图使用字节码格式，本项目专注于编辑器保存的资产
- **不输出资源文件**: 纹理、模型等二进制数据过于庞大，仅提取元数据
- **不支持修改**: 仅支持只读解析
- **依赖 UE 源码参考**: .uasset 格式无官方文档，需要 UE 源码作为参考

## 常见任务

### 1. 添加新属性类型解析器

1. 在 `src/uasset_read/parsers/property_types.py` 添加解析函数
2. 在 `src/uasset_read/parsers/dispatcher.py` 添加分派逻辑
3. 添加测试用例（`tests/test_property_parsing.py`）
4. 运行测试验证：`python -m pytest tests/test_property_parsing.py -v`

### 2. 添加新节点类型支持

1. 在 `src/uasset_read/models/node_types.py` 添加节点数据类
2. 在 `src/uasset_read/serializers/graph.py` 添加读取函数（`read_k2node_*`）
3. 在 `src/uasset_read/graph/from_archive.py` 添加节点处理逻辑
4. 添加测试用例（`tests/test_graph_parsing.py`）

### 3. 添加新输出格式

1. 在 `src/uasset_read/formatters/` 添加格式化函数
2. 在 `src/uasset_read/__init__.py` 导出
3. 在 CLI 中添加 `--output-format` 参数（`cli.py`）
4. 添加测试用例（`tests/test_output_formatting.py`）

### 4. 调试解析问题

1. 启用调试模式：设置环境变量 `DEBUG_PIN_PARSING=1`
2. 使用二进制分析工具验证偏移（参考 `debug/` 目录）
3. 检查边界常量是否触发（日志输出警告）
4. 对比旧版单文件输出（等价验证）

## 安全与审计

项目已完成 Phase 6-9 安全审计（见 `SECURITY.md`）：

- **已关闭威胁**: 19 个（验证通过）
- **已接受风险**: 12 个（需记录）
- **开放威胁**: 0 个

边界验证阈值已迁移至 `src/uasset_read/constants.py`（Phase 27）。

## 贡献指南

1. Fork 仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

**提交前检查**：

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行代码检查（如添加）
python -m py_compile src/uasset_read/*.py

# 验证等价性（如修改核心解析逻辑）
python uasset_read.py tests/testdata/test.uasset > old_output.json
python -c "from uasset_read import parse_uasset; print(parse_uasset('tests/testdata/test.uasset').format_json())" > new_output.json
diff old_output.json new_output.json
```

## 相关文档

- **项目说明**: `README.md` / `README.zh-CN.md`
- **项目结构**: `PROJECT-STRUCTURE.md`
- **安全审计**: `SECURITY.md`
- **Claude 指导**: `CLAUDE.md`
- **规划**: `.planning/PROJECT.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`
- **里程碑**: `.planning/MILESTONES.md`
- **需求**: `.planning/REQUIREMENTS.md`

## 版本历史

| 版本 | 日期 | 状态 | 主要特性 |
|------|------|------|----------|
| v1.0 | 2026-05-02 | ✅ 已发布 | 核心解析、基本属性、蓝图元数据 |
| v2.0 | 2026-05-02 | ✅ 已发布 | 蓝图图解析、高级属性、依赖分析 |
| v3.x | 2026-05-04 | ✅ 已发布 | 属性值提取、输出优化、Skill 封装 |
| v4.0 | 2026-05-05 | ✅ 已发布 | 节点属性深度解析、执行流、连接验证 |
| v5.0 | 2026-05-06 | ✅ 已发布 | 蓝图编译研究、元数据增强 |
| v5.1 | 2026-05-07 | ✅ 已发布 | 项目结构初始化（constants.py, exceptions.py） |
| v6.0 | 2026-05-10 | 🟢 进行中 | 模块化重构（Phase 27-35） |
| v6.1 | 📋 计划中 | - | 等价验证完成、发布准备 |

## 联系方式

- **GitHub**: https://github.com/soatori/uasset_read
- **问题反馈**: GitHub Issues
- **贡献**: Pull Requests

---

**最后更新**: 2026-05-13  
**维护者**: uasset_read Contributors  
**项目状态**: v6.0 模块化重构（Phase 35b 进行中）
