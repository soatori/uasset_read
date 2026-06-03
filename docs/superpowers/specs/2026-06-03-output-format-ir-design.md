# 输出格式统一化与 CLI 核心分离设计

**日期**: 2026-06-03 | **版本**: 0.4.0-dev | **状态**: 已批准

## 1. 问题与目标

### 输出格式问题

**现状**: 7 个 formatter + 12 个 exporter 各自拼接字符串/Dict，同一数据在不同格式中结构不一致，重复代码多。

**目标**: 建立 IR（中间表示）+ 多渲染器架构，实现单一数据源、多格式渲染、零重复。

### CLI 入口问题

**现状**: `cli.py`（400+ 行）承担三个职责：argparse 参数解析、核心解析路由、batch/graph 特殊模式。独立脚本无法复用核心逻辑，因为一切绑定在 argparse 流程中。

**目标**: 核心逻辑与入口分离，使 CLI、独立脚本、未来 Skill 共享同一套 API。

### 统一原则

- 仅保留蓝图原注释（NodeComment），不添加额外描述字段
- 结构自解释，字段名用 UE 原生术语
- 不考虑向后兼容，旧函数和导出器直接删除重建
- 核心函数纯 Python，无 argparse、无 sys.exit、无 print

---

## 2. IR 中间表示结构

### 顶层结构

```
PackageIR
├── header          # PackageFileSummary 精简版
├── name_map        # 名称表（供引用解析）
├── imports         # 导入表
├── exports         # 导出对象列表
│   └── ExportIR
│       ├── object_name
│       ├── object_class
│       ├── outer_path
│       ├── properties        # 属性列表（IPropertyHolder 注册表模式）
│       ├── graphs            # 仅蓝图类型
│       │   └── GraphIR
│       │       ├── graph_name
│       │       ├── nodes
│       │       │   └── NodeIR
│       │       │       ├── node_class
│       │       │       ├── node_comment    # 蓝图原注释
│       │       │       ├── pins            # PinIR 列表
│       │       │       │   └── linked_to   # 引用 PinID
│       │       │       └── execution_flow  # 序列化顺序 + Pin 连接
│       │       └── execution_chains
│       └── bulk_data         # L3+ 资产头部信息
└── linker            # 包链接摘要
```

### 规则

1. `properties` 使用注册表模式访问，禁止硬编码 if/elif
2. `graphs` 仅蓝图类 Export 非空，其余类型为空列表
3. `node_comment` 原样保留蓝图注释，不生成额外描述
4. `execution_flow` 是节点序列化顺序 + Pin 连接关系，非重新发明的格式
5. 所有 GUID（Node/Pin）统一为 32 位小写 hex（构建阶段完成）

---

## 3. 渲染层设计

### 统一接口

```python
class IRenderer(ABC):
    @abstractmethod
    def render(self, ir: PackageIR, options: RenderOptions) -> str: ...
    @property
    @abstractmethod
    def format_name(self) -> str: ...
```

### 渲染器列表

| 渲染器 | 格式 | 说明 |
|--------|------|------|
| JSONRenderer | json | `asdict()` 递归序列化 IR |
| TextRenderer | text | YAML 风格缩进，与 JSON 等价 |
| MarkdownRenderer | markdown | 标题 + Mermaid 流程图 |
| BlueprintTextRenderer | blueprint_text | 紧凑节点列表 |
| BlueprintUERenderer | blueprint_ue | 模拟 UE Ctrl+C 文本 |
| CppSkeletonRenderer | cpp_skeleton | C++ 头文件骨架 |
| N2CRenderer | n2c | N2C 中间格式 + 验证 |

### 关键规则

1. 渲染器**不得**访问 `ParseResult`，只能接收 `PackageIR`
2. 渲染器**不得**做数据转换（GUID 格式化等），在 IR 构建时完成
3. 渲染器**不得**拼接业务逻辑，只负责格式排版
4. 复用现有 `ExporterRegistry` 改为注册 `IRenderer`

---

## 4. IR 构建层

### 构建入口

```python
def build_package_ir(result: ParseResult) -> PackageIR: ...
```

### 构建流程

```
ParseResult → PackageIR 构建器
├── build_header(result.summary)     → PackageHeaderIR
├── build_exports(result.export_map) → list[ExportIR]
│   └── 按对象类型路由（ObjectTypeRegistry）
├── build_linker(result.linker)      → LinkerSummaryIR
└── finalize()                       → 跨引用解析、GUID 标准化
```

### 关键决策

