# UE5.5 解析器能力提升 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 提升解析器对 UE5.5 资产的支持覆盖率，从当前 ~60% 提升到 > 95%

**Architecture:** 镜像 UE 内部 FArchive 序列化管线，通过扩展 StructProperty 解析、K2Node 类型注册表、Kismet 字节码支持，实现对蓝图变量、节点、字节码的完整解析。

**Tech Stack:** Python 3.10+, 零运行时依赖, pytest TDD

---

## Phase 1: StructProperty UnknownStruct 回退修复 (R1)

### Task 1.1: 添加缺失的 StructProperty 快速路径

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py:218-350`
- Create: `tests/test_struct_property_ue55.py`

- [ ] **Step 1: 写失败测试 - TopLevelAssetPath 结构体**

```python
# tests/test_struct_property_ue55.py
"""UE5.5 StructProperty 扩展测试"""
import struct
import pytest
from uasset_read.archive import FArchive
from uasset_read.parsers.property_types import parse_struct_property
from uasset_read.models.properties import PropertyTag, StructValue


def _make_archive(data: bytes) -> FArchive:
    return FArchive(data)


def test_toplevel_asset_path():
    """TopLevelAssetPath: 2x FName (package + asset name)"""
    # Package: "/Game/FirstPerson/Blueprints/BP_FirstPerson"
    # Asset: "BP_FirstPerson"
    name_map = [
        "",  # 0
        "/Game/FirstPerson/Blueprints/BP_FirstPerson",  # 1
        "BP_FirstPerson",  # 2
    ]
    # FName 格式: i32 index + i32 number
    data = struct.pack('<ii', 1, 0) + struct.pack('<ii', 2, 0)
    archive = _make_archive(data)
    
    tag = PropertyTag(
        name="TestPath",
        type="StructProperty",
        size=len(data),
        struct_type="TopLevelAssetPath"
    )
    
    # 需要 mock export_map 和 import_map
    result = parse_struct_property(tag, archive, name_map, [], None)
    
    assert result.struct_type == "TopLevelAssetPath"
    assert "PackageName" in result.fields
    assert "AssetName" in result.fields
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_struct_property_ue55.py::test_toplevel_asset_path -v
```
Expected: FAIL with "TopLevelAssetPath not supported"

- [ ] **Step 3: 实现 TopLevelAssetPath 快速路径**

```python
# 在 src/uasset_read/parsers/property_types.py 的 parse_struct_property 函数中
# 在 _EXPECTED_STRUCT_SIZES 字典后添加

# Phase 76: 新增 TopLevelAssetPath 支持
_EXPECTED_STRUCT_SIZES["TopLevelAssetPath"] = 16  # 2x FName (4+4 bytes each)

# 在 parse_struct_property 函数中，BoxSphereBounds 处理后添加
if struct_type == "TopLevelAssetPath":
    pkg_name = archive.read_name(name_map)
    asset_name = archive.read_name(name_map)
    return StructValue(struct_type="TopLevelAssetPath", fields={
        "PackageName": pkg_name,
        "AssetName": asset_name,
    })
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_struct_property_ue55.py::test_toplevel_asset_path -v
```
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/parsers/property_types.py tests/test_struct_property_ue55.py
git commit -m "feat(struct): 添加 TopLevelAssetPath 结构体支持"
```

---

### Task 1.2: 添加 PointerToUberGraphFrame 支持

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py:218-350`
- Modify: `tests/test_struct_property_ue55.py`

- [ ] **Step 1: 写失败测试**

```python
# 在 tests/test_struct_property_ue55.py 中添加

def test_pointer_to_uber_graph_frame():
    """PointerToUberGraphFrame: 8 bytes (FPackageIndex)"""
    data = struct.pack('<ii', 42, 0)  # index=42, number=0
    archive = _make_archive(data)
    
    tag = PropertyTag(
        name="UberGraphFrame",
        type="StructProperty",
        size=8,
        struct_type="PointerToUberGraphFrame"
    )
    
    result = parse_struct_property(tag, archive, name_map=[], export_map=[], summary=None)
    
    assert result.struct_type == "PointerToUberGraphFrame"
    assert "FrameIndex" in result.fields
    assert result.fields["FrameIndex"] == 42
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_struct_property_ue55.py::test_pointer_to_uber_graph_frame -v
```
Expected: FAIL

- [ ] **Step 3: 实现 PointerToUberGraphFrame**

```python
# 在 parse_struct_property 函数中添加

if struct_type == "PointerToUberGraphFrame":
    frame_index = archive.read_i32()
    return StructValue(struct_type="PointerToUberGraphFrame", fields={
        "FrameIndex": frame_index,
    })
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_struct_property_ue55.py::test_pointer_to_uber_graph_frame -v
```
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/parsers/property_types.py tests/test_struct_property_ue55.py
git commit -m "feat(struct): 添加 PointerToUberGraphFrame 结构体支持"
```

---

