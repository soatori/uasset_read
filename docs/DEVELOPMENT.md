# 开发指南

本地开发环境搭建、编码规范、测试策略和 Superpowers 工作流说明。

## 1. 开发环境搭建

### 前置要求

- **Python >= 3.10** — 项目使用 `dataclasses`、`match` 语句、`|` Union 语法等 3.10+ 特性
- **pip + setuptools >= 61.0** — 构建系统
- **git** — 版本控制

### 克隆与安装

```bash
# 克隆仓库
git clone <repository-url>
cd uasset_read

# 创建虚拟环境（推荐）
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 安装开发依赖（含 pytest）
pip install -e ".[dev]"
```

安装后可验证：

```bash
uasset-read --help
python -m pytest tests/ --co -q
```

### Pre-commit

项目当前**未配置** pre-commit hooks。所有代码质量检查通过 CI 测试（pytest）和手动 `pytest` 运行保证。如有需要，可在本地创建 `.git/hooks/pre-commit` 脚本自行设置。

## 2. 项目结构

```
uasset_read/
├── src/uasset_read/        # 源代码（src layout）
│   ├── __init__.py         # 公共 API 导出（__all__ 控制，~150 符号）
│   ├── __main__.py         # python -m uasset_read 入口
│   ├── archive.py          # FArchive 二进制读取器（字节交换/mmap）
│   ├── cli.py              # CLI 入口（argparse）
│   ├── constants.py        # 版本/阈值/Package/CPF 标志常量
│   ├── exceptions.py       # UAssetError / VersionError / ParseError
│   ├── parse_uasset.py     # 主编排函数（parse_uasset / parse_uasset_with_linker）
│   ├── serializers/        # 二进制反序列化（PackageSummary/Import/Export/PropertyTag/Graph）
│   ├── models/             # 数据类（UEdGraph/Node/Pin、属性值类、Transform 值类）
│   ├── parsers/            # 14 种属性类型解析器 + 分派器
│   ├── blueprint/          # 蓝图元数据/变量/组件变换提取
│   ├── graph/              # 执行流/数据流/连接映射
│   ├── link/               # PackageLinker / UObjectInstance（两阶段对象图重建）
│   └── formatters/         # JSON/Text/Markdown 输出格式化
├── tests/                  # pytest 测试（554 tests）
├── .planning/              # 规划历史归档（v1.0-v13.0，MILESTONES.md 仍有效）
├── docs/superpowers/       # 当前规划（specs + plans，Superpowers 工作流）
├── temp/                   # 缓存/临时文件（gitignored）
├── pyproject.toml          # 构建配置 + pytest 配置
└── CLAUDE.md               # 项目上下文（AI 代理参考）
```

**外部参考目录**（Git 忽略，不属项目）：`UnrealEngine/`、`LyraStarterGame/`、`uasset_read_cpp/`

### 模块职责速查

| 模块 | 职责 | 添加新内容时修改 |
|------|------|-----------------|
| `archive.py` | 二进制读取、字节序、mmap | 新数据类型读取方法 |
| `serializers/` | 从 FArchive 读取 UE 结构 | 新结构反序列化 |
| `models/` | 数据类（dataclass） | 新节点类型、属性值类 |
| `parsers/` | 属性值解析（从序列化数据到模型） | 新属性类型解析器 |
| `blueprint/` | 蓝图语义提取（变量/组件/元数据） | 新提取函数 |
| `graph/` | 图解析（执行流/数据流） | 新流构建逻辑 |
| `link/` | 对象图链接（Import/Export 解析） | 链接器增强 |
| `formatters/` | 输出格式化（JSON/Text/Markdown） | 新输出格式 |

## 3. 编码规范

### 命名约定

- **类名**：`PascalCase`，镜像 UE 命名（`FArchive`、`UEdGraphPin`、`PackageLinker`）
- **函数/变量**：`snake_case`（`parse_property_value`、`read_package_summary`）
- **常量**：`PascalCase` 镜像 UE 风格（`PKG_Cooked`、`CPF_Edit`）或 `UPPER_SNAKE_CASE`（`MMAP_THRESHOLD`）
- **私有辅助**：前导下划线（`_extract_struct_type_from_tag`）

### 类型标注

