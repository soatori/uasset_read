# 输出格式统一化与 CLI 核心分离设计

**日期**: 2026-06-03 | **状态**: 已批准

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
│   ├── package_name       # 完整路径 /Game/...
│   ├── package_class      # 主类名
│   ├── package_flags
│   ├── total_export_count
│   ├── total_import_count
│   └── ue_version
├── name_map        # 名称表（供引用解析）
├── imports         # 导入表
├── exports         # 导出对象列表
│   └── ExportIR
│       ├── index              # 导出序号（0-based）
│       ├── object_name
│       ├── object_class
│       ├── serial_size        # 序列化数据大小
│       ├── outer_index_resolved  # 已解析的 outer 对象名
│       ├── super_index_resolved  # 父类路径（null 则无）
│       ├── parent_class       # 蓝图主类路径
│       ├── properties         # 属性列表（IPropertyHolder 注册表模式）
│       ├── graphs             # 仅蓝图类型
│       │   └── GraphIR
│       │       ├── graph_name
│       │       ├── graph_guid
│       │       ├── nodes
│       │       │   └── NodeIR
│       │       │       ├── node_guid     # 32位小写 hex
│       │       │       ├── node_class
│       │       │       ├── node_comment  # 蓝图原注释
│       │       │       ├── pins          # PinIR 列表
│       │       │       │   └── linked_to # 引用 PinID（32位小写 hex）
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

### Python 数据结构定义

```python
@dataclass
class PackageHeaderIR:
    package_name: str            # 包完整路径（/Game/.../BP_FirstPersonCharacter）
    package_class: str           # 包内主类名
    package_flags: int           # 精简后的 flag 值
    total_export_count: int
    total_import_count: int
    ue_version: str             # "5.x" 或 "4.x"

@dataclass
class PinIR:
    pin_name: str
    pin_type: str               # "EdGraphPin", "EdGraphPinType"
    pin_type_value: str | None  # 类型具体值（int, float, Object 等）
    linked_to: list[str]        # 目标 PinID 列表，32位小写 hex
    direction: str              # "EGPD_Input" | "EGPD_Output"
    default_value: str | None   # 默认值字符串化

@dataclass
class NodeIR:
    node_guid: str              # 32位小写 hex
    node_class: str             # "K2Node_Event" 等
    node_comment: str | None    # 蓝图原注释
    pins: list[PinIR]
    execution_flow: list[dict]  # 序列化顺序 + Pin 连接，非重新发明格式

@dataclass
class GraphIR:
    graph_guid: str             # 32位小写 hex
    graph_name: str
    graph_class: str
    nodes: list[NodeIR]
    execution_chains: list[list[str]]  # 节点 GUID 链

@dataclass
class PropertyIR:
    name: str
    type: str
    value: Any                  # 原始值，渲染器负责格式化
    array_index: int            # 数组索引（-1 表示非数组元素）
    guid: str | None            # PropertyTag GUID，可选

@dataclass
class ExportIR:
    index: int                    # 导出序号（0-based）
    object_name: str
    object_class: str
    serial_size: int              # 序列化数据大小
    outer_index_resolved: str | None  # 已解析的 outer 对象名
    super_index_resolved: str | None  # 已解析的父类路径（null 则无）
    parent_class: str | None      # 蓝图主类路径
    properties: list[PropertyIR]
    graphs: list[GraphIR]         # 仅蓝图类非空
    bulk_data: dict | None        # L3+ 资产（Texture2D/SkeletalMesh 等）的 BulkData 头部信息

@dataclass
class LinkerSummaryIR:
    has_linker: bool
    import_paths: list[str]     # 已解析的 import 对象路径列表
    export_paths: list[str]     # 已解析的 export 对象路径列表

@dataclass
class PackageIR:
    header: PackageHeaderIR
    name_map: list[str]
    imports: list[dict]         # 轻量导入摘要
    exports: list[ExportIR]
    linker: LinkerSummaryIR | None
```

---

## 2b. ParseResult → IR 映射规则

**原则**：数据不丢弃，重新归位到正确层级，消除游离的 `blueprint` 顶层对象。