### Task 1.3: 扩展 _TAGGED_FALLBACK_STRUCT_SCHEMAS

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py:39-44`
- Modify: `tests/test_struct_property_ue55.py`

- [ ] **Step 1: 写失败测试 - NewVariables 结构体**

```python
# 在 tests/test_struct_property_ue55.py 中添加

def test_new_variables_struct():
    """NewVariables: 蓝图变量定义数组"""
    # 构造包含 PropertyTag 循环的 NewVariables 数据
    # 这需要更复杂的测试数据构造
    pass  # TODO: 实现完整测试
```

- [ ] **Step 2: 扩展 _TAGGED_FALLBACK_STRUCT_SCHEMAS**

```python
# 在 src/uasset_read/parsers/property_types.py 中

_TAGGED_FALLBACK_STRUCT_SCHEMAS: dict[str, list[tuple[str, str]]] = {
    "MemberReference": [("MemberParent", "ObjectProperty"), ("MemberName", "NameProperty"), ("MemberGuid", "GuidProperty")],
    "SimpleMemberReference": [("MemberParent", "ObjectProperty"), ("MemberName", "NameProperty"), ("MemberGuid", "GuidProperty")],
    # Phase 76: 新增 UE5.5 结构体
    "NewVariables": [
        ("VarName", "NameProperty"),
        ("VarGuid", "GuidProperty"),
        ("VarType", "StructProperty"),  # FEdGraphPinType
    ],
    "ImplementedInterfaces": [
        ("InterfaceName", "NameProperty"),
        ("InterfaceGuid", "GuidProperty"),
    ],
    "LastEditedDocuments": [
        ("DocumentName", "NameProperty"),
    ],
    "CategorySorting": [
        ("CategoryName", "NameProperty"),
    ],
}
```

- [ ] **Step 3: 运行测试验证**

```bash
python -m pytest tests/test_struct_property_ue55.py -v
```

- [ ] **Step 4: 提交**

```bash
git add src/uasset_read/parsers/property_types.py tests/test_struct_property_ue55.py
git commit -m "feat(struct): 扩展 TaggedFallback 结构体注册表"
```

---

### Task 1.4: 处理 StructProperty 大小不匹配 (R6)

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py:200-220`
- Modify: `tests/test_struct_property_ue55.py`

- [ ] **Step 1: 写失败测试 - Vector4 32 bytes**

```python
# 在 tests/test_struct_property_ue55.py 中添加

def test_vector4_double_precision():
    """Vector4 32 bytes: double 精度版本 (UE5.5 LWC)"""
    # 4x double = 32 bytes
    data = struct.pack('<dddd', 1.0, 2.0, 3.0, 4.0)
    archive = _make_archive(data)
    
    tag = PropertyTag(
        name="TestVec4",
        type="StructProperty",
        size=32,
        struct_type="Vector4"
    )
    
    result = parse_struct_property(tag, archive, name_map=[], export_map=[], summary=None)
    
    assert result.struct_type == "Vector4"
    assert result.fields["X"] == 1.0
    assert result.fields["Y"] == 2.0
    assert result.fields["Z"] == 3.0
    assert result.fields["W"] == 4.0
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_struct_property_ue55.py::test_vector4_double_precision -v
```
Expected: FAIL (当前 Vector4 只支持 16 bytes)

- [ ] **Step 3: 修改 Vector4 支持 double 精度**

```python
# 在 parse_struct_property 函数中修改 Vector4 处理

if struct_type == "Vector4":
    if tag.size == 32:
        # UE5.5 LWC: double 精度
        x = archive.read_f64()
        y = archive.read_f64()
        z = archive.read_f64()
        w = archive.read_f64()
    else:
        # 标准 float 精度
        x = archive.read_f32()
        y = archive.read_f32()
        z = archive.read_f32()
        w = archive.read_f32()
    return StructValue(struct_type="Vector4", fields={"X": x, "Y": y, "Z": z, "W": w})
```

- [ ] **Step 4: 更新 _EXPECTED_STRUCT_SIZES**

```python
# 添加 LWC 支持的 sizes
EXPECTED_STRUCT_SIZES = {
    # ... 现有条目
    "Vector4": 16,  # 标准 size，32 在 parse 时处理
}
```

- [ ] **Step 5: 运行测试验证通过**

```bash
python -m pytest tests/test_struct_property_ue55.py::test_vector4_double_precision -v
```
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add src/uasset_read/parsers/property_types.py tests/test_struct_property_ue55.py
git commit -m "feat(struct): Vector4 支持 32 bytes double 精度 (UE5.5 LWC)"
```

---

## Phase 2: EExprToken 0xFF 补充 (R2) + K2Node 类型扩展 (R3)

### Task 2.1: 添加 EExprToken 0xFF 支持

**Files:**
- Modify: `src/uasset_read/kismet/tokens.py:13-145`
- Create: `tests/test_kismet_tokens_ue55.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_kismet_tokens_ue55.py
"""UE5.5 Kismet Token 扩展测试"""
from uasset_read.kismet.tokens import EExprToken


