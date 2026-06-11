# P1 UE 源码审计修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 3 个 P1 优先级的 UE 源码审计发现：版本常量系统性错误 (#94)、版本门控缺失 (#95)、数据模型偏差 (#102)

**Architecture:** 三阶段修复：(1) 修正 constants.py 中的版本常量和 GUID 定义；(2) 补充 FEdGraphPinType/PropertyTag/FText 的版本门控；(3) 修复 FEdGraphPinType 数据模型（补充缺失字段、移除错误字段）

**Tech Stack:** Python 3.10+, dataclasses, UE C++ 源码对照 (ObjectVersion.h, DevObjectVersion.cpp, EdGraphPin.h, Blueprint.h)

---

## 依赖关系图

```
Issue #94 (版本常量) ──┬──→ Issue #95 B.1/B.2 (FEdGraphPinType/PropertyTag 版本门控)
                       │
                       └──→ Issue #95 B.3 (FText 版本门控) ──→ Issue #102 3.4 (FText Category)
                       
Issue #102 3.1-3.3 (数据模型) ── 独立，可与 #94/#95 并行
```

**执行顺序：**
1. Phase 1: #94 (版本常量) — 基础工作
2. Phase 2: #95 B.1/B.2 (FEdGraphPinType/PropertyTag 版本门控) — 依赖 #94
3. Phase 3: #95 B.3 (FText 版本门控) — 依赖 #94
4. Phase 4: #102 (数据模型) — 3.1-3.3 独立，3.4 依赖 #95 B.3

---

## File Structure

### 修改文件

| 文件 | 职责 | 涉及 Issues |
|------|------|-------------|
| `src/uasset_read/constants.py` | 版本常量、GUID 定义 | #94 |
| `src/uasset_read/serializers/graph/pin_types.py` | FEdGraphPinType 序列化 | #95 B.1, #102 |
| `src/uasset_read/serializers/property_tags.py` | PropertyTag 序列化 | #95 B.2 |
| `src/uasset_read/serializers/graph/_common.py` | FText 序列化 | #95 B.3 |
| `src/uasset_read/blueprint/variable_extractor.py` | FBPVariableDescription 读取 | #102 3.4 |
| `src/uasset_read/models/core.py` | FEdGraphPinType 数据模型 | #102 3.1-3.3 |

### 新增文件

| 文件 | 职责 |
|------|------|
| `tests/test_ue_version_constants.py` | 版本常量正确性测试 |
| `tests/test_version_gating.py` | 版本门控行为测试 |
| `tests/test_pin_type_model.py` | FEdGraphPinType 数据模型测试 |

---

## Phase 1: Issue #94 — 版本常量系统性错误

### Task 1: 修正 CustomVersion GUID 定义

**Files:**
- Modify: `src/uasset_read/constants.py:31,168-179`
- Test: `tests/test_ue_version_constants.py`

- [ ] **Step 1: 编写 GUID 正确性测试**

```python
# tests/test_ue_version_constants.py
"""验证 CustomVersion GUID 与 UE 源码一致。"""
import pytest
from uasset_read.constants import (
    FCORE_OBJECT_VERSION_GUID,
    FEDITOR_OBJECT_VERSION_GUID,
    FANIM_OBJECT_VERSION_GUID,
    FPHYSICS_OBJECT_VERSION_GUID,
    FRENDERING_OBJECT_VERSION_GUID,
    FBLUEPRINTS_OBJECT_VERSION_GUID,
    FFRAMEWORK_OBJECT_VERSION_GUID,
    FRELEASE_OBJECT_VERSION_GUID,
    FUE5_MAINSTREAM_VERSION_GUID,
    FUE5RELEASESTREAM_OBJECT_VERSION_GUID,
)


def _parse_guid(guid_str: str) -> tuple:
    """解析 GUID 字符串为 (A, B, C, D) 四元组。"""
    parts = guid_str.split("-")
    a = int(parts[0], 16)
    b = int(parts[1], 16)
    c = int(parts[2], 16)
    d = int(parts[3], 16)
    return (a, b, c, d)


class TestCustomVersionGUIDs:
    """验证 CustomVersion GUID 与 UE DevObjectVersion.cpp 一致。"""
    
    def test_fcore_object_version_guid(self):
        """FCORE_OBJECT_VERSION_GUID: 375EC13C-06E448FB-B50084F0-262A717E"""
        # UE 源码: DevObjectVersion.cpp L26-35
        a, b, c, d = _parse_guid(FCORE_OBJECT_VERSION_GUID)
        assert a == 0x375EC13C
        assert b == 0x06E448FB
        assert c == 0xB50084F0
        assert d == 0x262A717E

    def test_feditor_object_version_guid(self):
        """FEDITOR_OBJECT_VERSION_GUID: E4B068ED-F49442E9-A231DA0B-2E46BB41"""
        a, b, c, d = _parse_guid(FEDITOR_OBJECT_VERSION_GUID)
        assert a == 0xE4B068ED
        assert b == 0xF49442E9
        assert c == 0xA231DA0B
        assert d == 0x2E46BB41

    def test_fblueprints_object_version_guid(self):
        """FBLUEPRINTS_OBJECT_VERSION_GUID: B0D832E4-1F894F0D-ACCF7EB7-36FD4AA2"""
        a, b, c, d = _parse_guid(FBLUEPRINTS_OBJECT_VERSION_GUID)
        assert a == 0xB0D832E4
        assert b == 0x1F894F0D
        assert c == 0xACCF7EB7
        assert d == 0x36FD4AA2

    def test_fframework_object_version_guid(self):
        """FFRAMEWORK_OBJECT_VERSION_GUID: CFFC743F-43B04480-939114DF-171D2073"""
        a, b, c, d = _parse_guid(FFRAMEWORK_OBJECT_VERSION_GUID)
        assert a == 0xCFFC743F
        assert b == 0x43B04480
        assert c == 0x939114DF
        assert d == 0x171D2073

    def test_frelease_object_version_guid(self):
        """FRELEASE_OBJECT_VERSION_GUID: 9C54D522-A8264FBE-94210746-61B482D0"""
        a, b, c, d = _parse_guid(FRELEASE_OBJECT_VERSION_GUID)
        assert a == 0x9C54D522
        assert b == 0xA8264FBE
        assert c == 0x94210746
        assert d == 0x61B482D0

    def test_fue5_mainstream_version_guid(self):
        """FUE5_MAINSTREAM_VERSION_GUID: 697DD581-E64F41AB-AA4A51EC-BEB7B628"""
        a, b, c, d = _parse_guid(FUE5_MAINSTREAM_VERSION_GUID)
        assert a == 0x697DD581
        assert b == 0xE64F41AB
        assert c == 0xAA4A51EC
        assert d == 0xBEB7B628

    def test_fue5releasestream_object_version_guid(self):
        """FUE5RELEASESTREAM_OBJECT_VERSION_GUID: D89B5E42-24BD4D46-8412ACA8-DF641779"""
        a, b, c, d = _parse_guid(FUE5RELEASESTREAM_OBJECT_VERSION_GUID)
        assert a == 0xD89B5E42
        assert b == 0x24BD4D46
        assert c == 0x8412ACA8
        assert d == 0xDF641779
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_ue_version_constants.py -v`
Expected: FAIL — 部分 GUID 值与 UE 源码不一致

