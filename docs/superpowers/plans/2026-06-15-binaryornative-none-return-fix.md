# BinaryOrNative Handler None 返回导致数据丢失 修复计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 BinaryOrNative handler 返回 None 时数据丢失问题，并支持 UE5 < 1012 旧格式属性标签。

**Architecture:** 双层防御：(1) handler 层对未知结构体类型返回 raw_data 而非 None；(2) property_parser 层对 handler 返回 None 的情况回退到 raw_data 读取。同时实现 UE5 旧版本（ue5 < 1012）的 PropertyTag 格式支持。

**Tech Stack:** Python 3.10+, UE5 .uasset 二进制格式, UE 源码参考 (PropertyTag.cpp)

**状态:** ✅ 已完成，通过代码审查，待提交

---

## 问题分析

### 根因 1: BinaryOrNative Handler 返回 None 导致数据丢失

**问题描述：**
- `_parse_struct_binary()` 对未知结构体类型（如 `IntPoint`、自定义 Struct）会 `seek(start_pos)` 并返回 `None`
- `property_parser.py` 使用 `return handler(...)` 直接传播 None
- 结果：属性值被完全丢弃，输出中缺失该字段

**影响范围：**
- 所有使用 BinaryOrNative 序列化的 StructProperty
- 典型样本：`T_GridChecker_A.uasset`（UE 5.0.x 资产）

**UE 源码参考：**
- `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\PropertyTag.cpp`
- `operator<<(FArchive&, FPropertyTag&)` 中 BinaryOrNative 处理逻辑

### 根因 2: UE5 < 1012 旧格式 PropertyTag 解析错误

**问题描述：**
- UE 5.3+ (ue5 >= 1012) 使用 `FPropertyTypeName` 树结构
- UE 5.0~5.2 (ue5 < 1012) 使用旧格式：`Type` 为完整 FName（8 字节）
- 解析器始终按新格式读取，导致 UE 5.0.x 资产的属性标签偏移错位

**UE 源码参考：**
- `LoadPropertyTagNoFullType()` (PropertyTag.cpp:195) — 旧格式实现
- `PROPERTY_TAG_COMPLETE_TYPE_NAME = 1012` — 版本阈值

---

## 文件结构

| 文件 | 职责 | 变更类型 |
|---|---|---|
| `src/uasset_read/parsers/binary_or_native_handlers.py` | BinaryOrNative 类型处理器 | 修改 |
| `src/uasset_read/parsers/property_parser.py` | 属性值解析入口 | 修改 |
| `src/uasset_read/serializers/property_tags.py` | PropertyTag 序列化器 | 修改 |
| `src/uasset_read/parse_uasset.py` | 主入口，版本传播 | 修改 |
| `tests/test_binary_or_native_handlers.py` | Handler 测试 | 已有 |
| `tests/test_property_parser_error_handling.py` | 错误处理测试 | 已有 |

---

## 任务

### Task 1: 修复 _parse_struct_binary 未知类型返回 None

**Files:**
- Modify: `src/uasset_read/parsers/binary_or_native_handlers.py:244-252`

- [x] **Step 1: 修改 else 分支，返回 raw_data 而非 None**

原代码：
```python
else:
    # 未知结构体类型，保留原始字节（不含 raw_data 以避免 hex 泄漏）
    archive.seek(start_pos)
    return None
```

修改为：
```python
else:
    # 未知结构体类型 — 返回 raw bytes 供下游保留，避免丢失数据
    return {
        "kind": "binary_or_native_property",
        "type": tag.type,
        "size": size,
        "raw_data": raw,
        "struct_type": struct_type,
    }
```

- [x] **Step 2: 验证测试通过**

Run: `python -m pytest tests/test_binary_or_native_handlers.py -v`
Expected: PASS

---

### Task 2: 修复 property_parser.py handler 返回 None 传播

**Files:**
- Modify: `src/uasset_read/parsers/property_parser.py:184-199`

- [x] **Step 1: 检查 handler 返回值，None 时回退到 raw_data**

原代码：
```python
handler = BINARY_OR_NATIVE_HANDLERS.get(tag.type)
if handler is not None:
    try:
        return handler(tag, archive, name_map, export_map, summary)
    except Exception as e:
        logger.warning("BinaryOrNative handler failed for %s: %s", tag.type, e)
raw_data = archive.read(tag.size) if tag.size > 0 else b""
```