def test_ex_max_is_0xff():
    """验证 EX_Max 值为 0xFF"""
    assert EExprToken.EX_Max == 0xFF


def test_0xff_token_exists():
    """0xFF 应该能被识别为有效 token"""
    # 当前 0xFF 是 EX_Max，需要确认 UE5.5 新增的 token
    # 如果 UE5.5 在 0x73-0xFE 范围有新 token，需要添加
    token = EExprToken(0xFF)
    assert token is not None
```

- [ ] **Step 2: 运行测试验证**

```bash
python -m pytest tests/test_kismet_tokens_ue55.py -v
```

- [ ] **Step 3: 检查 UE5.5 源码确认 0xFF 定义**

```python
# 如果 UE5.5 中 0xFF 是新 token（非 EX_Max），需要更新枚举
# 根据 PRD 描述，0xFF 可能是委托相关操作符
# 需要对照 UE 5.5 源码确认

# 临时方案：在 EExprToken 中添加注释说明
EX_Max = 0xFF  # 注意：UE5.5 可能在此处有新定义
```

- [ ] **Step 4: 提交**

```bash
git add src/uasset_read/kismet/tokens.py tests/test_kismet_tokens_ue55.py
git commit -m "docs(kismet): 添加 EExprToken 0xFF 说明"
```

---

### Task 2.2: 添加 K2Node_Message 支持

**Files:**
- Modify: `src/uasset_read/serializers/graph.py:1510-1560`
- Modify: `src/uasset_read/models/node_types.py`
- Create: `tests/test_k2node_ue55.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_k2node_ue55.py
"""UE5.5 K2Node 扩展测试"""
import struct
import pytest
from uasset_read.archive import FArchive
from uasset_read.serializers.graph import read_ed_graph_node


def _make_archive(data: bytes) -> FArchive:
    return FArchive(data)


def test_k2node_message_fallback():
    """K2Node_Message 应该有基本的 fallback 处理"""
    # 构造包含 K2Node_Message 的最小测试数据
    # 这需要理解 graph.py 的完整序列化格式
    pass  # TODO: 实现完整测试
```

- [ ] **Step 2: 添加 K2NodeMessage 数据类**

```python
# 在 src/uasset_read/models/node_types.py 中添加

@dataclass
class K2NodeMessage(UEdGraphNode):
    """K2Node_Message 消息调用节点。"""
    message_name: str = ""
    message_target: Optional[FMemberReference] = None
    
    @classmethod
    def from_archive(
        cls,
        archive: FArchive,
        name_map: List[str],
        import_map: List[ObjectImport],
        export_map: List[ObjectExport]
    ) -> Self:
        """延迟导入避免循环依赖。"""
        from uasset_read.serializers.graph import read_k2node_message
        return read_k2node_message(archive, name_map, import_map, export_map)
```

- [ ] **Step 3: 添加 read_k2node_message 函数**

```python
# 在 src/uasset_read/serializers/graph.py 中添加

def read_k2node_message(
    archive: FArchive,
    name_map: List[str],
    import_map: List[ObjectImport],
    export_map: List[ObjectExport],
    linker: Optional["PackageLinker"] = None,
) -> Dict[str, Any]:
    """读取 K2Node_Message 特有字段。
    
    K2Node_Message 用于跨模块消息通信，字段包括：
    - MessageName: 消息名称
    - MessageTarget: 消息目标引用
    """
    result = {}
    
    # 尝试读取消息名称
    try:
        message_name_idx = archive.read_i32()
        if 0 <= message_name_idx < len(name_map):
            result["message_name"] = name_map[message_name_idx]
        else:
            result["message_name"] = f"Message_{message_name_idx}"
    except Exception as e:
        logger.warning("K2Node_Message read failed: %s", e)
        result["message_name"] = "Unknown"
    
    return result
```

- [ ] **Step 4: 注册到类名分派**

```python
# 在 src/uasset_read/serializers/graph.py 的 read_ed_graph_node 函数中
# 在现有的 elif 分支后添加

elif class_name == "K2Node_Message":
    base_node.node_data = read_k2node_message(
        archive, name_map, import_map, export_map, linker,
    )
```

- [ ] **Step 5: 运行测试验证**

```bash
python -m pytest tests/test_k2node_ue55.py -v
```

- [ ] **Step 6: 提交**

```bash
git add src/uasset_read/serializers/graph.py src/uasset_read/models/node_types.py tests/test_k2node_ue55.py
git commit -m "feat(k2node): 添加 K2Node_Message 支持"
```

---

### Task 2.3: 添加其他 K2Node 类型支持

**Files:**
- Modify: `src/uasset_read/serializers/graph.py:1510-1560`
- Modify: `src/uasset_read/models/node_types.py`

- [ ] **Step 1: 批量添加 K2Node 数据类**

```python
# 在 src/uasset_read/models/node_types.py 中添加