- [ ] **Step 3: 修正 constants.py 中的 GUID 定义**

根据 UE 源码 `Engine/Source/Runtime/Core/Private/UObject/DevObjectVersion.cpp` L26-35：

```python
# src/uasset_read/constants.py

# ============================================================================
# CustomVersion GUIDs
# 来源: Engine/Source/Runtime/Core/Private/UObject/DevObjectVersion.cpp
# ============================================================================

# FCoreObjectVersion
FCORE_OBJECT_VERSION_GUID = "375EC13C-06E448FB-B50084F0-262A717E"

# FEditorObjectVersion
FEDITOR_OBJECT_VERSION_GUID = "E4B068ED-F49442E9-A231DA0B-2E46BB41"

# FAnimObjectVersion
FANIM_OBJECT_VERSION_GUID = "AF43A65D-7FD34947-98733E8E-D9C1BB05"

# FPhysicsObjectVersion
FPHYSICS_OBJECT_VERSION_GUID = "78F01B33-EBEA4F98-B9B484EA-CCB95AA2"

# FRenderingObjectVersion
FRENDERING_OBJECT_VERSION_GUID = "12F88B9F-88754AFC-A67CD90C-383ABD29"

# FBlueprintsObjectVersion
FBLUEPRINTS_OBJECT_VERSION_GUID = "B0D832E4-1F894F0D-ACCF7EB7-36FD4AA2"

# FFrameworkObjectVersion
FFRAMEWORK_OBJECT_VERSION_GUID = "CFFC743F-43B04480-939114DF-171D2073"

# FReleaseObjectVersion
FRELEASE_OBJECT_VERSION_GUID = "9C54D522-A8264FBE-94210746-61B482D0"

# FUE5MainStreamObjectVersion
FUE5_MAINSTREAM_VERSION_GUID = "697DD581-E64F41AB-AA4A51EC-BEB7B628"

# FUE5ReleaseStreamObjectVersion
FUE5RELEASESTREAM_OBJECT_VERSION_GUID = "D89B5E42-24BD4D46-8412ACA8-DF641779"
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_ue_version_constants.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/constants.py tests/test_ue_version_constants.py
git commit -m "fix: correct CustomVersion GUIDs to match UE DevObjectVersion.cpp (#94 A.1)"
```

---

### Task 2: 修正 UE4 版本常量值

**Files:**
- Modify: `src/uasset_read/constants.py:131-148`
- Test: `tests/test_ue_version_constants.py`

- [ ] **Step 1: 编写 UE4 版本常量正确性测试**

```python
# tests/test_ue_version_constants.py (追加)

class TestUE4VersionConstants:
    """验证 UE4 版本常量与 UE ObjectVersion.h enum 一致。
    
    来源: Engine/Source/Runtime/Core/Public/UObject/ObjectVersion.h
    enum EUnrealEngineObjectUE4Version {
        VER_UE4_OLDEST_LOADABLE_PACKAGE = 214,
        // ... 依次递增
    };
    """

    def test_ver_ue4_struct_guid_in_property_tag(self):
        """VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG = 446
        
        偏差 -110 是最严重的错误，导致版本 336-445 资产偏移错位。
        """
        from uasset_read.constants import VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG
        assert VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG == 446

    def test_ver_ue4_property_guid_in_property_tag(self):
        """VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG = 508"""
        from uasset_read.constants import VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG
        assert VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG == 508

    def test_ver_ue4_property_tag_set_map_support(self):
        """VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT = 514"""
        from uasset_read.constants import VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT
        assert VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT == 514

    def test_var_ue4_array_property_inner_tags(self):
        """VAR_UE4_ARRAY_PROPERTY_INNER_TAGS = 253"""
        from uasset_read.constants import VAR_UE4_ARRAY_PROPERTY_INNER_TAGS
        assert VAR_UE4_ARRAY_PROPERTY_INNER_TAGS == 253

    def test_ue4_name_hashes_serialized(self):
        """UE4_NAME_HASHES_SERIALIZED = 509"""
        from uasset_read.constants import UE4_NAME_HASHES_SERIALIZED
        assert UE4_NAME_HASHES_SERIALIZED == 509

    def test_ue4_preload_dependencies_in_cooked_exports(self):
        """UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS = 512"""
        from uasset_read.constants import UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS
        assert UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS == 512

    def test_ue4_templateindex_in_cooked_exports(self):
        """UE4_TemplateIndex_IN_COOKED_EXPORTS = 513"""
        from uasset_read.constants import UE4_TemplateIndex_IN_COOKED_EXPORTS
        assert UE4_TemplateIndex_IN_COOKED_EXPORTS == 513

    def test_ue4_64bit_exportmap_serialsizes(self):
        """UE4_64BIT_EXPORTMAP_SERIALSIZES = 516"""
        from uasset_read.constants import UE4_64BIT_EXPORTMAP_SERIALSIZES
        assert UE4_64BIT_EXPORTMAP_SERIALSIZES == 516

    def test_ue4_non_outer_package_import(self):
        """UE4_NON_OUTER_PACKAGE_IMPORT = 525"""
        from uasset_read.constants import UE4_NON_OUTER_PACKAGE_IMPORT
        assert UE4_NON_OUTER_PACKAGE_IMPORT == 525

    def test_ue4_serialize_text_in_packages(self):
        """UE4_SERIALIZE_TEXT_IN_PACKAGES = 464"""
        from uasset_read.constants import UE4_SERIALIZE_TEXT_IN_PACKAGES
        assert UE4_SERIALIZE_TEXT_IN_PACKAGES == 464
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_ue_version_constants.py::TestUE4VersionConstants -v`
Expected: FAIL — 多个常量值与 UE 源码不一致

- [ ] **Step 3: 修正 constants.py 中的 UE4 版本常量**

根据 UE 源码 `ObjectVersion.h` enum（从 VER_UE4_OLDEST_LOADABLE_PACKAGE = 214 开始递增）：

