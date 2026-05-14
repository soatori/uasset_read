# Phase 44: 模型增强 — UEdGraphPin linked_to_objects — PLAN.md

**Phase:** 044-model-enhancement
**Milestone:** v7.0 (UE 对象图重建)
**Estimated time:** ~0.5h
**Dependencies:** Phase 41-43 completed ✓

---

## 概述

本阶段在 `UEdGraphPin` 数据模型中添加 `linked_to_objects` 字段，将连接引用从原始 dict 名称升级为 `UObjectInstance` 实际对象引用。当 linker 可用时，调用者可以直接通过引脚连接获得目标节点的对象引用，而不需要二次查找。

## 任务分解

### 任务 1: 模型增强 — 添加 linked_to_objects 字段到 UEdGraphPin

**文件:** `src/uasset_read/models/core.py`

**修改点:**

1. 添加条件导入 `UObjectInstance`：
   ```python
   if TYPE_CHECKING:
       from uasset_read.archive import FArchive
       from uasset_read.serializers.package_summary import PackageFileSummary
       from uasset_read.serializers.object_resources import ObjectImport, ObjectExport
       from uasset_read.link.object_instance import UObjectInstance
   ```

2. 在 `UEdGraphPin` dataclass 中添加四个新增字段：
   ```python
   # PIN-04: 连接引用 — 原始 dict（保留兼容）
   linked_to_raw: List[dict] = field(default_factory=list)
   sub_pins: List[dict] = field(default_factory=list)
   parent_pin: Optional[dict] = None
   ref_pass_through: Optional[dict] = None
   # PIN-04+: 连接引用 — 解析后的 UObjectInstance（新增，linker 模式）
   linked_to_objects: List[Optional["UObjectInstance"]] = field(default_factory=list)
   sub_pins_objects: List[Optional["UObjectInstance"]] = field(default_factory=list)
   parent_pin_object: Optional["UObjectInstance"] = None
   ref_pass_through_object: Optional["UObjectInstance"] = None
   ```

**验证:** 类型检查通过，导入正确，无语法错误。

---

### 任务 2: 序列化增强 — 在 graph.py 中添加 linker 解析逻辑

**文件:** `src/uasset_read/serializers/graph.py`

**修改点:**

1. **`read_pin_reference`** — 添加 `linker` 参数，解析 `owning_node_index` 存入 `owning_node_object`:
   ```python
   def read_pin_reference(..., linker: Optional["PackageLinker"] = None) -> Optional[dict]:
       # ... 现有逻辑 ...
       if linker is not None and owning_node_index != 0:
           pkg_idx = PackageIndex(owning_node_index)
           if not pkg_idx.is_null:
               obj_ref = linker.resolve_package_index(pkg_idx)
               if result is not None:
                   result["owning_node_object"] = obj_ref
       return result
   ```

2. **`read_ue_graph_pin`** — 添加 `linker` 参数，从 raw dict 提取对象引用填充到 *objects 字段:
   - 函数签名添加 `linker: Optional["PackageLinker"] = None`
   - 读取 `linked_to` / `sub_pins` / `parent_pin` / `ref_pass_through` 后，遍历提取 `owning_node_object` 到对应的 *objects 字段
   - 构造 `UEdGraphPin` 时传入所有四个新增字段

3. **调用链传递检查** — 确保 `read_ue_graph_node` 调用 `read_ue_graph_pin` 时传递 `linker` 参数
   - 当前已有 `linker` 参数在 `read_ue_graph_node`，只需确认调用时传递

**为什么合并:** 所有修改都在同一个文件，是同一逻辑的连续步骤，不需要拆分。

---

### 任务 3: 验证与测试

**步骤:**

1. 导入测试 — `python -c "from uasset_read import parse_uasset_with_linker; print('Import OK')"`
2. 回归测试 — `python -m pytest tests/ -v` — 所有现有测试必须通过
3. 功能验证 — 创建一个简单的测试脚本验证 `linked_to_objects` 在 linker 模式下被正确填充

---

## 依赖关系图

```
任务 1 (模型增强)
    ↓
任务 2 (序列化增强，全在 graph.py)
    ↓
任务 3 (验证与测试)
```

每个任务依赖前一个任务，顺序执行。

## 风险与应对

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| 循环导入 | 低 | 高 | 使用 `TYPE_CHECKING` 条件导入，不在运行时导入 |
| 遗漏调用点 | 中 | 中 |  grep 搜索 `read_pin_reference` 确保只有一处定义一处调用 |
| 破坏向后兼容 | 低 | 高 | 新增字段都有默认值，不传入 linker 时空数组，不影响现有代码 |
| mypy 错误 | 中 | 中 | 正确使用 Optional["UObjectInstance"] 字符串类型提示 |

## 验收标准

- [x] `UEdGraphPin` 包含 `linked_to_objects` / `sub_pins_objects` / `parent_pin_object` / `ref_pass_through_object` 字段
- [x] 当 linker 传入时，这些字段被正确填充为 `UObjectInstance` 引用
- [x] 当 linker 为 None 时，这些字段为空默认值，不影响现有行为
- [x] 所有现有测试通过（373 passed, 0 failed）
- [x] 没有循环导入，模块可正常导入
- [x] mypy 类型检查通过

---

*Created: 2026-05-15*