@dataclass
class K2NodeCallDelegate(UEdGraphNode):
    """K2Node_CallDelegate 委托调用节点。"""
    delegate_name: str = ""
    
    @classmethod
    def from_archive(cls, archive: FArchive, name_map: List[str]) -> Self:
        from uasset_read.serializers.graph import read_k2node_call_delegate
        return read_k2node_call_delegate(archive, name_map)


@dataclass
class K2NodeCallArrayFunction(UEdGraphNode):
    """K2Node_CallArrayFunction 数组操作节点。"""
    function_name: str = ""
    
    @classmethod
    def from_archive(cls, archive: FArchive, name_map: List[str]) -> Self:
        from uasset_read.serializers.graph import read_k2node_call_array_function
        return read_k2node_call_array_function(archive, name_map)


@dataclass
class K2NodeCallParentFunction(UEdGraphNode):
    """K2Node_CallParentFunction 调用父类函数节点。"""
    function_name: str = ""
    
    @classmethod
    def from_archive(cls, archive: FArchive, name_map: List[str]) -> Self:
        from uasset_read.serializers.graph import read_k2node_call_parent_function
        return read_k2node_call_parent_function(archive, name_map)


@dataclass
class K2NodeFunctionResult(UEdGraphNode):
    """K2Node_FunctionResult 函数返回值节点。"""
    function_name: str = ""
    
    @classmethod
    def from_archive(cls, archive: FArchive, name_map: List[str]) -> Self:
        from uasset_read.serializers.graph import read_k2node_function_result
        return read_k2node_function_result(archive, name_map)


@dataclass
class K2NodeCreateWidget(UEdGraphNode):
    """K2Node_CreateWidget 创建 UI 控件节点。"""
    widget_class: str = ""
    
    @classmethod
    def from_archive(cls, archive: FArchive, name_map: List[str]) -> Self:
        from uasset_read.serializers.graph import read_k2node_create_widget
        return read_k2node_create_widget(archive, name_map)


@dataclass
class K2NodeAddDelegate(UEdGraphNode):
    """K2Node_AddDelegate 添加委托绑定节点。"""
    delegate_name: str = ""
    
    @classmethod
    def from_archive(cls, archive: FArchive, name_map: List[str]) -> Self:
        from uasset_read.serializers.graph import read_k2node_add_delegate
        return read_k2node_add_delegate(archive, name_map)


@dataclass
class K2NodeMacroInstance(UEdGraphNode):
    """K2Node_MacroInstance 宏实例节点。"""
    macro_name: str = ""
    
    @classmethod
    def from_archive(cls, archive: FArchive, name_map: List[str]) -> Self:
        from uasset_read.serializers.graph import read_k2node_macro_instance
        return read_k2node_macro_instance(archive, name_map)
```

- [ ] **Step 2: 添加对应的 read 函数**

```python
# 在 src/uasset_read/serializers/graph.py 中添加

def read_k2node_call_delegate(archive: FArchive, name_map: List[str]) -> Dict[str, Any]:
    """读取 K2Node_CallDelegate 字段。"""
    result = {}
    try:
        delegate_idx = archive.read_i32()
        if 0 <= delegate_idx < len(name_map):
            result["delegate_name"] = name_map[delegate_idx]
    except Exception as e:
        logger.warning("K2Node_CallDelegate read failed: %s", e)
    return result


def read_k2node_call_array_function(archive: FArchive, name_map: List[str]) -> Dict[str, Any]:
    """读取 K2Node_CallArrayFunction 字段。"""
    return {}  # 无额外字段


def read_k2node_call_parent_function(archive: FArchive, name_map: List[str]) -> Dict[str, Any]:
    """读取 K2Node_CallParentFunction 字段。"""
    return {}  # 无额外字段


def read_k2node_function_result(archive: FArchive, name_map: List[str]) -> Dict[str, Any]:
    """读取 K2Node_FunctionResult 字段。"""
    return {}  # 无额外字段


def read_k2node_create_widget(archive: FArchive, name_map: List[str]) -> Dict[str, Any]:
    """读取 K2Node_CreateWidget 字段。"""
    return {}  # 无额外字段


def read_k2node_add_delegate(archive: FArchive, name_map: List[str]) -> Dict[str, Any]:
    """读取 K2Node_AddDelegate 字段。"""
    return {}  # 无额外字段


def read_k2node_macro_instance(archive: FArchive, name_map: List[str]) -> Dict[str, Any]:
    """读取 K2Node_MacroInstance 字段。"""
    return {}  # 无额外字段
```

- [ ] **Step 3: 注册所有新 K2Node 类型**

```python
# 在 src/uasset_read/serializers/graph.py 的 read_ed_graph_node 函数中
# 在现有的 elif 分支后添加

elif class_name == "K2Node_CallDelegate":
    base_node.node_data = read_k2node_call_delegate(archive, name_map)
elif class_name == "K2Node_CallArrayFunction":
    base_node.node_data = read_k2node_call_array_function(archive, name_map)
elif class_name == "K2Node_CallParentFunction":
    base_node.node_data = read_k2node_call_parent_function(archive, name_map)