1. **直接替换**: 旧 `format_*` 函数、旧 `IExporter` 直接删除
2. **类型路由**: 复用 `ObjectTypeRegistry` 自动路由，不硬编码
3. **跨引用解析**: 构建阶段处理所有 `FPackageIndex`，IR 中无未解析索引
4. **GUID 标准化**: 构建阶段一次性完成

---

## 5. CLI 核心与入口分离

### 分层架构

```
uasset_read/
├── core.py              # 新增：核心解析 API（纯函数）
├── cli.py               # 瘦身：argparse + 委托 core.py
├── __main__.py          # 不变：python -m uasset_read 入口
└── simple.py            # 新增：快速诊断脚本（python -m uasset_read.simple）

项目根目录/
└── diag.py              # 新增：快捷诊断入口（python diag.py <path>）
```

### 文件职责

| 文件 | 职责 | 依赖 |
|------|------|------|
| `core.py` | 纯解析函数：parse_single, parse_batch, list_formats | 无 argparse |
| `cli.py` | argparse 定义 + 参数转 options + 委托 core.py | core.py |
| `simple.py` | 单文件快速诊断入口 | core.py |
| `diag.py` | 项目根快捷脚本 | core.py |

### core.py API

```python
def parse_single(
    file_path: str,
    format: str = "text",
    tolerant: bool = True,
    verbose: bool = False,
    include_schema: bool = False,
    include_function_graphs: bool = False,
    include_parent_assets: bool = False,
    asset_roots: list[str] | None = None,
    mappings_path: str | None = None,
    game: str | None = None,
) -> str:
    """解析单个 .uasset/.umap，返回格式化字符串。
    纯函数，无 argparse、无 sys.exit、无 print。
    需要 linker 的格式内部自动选择 parse_uasset_with_linker。
    """

@dataclass
class BatchResult:
    total: int
    success: list[str]
    skipped: list[tuple]
    failed: list[tuple]

def parse_batch(
    input_dir: str,
    format: str = "text",
    output_dir: str | None = None,
    tolerant: bool = True,
    **format_options,
) -> BatchResult:
    """批量解析目录下所有 .uasset/.umap。"""

def list_formats() -> list[str]:
    """返回所有支持的格式名列表。"""
```

### CLI 瘦身方案

`main()` 中原有的解析 + 导出逻辑委托给 `core.parse_single()`：

```python
# 旧：直接调用 parse_package + ExporterRegistry
# 新：
output_str = core.parse_single(str(file_path), fmt, **opts_dict)
```

`_handle_graph_mode` 和 `_handle_batch` 同样委托 `core.parse_single` / `core.parse_batch`。

### 快速诊断脚本

```python
#!/usr/bin/env python
"""快速诊断：python diag.py <path.uasset> [--format FORMAT]"""
import sys
from uasset_read.core import parse_single

if len(sys.argv) < 2:
    print("用法: python diag.py <path.uasset> [--format FORMAT]")
    sys.exit(1)

path = sys.argv[1]
fmt = "text"
if len(sys.argv) >= 4 and sys.argv[2] == "--format":
    fmt = sys.argv[3]

print(parse_single(path, format=fmt))
```

---

## 6. 迁移和测试

### 迁移顺序

1. 定义 `PackageIR` 数据结构（`models/ir.py`）
2. 定义 `core.py` API（parse_single, parse_batch, list_formats）
3. 实现 `build_package_ir()` 构建器 + `IRenderer` 接口
4. 实现 `parse_single` 内部逻辑（IR 构建 → 渲染器路由）
5. 实现 `parse_batch` 内部逻辑
6. 逐个迁移渲染器（JSON → Text → Markdown → BlueprintText → BlueprintUE → CppSkeleton → N2C）
7. CLI 瘦身：main() 委托 core.py
8. 创建 `diag.py` 和 `simple.py`
9. 删除旧的 `formatters/` 和 `exporter/` 模块
10. 更新 `cli.py` 和 `__init__.py`

### 测试矩阵

| 测试类型 | 用例 | 验证 |
|----------|------|------|
| IR 构建正确性 | 每种支持的资产类型 | IR 中 exports/properties/graphs 不为空 |
| JSON 渲染等价性 | 已知通过的真实资产 | 新输出关键字段与旧输出一致 |
| 渲染器独立性 | 固定 IR fixture | 给定同一 IR，输出可重复 |
| CLI 回归 | `--json/--text/--markdown` | CLI 输出格式正确 |
| 蓝图 Pin 连接 | ≥ 2 种蓝图资产 | linked_to 正确，GUID 统一 |
| core.parse_single | 每种格式 | 输出与现有 CLI 等价 |
| 脚本基本功能 | `python diag.py <path>` | 正确输出 |
| 错误处理 | 文件不存在、目录传入 | 正确抛出异常 |