所有函数签名使用完整类型标注。Python 3.10+ 原生 Union 语法优先：

```python
def parse_value(archive: FArchive, tag: PropertyTag) -> PropertyValue | StructValue:
```

循环引用或前向引用使用 `TYPE_CHECKING` 守卫：

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from uasset_read.link.linker import PackageLinker
```

### 文档字符串

- **模块级**：文件顶部 docstring，说明模块职责，必要时标注对应的源迁移位置（如 `等价迁移 uasset_read.py §6223-6412`）
- **公共函数/类**：Google 风格 docstring，包含参数说明和返回值
- **内部辅助函数**：一行 docstring 或省略（零注释策略）

### 零注释策略

对于逻辑自明的代码不添加冗余注释：

```python
# 不要这样（代码本身已说明）
x = archive.read_i32()  # 读取一个 int32

# 需要注释的情况：UE 二进制格式的特殊行为、魔法数字来源、边界条件
# UE5 开始 PropertyTag 包含 Extension 字段，需要检查标志位
if tag.flags & PROP_TAG_HAS_EXTENSIONS:
    ...
```

### 公共 API 管理

所有对外暴露的符号必须在 `src/uasset_read/__init__.py` 的 `__all__` 中注册。新增公共函数/类/常量时同步更新 `__all__` 列表。

## 4. 如何添加新功能

### 添加新的属性解析器

1. 在 `src/uasset_read/parsers/property_types.py` 中编写解析函数：

```python
def parse_my_property(archive: FArchive, tag: PropertyTag) -> PropertyValue:
    """解析 MyProperty 类型。"""
    value = archive.read_fstring()
    return PropertyValue(name=tag.name, value=value)
```

2. 在 `property_parser.py` 的分派器中注册类型映射
3. 在 `models/properties.py` 中添加对应的数据类（如需要新结构）
4. 在 `__init__.py` 中导出新函数
5. 编写测试：`tests/test_my_property.py`

### 添加新的节点类型

1. 在 `src/uasset_read/models/node_types.py` 中定义新的节点 dataclass：

```python
@dataclass
class K2NodeMyNewType(UEdGraphNode):
    """Custom blueprint node type."""
    my_field: str = ""
```

2. 在 `src/uasset_read/serializers/graph.py` 中编写 `read_k2node_my_new_type()`
3. 在 `create_node_from_archive()` 中添加类型分发
4. 在 `__init__.py` 中导出新类和读取函数
5. 编写测试验证读取正确性

### 添加新的输出格式化器

1. 在 `src/uasset_read/formatters/` 中创建新文件（如 `my_formatter.py`）
2. 编写格式化函数，接受 `ParseResult` 返回 `str`
3. 在 `formatters/__init__.py` 中导出
4. 在 `__init__.py` 中添加到公共 API 导出
5. 在 `cli.py` 中添加对应 `--my-format` 参数（如需要）

### 修改常量

在 `src/uasset_read/constants.py` 中添加，同步更新 `__init__.py` 的导入和 `__all__` 导出。

## 5. 测试策略

> 详细英文测试指南（测试哲学、MockArchive 模式、调试技巧等）见 [TESTING.md](TESTING.md)。

### 框架与配置

- **pytest >= 7.0**，配置在 `pyproject.toml` 的 `[tool.pytest.ini_options]`
- **pytest-cov >= 4.0**（可选，覆盖率报告）
- **零运行时依赖** — 测试不依赖外部 UE 资源

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

### 运行测试

```bash
# 运行全部测试
python -m pytest tests/ -v

# 快速运行（无详细输出）
python -m pytest tests/ -q

# 运行单个测试文件
python -m pytest tests/test_graph_parsing.py -v

# 运行单个测试函数
python -m pytest tests/test_graph_parsing.py::test_build_execution_flows -v