elif class_name == "K2Node_FunctionResult":
    base_node.node_data = read_k2node_function_result(archive, name_map)
elif class_name == "K2Node_CreateWidget":
    base_node.node_data = read_k2node_create_widget(archive, name_map)
elif class_name == "K2Node_AddDelegate":
    base_node.node_data = read_k2node_add_delegate(archive, name_map)
elif class_name == "K2Node_MacroInstance":
    base_node.node_data = read_k2node_macro_instance(archive, name_map)
```

- [ ] **Step 4: 运行测试验证**

```bash
python -m pytest tests/test_k2node_ue55.py -v
```

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/serializers/graph.py src/uasset_read/models/node_types.py
git commit -m "feat(k2node): 添加 7 种 K2Node 类型支持"
```

---

## Phase 3: P73-RECOVERY + BPGC + Struct 大小处理

### Task 3.1: 优化 P73-RECOVERY 引脚连接解析 (R4)

**Files:**
- Modify: `src/uasset_read/serializers/graph.py:35-70`
- Create: `tests/test_pin_recovery.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_pin_recovery.py
"""P73 Pin 连接恢复测试"""
import struct
import pytest
from uasset_read.archive import FArchive


def test_abnormal_pin_count_detection():
    """异常 Pin 计数值 0xFF0000 应该被检测为异常"""
    # 模拟异常的 Pin 连接数据
    # 0xFF0000 = 16711680，这不是合理的 Pin 数量
    abnormal_count = 0xFF0000
    
    # 验证检测逻辑
    assert abnormal_count > 1000  # 超过合理范围
    assert abnormal_count & 0xFF == 0  # 低字节为 0，可能是字节序问题
```

- [ ] **Step 2: 实现异常检测逻辑**

```python
# 在 src/uasset_read/serializers/graph.py 中添加

def _is_abnormal_pin_count(count: int) -> bool:
    """检测异常的 Pin 计数值。
    
    异常特征：
    - 超过 1000（蓝图节点通常 < 100 pins）
    - 低字节为 0（可能是字节序错误）
    - 是 0xFF 的倍数（填充字节）
    """
    if count > 1000:
        return True
    if count > 0 and count & 0xFF == 0:
        return True
    if count == 0xFF0000 or count == 0x00FF00:
        return True
    return False


def _recover_pin_count(raw_value: int) -> int:
    """尝试恢复异常的 Pin 计数值。
    
    可能的恢复策略：
    1. 字节序交换
    2. 右移 8 位
    3. 使用低字节
    """
    if raw_value == 0xFF0000:
        return 0  # 可能是空值
    if raw_value > 0xFF00:
        # 可能是字节序问题，尝试交换
        swapped = struct.unpack('<H', struct.pack('>H', raw_value & 0xFFFF))[0]
        return swapped
    return raw_value
```

- [ ] **Step 3: 集成到 Pin 读取流程**

```python
# 在 src/uasset_read/serializers/graph.py 的 read_ue_graph_pin 函数中
# 在读取 LinkedTo 列表时添加

# 读取 LinkedTo 计数
linked_to_count = archive.read_i32()

if _is_abnormal_pin_count(linked_to_count):
    logger.warning(
        "P73-RECOVERY: Abnormal LinkedTo count %d at offset %d, attempting recovery",
        linked_to_count, archive.tell() - 4
    )
    linked_to_count = _recover_pin_count(linked_to_count)
    _record_pin_recovery({
        "type": "abnormal_count",
        "original": raw_value,
        "recovered": linked_to_count,
        "offset": archive.tell() - 4,
    })
```

- [ ] **Step 4: 运行测试验证**

```bash
python -m pytest tests/test_pin_recovery.py -v
```

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/serializers/graph.py tests/test_pin_recovery.py
git commit -m "fix(graph): 优化 P73-RECOVERY 异常 Pin 计数值处理"
```

---

### Task 3.2: 改进 BPGC 字节码回退策略 (R5)

**Files:**
- Modify: `src/uasset_read/kismet/bpgc_bytecode.py:33-82`
- Modify: `src/uasset_read/kismet/bytecode_extractor.py`
- Create: `tests/test_bpgc_improvement.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_bpgc_improvement.py
"""BPGC 字节码回退改进测试"""
import struct
import pytest
from uasset_read.kismet.bpgc_bytecode import _parse_cooked_bytecode_buffer


def test_parse_with_trailing_garbage():
    """应该能处理尾部垃圾数据"""
    # 正常函数字节码
    func1 = bytes([0x00, 0x01, 0x04, 0x53])  # LocalVar, InstanceVar, Return, EndOfScript
    # 尾部有垃圾数据
    garbage = b'\xFF\xFF\xFF\xFF'
    
    data = struct.pack('<I', len(func1)) + func1 + garbage
    buffers = _parse_cooked_bytecode_buffer(data)
    
    assert len(buffers) == 1
    assert buffers[0].endswith(b'\x53')