```python
# src/uasset_read/constants.py

# ============================================================================
# UE4 版本常量（对应 EUnrealEngineObjectUE4Version）
# 来源: Engine/Source/Runtime/Core/Public/UObject/ObjectVersion.h
# 基准: VER_UE4_OLDEST_LOADABLE_PACKAGE = 214
# ============================================================================

# PropertyTag 版本门控常量
VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG = 446      # StructGuid 字段加入（偏差 -110 → 修正）
VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG = 508    # PropertyGuid 字段加入（偏差 -7 → 修正）
VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT = 514     # Set/MapProperty 支持（偏差 -3 → 修正）
VAR_UE4_ARRAY_PROPERTY_INNER_TAGS = 253        # ArrayProperty inner type 字段加入（偏差 -29 → 修正）

# 其他 UE4 版本常量
UE4_NAME_HASHES_SERIALIZED = 509               # 名称表条目后添加 4 字节哈希（偏差 +5 → 修正）
UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS = 512  # 偏差 -6 → 修正
UE4_TemplateIndex_IN_COOKED_EXPORTS = 513      # 偏差 -6 → 修正
UE4_64BIT_EXPORTMAP_SERIALSIZES = 516          # 偏差 -6 → 修正
UE4_NON_OUTER_PACKAGE_IMPORT = 525             # 偏差 -5 → 修正
UE4_SERIALIZE_TEXT_IN_PACKAGES = 464           # 偏差 +53 → 修正

# 保持不变的常量（已验证正确）
UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID = 516
UE4_ADD_STRING_ASSET_REFERENCES_MAP = 384
UE4_ADDED_SEARCHABLE_NAMES = 510
UE4_ADDED_PACKAGE_OWNER = 518
UE4_LOAD_FOR_EDITOR_GAME = 365
UE4_COOKED_ASSETS_IN_EDITOR_SUPPORT = 485
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_ue_version_constants.py::TestUE4VersionConstants -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/constants.py tests/test_ue_version_constants.py
git commit -m "fix: correct UE4 version constants to match ObjectVersion.h enum (#94 A.2)"
```

---

### Task 3: 补充 FEdGraphPinType 版本门控常量

**Files:**
- Modify: `src/uasset_read/constants.py:151-163`
- Test: `tests/test_ue_version_constants.py`

- [ ] **Step 1: 编写 FEdGraphPinType 版本门控常量测试**

```python
# tests/test_ue_version_constants.py (追加)

class TestFEdGraphPinTypeVersionConstants:
    """验证 FEdGraphPinType 序列化版本常量。"""

    def test_ver_ue4_memberreference_in_pintype(self):
        """VER_UE4_MEMBERREFERENCE_IN_PINTYPE = 355
        
        PinSubCategoryMemberReference 字段加入。
        """
        from uasset_read.constants import VER_UE4_MEMBERREFERENCE_IN_PINTYPE
        assert VER_UE4_MEMBERREFERENCE_IN_PINTYPE == 355

    def test_ver_ue4_serialize_pintype_const(self):
        """VER_UE4_SERIALIZE_PINTYPE_CONST = 456
        
        bIsConst 字段加入。
        """
        from uasset_read.constants import VER_UE4_SERIALIZE_PINTYPE_CONST
        assert VER_UE4_SERIALIZE_PINTYPE_CONST == 456
```

- [ ] **Step 2: 运行测试验证**

Run: `pytest tests/test_ue_version_constants.py::TestFEdGraphPinTypeVersionConstants -v`
Expected: PASS（当前值已正确）

- [ ] **Step 3: 确认常量值正确**

当前 constants.py 中的值已正确：
- `VER_UE4_MEMBERREFERENCE_IN_PINTYPE = 355` ✅
- `VER_UE4_SERIALIZE_PINTYPE_CONST = 456` ✅

无需修改。

- [ ] **Step 4: Commit（如有修改）**

```bash
git add src/uasset_read/constants.py tests/test_ue_version_constants.py
git commit -m "test: add FEdGraphPinType version constant tests (#95 B.1)"
```

---

### Task 4: 补充 FText 版本门控常量

**Files:**
- Modify: `src/uasset_read/constants.py:158-163`
- Test: `tests/test_ue_version_constants.py`

- [ ] **Step 1: 编写 FText 版本门控常量测试**

```python
# tests/test_ue_version_constants.py (追加)

class TestFTextVersionConstants:
    """验证 FText 序列化版本常量。"""

    def test_ver_ue4_ftext_history(self):
        """VER_UE4_FTEXT_HISTORY = 428
        
        FText 历史数据序列化入口：旧格式 vs FTextHistory。
        """
        from uasset_read.constants import VER_UE4_FTEXT_HISTORY
        assert VER_UE4_FTEXT_HISTORY == 428

    def test_ver_ue4_added_currency_code_to_ftext(self):
        """VER_UE4_ADDED_CURRENCY_CODE_TO_FTEXT = 470
        
        AsCurrency 添加 CurrencyCode 字段。
        """
        from uasset_read.constants import VER_UE4_ADDED_CURRENCY_CODE_TO_FTEXT
        assert VER_UE4_ADDED_CURRENCY_CODE_TO_FTEXT == 470

    def test_ver_ue4_added_namespace_and_key_data_to_ftext(self):
        """VER_UE4_ADDED_NAMESPACE_AND_KEY_DATA_TO_FTEXT = 139
        
        Pre-FTEXT_HISTORY 版本的 namespace/key 数据。
        """
        from uasset_read.constants import VER_UE4_ADDED_NAMESPACE_AND_KEY_DATA_TO_FTEXT
        assert VER_UE4_ADDED_NAMESPACE_AND_KEY_DATA_TO_FTEXT == 139

    def test_ver_ue4_ftext_history_date_timezone(self):
        """VER_UE4_FTEXT_HISTORY_DATE_TIMEZONE = 539
        
        AsDate/AsTime 添加 TimeZone 字段。
        """
        from uasset_read.constants import VER_UE4_FTEXT_HISTORY_DATE_TIMEZONE
        assert VER_UE4_FTEXT_HISTORY_DATE_TIMEZONE == 539
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_ue_version_constants.py::TestFTextVersionConstants -v`
Expected: FAIL — 部分常量缺失或值错误

- [ ] **Step 3: 修正/补充 constants.py 中的 FText 版本常量**

```python
# src/uasset_read/constants.py

# ============================================================================
# FText 序列化版本常量（EUnrealEngineObjectUE4Version）
# 来源: Engine/Source/Runtime/Core/Private/Internationalization/Text.cpp
# ============================================================================

VER_UE4_FTEXT_HISTORY = 428                      # FText 历史数据序列化（偏差 +60 → 修正）
VER_UE4_ADDED_NAMESPACE_AND_KEY_DATA_TO_FTEXT = 139  # Pre-FTEXT_HISTORY namespace/key
VER_UE4_ADDED_CURRENCY_CODE_TO_FTEXT = 470       # AsCurrency CurrencyCode 字段（偏差 +81 → 修正）
VER_UE4_FTEXT_HISTORY_DATE_TIMEZONE = 539        # AsDate/AsTime TimeZone 字段
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_ue_version_constants.py::TestFTextVersionConstants -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/constants.py tests/test_ue_version_constants.py
git commit -m "fix: correct FText version constants to match Text.cpp (#95 B.3)"
```

---

## Phase 2: Issue #95 B.1/B.2 — FEdGraphPinType/PropertyTag 版本门控

### Task 5: FEdGraphPinType 补充版本门控

**Files:**
- Modify: `src/uasset_read/serializers/graph/pin_types.py:28-158`
- Test: `tests/test_version_gating.py`

- [ ] **Step 1: 编写 FEdGraphPinType 版本门控测试**

