# IR 模型层与渲染器可维护性改进设计

status: historical

> **Status: historical proposal; target architecture superseded.** Retain this document as refactor history only. New work follows [`../2026-08-26-package-first-uasset-parser-refactor.md`](../2026-08-26-package-first-uasset-parser-refactor.md).

**日期**: 2026-07-17
**关联 Issue**: #436
**状态**: 待审批

## 背景

基于 #436 架构审查，对 `uasset_read` 项目的 IR 模型层和渲染器进行可维护性改进。项目当前状态：177 个 Python 文件、21 个目录、零运行时依赖。

核心管线设计健康，但存在以下维护性问题：

- PackageIR 上帝对象（29 个字段混合不同关注点）
- IR 中大量 dict 字段丢失类型安全
- ExportIR 字段重复
- 渲染器过滤逻辑重复
- render_to 不在 ABC 接口
- 双重 skip/strategy 系统
- parse_uasset.py 职责过重
- ir.py 混合核心 IR 和动画 IR
- ExportParseStatus 枚举与状态集合不同步

## 实施顺序

依赖优先（修正后）：P8 → P1 → P2 → P9 → P3 → P4 → P5 → P6 → P7

**理由**：P8（ir.py 拆分）应最先执行，避免 P1/P2 的改动在 P8 中需要二次调整。

---

## P1: PackageIR 拆分

### 目标

将 PackageIR 的 29 个字段按领域分组，减少认知负担。

### 新结构

```python
@dataclass
class PackageIR:
    """顶层 IR 结构（重组后）。"""
    header: PackageHeaderIR
    name_map: tuple[str, ...]
    imports: list[ImportIR]
    exports: list[ExportIR]
    linker: LinkerSummaryIR | None
    blueprint: BlueprintIR | None = None
    animation: AnimationDataIR | None = None
    diagnostics: list[OffsetRangeDiagnostic] = field(default_factory=list)
    dependencies: PackageDependenciesIR | None = None
    diagnostics_data: DiagnosticsDataIR | None = None
    debug: DebugIR | None = None

@dataclass
class AnimationDataIR:
    """动画数据聚合。"""
    anim_blueprint: AnimBlueprintIR | None = None
    anim_sequence: AnimSequenceIR | None = None
    anim_montage: AnimMontageIR | None = None

@dataclass
class PackageDependenciesIR:
    """包依赖数据。"""
    resolved_parent_assets: list[dict] = field(default_factory=list)
    inherited_blueprint_graphs: list[dict] = field(default_factory=list)
    depends_map: list[list[int]] = field(default_factory=list)
    resolved_depends_map: list[list[dict]] = field(default_factory=list)
    soft_object_paths: list[dict] = field(default_factory=list)
    soft_package_references: list[str] = field(default_factory=list)
    asset_registry_data_offset: int = 0
    asset_registry_data: dict | None = None

@dataclass
class DiagnosticsDataIR:
    """诊断和状态数据。"""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    status: str = "success"
    status_message: str | None = None
    status_code: str | None = None
```

### 影响范围

- `src/uasset_read/models/ir.py` — PackageIR 定义
- `src/uasset_read/ir_builder.py` — PackageIR 构建
- `src/uasset_read/renderers/json_renderer.py` — 渲染逻辑
- `src/uasset_read/renderers/markdown_renderer.py` — 渲染逻辑（直接访问 `ir.anim_blueprint`、`ir.anim_sequence`、`ir.anim_montage`）
- `tests/` — 相关测试用例

---

## P2: dict → dataclass

### 目标

为高频 dict 字段定义专用 dataclass，提升类型安全。

### 修正说明

**ImportIR 已存在**：`ImportIR` 在 `ir.py:251-259` 已定义，`ir_builder.py` 的 `_build_imports()` 已返回 `list[ImportIR]`。当前 `PackageIR.imports: list[dict]` 类型注解是 **bug**，需修正为 `list[ImportIR]`。

### 新增 dataclass

```python
@dataclass
class FunctionGraphIR:
    """函数图数据（基于 _build_function_graphs_safe() 实际字段）。"""
    function_name: str
    graph_source: str = ""
    entry_node_guid: str = ""
    signature: dict = field(default_factory=dict)
    execution_flows: list[dict] = field(default_factory=list)
    fallback_reason: str | None = None

@dataclass
class ResolvedDependIR:
    """已解析的依赖关系。"""
    asset_path: str
    export_index: int
    dependency_type: str | None = None

@dataclass
class ExportTransformsIR:
    """Export 变换数据（原 diagnostics 字段，实际内容是 transforms）。"""
    transforms: dict = field(default_factory=dict)

@dataclass
class BulkDataIR:
    """批量数据。"""
    data_type: str
    data: bytes | None = None
    offset: int = 0
    size: int = 0
```