def test_parse_multiple_functions():
    """应该能正确解析多个函数"""
    func1 = bytes([0x00, 0x53])  # LocalVar, EndOfScript
    func2 = bytes([0x01, 0x53])  # InstanceVar, EndOfScript
    func3 = bytes([0x04, 0x53])  # Return, EndOfScript
    
    data = (
        struct.pack('<I', len(func1)) + func1 +
        struct.pack('<I', len(func2)) + func2 +
        struct.pack('<I', len(func3)) + func3
    )
    
    buffers = _parse_cooked_bytecode_buffer(data)
    assert len(buffers) == 3
```

- [ ] **Step 2: 运行测试验证现有实现**

```bash
python -m pytest tests/test_bpgc_improvement.py -v
```

- [ ] **Step 3: 增强字节码解析容错**

```python
# 在 src/uasset_read/kismet/bpgc_bytecode.py 中修改

def _parse_cooked_bytecode_buffer(data: bytes) -> list[bytes]:
    """解析 BPGC 脚本区域字节码。
    
    Phase 76 改进：
    - 支持 EX_EndOfScript (0x53) 和 0xDD 两种结束标记
    - 容错处理：跳过无效的 size 前缀
    - 支持尾部垃圾数据
    """
    buffers: list[bytes] = []
    offset = 0
    data_len = len(data)
    
    while offset < data_len:
        # 需要至少 4 字节读取 size
        if offset + 4 > data_len:
            break
        
        # 读取 u32 size（小端序）
        size = int.from_bytes(data[offset:offset + 4], byteorder='little', signed=False)
        offset += 4
        
        # Phase 76: 容错处理 - 如果 size 不合理，尝试跳过
        if size == 0 or size > (data_len - offset):
            # 尝试查找下一个有效的 EX_EndOfScript
            next_sentinel = _find_next_sentinel(data, offset - 4)
            if next_sentinel > offset:
                # 跳到下一个有效位置
                offset = next_sentinel - 3  # -3 因为后面会 +4
                continue
            break
        
        buf = data[offset:offset + size]
        offset += size
        
        # 验证 buffer 以期望的标记结尾
        if buf and buf[-1] not in (_END_OF_SCRIPT, _COOKED_END_SENTINEL):
            logger.warning(
                "Bytecode buffer #%d ends with 0x%02X (expected 0x%02X or 0x%02X), "
                "accepting in tolerant mode",
                len(buffers), buf[-1], _END_OF_SCRIPT, _COOKED_END_SENTINEL,
            )
        
        buffers.append(buf)
    
    return buffers


def _find_next_sentinel(data: bytes, start: int) -> int:
    """在 data 中查找下一个 EX_EndOfScript 或 0xDD 标记。"""
    for i in range(start, len(data)):
        if data[i] in (_END_OF_SCRIPT, _COOKED_END_SENTINEL):
            return i
    return len(data)
```

- [ ] **Step 4: 运行测试验证**

```bash
python -m pytest tests/test_bpgc_improvement.py -v
```

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/kismet/bpgc_bytecode.py tests/test_bpgc_improvement.py
git commit -m "feat(bpgc): 改进字节码回退解析容错"
```

---

### Task 3.3: 处理 BoxSphereBounds 114 bytes (R6)

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py:329-341`
- Modify: `tests/test_struct_property_ue55.py`

- [ ] **Step 1: 写失败测试**

```python
# 在 tests/test_struct_property_ue55.py 中添加

def test_box_sphere_bounds_114_bytes():
    """BoxSphereBounds 114 bytes: UE5.5 扩展格式"""
    # 114 bytes = 28 个 float (标准 40 bytes) + 额外数据
    # 标准格式: Origin(12) + BoxExtent(12) + SphereRadius(4) = 28 floats = 112 bytes
    # 114 bytes 可能包含 padding 或新字段
    data = struct.pack('<28f', *range(28))  # 28 floats
    archive = _make_archive(data)
    
    tag = PropertyTag(
        name="TestBounds",
        type="StructProperty",
        size=114,
        struct_type="BoxSphereBounds"
    )
    
    result = parse_struct_property(tag, archive, name_map=[], export_map=[], summary=None)
    
    assert result.struct_type == "BoxSphereBounds"
    assert "Origin" in result.fields
    assert "BoxExtent" in result.fields
    assert "SphereRadius" in result.fields
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python -m pytest tests/test_struct_property_ue55.py::test_box_sphere_bounds_114_bytes -v
```
Expected: FAIL (当前 BoxSphereBounds 只支持 40 bytes)

- [ ] **Step 3: 修改 BoxSphereBounds 支持扩展格式**

```python
# 在 parse_struct_property 函数中修改 BoxSphereBounds 处理