修改为：
```python
handler = BINARY_OR_NATIVE_HANDLERS.get(tag.type)
if handler is not None:
    try:
        result = handler(tag, archive, name_map, export_map, summary)
        if result is not None:
            return result
        # Handler 返回 None（未知类型/解析失败），继续回退到 raw_data
    except Exception as e:
        logger.warning("BinaryOrNative handler failed for %s: %s", tag.type, e)
raw_data = archive.read(tag.size) if tag.size > 0 else b""
```

- [x] **Step 2: 验证测试通过**

Run: `python -m pytest tests/test_property_parser_error_handling.py -v`
Expected: PASS

---

### Task 3: 实现 UE5 < 1012 旧格式 PropertyTag 解析

**Files:**
- Modify: `src/uasset_read/serializers/property_tags.py`
- Modify: `src/uasset_read/parse_uasset.py`

- [x] **Step 1: 在 parse_uasset.py 中传播 file_version_ue5 到 archive**

在 `parse_package()` 函数中，summary 解析后添加：
```python
archive._file_version_ue5 = result.summary.file_version_ue5
```

位置：约 line 503，在 `result.summary = summary` 之后。

- [x] **Step 2: 修改 _read_property_type_name 支持版本参数**

添加 `file_version_ue5` 参数，对 ue5 < 1012 返回简单 FName：
```python
def _read_property_type_name(
    archive: FArchive,
    name_map: List[str],
    max_nodes: int = MAX_PROPERTY_TYPE_NODES,
    file_version_ue5: int = PROPERTY_TAG_COMPLETE_TYPE_NAME,
) -> PropertyTypeName:
    # UE 5.0.x ~ 5.2: 属性类型名为简单 FName（仅 name index）
    if file_version_ue5 < PROPERTY_TAG_COMPLETE_TYPE_NAME:
        simple_name = archive.read_name(name_map)
        return PropertyTypeName(simple_name)
    # ... 原有新格式逻辑
```

- [x] **Step 3: 实现 _read_property_tag_legacy 函数**

完整实现旧格式 PropertyTag 读取，对应 UE `LoadPropertyTagNoFullType()`：

```python
def _read_property_tag_legacy(
    archive: "FArchive",
    name_map: List[str],
    tag: "PropertyTag",
    tolerant: bool = False,
) -> "PropertyTag":
    """读取 UE5 < 1012 的旧格式属性标签。"""
    # Type: 完整 FName (8 bytes: index + number)
    type_index = archive.read_u32()
    type_number = archive.read_u32()
    if 0 <= type_index < len(name_map):
        base_type = name_map[type_index]
        tag.type = f"{base_type}_{type_number}" if type_number > 0 else base_type
    else:
        tag.type = "None"

    # Size
    tag.size = archive.read_i32()
    archive.validate_size(tag.size, tag.name, tolerant=tolerant)

    # ArrayIndex — 旧格式始终存在
    tag.array_index = archive.read_i32()

    # Type.number == 0 时的额外字段
    if type_number == 0:
        if tag.type == "StructProperty":
            tag.struct_type = archive.read_name(name_map)
            tag.property_guid = archive.read_bytes(16)  # StructGuid
        elif tag.type == "BoolProperty":
            tag.bool_val = 0
        elif tag.type == "ByteProperty":
            enum_name = archive.read_name(name_map)
            if enum_name and enum_name != "None":
                tag.enum_type = enum_name
        elif tag.type == "EnumProperty":
            enum_name = archive.read_name(name_map)
            if enum_name and enum_name != "None":
                tag.enum_type = enum_name
    elif tag.type == "BoolProperty":
        tag.bool_val = 1

    # 旧格式无 Flags 字节
    tag.serialize_type = "Property"
    tag.flags = 0

    # 设置偏移
    tag.value_start_offset = archive.tell()
    if tag.size > 0:
        tag.value_end_offset = tag.value_start_offset + tag.size
    else:
        tag.value_end_offset = tag.value_start_offset

    return tag
```

- [x] **Step 4: 在 read_property_tag 中添加版本分发**

