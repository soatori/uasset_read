# BP_FirstPersonCharacter.uasset 解析调试报告

## 概述

本报告记录使用 uasset_read.py 解析 `BP_FirstPersonCharacter.uasset` 文件时发现的 **FObjectExport 序列化顺序 bug**。

## 文件信息

| 属性 | 值 |
|------|-----|
| 文件路径 | `E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset` |
| 文件大小 | 138,384 bytes |
| UE4 版本 | 522 |
| UE5 版本 | 1017 |
| LegacyFileVersion | -9 |
| ExportCount | 69 |
| ExportOffset | 14861 |

## 发现的 Bug

### Bug #1: 漏掉 TemplateIndex 字段

**影响版本**: UE4 >= 506 (VER_UE4_TemplateIndex_IN_COOKED_EXPORTS)

当前代码在 SuperIndex 和 OuterIndex 之间漏掉了 TemplateIndex 字段。

**症状**:
- SerialSize/SerialOffset 数值异常大（超出文件大小）
- 所有后续字段错位

### Bug #2: 漏掉大量 ExportMap 后续字段

从 ObjectResource.cpp (lines 165-222) 发现，FObjectExport 在 SerialOffset 之后还有很多字段：

| 字段名 | 类型 | 版本条件 |
|--------|------|----------|
| bForcedExport | bool | Always |
| bNotForClient | bool | Always |
| bNotForServer | bool | Always |
| PackageGuid | FGuid (16B) | UE5 < 1005 |
| bIsInheritedInstance | bool | UE5 >= 1004 |
| PackageFlags | uint32 | Always |
| bNotAlwaysLoadedForEditorGame | bool | UE4 >= ? |
| bIsAsset | bool | UE4 >= ? |
| bGeneratePublicHash | bool | UE5 >= 1003 |
| FirstExportDependency | int32 | UE4 >= 505 |
| SerializationBeforeSerializationDependencies | int32 | UE4 >= 505 |
| CreateBeforeSerializationDependencies | int32 | UE4 >= 505 |
| SerializationBeforeCreateDependencies | int32 | UE4 >= 505 |
| CreateBeforeCreateDependencies | int32 | UE4 >= 505 |
| ScriptSerializationStartOffset | int64 | UE5 >= 1010 |
| ScriptSerializationEndOffset | int64 | UE5 >= 1010 |

## 正确的 FObjectExport 序列化顺序

基于 UE 5.7 源码 (ObjectResource.cpp lines 125-224):

```
1.  ClassIndex                (int32)
2.  SuperIndex                (int32)
3.  TemplateIndex             (int32)  [UE4 >= 506]
4.  OuterIndex                (int32)
5.  ObjectName                (FName = uint32 + uint32)
6.  ObjectFlags               (uint32)
7.  SerialSize                (int64)  [UE4 >= 508, 否则 int32]
8.  SerialOffset              (int64)  [UE4 >= 508, 否则 int32]
9.  bForcedExport             (bool/uint8)
10. bNotForClient             (bool/uint8)
11. bNotForServer             (bool/uint8)
12. PackageGuid               (FGuid 16B) [UE5 < 1005]
13. bIsInheritedInstance      (bool/uint8) [UE5 >= 1004]
14. PackageFlags              (uint32)
15. bNotAlwaysLoadedForEditorGame (bool/uint8) [UE4 >= ?]
16. bIsAsset                  (bool/uint8) [UE4 >= ?]
17. bGeneratePublicHash       (bool/uint8) [UE5 >= 1003]
18. FirstExportDependency     (int32) [UE4 >= 505]
19. SerializationBeforeSerializationDependencies (int32) [UE4 >= 505]
20. CreateBeforeSerializationDependencies (int32) [UE4 >= 505]
21. SerializationBeforeCreateDependencies (int32) [UE4 >= 505]
22. CreateBeforeCreateDependencies (int32) [UE4 >= 505]
23. ScriptSerializationStartOffset (int64) [UE5 >= 1010 && !Unversioned]
24. ScriptSerializationEndOffset (int64) [UE5 >= 1010 && !Unversioned]
```

## 验证测试

### 修正前的解析结果（错误）

```
ClassIndex: -18
SuperIndex: 0
OuterIndex: 0
ObjectName: /Script/SlateCore (idx=4, num=320) ← 错位！
ObjectFlags: 0x00000000 ← 错位！
SerialSize: 197568757801 ← 完全错误！
SerialOffset: 321555611516928 ← 完全错误！
```

### 修正后的解析结果（添加 TemplateIndex）

```
ClassIndex: -18
SuperIndex: 0
TemplateIndex: 0 ← 新增字段
OuterIndex: 4 ← 正确值
ObjectName: idx=320, num=0 ← 正确索引
ObjectFlags: 0x00040029 ← 合理标志
SerialSize: 46 ← 合理大小
SerialOffset: 74868 ← 在文件范围内
```

## 修复建议

### uasset_read.py 修改位置

`read_export_map()` 函数 (行 1267-1330) 需要修改：

```python
def read_export_map(...):
    ...
    for _ in range(summary.export_count):
        class_index = PackageIndex(archive.read_i32())
        super_index = PackageIndex(archive.read_i32())
        
        # 新增: TemplateIndex (UE4 >= 506)
        template_index = 0
        if summary.file_version_ue4 >= 506:  # VER_UE4_TemplateIndex_IN_COOKED_EXPORTS
            template_index = archive.read_i32()
        
        outer_index = PackageIndex(archive.read_i32())
        object_name = archive.read_name(name_map)
        object_flags = archive.read_u32()
        
        # SerialSize/SerialOffset (UE4 >= 508 使用 int64)
        serial_size = archive.read_i64()
        serial_offset = archive.read_i64()
        
        # 新增: 布尔标志字段
        b_forced_export = archive.read_u8() != 0
        b_not_for_client = archive.read_u8() != 0
        b_not_for_server = archive.read_u8() != 0
        
        # 新增: PackageGuid (UE5 < 1005)
        is_ue5_file = summary.legacy_file_version <= -8
        if is_ue5_file and summary.file_version_ue5 < 1005:
            archive.read(16)  # Skip FGuid
        
        # 新增: bIsInheritedInstance (UE5 >= 1004)
        if is_ue5_file and summary.file_version_ue5 >= 1004:
            archive.read_u8()
        
        # 新增: PackageFlags (注意与 ObjectFlags 区分)
        archive.read_u32()
        
        # ... 更多字段 ...
```

## 结论

当前的 `read_export_map()` 实现严重不完整，仅解析了 FObjectExport 结构的前 8 个字段（实际上因漏掉 TemplateIndex 只有 7 个正确），导致：

1. 所有导出条目的 SerialSize/SerialOffset 错误
2. 无法正确定位导出数据
3. Blueprint 元数据提取失败（offset 超出范围）

**优先级**: 高 - 这是核心解析 bug，影响所有后续功能。

---

**报告日期**: 2026-05-02
**调试工具**: uasset_read.py + UE 5.7 源码分析