### 替换映射

- `PackageIR.imports: list[dict]` → `list[ImportIR]`（修正类型注解 bug）
- `PackageIR.function_graphs: list[dict]` → `list[FunctionGraphIR]`
- `PackageIR.resolved_parent_assets: list[dict]` → `list[dict]`（保持，数据结构简单）
- `PackageIR.inherited_blueprint_graphs: list[dict]` → `list[dict]`（保持）
- `PackageIR.logic_sources: list[dict]` → `list[dict]`（保持）
- `PackageIR.soft_object_paths: list[dict]` → `list[dict]`（保持）
- `PackageIR.resolved_depends_map: list[list[dict]]` → `list[list[ResolvedDependIR]]`
- `ExportIR.diagnostics: dict` → `ExportTransformsIR`
- `ExportIR.bulk_data: dict` → `BulkDataIR`
- `ExportIR.asset_type_data: dict` → `AssetTypeDataIR`（新增，结构待确认）

### 影响范围

- `src/uasset_read/models/ir.py` — 新增 dataclass 定义
- `src/uasset_read/ir_builder.py` — 构建逻辑
- `src/uasset_read/renderers/` — 渲染逻辑

---

## P8: ir.py 拆分

### 目标

将动画 IR 模型拆分到独立文件，保持 ir.py 简洁。

### 新文件结构

```
src/uasset_read/models/
├── ir.py          # 核心 IR 模型（PackageIR、ExportIR、BlueprintIR 等）
├── ir_anim.py     # 动画 IR 模型（8 个类型）
└── __init__.py    # 统一导出
```

### 动画模型完整列表（ir_anim.py）

- `AnimNotifyIR` — FAnimNotifyEvent
- `BakedExitTransitionIR` — FBakedStateExitTransition
- `BakedStateIR` — FBakedAnimationState
- `BakedTransitionIR` — FAnimationTransitionBetweenStates
- `BakedStateMachineIR` — FBakedAnimationStateMachine
- `AnimBlueprintIR` — 动画蓝图顶层结构
- `AnimSequenceIR` — 动画序列
- `AnimMontageIR` — 动画蒙太奇

### 导出策略

```python
# ir.py 导出核心模型
from .ir import PackageIR, ExportIR, BlueprintIR, ...

# ir_anim.py 导出动画模型
from .ir_anim import AnimNotifyIR, BakedExitTransitionIR, ...

# __init__.py 统一导出
from .ir import *
from .ir_anim import *
```

### 影响范围

- `src/uasset_read/models/ir.py` — 移除动画模型
- `src/uasset_read/models/ir_anim.py` — 新增动画模型
- `src/uasset_read/models/__init__.py` — 更新导出

---

## P9: ExportParseStatus 枚举同步

### 目标

让枚举自动生成状态集合，消除手动同步需求。

### 修正说明

**模块归属问题**：`ExportParseStatus` 定义在 `models/fallback.py`，`PARTIAL_STATUSES`/`FAILED_STATUSES` 定义在 `models/status.py`。为避免循环依赖，建议：

- 枚举定义保留在 `fallback.py`
- 属性方法直接在枚举类上定义
- 集合由枚举自动生成，保留在 `status.py`（延迟导入）

### 新设计

```python
# fallback.py
class ExportParseStatus(Enum):
    """Export 解析状态。"""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    # ... 其他状态
    
    @property
    def is_partial(self) -> bool:
        return self.value.startswith("partial")
    
    @property
    def is_failed(self) -> bool:
        return self.value.startswith("failed")

# status.py（延迟导入，避免循环依赖）
from .fallback import ExportParseStatus

PARTIAL_STATUSES = frozenset(s for s in ExportParseStatus if s.is_partial)
FAILED_STATUSES = frozenset(s for s in ExportParseStatus if s.is_failed)
```

### 优势

- 添加新状态只需在枚举中定义
- 属性方法基于命名规则自动判断
- 保留在 status.py 的集合仍可直接使用

### 影响范围

- `src/uasset_read/models/fallback.py` — ExportParseStatus 定义
- `src/uasset_read/models/status.py` — 状态集合（延迟导入）

---

## P3: ExportIR 字段重复

### 目标

消除 ExportIR 和 ExportRawIR 之间的字段重复。

### 设计方案