```python
# tests/test_version_gating.py
"""验证序列化器的版本门控行为。"""
import pytest
from unittest.mock import MagicMock
from io import BytesIO


def _make_archive(data: bytes):
    """创建 mock FArchive。"""
    from uasset_read.archive import FArchive
    archive = MagicMock(spec=FArchive)
    buf = BytesIO(data)
    archive.read = lambda n: buf.read(n)
    archive.read_u8 = lambda: int.from_bytes(buf.read(1), 'little')
    archive.read_i32 = lambda: int.from_bytes(buf.read(4), 'little', signed=True)
    archive.read_bool = lambda: int.from_bytes(buf.read(4), 'little') != 0
    archive.read_name = lambda names: names[int.from_bytes(buf.read(4), 'little')]
    archive.read_fstring = lambda: buf.read(int.from_bytes(buf.read(4), 'little')).decode('utf-8')
    archive.tell = lambda: buf.tell()
    archive.seek = lambda pos: buf.seek(pos)
    return archive


def _make_summary(**custom_versions):
    """创建 mock PackageFileSummary。"""
    summary = MagicMock()
    summary.file_version_ue4 = custom_versions.pop('ue4_version', 500)
    summary.get_custom_version = lambda guid, default: custom_versions.get(guid, default)
    return summary


class TestFEdGraphPinTypeVersionGating:
    """验证 FEdGraphPinType 版本门控。"""

    def test_pins_store_fname_fstring_fallback(self):
        """< FFrameworkObjectVersion::PinsStoreFName (19): 使用 FString"""
        from uasset_read.serializers.graph.pin_types import read_ed_graph_pin_type
        from uasset_read.constants import FFRAMEWORK_OBJECT_VERSION_GUID
        
        # framework_version = 10 < 19，应使用 FString
        data = (
            b'\x06\x00\x00\x00object\x00'  # PinCategory (FString)
            b'\x04\x00\x00\x00int\x00'     # PinSubCategory (FString)
            b'\x00\x00\x00\x00'            # PinSubCategoryObject
            b'\x00'                         # bIsMap (legacy)
            b'\x00'                         # bIsSet (legacy)
            b'\x00\x00\x00\x00'            # bIsReference
            b'\x00\x00\x00\x00'            # bIsWeakPointer
        )
        archive = _make_archive(data)
        summary = _make_summary(**{FFRAMEWORK_OBJECT_VERSION_GUID: 10})
        
        pin_type = read_ed_graph_pin_type(archive, [], summary)
        assert pin_type.pin_category == "object"

    def test_pins_store_fname_fname_format(self):
        """>= FFrameworkObjectVersion::PinsStoreFName (19): 使用 FName"""
        from uasset_read.serializers.graph.pin_types import read_ed_graph_pin_type
        from uasset_read.constants import FFRAMEWORK_OBJECT_VERSION_GUID
        
        # framework_version = 20 >= 19，应使用 FName
        name_map = ["object", "int"]
        data = (
            b'\x00\x00\x00\x00'  # PinCategory (FName index 0 = "object")
            b'\x01\x00\x00\x00'  # PinSubCategory (FName index 1 = "int")
            b'\x00\x00\x00\x00'  # PinSubCategoryObject
            b'\x00'              # ContainerType (None)
            b'\x00\x00\x00\x00'  # bIsReference
            b'\x00\x00\x00\x00'  # bIsWeakPointer
        )
        archive = _make_archive(data)
        summary = _make_summary(**{FFRAMEWORK_OBJECT_VERSION_GUID: 20})
        
        pin_type = read_ed_graph_pin_type(archive, name_map, summary)
        assert pin_type.pin_category == "object"
        assert pin_type.pin_subcategory == "int"

    def test_memberreference_in_pintype_gating(self):
        """>= VER_UE4_MEMBERREFERENCE_IN_PINTYPE (355): 读取 PinSubCategoryMemberReference"""
        from uasset_read.serializers.graph.pin_types import read_ed_graph_pin_type
        from uasset_read.constants import (
            FFRAMEWORK_OBJECT_VERSION_GUID,
            VER_UE4_MEMBERREFERENCE_IN_PINTYPE,
        )
        
        # ue4_version = 400 >= 355，应读取 MemberReference
        name_map = ["object", "", "MemberName"]
        data = (
            b'\x00\x00\x00\x00'  # PinCategory
            b'\x01\x00\x00\x00'  # PinSubCategory
            b'\x00\x00\x00\x00'  # PinSubCategoryObject
            b'\x00'              # ContainerType
            b'\x00\x00\x00\x00'  # bIsReference
            b'\x00\x00\x00\x00'  # bIsWeakPointer
            # MemberReference (ue4_version >= 355)
            b'\x00\x00\x00\x00'  # MemberParent
            b'\x02\x00\x00\x00'  # MemberName (FName index 2)
            b'\x00' * 16         # MemberGuid
        )
        archive = _make_archive(data)
        summary = _make_summary(
            **{FFRAMEWORK_OBJECT_VERSION_GUID: 20},
            ue4_version=400,
        )
        
        pin_type = read_ed_graph_pin_type(archive, name_map, summary)
        # 应成功读取，不抛异常

    def test_serialize_pintype_const_gating(self):
        """>= VER_UE4_SERIALIZE_PINTYPE_CONST (456): 读取 bIsConst"""
        from uasset_read.serializers.graph.pin_types import read_ed_graph_pin_type
        from uasset_read.constants import (
            FFRAMEWORK_OBJECT_VERSION_GUID,
            VER_UE4_SERIALIZE_PINTYPE_CONST,
        )
        
        # ue4_version = 500 >= 456，应读取 bIsConst
        name_map = ["object", ""]
        data = (
            b'\x00\x00\x00\x00'  # PinCategory
            b'\x01\x00\x00\x00'  # PinSubCategory
            b'\x00\x00\x00\x00'  # PinSubCategoryObject
            b'\x00'              # ContainerType
            b'\x00\x00\x00\x00'  # bIsReference
            b'\x00\x00\x00\x00'  # bIsWeakPointer
            b'\x01\x00\x00\x00'  # bIsConst (ue4_version >= 456)
        )
        archive = _make_archive(data)
        summary = _make_summary(
            **{FFRAMEWORK_OBJECT_VERSION_GUID: 20},
            ue4_version=500,
        )
        
        pin_type = read_ed_graph_pin_type(archive, name_map, summary)
        assert pin_type.is_const == True
```

- [ ] **Step 2: 运行测试验证当前行为**

Run: `pytest tests/test_version_gating.py::TestFEdGraphPinTypeVersionGating -v`
Expected: 部分 PASS（当前实现已有部分版本门控）

- [ ] **Step 3: 审查 pin_types.py 版本门控完整性**

当前 `read_ed_graph_pin_type()` 已实现的版本门控：
- ✅ `FFRAMEWORK_VERSION_PINS_STORE_FNAME` (19): FName vs FString
- ✅ `FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE` (15): uint8 vs 3 bools
- ✅ `VER_UE4_MEMBERREFERENCE_IN_PINTYPE` (355): PinSubCategoryMemberReference
- ✅ `VER_UE4_SERIALIZE_PINTYPE_CONST` (456): bIsConst
- ✅ `FRELEASE_VERSION_PIN_TYPE_UOBJECT_WRAPPER` (10): bIsUObjectWrapper
- ✅ `FUE5RELEASESTREAM_VERSION_SERIALIZE_FLOAT_PIN_DEFAULTS_AS_SINGLE_PRECISION` (36): bSerializeAsSinglePrecisionFloat