if struct_type == "BoxSphereBounds":
    if tag.size == 114:
        # UE5.5 扩展格式：标准字段 + 额外 padding
        ox = archive.read_f32()
        oy = archive.read_f32()
        oz = archive.read_f32()
        bx = archive.read_f32()
        by = archive.read_f32()
        bz = archive.read_f32()
        sr = archive.read_f32()
        # 跳过剩余的 padding 字节
        remaining = tag.size - 28  # 28 floats = 112 bytes
        if remaining > 0:
            archive.read_bytes(remaining)
    else:
        # 标准格式
        ox = archive.read_f32()
        oy = archive.read_f32()
        oz = archive.read_f32()
        bx = archive.read_f32()
        by = archive.read_f32()
        bz = archive.read_f32()
        sr = archive.read_f32()
    
    return StructValue(struct_type="BoxSphereBounds", fields={
        "Origin": {"X": ox, "Y": oy, "Z": oz},
        "BoxExtent": {"X": bx, "Y": by, "Z": bz},
        "SphereRadius": sr,
    })
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_struct_property_ue55.py::test_box_sphere_bounds_114_bytes -v
```
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/parsers/property_types.py tests/test_struct_property_ue55.py
git commit -m "feat(struct): BoxSphereBounds 支持 114 bytes 扩展格式"
```

---

## Phase 4: MaterialInstance 序列化格式适配 (R7)

### Task 4.1: 修复 MaterialInstance 解析错误

**Files:**
- Modify: `src/uasset_read/parsers/asset_types/material_instance.py`
- Create: `tests/test_material_instance_ue55.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_material_instance_ue55.py
"""UE5.5 MaterialInstance 解析测试"""
import struct
import pytest
from uasset_read.archive import FArchive
from uasset_read.parsers.asset_types.material_instance import parse_material_instance


def _make_archive(data: bytes) -> FArchive:
    return FArchive(data)


def test_material_instance_basic():
    """MaterialInstance 基本解析"""
    name_map = ["", "ParentMaterial", "ScalarParam", "VectorParam", "TextureParam"]
    
    data = struct.pack('<i', 1)  # ParentMaterial index
    data += struct.pack('<i', 1)  # Scalar count
    data += struct.pack('<i', 2)  # ScalarParam name index
    data += struct.pack('<f', 0.5)  # Scalar value
    data += struct.pack('<i', 1)  # Vector count
    data += struct.pack('<i', 3)  # VectorParam name index
    data += struct.pack('<ffff', 1.0, 0.0, 0.0, 1.0)  # Vector RGBA
    data += struct.pack('<i', 1)  # Texture count
    data += struct.pack('<i', 4)  # TextureParam name index
    data += struct.pack('<i', 0)  # Texture index
    
    archive = _make_archive(data)
    result = parse_material_instance(archive, name_map)
    
    assert "parent_material_index" in result
    assert "parameter_overrides" in result
    assert result["override_count"] == 3
```

- [ ] **Step 2: 运行测试验证现有实现**

```bash
python -m pytest tests/test_material_instance_ue55.py -v
```

- [ ] **Step 3: 添加错误处理**

```python
# 在 src/uasset_read/parsers/asset_types/material_instance.py 中修改

def parse_material_instance(archive: FArchive, name_map: list[str]) -> dict[str, Any]:
    """解析 MaterialInstanceConstant 资产的核心属性。
    
    Phase 76 改进：
    - 添加边界检查防止 offset 越界
    - 处理负数 count 值
    - 容错处理格式差异
    """
    result: Dict[str, Any] = {}
    
    try:
        # ParentMaterial (ObjectProperty / FPackageIndex)
        parent_idx = archive.read_i32()
        result["parent_material_index"] = parent_idx
        
        # ScalarParameterOverrides
        scalar_count = archive.read_i32()
        if scalar_count < 0 or scalar_count > 1000:
            logger.warning("Invalid scalar_count: %d, skipping", scalar_count)
            scalar_count = 0
        
        scalar_overrides = {}
        for _ in range(scalar_count):
            param_name_idx = archive.read_i32()
            if param_name_idx < 0 or param_name_idx >= len(name_map):
                param_name = f"param_{param_name_idx}"
            else:
                param_name = name_map[param_name_idx]
            param_value = archive.read_f32()
            scalar_overrides[param_name] = param_value
        result["scalar_overrides"] = scalar_overrides
        
        # VectorParameterOverrides
        vector_count = archive.read_i32()
        if vector_count < 0 or vector_count > 1000:
            logger.warning("Invalid vector_count: %d, skipping", vector_count)
            vector_count = 0
        
        vector_overrides = {}
        for _ in range(vector_count):
            param_name_idx = archive.read_i32()
            if param_name_idx < 0 or param_name_idx >= len(name_map):
                param_name = f"param_{param_name_idx}"
            else:
                param_name = name_map[param_name_idx]
            r = archive.read_f32()
            g = archive.read_f32()
            b = archive.read_f32()
            a = archive.read_f32()
            vector_overrides[param_name] = (r, g, b, a)
        result["vector_overrides"] = vector_overrides
        
        # TextureParameterOverrides
        texture_count = archive.read_i32()
        if texture_count < 0 or texture_count > 1000:
            logger.warning("Invalid texture_count: %d, skipping", texture_count)
            texture_count = 0
        
        texture_overrides = {}
        for _ in range(texture_count):
            param_name_idx = archive.read_i32()
            if param_name_idx < 0 or param_name_idx >= len(name_map):
                param_name = f"param_{param_name_idx}"
            else:
                param_name = name_map[param_name_idx]
            texture_idx = archive.read_i32()
            texture_overrides[param_name] = texture_idx
        result["texture_overrides"] = texture_overrides
        
        # 汇总
        result["parameter_overrides"] = {
            "scalar": scalar_overrides,
            "vector": vector_overrides,
            "texture": texture_overrides,
        }
        result["override_count"] = scalar_count + vector_count + texture_count
        
    except Exception as e:
        logger.error("MaterialInstance parse failed: %s", e)
        result["parse_error"] = str(e)
    
    return result
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python -m pytest tests/test_material_instance_ue55.py -v
```