- 移除 ExportIR 中重复的 9 个字段
- 通过 `ue_export_raw` 引用访问原始数据
- 添加 `@property` 代理，保持向后兼容

```python
@dataclass
class ExportIR:
    """Export IR（重组后）。"""
    # ... 核心字段 ...
    ue_export_raw: ExportRawIR | None = None
    
    @property
    def object_flags(self) -> int:
        return self.ue_export_raw.object_flags if self.ue_export_raw else 0
    
    @property
    def template_index(self) -> int:
        return self.ue_export_raw.template_index if self.ue_export_raw else 0
    
    # ... 其他代理属性 ...
```

### 影响范围

- `src/uasset_read/models/ir.py` — ExportIR 定义
- `src/uasset_read/ir_builder.py` — 构建逻辑

---

## P4: 渲染器过滤逻辑重复

### 目标

提取公共过滤逻辑到 base.py。

### 修正说明

**常量已在 base.py 定义**：`EDITOR_PROPERTY_NAMES`、`EDITOR_VARIABLE_NAMES`、`EDITOR_NODE_CLASSES` 和 `is_blueprint_export()` 函数已在 `base.py` 中定义，两个渲染器都在 import 它们。重复的是过滤的**调用模式**（if/else 判断），不是常量定义本身。

### 设计方案

```python
# base.py
class RendererBase(ABC):
    """渲染器基类。"""
    
    @staticmethod
    def filter_editor_items(
        items: list,
        class_field: str = "object_class",
        exclude_classes: frozenset = EDITOR_NODE_CLASSES
    ) -> list:
        """过滤编辑器专用项。"""
        return [item for item in items if getattr(item, class_field, None) not in exclude_classes]
    
    @staticmethod
    def filter_variables(
        variables: list,
        exclude_patterns: tuple = ("DefaultSceneRoot", "Self")
    ) -> list:
        """过滤内置变量。"""
        return [v for v in variables if not any(p in v.name for p in exclude_patterns)]
```

### 影响范围

- `src/uasset_read/renderers/base.py` — 新增过滤方法
- `src/uasset_read/renderers/json_renderer.py` — 使用公共过滤
- `src/uasset_read/renderers/markdown_renderer.py` — 使用公共过滤

---

## P5: render_to 不在 ABC

### 目标

将 render_to 提升到 ABC 接口。

### 设计方案

```python
# base.py
class IRenderer(ABC):
    """渲染器接口。"""
    
    @abstractmethod
    def render(self, ir: PackageIR, options: dict) -> str:
        """渲染为字符串。"""
        pass
    
    def render_to(self, ir: PackageIR, writer, options: dict) -> None:
        """渲染到文件/流。默认实现写入 render() 结果。
        
        注意：JSONRenderer 覆盖此方法以使用 json.dump() 流式写入，
        性能优于先 render 成字符串再写入。
        """
        writer.write(self.render(ir, options))
```

### 影响范围

- `src/uasset_read/renderers/base.py` — IRenderer 接口
- `src/uasset_read/renderers/json_renderer.py` — render_to 方法

---

## P6: 双重 skip/strategy 系统

### 目标

统一到 CLASS_STRATEGY_TABLE。

### 修正说明

**前缀匹配问题**：`SKIP_CLASS_PREFIXES` 包含 11 个前缀（如 `CubeBuilder`、`GeomModifier_`、`BrushBuilder` 等），而 `CLASS_STRATEGY_TABLE` 是精确名映射，不支持前缀。需要扩展策略表以支持前缀匹配。

### 设计方案

1. 扩展 `CLASS_STRATEGY_TABLE` 支持前缀匹配（使用 `_PREFIX` 后缀标记）
2. 将 `SKIP_CLASS_NAMES` 中的精确名条目迁移到 `CLASS_STRATEGY_TABLE`
3. 将 `SKIP_CLASS_PREFIXES` 中的前缀条目迁移到 `CLASS_STRATEGY_TABLE`
4. 删除 `class_specific_skip.py` 中的冗余定义