**结论：** FEdGraphPinType 版本门控已完整实现，无需修改。

- [ ] **Step 4: Commit 测试**

```bash
git add tests/test_version_gating.py
git commit -m "test: add FEdGraphPinType version gating tests (#95 B.1)"
```

---

### Task 6: PropertyTag 补充版本门控

**Files:**
- Modify: `src/uasset_read/serializers/property_tags.py:171-285`
- Test: `tests/test_version_gating.py`

- [ ] **Step 1: 编写 PropertyTag 版本门控测试**

```python
# tests/test_version_gating.py (追加)

class TestPropertyTagVersionGating:
    """验证 PropertyTag UE4 路径版本门控。"""

    def test_struct_guid_in_property_tag_gating(self):
        """>= VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG (446): 读取 StructGuid"""
        from uasset_read.serializers.property_tags import read_property_tag
        
        # legacy_file_version = -500 (UE4 version 500 >= 446)
        name_map = ["TestProp", "StructProperty", "Vector", "None"]
        data = (
            b'\x00\x00\x00\x00'  # Name (FName index 0)
            b'\x01\x00\x00\x00'  # Type (FName index 1 = "StructProperty")
            b'\x02\x00\x00\x00'  # StructType (FName index 2 = "Vector")
            b'\x01'              # has_struct_guid = true
            b'\x00' * 16         # StructGuid (16 bytes)
            b'\x0c\x00\x00\x00'  # Size (12)
            b'\x00\x00\x00\x00'  # ArrayIndex
            b'\x00'              # has_guid = false
        )
        archive = _make_archive(data)
        
        tag = read_property_tag(
            archive, name_map,
            engine_family="ue4",
            legacy_file_version=-500,  # UE4 version 500
        )
        assert tag.name == "TestProp"
        assert tag.type == "StructProperty"
        assert tag.struct_type == "Vector"
        assert tag.struct_guid is not None

    def test_struct_guid_skipped_for_old_version(self):
        """< VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG (446): 跳过 StructGuid"""
        from uasset_read.serializers.property_tags import read_property_tag
        
        # legacy_file_version = -400 (UE4 version 400 < 446)
        name_map = ["TestProp", "StructProperty", "Vector", "None"]
        data = (
            b'\x00\x00\x00\x00'  # Name
            b'\x01\x00\x00\x00'  # Type = "StructProperty"
            b'\x02\x00\x00\x00'  # StructType = "Vector"
            # 无 StructGuid（版本 < 446）
            b'\x0c\x00\x00\x00'  # Size
            b'\x00\x00\x00\x00'  # ArrayIndex
        )
        archive = _make_archive(data)
        
        tag = read_property_tag(
            archive, name_map,
            engine_family="ue4",
            legacy_file_version=-400,  # UE4 version 400
        )
        assert tag.struct_guid is None

    def test_property_guid_in_property_tag_gating(self):
        """>= VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG (508): 读取 PropertyGuid"""
        from uasset_read.serializers.property_tags import read_property_tag
        
        name_map = ["TestProp", "IntProperty", "None"]
        data = (
            b'\x00\x00\x00\x00'  # Name
            b'\x01\x00\x00\x00'  # Type = "IntProperty"
            b'\x04\x00\x00\x00'  # Size (4)
            b'\x00\x00\x00\x00'  # ArrayIndex
            b'\x01'              # has_guid = true
            b'\x00' * 16         # PropertyGuid
        )
        archive = _make_archive(data)
        
        tag = read_property_tag(
            archive, name_map,
            engine_family="ue4",
            legacy_file_version=-520,  # UE4 version 520 >= 508
        )
        assert tag.property_guid is not None

    def test_set_map_support_gating(self):
        """>= VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT (514): 支持 MapProperty"""
        from uasset_read.serializers.property_tags import read_property_tag
        
        name_map = ["TestMap", "MapProperty", "StrProperty", "IntProperty", "None"]
        data = (
            b'\x00\x00\x00\x00'  # Name
            b'\x01\x00\x00\x00'  # Type = "MapProperty"
            b'\x02\x00\x00\x00'  # KeyType = "StrProperty"
            b'\x03\x00\x00\x00'  # ValueType = "IntProperty"
            b'\x00\x00\x00\x00'  # Size
            b'\x00\x00\x00\x00'  # ArrayIndex
        )
        archive = _make_archive(data)
        
        tag = read_property_tag(
            archive, name_map,
            engine_family="ue4",
            legacy_file_version=-520,  # UE4 version 520 >= 514
        )
        assert tag.key_type == "StrProperty"
        assert tag.value_type == "IntProperty"

    def test_array_inner_tags_gating(self):
        """>= VAR_UE4_ARRAY_PROPERTY_INNER_TAGS (253): 读取 ArrayProperty InnerType"""
        from uasset_read.serializers.property_tags import read_property_tag
        
        name_map = ["TestArray", "ArrayProperty", "IntProperty", "None"]
        data = (
            b'\x00\x00\x00\x00'  # Name
            b'\x01\x00\x00\x00'  # Type = "ArrayProperty"
            b'\x02\x00\x00\x00'  # InnerType = "IntProperty"
            b'\x00\x00\x00\x00'  # Size
            b'\x00\x00\x00\x00'  # ArrayIndex
        )
        archive = _make_archive(data)
        
        tag = read_property_tag(
            archive, name_map,
            engine_family="ue4",
            legacy_file_version=-300,  # UE4 version 300 >= 253
        )
        assert tag.inner_type == "IntProperty"
```

- [ ] **Step 2: 运行测试验证当前行为**

Run: `pytest tests/test_version_gating.py::TestPropertyTagVersionGating -v`
Expected: 部分 FAIL（版本门控使用 legacy_file_version 比较逻辑可能有问题）

- [ ] **Step 3: 审查 property_tags.py 版本门控逻辑**

当前 `_read_property_tag_ue4()` 的版本门控逻辑：

```python
# 当前代码（第 214 行）
if legacy_file_version >= -VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG:
    has_struct_guid = archive.read_u8()
```

**问题：** `legacy_file_version` 是负数（如 -500），比较逻辑是 `legacy_file_version >= -446`，即 `-500 >= -446` 为 False。

**正确逻辑：** UE4 version 500 >= 446 时应读取 StructGuid。

**修复：** 将 `legacy_file_version` 取绝对值后再比较，或改用 `abs(legacy_file_version) >= VER_UE4_*`。

- [ ] **Step 4: 修正 property_tags.py 版本门控比较逻辑**