| ParseResult 字段 | 映射到 IR | 处理 |
|-------------------|-----------|------|
| `summary` | `PackageIR.header` | 提取 package_class, flags, counts |
| `name_map` | `PackageIR.name_map` | 直接传递 |
| `import_map` | `PackageIR.imports` | 通过 linker 解析为路径摘要 |
| `export_map` | `PackageIR.exports` | 逐条转 ExportIR，ObjectTypeRegistry 路由 graphs |
| `blueprint.variables` | `ExportIR.properties` | 变量本质是属性，归入主 Export 的 properties 列表 |
| `blueprint.functions` | `GraphIR.nodes`（函数定义节点） | 函数元数据通过 Graph 节点表达，不单独保留 |
| `blueprint.events` | `GraphIR.nodes`（事件节点） | 事件本质是 K2Node_Event，已在 nodes 中 |
| `blueprint.graphs` 摘要 | `ExportIR.graphs` 头部 | 图摘要已是 graphs 列表的聚合，不单独保留 |
| `blueprint.Nodes` 索引 | `GraphIR.nodes` | 扁平节点索引已是 nodes 本身，不保留冗余副本 |
| `blueprint.Warnings` | 构建阶段日志 | 不进入 IR，构建过程中记录到 stderr |
| `graphs` (UEdGraph) | `ExportIR.graphs` | UEdGraphNode → NodeIR，UEdGraphPin → PinIR |
| `errors` | 构建阶段处理 | 不进入 IR；tolerant 模式跳过，strict 模式抛 `IRError` |
| `warnings` | 构建阶段处理 | 同上 |
| `decompiled_functions` | `ExportIR.properties`（可选） | kismet 反编译结果，作为可选字段保留，tolerant 失败不阻断 |
| `linker` | `PackageIR.linker` | 提取路径摘要 |
| `version_container` | `PackageIR.header.ue_version` | 提取版本字符串 |
| `components` | `ExportIR.properties`（可选） | 组件初始化信息，作为可选字段保留 |
| `soft_references` / `circular_deps` | 丢弃 | 引用分析非核心职责，不参与 IR |
| `resolved_parent_assets` / `inherited_blueprint_graphs` / `logic_sources` | 丢弃 | 元数据/引用分析，非输出所需 |

### 归位说明

**`blueprint` 顶层对象消除**：当前 JSON 输出中 `blueprint` 是一个游离的顶层对象，包含 Nodes、Graphs、Variables、Functions、Events 等大量数据。IR 中这些数据归位到正确层级：

- **Variables** → 归入蓝图主 Export 的 `properties` 列表（变量本质就是属性定义）
- **Functions/Events** → 通过 `GraphIR.nodes` 中的函数/事件节点表达（已在节点列表中）
- **Nodes 索引** → 就是 `GraphIR.nodes` 本身（不保留冗余副本）
- **Graphs 摘要** → 就是 `ExportIR.graphs` 列表头部（不保留聚合摘要）

**JSON 输出对比**：

| 当前 JSON 顶层字段 | IR JSON 中的位置 | 变化 |
|---------------------|------------------|------|
| `blueprint` | 不存在 | 消除，数据归入 exports |
| `blueprint.Nodes` | `exports[].graphs[].nodes[]` | 下沉到 Export 级别 |
| `blueprint.Graphs` | `exports[].graphs[]` | 下沉到 Export 级别 |
| `blueprint.Variables` | `exports[].properties[]` | 归入属性列表 |
| `blueprint.Functions` | `exports[].graphs[].nodes[]`（函数节点） | 已在节点中 |
| `decompiled_functions` | `exports[].properties[]`（可选） | 归入属性或移除 |
| `components` | `exports[].properties[]`（可选） | 归入属性或移除 |

---

## 3. 渲染层设计

### 统一接口