```python
# class_serialization_strategy.py
CLASS_STRATEGY_TABLE: dict[str, SerializationStrategy] = {
    # 精确名匹配
    "NiagaraComponent": SerializationStrategy.SKIP,
    "NiagaraSystem": SerializationStrategy.SKIP,
    "EditorUtilityObject": SerializationStrategy.SKIP,
    # ... 其他精确名条目
    
    # 前缀匹配（使用 _PREFIX 后缀标记）
    "CubeBuilder_PREFIX": SerializationStrategy.SKIP,
    "GeomModifier__PREFIX": SerializationStrategy.SKIP,
    "BrushBuilder_PREFIX": SerializationStrategy.SKIP,
    # ... 其他前缀条目
}

def get_serialization_strategy(class_name: str) -> SerializationStrategy | None:
    """获取类的序列化策略（支持精确名和前缀匹配）。"""
    # 精确名匹配
    if class_name in CLASS_STRATEGY_TABLE:
        return CLASS_STRATEGY_TABLE[class_name]
    
    # 前缀匹配
    for key, strategy in CLASS_STRATEGY_TABLE.items():
        if key.endswith("_PREFIX"):
            prefix = key[:-7]  # 移除 _PREFIX 后缀
            if class_name.startswith(prefix):
                return strategy
    
    return None

# class_specific_skip.py（删除或简化）
# 不再维护独立的 SKIP_CLASS_NAMES 和 SKIP_CLASS_PREFIXES
```

### 影响范围

- `src/uasset_read/parsers/class_serialization_strategy.py` — 策略表（扩展支持前缀）
- `src/uasset_read/parsers/class_specific_skip.py` — 删除或简化

---

## P7: parse_uasset.py 职责过重

### 目标

将 parse_uasset.py 拆分为更小的模块。

### 修正说明

**已有拆分**：当前 `parse_uasset.py` 已经将部分逻辑提取到：

- `parse_stages.py` — 阶段执行逻辑
- `parse_post_process.py` — 后处理逻辑

设计应基于现有拆分状态，而非从零开始。

### 当前文件结构

```
src/uasset_read/
├── parse_uasset.py          # 核心编排（_parse_package_core）+ 轻量解析辅助函数
├── parse_stages.py          # 已有：阶段执行逻辑
├── parse_post_process.py    # 已有：后处理逻辑
└── ...
```

### 新增文件结构

```
src/uasset_read/
├── parse_uasset.py          # 核心编排（_parse_package_core）
├── parse_stages.py          # 已有：阶段执行逻辑
├── parse_post_process.py    # 已有：后处理逻辑
├── parse_utils.py           # 新增：轻量解析辅助函数
│   ├── _apply_lightweight_parse()
│   ├── _build_lightweight_graphs()
│   └── _resolve_parse_params()
├── parse_error_handler.py   # 新增：错误处理
│   └── _handle_parse_error()
└── parse_memory.py          # 新增：内存清理
    └── _cleanup_parse_memory()
```

### parse_uasset.py 保留

- `_parse_package_core()` — 核心编排逻辑
- 公开 API 函数（`parse_uasset()`、`parse_package()` 等）

### 新模块职责

- `parse_utils.py` — 轻量解析相关的辅助函数
- `parse_error_handler.py` — 错误处理和恢复逻辑
- `parse_memory.py` — 内存清理和资源释放

### 影响范围

- `src/uasset_read/parse_uasset.py` — 移除辅助函数
- `src/uasset_read/parse_utils.py` — 新增
- `src/uasset_read/parse_error_handler.py` — 新增
- `src/uasset_read/parse_memory.py` — 新增
- `src/uasset_read/parse_stages.py` — 已有，无需修改
- `src/uasset_read/parse_post_process.py` — 已有，无需修改

---

## 验证计划

### 单元测试

- 为新增的 dataclass 编写构造和访问测试
- 为过滤函数编写边界条件测试
- 为枚举属性编写同步测试

### 集成测试

- 运行现有测试套件，确保无回归
- 测试 JSON 和 Markdown 渲染器输出一致性

### 兼容性测试

- 验证向后兼容性（属性访问、导入路径）
- 测试与现有代码的集成

---

## 风险与缓解

| 风险 | 影响 | 缓解措施 |
| ------ | ------ | ---------- |
| 渲染器输出格式变化 | 高 | 逐字段对比测试 |
| 性能回归 | 中 | 基准测试对比 |
| 测试覆盖不足 | 中 | 补充边界条件测试 |

---

## 总结

本次重构将显著提升 IR 模型层和渲染器的可维护性：

- PackageIR 从 29 字段重组为领域组
- 修正 ImportIR 类型注解 bug
- 高频 dict 字段替换为类型安全的 dataclass（含 5 个遗漏字段）
- 动画 IR 模型（8 个类型）独立到专用文件
- 消除重复代码和双重系统（含前缀匹配支持）
- parse_uasset.py 基于现有拆分状态优化
- ExportParseStatus 枚举同步避免循环依赖

所有改进遵循渐进式原则，保持向后兼容性。