```python
# src/uasset_read/serializers/property_tags.py

def _read_property_tag_ue4(
    archive: FArchive,
    name_map: List[str],
    tolerant: bool = False,
    mappings: Optional[Any] = None,
    struct_name: Optional[str] = None,
    legacy_file_version: int = -6,
) -> PropertyTag:
    """读取 UE4 格式的 PropertyTag。"""
    from uasset_read.constants import (
        UE4_NAME_HASHES_SERIALIZED,
        VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG,
        VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG,
        VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT,
        VAR_UE4_ARRAY_PROPERTY_INNER_TAGS,
    )
    
    # 将 legacy_file_version 转换为 UE4 version（正数）
    ue4_version = abs(legacy_file_version)
    
    tag_start_pos = archive.tell()
    tag = PropertyTag(name=archive.read_name(name_map), type="", size=0, tag_start_offset=tag_start_pos)
    
    if tag.name == "None":
        return tag
    
    type_name = archive.read_name(name_map)
    tag.type = type_name
    
    if type_name == "StructProperty":
        tag.struct_type = archive.read_name(name_map)
        
        # StructGuid: ue4_version >= 446 时存在
        if ue4_version >= VER_UE4_STRUCT_GUID_IN_PROPERTY_TAG:
            has_struct_guid = archive.read_u8()
            if has_struct_guid:
                tag.struct_guid = archive.read_bytes(16)
    
    elif type_name == "EnumProperty":
        tag.enum_type = archive.read_name(name_map)
    
    elif type_name == "ByteProperty":
        enum_name = archive.read_name(name_map)
        if enum_name and enum_name != "None":
            tag.enum_type = enum_name
    
    elif type_name in ("ArrayProperty", "SetProperty"):
        # ue4_version >= 253 时存在 inner type
        if ue4_version >= VAR_UE4_ARRAY_PROPERTY_INNER_TAGS:
            tag.inner_type = archive.read_name(name_map)
        else:
            raise ParseError(
                f"Array/Set inner type not supported in UE4 version {ue4_version} "
                f"(requires >= {VAR_UE4_ARRAY_PROPERTY_INNER_TAGS})"
            )
    
    elif type_name == "MapProperty":
        # ue4_version >= 514 时支持
        if ue4_version < VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT:
            raise ParseError(
                f"MapProperty not supported in UE4 version {ue4_version} "
                f"(requires >= {VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT})"
            )
        tag.key_type = archive.read_name(name_map)
        tag.value_type = archive.read_name(name_map)
    
    elif type_name == "SetProperty":
        if ue4_version < VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT:
            raise ParseError(
                f"SetProperty not supported in UE4 version {ue4_version} "
                f"(requires >= {VER_UE4_PROPERTY_TAG_SET_MAP_SUPPORT})"
            )
    
    tag.size = archive.read_i32()
    archive.validate_size(tag.size, tag.name, tolerant=tolerant)
    tag.array_index = archive.read_i32()
    
    # PropertyGuid: ue4_version >= 508 时条件存在
    if ue4_version >= VER_UE4_PROPERTY_GUID_IN_PROPERTY_TAG:
        has_guid = archive.read_u8()
        if has_guid:
            tag.property_guid = archive.read_bytes(16)
    
    tag.value_start_offset = archive.tell()
    if tag.size > 0:
        tag.value_end_offset = tag.value_start_offset + tag.size
    else:
        tag.value_end_offset = tag.value_start_offset
    
    tag.serialize_type = "Property"
    return tag
```

- [ ] **Step 5: 运行测试验证通过**

Run: `pytest tests/test_version_gating.py::TestPropertyTagVersionGating -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/uasset_read/serializers/property_tags.py tests/test_version_gating.py
git commit -m "fix: correct PropertyTag UE4 version gating comparison logic (#95 B.2)"
```

---

## Phase 3: Issue #95 B.3 — FText 版本门控

### Task 7: FText 序列化补充版本门控

**Files:**
- Modify: `src/uasset_read/serializers/graph/_common.py:225-292`
- Modify: `src/uasset_read/blueprint/variable_extractor.py:410-481`
- Test: `tests/test_version_gating.py`

- [ ] **Step 1: 编写 FText 版本门控测试**

```python
# tests/test_version_gating.py (追加)

class TestFTextVersionGating:
    """验证 FText 序列化版本门控。"""

    def test_ftext_history_gating(self):
        """>= VER_UE4_FTEXT_HISTORY (428): 读取 history_type"""
        from uasset_read.blueprint.variable_extractor import read_ftext
        
        # ue4_version = 500 >= 428，应读取 history_type
        data = (
            b'\x00\x00\x00\x00'  # flags
            b'\x00'              # history_type = 0 (Base)
            b'\x00\x00\x00\x00'  # namespace (empty FString)
            b'\x00\x00\x00\x00'  # key (empty FString)
            b'\x05\x00\x00\x00Hello'  # source_string
        )
        archive = _make_archive(data)
        summary = _make_summary(ue4_version=500)
        
        result = read_ftext(archive, summary)
        assert result == "Hello"

    def test_ftext_no_history_for_old_version(self):
        """< VER_UE4_FTEXT_HISTORY (428): 跳过 history_type，直接读 Base 格式"""
        from uasset_read.blueprint.variable_extractor import read_ftext
        
        # ue4_version = 400 < 428，无 history_type
        data = (
            b'\x00\x00\x00\x00'  # flags
            # 无 history_type（旧版本）
            b'\x00\x00\x00\x00'  # namespace
            b'\x00\x00\x00\x00'  # key
            b'\x05\x00\x00\x00World'  # source_string
        )
        archive = _make_archive(data)
        summary = _make_summary(ue4_version=400)
        
        result = read_ftext(archive, summary)
        assert result == "World"
```

- [ ] **Step 2: 运行测试验证当前行为**

Run: `pytest tests/test_version_gating.py::TestFTextVersionGating -v`
Expected: PASS（当前 `read_ftext()` 已实现版本门控）

- [ ] **Step 3: 审查 read_ftext() 版本门控**

当前 `read_ftext()` 实现（variable_extractor.py:410-481）：

```python
def read_ftext(archive, summary=None) -> str:
    _flags = archive.read_i32()
    
    ue4_version = summary.file_version_ue4 if summary and hasattr(summary, 'file_version_ue4') else 500
    if ue4_version >= VER_UE4_FTEXT_HISTORY:
        history_type = archive.read_i8()
    else:
        history_type = 0  # 旧版本无 history_type，默认 Base 格式
    
    # ... 根据 history_type 读取
```

**结论：** `read_ftext()` 版本门控已正确实现。

- [ ] **Step 4: 审查 _common.py 中的 FText 序列化**

`read_ftext_with_history()` 已实现完整的 history_type 分支处理，版本门控由调用方负责。

- [ ] **Step 5: Commit 测试**

```bash
git add tests/test_version_gating.py
git commit -m "test: add FText version gating tests (#95 B.3)"
```

---

## Phase 4: Issue #102 — FEdGraphPinType 数据模型修复

### Task 8: 补充 FEdGraphTerminalType 数据模型

**Files:**
- Modify: `src/uasset_read/models/core.py:22-48`
- Test: `tests/test_pin_type_model.py`

- [ ] **Step 1: 编写 FEdGraphTerminalType 测试**