```python
@dataclass
class RenderOptions:
    """渲染选项（渲染器只读，不修改）。"""
    verbose: bool = False          # 是否包含额外字段
    indent: int = 2                # JSON 缩进
    include_schema: bool = False   # 是否包含字段语义注解
    include_function_graphs: bool = False  # 是否包含顶层 function_graphs 数组

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
| JSONRenderer | json | 递归序列化 IR 为 JSON，包含 status 字段 |
| TextRenderer | text | YAML 风格缩进，与 JSON 等价 |
| MarkdownRenderer | markdown | 标题 + Mermaid 流程图 |
| BlueprintTextRenderer | blueprint_text | 紧凑节点列表 |
| BlueprintUERenderer | blueprint_ue | 模拟 UE Ctrl+C 文本 |
| CppSkeletonRenderer | cpp_skeleton | C++ 头文件骨架（可选） |

> N2C 渲染器已删除（对应 n2c/ 模块整体移除）

### JSON 输出结构

JSONRenderer 输出的顶层结构（消除 blueprint 顶层对象后）：

```json
{
  "status": { "status": "success", "message": null, "code": null },
  "summary": { "package_name": "/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter", "package_class": "...", "package_flags": 262144, "total_export_count": 69, "total_import_count": 73, "ue_version": "5.x" },
  "name_map": [...],
  "imports": [...],
  "exports": [
    {
      "index": 0,
      "object_name": "Default__BP_FirstPersonCharacter_C",
      "object_class": "BlueprintGeneratedClass",
      "serial_size": 46,
      "outer_index_resolved": "Default__BP_FirstPersonCharacter_C",
      "super_index_resolved": null,
      "parent_class": "/Script/Engine.Character",
      "properties": [
        { "name": "BlueprintSystemVersion", "type": "IntProperty", "value": 2, "array_index": -1, "guid": null },
        { "name": "DefaultSceneRoot", "type": "ObjectProperty", "value": {...}, "array_index": -1, "guid": null }
      ],
      "graphs": [
        {
          "graph_name": "Aim",
          "graph_guid": "...",
          "nodes": [
            {
              "node_guid": "...",
              "node_class": "K2Node_Event",
              "node_comment": "事件节点注释",
              "pins": [
                { "pin_name": "Then", "pin_type": "exec", "pin_type_value": null, "linked_to": ["..."], "direction": "EGPD_Output", "default_value": null }
              ],
              "execution_flow": []
            }
          ],
          "execution_chains": [["...", "...", "..."]]
        }
      ]
    }
  ],
  "linker": { "has_linker": true, "import_paths": [...], "export_paths": [...] }
}
```

**与当前 JSON 的差异**：

| 变化 | 当前 | IR |
|------|------|-----|
| `blueprint` 顶层对象 | 存在 | **消除**，数据归入 exports |
| `output_version` | `"4.0"` | **消除**，不需要 |
| `components` 顶层 | 存在（蓝图）/ []（非蓝图） | 归入 exports[].properties（可选） |
| `decompiled_functions` 顶层 | 存在 | 归入 exports[].properties（可选） |
| `resolved_parent_assets` | [] | **消除** |
| `inherited_blueprint_graphs` | [] | **消除** |
| `logic_sources` | [] | **消除** |
| `errors` 顶层 | [] | 渲染器不输出，由 status 字段表达 |
| `_schema` | 可选 | 可选（include_schema=True） |
| `function_graphs` 顶层 | 存在（`--function-graphs`） | 渲染器动态生成（不在 IR 中存储） |
| `bulk_data` 字段 | 不存在 | 新增：L3+ 资产的 BulkData 头部信息（可选） |

### 关键规则

1. 渲染器**不得**访问 `ParseResult`，只能接收 `PackageIR`
2. 渲染器**不得**做数据转换（GUID 格式化等），在 IR 构建时完成
3. 渲染器**不得**拼接业务逻辑，只负责格式排版
4. 复用现有 `ExporterRegistry` 改为注册 `IRenderer`
5. `function_graphs` 是**计算派生视图**（按函数/事件分组节点 + 签名 + 执行流），不在 IR 中存储，由渲染器在 `include_function_graphs=True` 时从 `GraphIR.nodes` 动态生成

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
5. **Graph → Export 归属**: `UEdGraph` 没有直接 outer 引用。构建层通过 linker 将 graphs 归入 `BlueprintGeneratedClass` 类型的 Export（蓝图的主导出）。非蓝图资产的 graphs 为空列表。

### 错误处理策略

- **tolerant 模式（默认）**：IR 构建阶段遇到可恢复问题（如单个 Export 解析失败、缺少 Pin GUID）时跳过该项继续，不抛出异常。最终 IR 中可能包含不完整的 ExportIR/NodeIR，但结构完整。
- **strict 模式**：任何 IR 构建失败都立即抛出 `IRError`，终止解析。
- **渲染器错误**：渲染器只负责格式排版，不处理数据错误。IR 中的空字段由渲染器决定是否跳过或输出占位。
- **降级行为**：当 IR 构建因数据损坏无法完成时，`core.parse_single()` 降级为直接调用旧 `parse_package()` + 旧 formatter 输出，确保快捷脚本始终有结果（非零结果优于零结果）。

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

## 6. 精简决策（轻量化方向）

### 目标

项目定位为**轻量化脚本**——`python diag.py <path>` 或 `python -m uasset_read <path>` 直接解析出结果，不需要 pip install。

### 删除的模块

| 模块 | 文件数 | 删除理由 |
|------|--------|----------|
| **exporter/** | 13 | IExporter 接口 + 注册表 + 批量导出 = 一个 dict + 循环调 formatter，过度抽象 |
| **n2c/** | 15+ | 57 种节点处理器 + JSON Schema 验证器，专用工具非核心需求 |
| **agent/** | 2 | AI 翻译管线，高级功能，与核心解析无关 |

### 保留为可选

| 模块 | 保留理由 |
|------|----------|
| **cpp_gen/** | 蓝图→C++ 骨架有用，但不走快捷路径，仅被 `--cpp-skeleton` 调用 |
| **kismet/** | 蓝图字节码反编译是核心能力（parse_uasset 已依赖），但 tolerant 失败不阻断主流程，暂不重构（需进一步研究） |
| **pak/ / iostore/** | 可选依赖，保留 |

### 格式路由替换方案

用 `core.py` 中的 `RENDERER_REGISTRY` 取代旧的 `ExporterRegistry` + `FORMAT_REGISTRY`：

```python
RENDERER_REGISTRY: dict[str, type[IRenderer]] = {
    "json": JSONRenderer,
    "text": TextRenderer,
    "text_summary": TextRenderer,
    "markdown": MarkdownRenderer,
    "blueprint_text": BlueprintTextRenderer,
    "blueprint_ue_text": BlueprintUERenderer,
    "cpp_skeleton": CppSkeletonRenderer,
}