```python
def read_property_tag(archive, name_map, tolerant=False, ...):
    # ...
    tag = PropertyTag(name=archive.read_name(name_map), ...)
    if tag.name == "None":
        return tag

    # 从 archive 获取 UE5 版本号
    file_version_ue5 = getattr(archive, '_file_version_ue5', PROPERTY_TAG_COMPLETE_TYPE_NAME)

    if file_version_ue5 < PROPERTY_TAG_COMPLETE_TYPE_NAME:
        return _read_property_tag_legacy(archive, name_map, tag, tolerant)

    # === UE5 >= 1012: 完整 FPropertyTypeName 格式 ===
    # ... 原有逻辑
```

- [x] **Step 5: 验证测试通过**

Run: `python -m pytest tests/ -v -k "property_tag or binary_or_native"`
Expected: PASS

---

### Task 4: 验证修复效果

- [x] **Step 1: 运行全量单元测试**

Run: `python -m pytest tests/ -v`
Expected: 1384+ tests pass, 0 failures

- [x] **Step 2: 验证 Issue 相关资产**

Run:
```bash
python run.py "E:/Develop/lib/Samples/StarterContent/Materials/M_Brick_Clay_New.uasset"
python run.py "E:/Develop/lib/Samples/StarterContent/Materials/M_DustMote.uasset"
python run.py "E:/Develop/lib/Samples/StarterContent/Materials/M_Mannequin.uasset"
python run.py "E:/Develop/lib/Samples/FirstPerson/Textures/T_GridChecker_A.uasset"
python run.py "E:/Develop/lib/Samples/FirstPerson/Blueprints/NS_Jump_Trail.uasset"
python run.py "E:/Develop/lib/Samples/FirstPerson/Blueprints/MM_Rifle_Jump_Start.uasset"
```
Expected: 所有资产 parse_status = "success"

- [x] **Step 3: 验证随机资产采样**

Run: `python scripts/test_matrix.py random --seed 42 --count 30`
Expected: OK 率 ≥ 60%，partial 率 ≤ 40%，failed = 0

---

## 测试覆盖

已有测试验证修复：

| 测试文件 | 覆盖内容 |
|---|---|
| `tests/test_binary_or_native_handlers.py` | Handler 成功路径 + 边界条件 |
| `tests/test_property_parser_error_handling.py` | Handler 失败回退到 raw_data |
| `tests/test_sample_assets_representative.py` | 样本资产解析验证 |

---

## 提交清单

- [x] 代码修改完成（4 文件，+121/-5 行）
- [x] 单元测试全部通过
- [x] Issue 相关资产验证通过
- [ ] 提交代码（待用户确认）

提交信息建议：
```
fix: BinaryOrNative handler None 返回修复 + UE5 旧格式 PropertyTag 支持

- binary_or_native_handlers: 未知 StructProperty 返回 raw_data 而非 None
- property_parser: handler 返回 None 时回退到 raw_data 读取
- property_tags: 实现 ue5 < 1012 旧格式 PropertyTag 解析 (LoadPropertyTagNoFullType)
- parse_uasset: 传播 file_version_ue5 到 archive 供序列化器使用

Fixes #144, #145, #146, #156, #157, #158, #161, #162, #163
```

---

## 剩余问题（非本次修复范围）

随机采样中仍有 ~25-36% partial 结果，主要来自：

| 资产类型 | 数量 | 根因 | Issue |
|---|---|---|---|
| BakedStaticMeshActor | ~13 | StrProperty UTF-16 长度异常 (1.6GB) | 待调查 |
| StaticMeshComponent | ~2 | StaticMeshDerivedDataKey size 超限 | 待调查 |
| MetaSoundSource/Patch | ~3 | MetaSound 自定义序列化格式 | 待调查 |
| BlendSpace/BodySetup | ~3 | 各自特有格式问题 | 待调查 |

这些问题独立于 BinaryOrNative 修复，需要单独排查。

---

## 参考

- UE 源码: `E:\Develop\lib\UnrealEngine\Engine\Source\Runtime\CoreUObject\Private\UObject\PropertyTag.cpp`
- `LoadPropertyTagNoFullType()` — 旧格式实现 (line 195)
- `operator<<(FArchive&, FPropertyTag&)` — 版本分发 (line 430)
- `PROPERTY_TAG_COMPLETE_TYPE_NAME = 1012` — 版本阈值常量
