---
phase: 72i
plan: 72i
status: complete
completed: 2026-05-24
---

# Phase 72-I 执行摘要

## 目标

修复 BP_FirstPersonCharacter.uasset 解析中的 12 项错误，合并 Phase 72-H 的 FString 容错 + LinkedTo 恢复 + StructValue JSON 序列化修复。

## 执行波次

### Wave 1: StructValue JSON 递归序列化 + 节点发现 fallback 扩展

- **1A. JSON 递归序列化:** `json_formatter.py` — `serialize_property_value()` 将 dict/list 从 isinstance 检查中分离，递归处理嵌套值。将 hasattr() 替换为 isinstance() 精确匹配 StructValue/MapValue/SetValue/EnumValue/TextValue/DelegateValue。
- **1B. 节点发现 fallback:** `graph.py` — `read_ue_graph()` 的 fallback 条件从 `(nodes_count==0 or len(nodes)==0)` 改为始终执行 (`graph_export_idx>0`)，fallback 结果与主路径通过 `_export_index` 去重合并。

提交: `af51d71`

### Wave 2: FString 容错增强 + LinkedTo 滑动恢复

- **2A. FString 边界防卫:** `archive.py` — `read_fstring()` 入口记录 `pos_before`，读取 length 后检查文件边界，无效 length 时 seek 回入口位置再抛 ParseError。增强内部 null 检测，区分 UTF-16 null 终止符（合法）与 UTF-8 内部 null（异常）。
- **2B. LinkedTo 滑动恢复:** `graph.py` — `read_pin_array()` count 异常时在 ±8 字节范围扫描合法 i32 count (0..20)，验证候选后恢复。`read_ue_graph_pin()` LinkedTo 失败时扫描前方 256 字节寻找 SubPins 起始位置。
- 修复 `test_phase72d_fstring_fname.py` 断言匹配新日志格式。

提交: `acec5d2`

### Wave 3: 级联效果验证 + 剩余修复

- **3D. Comment 字段:** `graph.py` — PropertyTag 循环中显式处理 `bCommentBubbleVisible_InDetailsPanel` (BoolProperty) 和 `CommentDepth` (IntProperty)。
- **3E. Direction 比较:** `variable_extractor.py` — 同时支持 int (0/1) 和 string (EGPD_Input/EGPD_Output) 的 direction 比较。
- **3C. Size 越界安全网:** `property_tags.py` — validate_size 失败时 seek 跳过损坏的 size (最大 64KB) 后再 raise，防止级联指针错位。

提交: `a9826d8`

## 测试结果

```
1368 passed, 123 skipped, 2 xpassed, 0 failed
```

## 修改文件

| 文件 | 变更 |
|------|------|
| `src/uasset_read/formatters/json_formatter.py` | JSON 递归序列化 (Wave 1A) |
| `src/uasset_read/serializers/graph.py` | 节点发现 fallback + LinkedTo 恢复 + Comment 字段 (Wave 1B/2B/3D) |
| `src/uasset_read/archive.py` | FString 边界防卫 (Wave 2A) |
| `src/uasset_read/serializers/property_tags.py` | Size 越界安全网 (Wave 3C) |
| `src/uasset_read/blueprint/variable_extractor.py` | Direction int/string 兼容 (Wave 3E) |
| `tests/test_phase72d_fstring_fname.py` | 日志断言更新 (Wave 2) |

## 自检

- [x] JSON 序列化不抛 TypeError
- [x] FString 异常长度回退指针
- [x] LinkedTo 异常 count 滑动恢复
- [x] Direction 同时支持 int 和 string 比较
- [x] 1368 测试通过，0 失败
- [x] 无回归
