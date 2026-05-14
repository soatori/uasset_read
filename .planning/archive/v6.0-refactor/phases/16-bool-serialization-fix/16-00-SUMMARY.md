---
phase: 16-bool-serialization-fix
plan: 00
type: phase-summary
subsystem: uasset_read
tags: [bugfix, bool-serialization, ue5-compatibility]
key-files:
  created: []
  modified:
    - path: uasset_read.py
      change: "FArchive.read_bool() + 16 bool field fixes"
metrics:
  bool_fields_fixed: 16
  export_map_fixed: 7
  import_map_fixed: 1
  blueprint_graph_fixed: 8
  ue57_exports_parsed: 69
---

# Phase 16: Bool 序列化修复 — SUMMARY

## 完成状态

**Status:** ✓ Complete
**Date:** 2026-05-03
**Commit:** 5225cda

## 修复内容

### 问题根因

UE bool 序列化使用 4-byte uint32（自 UE3 开始的标准），解析器错误使用 1-byte read_u8()，导致：
- ExportMap 条目大小计算错误（少读 21 bytes/条目）
- SerialOffset 出现无效负值
- UE 5.7 资产解析完全失败

### 修复方案

1. **FArchive.read_bool() 方法**
   - 新增方法：`return self.read_u32() != 0`
   - UE 源码参考：Archive.h line 1535

2. **16 个 bool 字段替换**
   - ExportMap: 7 个 (b_forced_export, b_not_for_client, etc.)
   - ImportMap: 1 个 (b_import_optional)
   - Blueprint Graph: 8 个 (FEdGraphPinType 4 + 其他 4)

## 验证结果

### UE 5.7 资产测试

**资产:** BP_FirstPersonCharacter.uasset
**文件大小:** 138,384 bytes

| 验证项 | 结果 |
|--------|------|
| 解析状态 | ✓ 成功 |
| Exports 解析 | 69 个 ✓ |
| 偏移范围 | 0-137,775 (有效) ✓ |
| 无错误 | ✓ |

### 偏移验证（与 RESEARCH.md 一致）

| Export | 对象名 | SerialOffset | 状态 |
|--------|--------|--------------|------|
| 0 | Arrow | 74868 | ✓ 有效 |
| 1 | BP_FirstPersonCharacter | 74914 | ✓ 有效 |
| 2 | BP_FirstPersonCharacter_C | 76929 | ✓ 有效 |
| 3 | Default__BP_FirstPersonCharacter_C | 77746 | ✓ 有效 |

## 代码变更

```diff
# FArchive 新增方法
+ def read_bool(self) -> bool:
+     return self.read_u32() != 0

# ExportMap 替换 (7 处)
- b_forced_export = bool(archive.read_u8())
+ b_forced_export = archive.read_bool()

# ImportMap 替换 (1 处)
- b_import_optional = bool(archive.read_u8())
+ b_import_optional = archive.read_bool()

# Blueprint Graph 替换 (8 处)
- pin_type.is_reference = archive.read_u8() != 0
+ pin_type.is_reference = archive.read_bool()
```

## Self-Check

- [x] 所有 16 个 bool 字段使用 read_bool()
- [x] grep -c "bool(archive.read_u8())" 返回 0
- [x] grep -c "archive.read_u8() != 0" 返回 0
- [x] UE 5.7 资产解析返回 exports (69 个)
- [x] 所有 serial_offset 在有效范围内
- [x] Python 语法检查通过

## Deviations

None — 所有修复按计划执行。

---

*Phase 16 complete: 2026-05-03*