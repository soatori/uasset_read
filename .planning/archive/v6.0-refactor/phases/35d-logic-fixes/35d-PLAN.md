# Phase 35d-PLAN.md

**里程碑**: v6.0 模块化重构 — 代码审查逻辑与质量修复
**创建日期**: 2026-05-13
**依赖**: Phase 35b
**状态**: 计划中
**优先级**: P1 - 高

---

## 目标

修复全量代码审查发现的属性解析 bug、蓝图提取 bug、输出格式问题，共 6 个计划，分 2 个 wave 执行。

---

## 执行波次

| Wave | Plans | 说明 |
|------|-------|------|
| 1 | 35d-01, 35d-02, 35d-03, 35d-05, 35d-06 | 独立修复，可并行 |
| 2 | 35d-04 | 依赖 35d-02（json_formatter.py 字段修复） |

---

## 计划

### 35d-01: property_types.py 属性解析器修复

**文件**: `src/uasset_read/parsers/property_types.py`
**问题**:
1. `parse_array_property:109-112` — 数组 `remaining_size` 未减 4 字节 count 字段（CR-09）
2. `_extract_map_types_from_tag:323` — 嵌套逗号导致类型拆分错误（MED-01）
3. `parse_array_property/parse_map_property/parse_set_property` — 缺少 entry count 验证（HIGH-07）

**修复**:
1. `remaining_size = tag.size - 4`（减 count 字段）
2. `params.split(",", 1)` 仅按第一个逗号拆分
3. 添加 count/num_entries/num_elements 的负数和超限验证

**验收**:
- 数组元素解析正确
- 嵌套逗号类型正确拆分
- 超限计数抛出 ParseError
- 全部测试通过

---

### 35d-02: variable_extractor.py 蓝图变量提取修复

**文件**: `src/uasset_read/blueprint/variable_extractor.py`, `src/uasset_read/models/blueprint.py`, `src/uasset_read/formatters/json_formatter.py`
**问题**:
1. `line 61` — `CPF_Net` 和 `CPF_Replicated` 混淆，`is_replicated` 映射错误（CR-11）
2. `blueprint.py:156` — `metadata` 和 `meta_data` 重复字段（LOW-04）
3. `line 149` — 未检查 `hasattr(prop, "type")`（HIGH-10）

**修复**:
1. `is_replicated` 映射 `CPF_Replicated`，`CPF_Net` 留给 `is_net`
2. 删除 `meta_data` 冗余字段，json_formatter.py 改用 `variable.metadata`
3. 添加 `getattr(prop, 'type', None)` 检查

**验收**:
- 复制标志正确映射
- 蓝图变量无冗余字段，json_formatter 使用 variable.metadata
- prop.type 访问有 hasattr 保护
- 全部测试通过

---

### 35d-03: 模型类修复

**文件**: `src/uasset_read/models/properties.py`
**问题**:
1. `properties.py:45-94` — StructValue/MapValue/SetValue 等子类缺少默认 `property_type`（CR-13）

**修复**:
1. 为每个子类添加默认 `property_type: str = "XXXProperty"`

**验收**:
- 子类不需要手动传 property_type
- 全部测试通过

---

### 35d-04: json_formatter.py MapValue/SetValue 递归序列化 + 其他 formatter 修复

**文件**: `src/uasset_read/formatters/json_formatter.py`, `src/uasset_read/formatters/markdown_formatter.py`, `src/uasset_read/blueprint/transform_parser.py`
**依赖**: 35d-02（json_formatter.py 字段修复必须先完成）
**问题**:
1. `line 163` — MapValue 的 `entries` 未递归调用 `serialize_property_value`（CR-14）
2. `line 168` — SetValue 的 `elements` 未递归调用 `serialize_property_value`（CR-15）
3. `markdown_formatter.py` — 表格单元格未转义 `|` 字符（HIGH-17）
4. `transform_parser.py` — 直接访问字典键，缺失时抛 KeyError（HIGH-09）

**修复**:
```python
# MapValue
"entries": [serialize_property_value(entry, depth + 1, max_depth) for entry in value.entries]
# SetValue
"elements": [serialize_property_value(elem, depth + 1, max_depth) for elem in value.elements]
```
- 添加 `_escape_md_cell()` 转义函数
- 所有字典访问改为 `fields.get("X", 0.0)` 形式

**验收**:
- 嵌套结构在 JSON 输出中正确序列化
- 含 `|` 的资产名不破坏表格
- 缺失字段默认 0.0
- 全部测试通过

---

### 35d-05: flow_builder.py 安全迭代 + node_guid 检查

**文件**: `src/uasset_read/graph/flow_builder.py`
**问题**:
1. `line 204,284,414` — 假定 `linked_to_raw` 总是可迭代，但可能非列表（LOW-06）
2. `line 232` — `current_node.node_guid in visited` 未检查 None（LOW-07）

**修复**:
1. 添加 `_safe_linked_to()` 辅助函数处理 None 和非列表值
2. GUID 为 None 时用 `id(current_node)` 作为 fallback

**验收**:
- 非列表 linked_to_raw 不抛 TypeError
- 无 GUID 节点不抛 TypeError
- 全部测试通过

---

### 35d-06: 代码质量清理

**文件**: `src/uasset_read/constants.py`, `src/uasset_read/parsers/property_parser.py`, `src/uasset_read/parsers/property_types.py`
**问题**:
1. `constants.py:50,85` — `PROPERTY_TAG_COMPLETE_TYPE_NAME` 和 `UE5_PROPERTY_TAG_COMPLETE_TYPE_NAME` 重复定义（MED-14）
2. `property_parser.py:97` — 不可达的 `return None` 死代码（HIGH-08）
3. `property_types.py:445-451` — 重复的 `_derive_node_name` 函数（MED-14）

**修复**:
1. 删除重复定义，保留别名关系
2. 删除死代码
3. 删除 misplaced 函数（保留 flow_builder.py 中的版本）

**验收**:
- 常量只有单一明确定义（或显式别名）
- 无不可达代码
- 无重复函数
- 全部测试通过

---

## 产出文件

- `src/uasset_read/parsers/property_types.py` — 属性解析器修复 + 重复函数删除
- `src/uasset_read/blueprint/variable_extractor.py` — 3 处修改（CR-11, LOW-04, HIGH-10）
- `src/uasset_read/models/blueprint.py` — 删除冗余字段
- `src/uasset_read/models/properties.py` — 6 处默认值添加
- `src/uasset_read/formatters/json_formatter.py` — 2 处修改（递归序列化 + meta_data 修复）
- `src/uasset_read/formatters/markdown_formatter.py` — 转义函数 + N 处调用
- `src/uasset_read/blueprint/transform_parser.py` — 3 处修改
- `src/uasset_read/graph/flow_builder.py` — 安全迭代 + GUID 检查
- `src/uasset_read/constants.py` — 重复常量清理
- `src/uasset_read/parsers/property_parser.py` — 死代码删除

## 测试验证

```bash
python -m pytest tests/ -v
```

**预期**: 无回归，424+ passed, 67 skipped, 0 failed（35b 修复后再验证）