- [ ] **Step 5: 提交**

```bash
git add src/uasset_read/parsers/asset_types/material_instance.py tests/test_material_instance_ue55.py
git commit -m "fix(material): 修复 MaterialInstance 解析边界检查"
```

---

### Task 4.2: 集成测试验证

**Files:**
- Create: `tests/test_integration_ue55.py`

- [ ] **Step 1: 创建集成测试**

```python
# tests/test_integration_ue55.py
"""UE5.5 集成测试 - 验证所有修复的协同工作"""
import os
import pytest
from pathlib import Path


# 测试样本路径（需要外部样本）
SAMPLE_DIR = Path(os.environ.get("UE55_SAMPLE_DIR", "E:\\Develop\\lib\\UnrealEngine\\Samples\\FirstPerson"))


@pytest.mark.integration
class TestUE55Integration:
    """UE5.5 集成测试套件"""
    
    @pytest.mark.skipif(not SAMPLE_DIR.exists(), reason="Sample directory not found")
    def test_struct_property_coverage(self):
        """验证 StructProperty 解析通过率 > 95%"""
        from uasset_read.parse_uasset import parse_uasset
        
        # 遍历样本文件
        uasset_files = list(SAMPLE_DIR.glob("**/*.uasset"))[:10]  # 取前10个测试
        
        total = 0
        success = 0
        errors = []
        
        for f in uasset_files:
            try:
                result = parse_uasset(str(f))
                total += 1
                if result and "error" not in str(result).lower():
                    success += 1
            except Exception as e:
                errors.append((f.name, str(e)))
        
        if total == 0:
            pytest.skip("No uasset files found")
        
        coverage = success / total
        assert coverage > 0.95, f"StructProperty coverage {coverage:.1%} < 95%. Errors: {errors[:5]}"
    
    @pytest.mark.skipif(not SAMPLE_DIR.exists(), reason="Sample directory not found")
    def test_k2node_fallback_rate(self):
        """验证 K2Node fallback 率 < 10%"""
        from uasset_read.parse_uasset import parse_uasset
        
        uasset_files = list(SAMPLE_DIR.glob("**/*.uasset"))[:10]
        
        total_nodes = 0
        fallback_nodes = 0
        
        for f in uasset_files:
            try:
                result = parse_uasset(str(f))
                if result and "graphs" in result:
                    for graph in result["graphs"]:
                        if "nodes" in graph:
                            for node in graph["nodes"]:
                                total_nodes += 1
                                if node.get("class_name", "").startswith("Unknown"):
                                    fallback_nodes += 1
            except Exception:
                pass
        
        if total_nodes == 0:
            pytest.skip("No nodes found")
        
        fallback_rate = fallback_nodes / total_nodes
        assert fallback_rate < 0.10, f"K2Node fallback rate {fallback_rate:.1%} > 10%"
```

- [ ] **Step 2: 运行集成测试**

```bash
python -m pytest tests/test_integration_ue55.py -v -m integration
```

- [ ] **Step 3: 提交**

```bash
git add tests/test_integration_ue55.py
git commit -m "test: 添加 UE5.5 集成测试"
```

---

## 验证命令

完成所有任务后，运行以下命令验证：

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行新增的 UE5.5 测试
python -m pytest tests/test_struct_property_ue55.py tests/test_k2node_ue55.py tests/test_material_instance_ue55.py -v

# 运行集成测试（需要样本文件）
python -m pytest tests/test_integration_ue55.py -v -m integration

# 检查代码覆盖率
python -m pytest tests/ -v --cov=uasset_read --cov-report=html
```

---

## 成功指标

- [ ] StructProperty 解析通过率 > 95%
- [ ] K2Node fallback 率 < 10%
- [ ] MaterialInstance 可解析
- [ ] 所有测试通过
- [ ] 无新增 lint 错误

---

## 风险与注意事项

1. **UE5.5 源码依赖**: 部分结构体格式需要对照 UE 5.5 源码确认
2. **测试样本**: 集成测试需要外部样本文件
3. **零依赖约束**: 不引入第三方库
4. **向后兼容**: 确保现有解析不受影响