# 覆盖率报告
python -m pytest tests/ --cov=uasset_read --cov-report=term-missing
```

### 测试组织

测试文件按功能和 Phase 编号组织：

| 文件模式 | 说明 | 示例 |
|----------|------|------|
| `test_uasset_read.py` | 核心功能 | 基础解析、版本检测 |
| `test_phase{N}_*.py` | 特定 Phase 功能 | `test_phase12_blueprint_variables.py` |
| `test_link_*.py` | PackageLinker 相关 | `test_link_linker.py`, `test_link_object_instance.py` |
| `test_ue5_*.py` | UE5 特有行为 | `test_ue5_bool_serialization.py`, `test_ue5_pin_bitfield.py` |
| `test_*.py` | 按功能分类 | `test_graph_parsing.py`, `test_blueprint_extraction.py` |

### 编写新测试

- 文件名：`test_{feature}.py` 或 `test_phase{N}_{description}.py`
- 测试类：`Test{FeatureName}` 前缀
- 测试函数：`test_{behavior}` 前缀
- 使用 `pytest.raises()` 验证异常路径
- 测试资产路径：引用 `E:\Develop\lib\UnrealEngine\Samples\FirstPerson` 下的 `.uasset` 文件，或使用 `pytest.skip()` 跳过缺失资产的测试

### 已知测试状态

- **554 tests collected**，520 passing
- Phase 49（函数调用引脚解析）对应的测试尚未通过（功能待实现）
- 34 tests skipped（通常因测试资产不可用）

## 6. Superpowers 工作流

本项目使用 Superpowers 进行规划和执行。

### Specs + Plans

Spec 文档位于 `docs/superpowers/specs/`，描述"做什么"和"为什么"。
实施计划位于 `docs/superpowers/plans/`，描述"怎么做"（由 writing-plans 技能生成）。

### 规划历史

v1.0-v13.0 的 GSD Phase 规划已归档至 `.planning/archive/`。

## 7. 分支策略

### 分支模型

| 分支 | 用途 |
|------|------|
| `master` | 主分支，稳定版本，受保护 |
| `v{major}-{minor}-dev` | 开发分支（当前 `v2.8-dev`） |

### 工作流程

1. 从 `master` 创建开发分支（如 `v2.8-dev`）
2. 所有开发工作在该开发分支上进行
3. Phase 完成后在开发分支上提交
4. 里程碑完成后通过 PR 合并到 `master`

### 提交信息格式

采用 Conventional Commits 格式：

```
type(scope): description

feat(49): add K2Node function call pin parsing
fix(47): resolve Pin LinkedTo serialization bug
docs(50): update STATE.md for Phase 50 completion
```

类型：`feat`（新功能）、`fix`（修复）、`docs`（文档）、`refactor`（重构）、`test`（测试）、`chore`（杂项）

### 合并到 master

- 开发分支通过 PR 合并到 `master`
- PR 标题简短描述变更内容
- PR 正文包含 Phase 编号和变更摘要
- 合并前确保所有测试通过

## 8. 调试技巧

### CLI --verbose 模式

```bash
uasset-read file.uasset --verbose
```

`--verbose` 标志在输出中包含额外的 detail 字段，便于查看完整数据结构。

### tolerant vs strict 模式

CLI 默认启用 tolerant 模式（宽容 UE5 序列化偏差）。遇到解析问题时，可切换到 strict 模式定位具体错误：

```bash
uasset-read file.uasset --strict
```

strict 模式下，序列化异常会直接抛出而非跳过，便于定位问题字段。

### FArchive 调试

`FArchive` 类在构造时接受 `tolerant` 参数。在代码中可以直接实例化并检查内部状态：

```python
from uasset_read import FArchive

archive = FArchive("file.uasset", tolerant=False)
print(f"File size: {archive._file_size}")
print(f"Byte swapping: {archive._byte_swapping}")
print(f"mmap active: {archive._use_mmap}")
```

### 异常上下文

`ParseError` 携带 `ErrorContext` 对象，包含错误发生时的偏移量、解析阶段和操作类型：

```python
try:
    result = parse_uasset("file.uasset")
except ParseError as e:
    if e.context:
        print(f"Phase: {e.context.phase}")
        print(f"Offset: {e.context.offset}")
        print(f"Operation: {e.context.operation}")
```

### 临时输出

解析结果可输出到文件便于分析：

```bash
uasset-read file.uasset --json --output output.json
```

输出到 `output/` 目录（已在 `.gitignore` 中排除）。

### 测试资产

真实测试资产位于 `E:\Develop\lib\UnrealEngine\Samples\FirstPerson`，包含 `BP_FirstPersonCharacter.uasset` 等文件，可用于验证解析行为。