def get_renderer(format: str) -> IRenderer:
    cls = RENDERER_REGISTRY.get(format)
    if cls is None:
        raise ValueError(f"未知格式: {format}")
    return cls()
```

渲染器实例化 + 调用：
```python
renderer = get_renderer(format)
output = renderer.render(ir, RenderOptions(verbose=verbose, indent=2))
```

取代旧的 13 文件 exporter 系统 + dict+函数 路由。

### 项目布局调整

| 变化 | 旧 | 新 |
|------|----|----|
| 打包方式 | setuptools + pip install | 直接脚本运行 `python run.py` 或 `python -m uasset_read` |
| 入口 | `uasset-read` CLI 命令 | `run.py`（项目根） + `python -m uasset_read` |

---

## 7. 更新后的迁移顺序

1. 定义 `PackageIR` 数据结构（`models/ir.py`）
2. 精简导出系统：删除 `exporter/`、`n2c/`、`agent/`，formatters 接管路由
3. 定义 `core.py` API（parse_single, parse_batch, list_formats）
4. 实现 `build_package_ir()` 构建器 + `IRenderer` 接口
5. 实现 `parse_single` 内部逻辑（IR 构建 → 渲染器路由）
6. 实现 `parse_batch` 内部逻辑
7. 逐个迁移渲染器（JSON → Text → Markdown → BlueprintText → BlueprintUE → CppSkeleton）
8. CLI 瘦身：main() 委托 core.py
9. 创建 `diag.py` 和 `simple.py`
10. 删除旧的 `formatters/` 旧函数，更新 `__init__.py`
11. 研究 kismet 模块是否需要精简

### 测试矩阵

| 测试类型 | 用例 | 验证 |
|----------|------|------|
| IR 构建正确性 | 每种支持的资产类型 | IR 中 exports/properties/graphs 不为空 |
| JSON 渲染等价性 | 已知通过的真实资产 | 新输出关键字段与旧输出一致 |
| 渲染器独立性 | 固定 IR fixture | 给定同一 IR，输出可重复 |
| CLI 回归 | `--json/--text/--markdown` | CLI 输出格式正确 |
| 蓝图 Pin 连接 | ≥ 2 种蓝图资产 | linked_to 正确，GUID 统一 |
| export() 函数 | 每种格式 | 输出与现有 CLI 等价 |
| 快捷脚本 | `python diag.py <path>` | 正确输出 |
| 错误处理 | 文件不存在、目录传入 | 正确抛出异常 |
| **结构变化验证** | 蓝图资产 | 无顶层 `blueprint` 字段，graphs 在 exports 下 |
| **结构变化验证** | 蓝图资产 | `blueprint.variables` 归入 exports[].properties |
| **结构变化验证** | 所有资产 | 无 `output_version` 字段 |
| **字段完整性** | 所有资产 | ExportIR 包含 index/serial_size/outer_index_resolved |
| **字段完整性** | 所有资产 | PropertyIR 包含 array_index |
| **BulkData** | Texture2D/SkeletalMesh | ExportIR.bulk_data 非空 |