```python
# tests/test_pin_type_model.py
"""验证 FEdGraphPinType 数据模型与 UE 源码一致。"""
import pytest
from uasset_read.models.core import FEdGraphPinType, FEdGraphTerminalType


class TestFEdGraphTerminalType:
    """验证 FEdGraphTerminalType（Map value 类型）。"""

    def test_ftext_terminal_type_creation(self):
        """FEdGraphTerminalType 可正确创建。"""
        terminal = FEdGraphTerminalType(
            pin_category="int",
            pin_subcategory="",
            pin_subcategory_object=None,
        )
        assert terminal.pin_category == "int"

    def test_pin_type_with_value_type(self):
        """FEdGraphPinType 可包含 pin_value_type。"""
        pin_type = FEdGraphPinType(
            pin_category="map",
            pin_value_type=FEdGraphTerminalType(pin_category="int"),
        )
        assert pin_type.pin_value_type is not None
        assert pin_type.pin_value_type.pin_category == "int"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_pin_type_model.py -v`
Expected: FAIL — `FEdGraphTerminalType` 未定义

- [ ] **Step 3: 在 models/core.py 中添加 FEdGraphTerminalType**

```python
# src/uasset_read/models/core.py

@dataclass
class FEdGraphTerminalType:
    """Map value 类型（UE EdGraphPin.h:50-70）。
    
    FEdGraphTerminalType 用于表示 Map 的 value 类型。
    例如 TMap<FString, int> 的 pin_value_type.pin_category = "int"。
    """
    pin_category: str = ""
    pin_subcategory: str = ""
    pin_subcategory_object: Optional[int] = None  # FPackageIndex (int32)
    pin_subcategory_object_name: Optional[str] = None


@dataclass
class FEdGraphPinType:
    """蓝图引脚类型结构。"""
    pin_category: str = ""
    pin_subcategory: str = ""
    pin_subcategory_object: Optional[int] = None
    pin_subcategory_object_name: Optional[str] = None
    pin_subcategory_object_ref: Optional["UObjectInstance"] = None
    # Map value 类型（Issue #102 3.1）
    pin_value_type: Optional[FEdGraphTerminalType] = None
    container_type: int = 0
    is_reference: bool = False
    is_weak_pointer: bool = False
    is_const: bool = False
    is_uobject_wrapper: bool = False
    b_serialize_as_single_precision_float: bool = False
    # 注意：is_map_key / is_map_value 已移除（Issue #102 3.3）
    # Map 信息通过 pin_value_type 表达
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_pin_type_model.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/models/core.py tests/test_pin_type_model.py
git commit -m "feat: add FEdGraphTerminalType for Map value type (#102 3.1)"
```

---

### Task 9: 补充 FSimpleMemberReference 数据模型

**Files:**
- Modify: `src/uasset_read/models/core.py:211-230`
- Test: `tests/test_pin_type_model.py`

- [ ] **Step 1: 编写 FSimpleMemberReference 测试**

```python
# tests/test_pin_type_model.py (追加)

class TestFSimpleMemberReference:
    """验证 FSimpleMemberReference（成员引用）。"""

    def test_member_reference_creation(self):
        """FSimpleMemberReference 可正确创建。"""
        from uasset_read.models.core import FSimpleMemberReference
        ref = FSimpleMemberReference(
            member_parent_class=5,
            member_name="MyMember",
            member_guid="00000000-0000-0000-0000-000000000000",
        )
        assert ref.member_name == "MyMember"

    def test_pin_type_with_member_reference(self):
        """FEdGraphPinType 可包含 pin_subcategory_member_reference。"""
        from uasset_read.models.core import FSimpleMemberReference
        pin_type = FEdGraphPinType(
            pin_category="float",
            pin_subcategory_member_reference=FSimpleMemberReference(
                member_name="StructMember",
            ),
        )
        assert pin_type.pin_subcategory_member_reference.member_name == "StructMember"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_pin_type_model.py::TestFSimpleMemberReference -v`
Expected: FAIL — `FSimpleMemberReference` 未定义

- [ ] **Step 3: 在 models/core.py 中添加 FSimpleMemberReference**

```python
# src/uasset_read/models/core.py

@dataclass
class FSimpleMemberReference:
    """简单成员引用（UE CoreMinimal.h）。
    
    用于 FEdGraphPinType::PinSubCategoryMemberReference。
    表示结构成员或函数引用。
    """
    member_parent_class: Optional[int] = None  # FPackageIndex
    member_name: str = ""
    member_guid: str = ""


@dataclass
class FEdGraphPinType:
    """蓝图引脚类型结构。"""
    pin_category: str = ""
    pin_subcategory: str = ""
    pin_subcategory_object: Optional[int] = None
    pin_subcategory_object_name: Optional[str] = None
    pin_subcategory_object_ref: Optional["UObjectInstance"] = None
    pin_value_type: Optional[FEdGraphTerminalType] = None
    # 成员引用（Issue #102 3.2）
    pin_subcategory_member_reference: Optional[FSimpleMemberReference] = None
    container_type: int = 0
    is_reference: bool = False
    is_weak_pointer: bool = False
    is_const: bool = False
    is_uobject_wrapper: bool = False
    b_serialize_as_single_precision_float: bool = False
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_pin_type_model.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/models/core.py tests/test_pin_type_model.py
git commit -m "feat: add FSimpleMemberReference for PinSubCategoryMemberReference (#102 3.2)"
```

---

### Task 10: 移除 is_map_key / is_map_value 错误字段

**Files:**
- Modify: `src/uasset_read/models/core.py:22-48`
- Modify: `src/uasset_read/serializers/graph/pin_types.py:88-116`
- Test: `tests/test_pin_type_model.py`

- [ ] **Step 1: 编写测试验证字段移除**

```python
# tests/test_pin_type_model.py (追加)

class TestFEdGraphPinTypeFieldRemoval:
    """验证 FEdGraphPinType 错误字段已移除。"""

    def test_is_map_key_removed(self):
        """is_map_key 字段已移除。"""
        pin_type = FEdGraphPinType()
        assert not hasattr(pin_type, 'is_map_key')

    def test_is_map_value_removed(self):
        """is_map_value 字段已移除。"""
        pin_type = FEdGraphPinType()
        assert not hasattr(pin_type, 'is_map_value')

    def test_map_expressed_via_pin_value_type(self):
        """Map 类型通过 pin_value_type 表达。"""
        pin_type = FEdGraphPinType(
            pin_category="map",
            container_type=3,  # Map
            pin_value_type=FEdGraphTerminalType(pin_category="int"),
        )
        assert pin_type.container_type == 3
        assert pin_type.pin_value_type.pin_category == "int"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_pin_type_model.py::TestFEdGraphPinTypeFieldRemoval -v`
Expected: FAIL — `is_map_key` / `is_map_value` 仍存在

- [ ] **Step 3: 从 FEdGraphPinType 移除错误字段**

