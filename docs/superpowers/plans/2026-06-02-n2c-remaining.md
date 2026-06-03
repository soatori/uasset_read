# N2C 模块剩余问题修复计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) 或 superpowers:executing-plans 执行此计划。

**Goal:** 消除 N2C 模块的全局可变状态（单例模式），并补充核心节点处理器覆盖。

**Architecture:** 两个独立 Task，每个可单独测试和提交。采用依赖注入模式替代全局单例，新增处理器覆盖最常用的 30 种节点类型。

**Tech Stack:** Python 3.10+, pytest

**全局约束:**
- 测试命令: `python -m pytest tests/ -v --tb=short -W ignore::DeprecationWarning`
- 不修改公共 API 的运行时行为
- 临时文件放在 `temp/` 目录

---

## 剩余问题分析

### n2c-singleton: 全局可变状态改为依赖注入

当前状态：
- `N2CProcessorRegistry.get_instance()` — 单例 + `reset()` 测试隔离
- `N2CNodeTypeRegistry.get_instance()` — 单例 + `reset()` 测试隔离
- 两处全局 `_instance` 变量 + `reset()` 方法

问题：
- 测试顺序敏感（依赖全局状态）
- 并发不安全（多线程环境竞争）
- 导入时触发隐式状态

方案：
- 删除 `_instance` 和 `reset()` 方法
- 改为函数式 API：`get_processor_registry()` 和 `get_type_registry()` 返回模块级实例
- 调用方通过参数传入 registry 而非直接获取单例

### n2c-processor-coverage: 补充处理器覆盖

当前状态：
- 126 种 `N2CNodeType` 枚举值
- ~20 种有专用处理器（call_function, cast, comment, delegate, enhanced_input, event, fallback, flow_control, function_entry, variable, widget）
- ~100+ 种走 Fallback 处理器

需要补充覆盖的最常用类型（Phase 69 已标记为"已用"）：
- `Sequence`, `Branch`, `SwitchInt`, `SwitchString`, `SwitchEnum`
- `VariableGet`, `VariableSet`
- `DynamicCast`, `ClassDynamicCast`
- `MakeStruct`, `BreakStruct`, `MakeArray`, `MakeMap`, `MakeSet`
- `AsyncAction`, `Timeline`, `FormatText`, `MathExpression`
- `AddDelegate`, `CreateDelegate`, `ClearDelegate`
- `ForEachElementInEnum`, `ForEachLoop`, `ForEachLoopWithBreak`

---

## Task 1: N2C 单例模式改为依赖注入

**Files:**
- Modify: `src/uasset_read/n2c/processor_registry.py`
- Modify: `src/uasset_read/n2c/type_registry.py`
- Modify: `src/uasset_read/n2c/__init__.py`
- Modify: `src/uasset_read/n2c/serializer.py`（调用方）
- Modify: `src/uasset_read/n2c/processors/*.py`（调用方）

### Step 1: 修改 processor_registry.py

读取 `src/uasset_read/n2c/processor_registry.py`。

将 `N2CProcessorRegistry` 改为非单例：

```python
class N2CProcessorRegistry:
    """节点处理器注册表。

    负责注册、查找和调度 N2CNodeProcessor 实例。
    支持设置 fallback 处理器处理未知类型。
    """

    def __init__(self) -> None:
        self._processors: Dict[N2CNodeType, N2CNodeProcessor] = {}
        self._fallback: Optional[N2CNodeProcessor] = None

    def register(self, node_type: N2CNodeType, processor: N2CNodeProcessor) -> None:
        self._processors[node_type] = processor

    def set_fallback(self, processor: N2CNodeProcessor) -> None:
        self._fallback = processor

    def get(self, node_type: N2CNodeType) -> Optional[N2CNodeProcessor]:
        return self._processors.get(node_type)

    def get_or_fallback(self, node_type: N2CNodeType) -> N2CNodeProcessor:
        p = self._processors.get(node_type)
        if p is None and self._fallback is None:
            raise ValueError(f"No processor for {node_type} and no fallback set")
        return p or self._fallback

    def has(self, node_type: N2CNodeType) -> bool:
        return node_type in self._processors
```

删除 `_instance`、`get_instance()`、`reset()` 方法。

在模块底部创建全局实例：

```python
# 模块级实例（向后兼容，调用方无需修改）
_default_registry: Optional[N2CProcessorRegistry] = None


def get_registry() -> N2CProcessorRegistry:
    """获取默认处理器注册表（懒初始化）。"""
    global _default_registry
    if _default_registry is None:
        _default_registry = N2CProcessorRegistry()
        _register_default_processors(_default_registry)
    return _default_registry


def _register_default_processors(registry: N2CProcessorRegistry) -> None:
    """注册所有默认处理器。"""
    from uasset_read.n2c.processors import call_function, cast, comment, delegate, ...
    registry.register(N2CNodeType.CallFunction, call_function.CallFunctionProcessor())
    registry.register(N2CNodeType.DynamicCast, cast.CastProcessor())
    # ... 其他处理器
```

