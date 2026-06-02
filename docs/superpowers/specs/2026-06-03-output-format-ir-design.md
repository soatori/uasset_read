# 输出格式统一化设计 — IR 中间表示

**日期**: 2026-06-03 | **版本**: 0.4.0-dev | **状态**: 已批准

## 1. 问题与目标

**现状**: 7 个 formatter + 12 个 exporter 各自拼接字符串/Dict，同一数据在不同格式中结构不一致，重复代码多。

**目标**: 建立 IR（中间表示）+ 多渲染器架构，实现单一数据源、多格式渲染、零重复。

**原则**:
- 仅保留蓝图原注释（NodeComment），不添加额外描述字段
- 结构自解释，字段名用 UE 原生术语
- 不考虑向后兼容，旧函数和导出器直接删除重建

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

## 5. 迁移和测试

### 迁移顺序

1. 定义 `PackageIR` 数据结构（`models/ir.py`）
2. 实现 `build_package_ir()` 构建器
3. 实现 `IRenderer` 接口和 `RendererRegistry`
4. 逐个迁移渲染器（JSON → Text → Markdown → BlueprintText → BlueprintUE → CppSkeleton → N2C）
5. 删除旧的 `formatters/` 和 `exporter/` 模块
6. 更新 `cli.py` 和 `__init__.py`

### 测试矩阵

| 测试类型 | 用例 | 验证 |
|----------|------|------|
| IR 构建正确性 | 每种支持的资产类型 | IR 中 exports/properties/graphs 不为空 |
| JSON 渲染等价性 | 已知通过的真实资产 | 新输出关键字段与旧输出一致 |
| 渲染器独立性 | 固定 IR fixture | 给定同一 IR，输出可重复 |
| CLI 回归 | `--json/--text/--markdown` | CLI 输出格式正确 |
| 蓝图 Pin 连接 | ≥ 2 种蓝图资产 | linked_to 正确，GUID 统一 |