```python
# src/uasset_read/models/core.py

@dataclass
class FEdGraphPinType:
    """蓝图引脚类型结构。"""
    pin_category: str = ""
    pin_subcategory: str = ""
    pin_subcategory_object: Optional[int] = None
    pin_subcategory_object_name: Optional[str] = None
    pin_subcategory_object_ref: Optional["UObjectInstance"] = None
    pin_value_type: Optional[FEdGraphTerminalType] = None
    pin_subcategory_member_reference: Optional[FSimpleMemberReference] = None
    container_type: int = 0
    is_reference: bool = False
    is_weak_pointer: bool = False
    is_const: bool = False
    is_uobject_wrapper: bool = False
    b_serialize_as_single_precision_float: bool = False
    # 已移除: is_map_key, is_map_value（UE 中不存在，Map 通过 pin_value_type 表达）
```

- [ ] **Step 4: 更新 pin_types.py 序列化逻辑**

```python
# src/uasset_read/serializers/graph/pin_types.py

def read_ed_graph_pin_type(
    archive: FArchive,
    name_map: List[str],
    summary: PackageFileSummary,
    import_map: Optional[List[ObjectImport]] = None,
    export_map: Optional[List[ObjectExport]] = None,
    linker: Optional["PackageLinker"] = None,
) -> FEdGraphPinType:
    """解析 FEdGraphPinType（UE4/UE5 兼容 — 带版本门控）。"""
    from uasset_read.models.core import FEdGraphTerminalType
    
    pin_type = FEdGraphPinType()
    
    # ... 现有代码 ...
    
    # =========================================================================
    # 3. ContainerType / PinValueType
    # =========================================================================
    if framework_version >= FFRAMEWORK_VERSION_ED_GRAPH_PIN_CONTAINER_TYPE:
        pin_type.container_type = archive.read_u8()
        if pin_type.container_type == 3:  # Map
            # 读取 FEdGraphTerminalType (PinValueType)
            pin_type.pin_value_type = FEdGraphTerminalType(
                pin_category=archive.read_name(name_map),
                pin_subcategory=archive.read_name(name_map),
                pin_subcategory_object=archive.read_i32(),
            )
    else:
        # UE4 旧格式：3 个 bool
        bIsMap = archive.read_bool()
        bIsSet = archive.read_bool()
        if bIsMap:
            pin_type.pin_value_type = FEdGraphTerminalType(
                pin_category=archive.read_name(name_map),
                pin_subcategory=archive.read_name(name_map),
                pin_subcategory_object=archive.read_i32(),
            )
        bIsArray = archive.read_bool()
        
        if bIsArray:
            pin_type.container_type = 1
        elif bIsSet:
            pin_type.container_type = 2
        elif bIsMap:
            pin_type.container_type = 3
        else:
            pin_type.container_type = 0
    
    # ... 其余代码 ...
```

- [ ] **Step 5: 运行测试验证通过**

Run: `pytest tests/test_pin_type_model.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/uasset_read/models/core.py src/uasset_read/serializers/graph/pin_types.py tests/test_pin_type_model.py
git commit -m "refactor: remove is_map_key/is_map_value, use pin_value_type for Map (#102 3.3)"
```

---

### Task 11: FText Category 完整读取

**Files:**
- Modify: `src/uasset_read/blueprint/variable_extractor.py:975-976`
- Test: `tests/test_pin_type_model.py`

- [ ] **Step 1: 编写 FText Category 测试**

```python
# tests/test_pin_type_model.py (追加)

class TestBlueprintVariableFTextCategory:
    """验证 BlueprintVariable.Category 使用 FText 读取。"""

    def test_category_is_ftext(self):
        """Category 字段应使用 read_ftext() 读取。"""
        # 此测试需要 mock archive，验证 read_blueprint_variable() 调用 read_ftext()
        # 简化测试：验证 read_ftext() 可正确读取 Category
        from uasset_read.blueprint.variable_extractor import read_ftext
        
        data = (
            b'\x00\x00\x00\x00'  # flags
            b'\x00'              # history_type = 0 (Base)
            b'\x00\x00\x00\x00'  # namespace
            b'\x00\x00\x00\x00'  # key
            b'\x08\x00\x00\x00Default\x00'  # source_string = "Default"
        )
        archive = _make_archive(data)
        summary = _make_summary(ue4_version=500)
        
        result = read_ftext(archive, summary)
        assert result == "Default"
```

- [ ] **Step 2: 运行测试验证**

Run: `pytest tests/test_pin_type_model.py::TestBlueprintVariableFTextCategory -v`
Expected: PASS

- [ ] **Step 3: 更新 read_blueprint_variable() 使用 read_ftext()**

```python
# src/uasset_read/blueprint/variable_extractor.py

def read_blueprint_variable(
    archive,
    name_map: List[str],
    summary,
) -> BlueprintVariable:
    """从 blueprint export 读取 FBPVariableDescription。"""
    var = BlueprintVariable(
        var_name=archive.read_name(name_map)
    )
    
    var.var_guid = _read_guid(archive)
    var.var_type = read_ed_graph_pin_type(archive, name_map, summary)
    var.friendly_name = archive.read_fstring()
    
    # Category (FText) — 使用 read_ftext() 完整读取（Issue #102 3.4）
    var.category = read_ftext(archive, summary)
    
    var.property_flags = archive.read_u64()
    # ... 其余代码 ...
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_pin_type_model.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/blueprint/variable_extractor.py tests/test_pin_type_model.py
git commit -m "fix: use read_ftext() for BlueprintVariable.Category (#102 3.4)"
```

---

## Task 12: 运行全量测试验证

- [ ] **Step 1: 运行所有新增测试**

Run: `pytest tests/test_ue_version_constants.py tests/test_version_gating.py tests/test_pin_type_model.py -v`
Expected: 全部 PASS

- [ ] **Step 2: 运行回归测试**

Run: `python scripts/test_matrix.py unit`
Expected: 全部 PASS（或仅有预存在的失败）

- [ ] **Step 3: Commit 最终状态**

```bash
git add -A
git commit -m "test: complete P1 UE source audit fixes (#94, #95, #102)"
```

---

## 完成标准

1. ✅ 所有 CustomVersion GUID 与 UE DevObjectVersion.cpp 一致
2. ✅ 所有 UE4 版本常量与 UE ObjectVersion.h enum 一致
3. ✅ PropertyTag UE4 路径版本门控逻辑正确
4. ✅ FEdGraphPinType 数据模型包含 FEdGraphTerminalType 和 FSimpleMemberReference
5. ✅ FEdGraphPinType 移除 is_map_key / is_map_value 错误字段
6. ✅ BlueprintVariable.Category 使用 FText 完整读取
7. ✅ 全量测试通过

---

## 风险与注意事项

1. **版本常量修正影响范围大**：修正后的版本常量会影响所有依赖版本门控的序列化路径。需要在多种 UE4/UE5 版本的资产上验证。

2. **is_map_key / is_map_value 移除**：如果有外部代码依赖这两个字段，需要更新。搜索 `is_map_key` / `is_map_value` 确认无其他引用。

3. **FText Category 读取**：`read_ftext()` 依赖 `summary.file_version_ue4`，确保 summary 正确传递。

4. **向后兼容**：根据项目约束，无需向后兼容。可直接修改接口。