### Step 2: 修改 type_registry.py

同样将 `N2CNodeTypeRegistry` 改为非单例，添加模块级实例：

```python
_default_type_registry: Optional[N2CNodeTypeRegistry] = None


def get_type_registry() -> N2CNodeTypeRegistry:
    """获取默认类型注册表（懒初始化）。"""
    global _default_type_registry
    if _default_type_registry is None:
        _default_type_registry = N2CNodeTypeRegistry()
    return _default_type_registry
```

### Step 3: 更新 __init__.py

在 `n2c/__init__.py` 中导出新的 API：

```python
from uasset_read.n2c.processor_registry import get_registry as get_processor_registry
from uasset_read.n2c.type_registry import get_type_registry
```

保留旧的 `N2CProcessorRegistry.get_instance()` 别名（向后兼容）：

```python
# 向后兼容：旧 API 别名
def _get_instance_compat():
    return get_processor_registry()
```

### Step 4: 更新调用方

搜索代码库中所有 `N2CProcessorRegistry.get_instance()` 和 `N2CNodeTypeRegistry.get_instance()` 调用，替换为 `get_registry()` 和 `get_type_registry()`。

### Step 5: 测试 + 提交

```bash
python -m pytest tests/ -v --tb=short -x -W ignore::DeprecationWarning
git add -A && git commit -m "refactor: N2C 单例模式改为依赖注入

- 删除 N2CProcessorRegistry._instance/reset()
- 删除 N2CNodeTypeRegistry._instance/reset()
- 新增 get_registry() 和 get_type_registry() 模块级函数
- 更新所有调用方
- 测试通过"
```

---

## Task 2: 补充核心节点处理器

**Files:**
- Create: `src/uasset_read/n2c/processors/flow_control.py`（扩展）
- Create: `src/uasset_read/n2c/processors/struct_ops.py`
- Create: `src/uasset_read/n2c/processors/variable_ops.py`
- Modify: `src/uasset_read/n2c/processors/__init__.py`
- Modify: `src/uasset_read/n2c/processor_registry.py`（注册新处理器）

### 补充的处理器

按优先级分组：

**Group 1: 控制流（扩展已有 flow_control.py）**
- `Sequence` — 执行序列
- `Branch` — 条件分支
- `SwitchInt/SwitchString/SwitchEnum` — 切换
- `ForEachLoop/ForEachLoopWithBreak` — 循环

**Group 2: 结构体操作（新建 struct_ops.py）**
- `MakeStruct/BreakStruct` — 结构体创建/解构
- `MakeArray/MakeMap/MakeSet` — 容器创建
- `DynamicCast/ClassDynamicCast` — 类型转换

**Group 3: 变量操作（新建 variable_ops.py）**
- `VariableGet` — 变量读取
- `VariableSet` — 变量写入
- `AddDelegate/CreateDelegate/ClearDelegate` — 委托操作

### Step 1: 扩展 flow_control.py

读取 `src/uasset_read/n2c/processors/flow_control.py`，添加 Sequence、Branch、Switch* 处理器。

### Step 2: 创建 struct_ops.py

为 MakeStruct/BreakStruct/MakeArray/MakeMap/MakeSet 实现简单处理器。

### Step 3: 创建 variable_ops.py

为 VariableGet/VariableSet 和委托操作实现处理器。

### Step 4: 注册到 registry

在 `_register_default_processors` 中注册新处理器。

### Step 5: 测试 + 提交

```bash
python -m pytest tests/ -v --tb=short -x -W ignore::DeprecationWarning
git add -A && git commit -m "feat: 补充 N2C 核心节点处理器（30 种类型覆盖）

- 扩展 flow_control: Sequence, Branch, Switch*, ForEachLoop
- 新增 struct_ops: MakeStruct, BreakStruct, MakeArray/Map/Set, DynamicCast
- 新增 variable_ops: VariableGet, VariableSet, 委托操作
- 处理器覆盖从 ~20 种提升到 ~50 种
- 测试通过"
```

---

## 计划自审

### 规格覆盖

| 问题 ID | Task | 状态 |
|---------|------|------|
| n2c-singleton | Task 1 | ✅ |
| n2c-processor-coverage | Task 2 | ✅ |

### 风险评估

- **Task 1**（依赖注入）风险中等，需要更新所有调用方但不改变语义
- **Task 2**（新增处理器）风险低，纯新增代码不影响现有处理器

### 完成后的状态

0.3.7-dev + 0.4.0 将覆盖原始 50 个审查问题中的 **全部 50 个**（50/50, 100%）。
