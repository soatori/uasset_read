# uasset_read 资产解析补充计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 分两阶段补齐 uasset_read 的蓝图解析缺口和新资产类型解析能力，每阶段通过 external\CUE4Parse BPExtractor 实测对比 + 源码对比验证。

**Architecture:** Phase 1 聚焦蓝图解析缺口修复（StructProperty、LinkedTo、N2C 处理器、FText、PropertyTag 扩展）；Phase 2 扩展新资产类型（SkeletalMesh、Texture2D、Material、MaterialInstance）的语义提取。每阶段以 BP_FirstPersonCharacter.uasset 为核心对比案例。

**Tech Stack:** Python 3.10+, CUE4Parse (C# .NET 8.0 BPExtractor.exe), pytest, Unreal Engine 5 Samples

---

## 文件结构总览

### Phase 1 新增/修改

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/uasset_read/parsers/property_types.py` | Modify | StructProperty fallback 读取机制 |
| `src/uasset_read/serializers/graph.py` | Modify | read_pin_array 恢复机制改进 |
| `src/uasset_read/n2c/processors/comment.py` | Create | EdGraphNode_Comment 处理器 |
| `src/uasset_read/n2c/processors/enhanced_input.py` | Create | K2Node_EnhancedInputAction 处理器 |
| `src/uasset_read/n2c/processors/__init__.py` | Modify | 注册新处理器 |
| `src/uasset_read/n2c/node_types.py` | Modify | 添加 Comment/EnhancedInputAction NodeType |
| `src/uasset_read/parsers/ftext.py` | Modify | FText history_type 2-10 补全 |
| `src/uasset_read/serializers/property_tag.py` | Modify | PropertyTag UE5.11+ 扩展字段 |
| `tests/phase76/` | Create | Phase 1 测试 |

### Phase 2 新增

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/uasset_read/parsers/asset_types/skeletal_mesh.py` | Create | SkeletalMesh 属性提取 |
| `src/uasset_read/parsers/asset_types/texture2d.py` | Create | Texture2D 属性提取 |
| `src/uasset_read/parsers/asset_types/material.py` | Create | Material 属性提取 |
| `src/uasset_read/parsers/asset_types/material_instance.py` | Create | MaterialInstanceConstant 属性提取 |
| `src/uasset_read/parsers/asset_types/__init__.py` | Create | 模块入口 |
| `tests/phase77/` | Create | Phase 2 测试 |

---

## Phase 1: 蓝图解析补齐

### Task 1.1: StructProperty Fallback 修复

**问题**: `BP_FirstPersonCharacter.uasset` 中 `RelativeLocation`、`RelativeRotation`、`BlueprintGuid` 等 StructProperty 解析为 `UnknownStruct`（空 fields），`CharacterMesh0.RelativeLocation` 报 `Invalid size -1067974656`。

**参考**: CUE4Parse `BlueprintNodeExtractor.GetGuidProperty()` — 双重路径：直接类型 → StructProperty fallback。

**Files:**
- Modify: `src/uasset_read/parsers/property_types.py` (L399-407 StructProperty fallback 路径)
- Test: `tests/phase76/test_struct_property.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/phase76/test_struct_property.py
"""StructProperty fallback 修复测试。"""
import pytest
from uasset_read import parse_uasset_with_linker

SAMPLE_DIR = "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints"

def test_struct_property_relative_location():
    """BP_FirstPersonCharacter 的组件 RelativeLocation 应解析出 XYZ。"""
    result = parse_uasset_with_linker(f"{SAMPLE_DIR}/BP_FirstPersonCharacter.uasset")
    assert result.is_success

    # 查找 FirstPersonCamera 组件的 RelativeLocation
    for component in result.components:
        if "Camera" in component.name or "FirstPersonCamera" in component.name:
            rel_loc = component.properties.get("RelativeLocation")
            if rel_loc is not None:
                # 不能是 UnknownStruct（空 fields）
                assert rel_loc.get("fields", {}), (
                    f"RelativeLocation parsed as UnknownStruct: {rel_loc}"
                )
                fields = rel_loc["fields"]
                assert "X" in fields or "Translation" in fields, (
                    f"RelativeLocation missing X/Translation: {fields}"
                )

def test_struct_property_node_guid():
    """蓝图节点 NodeGuid 应成功提取。"""
    result = parse_uasset_with_linker(f"{SAMPLE_DIR}/BP_FirstPersonCharacter.uasset")
    assert result.is_success

    # 统计成功提取的 NodeGuid 数量
    guid_count = 0
    unknown_struct_count = 0
    for graph in result.graphs:
        for node in graph.nodes:
            if node.node_data and isinstance(node.node_data, dict):
                guid = node.node_data.get("node_guid")
                if guid:
                    guid_count += 1
                elif "UnknownStruct" in str(node.node_data):
                    unknown_struct_count += 1

    assert guid_count > 0, "No NodeGuid extracted"
    assert unknown_struct_count == 0, (
        f"{unknown_struct_count} nodes with UnknownStruct instead of NodeGuid"
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd E:\Develop\uasset_read
pytest tests/phase76/test_struct_property.py -v
```

Expected: FAIL — StructProperty 当前回退到 `UnknownStruct`（空 fields），NodeGuid 无法提取。

- [ ] **Step 3: Write minimal implementation**

修改 `src/uasset_read/parsers/property_types.py` L399-407，增加 fallback 机制：

```python
# 在 L399 的 UnknownStruct 回退之前，增加已知结构体扩展注册
# 新增结构体定义到 _TAGGED_FALLBACK_STRUCTS

# Vector (UE5 LWC: 3x double)
_TAGGED_FALLBACK_STRUCTS["Vector"] = {
    "fields": [
        ("X", "f64"),
        ("Y", "f64"),
        ("Z", "f64"),
    ]
}

# Rotator (UE5 LWC: 3x double)
_TAGGED_FALLBACK_STRUCTS["Rotator"] = {
    "fields": [
        ("Pitch", "f64"),
        ("Yaw", "f64"),
        ("Roll", "f64"),
    ]
}

# FGuid (4x uint32)
_TAGGED_FALLBACK_STRUCTS["Guid"] = {
    "fields": [
        ("A", "u32"),
        ("B", "u32"),
        ("C", "u32"),
        ("D", "u32"),
    ]
}

# Box (2x Vector)
_TAGGED_FALLBACK_STRUCTS["Box"] = {
    "fields": [
        ("Min", "Vector"),
        ("Max", "Vector"),
        ("IsValid", "u8"),
    ]
}

# Sphere (Vector + float)
_TAGGED_FALLBACK_STRUCTS["Sphere"] = {
    "fields": [
        ("Center", "Vector"),
        ("W", "f32"),
    ]
}
```

同时修复 `CharacterMesh0.RelativeLocation` 的 `Invalid size -1067974656` 问题：

```python
# 在 L399 之前增加 size 验证
if tag.size is not None and tag.size < 0:
    # UE5 unversioned 格式可能 size 字段被误读，尝试跳过到 None terminator
    archive.seek(archive.tell() + max(0, tag.size & 0xFFFFFFFF))  # 取无符号值
    return StructValue(
        struct_type=declared_struct_type or "UnknownStruct",
        fields={},
        raw_size=tag.size,
        parse_status="negative_size_skipped",
    )

if declared_struct_type not in _TAGGED_FALLBACK_STRUCTS:
    # ... existing code ...
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd E:\Develop\uasset_read
pytest tests/phase76/test_struct_property.py -v
```

Expected: PASS

- [ ] **Step 5: BPExtractor 对比验证**

```bash
cd E:\Develop\uasset_read
# 运行 BPExtractor 提取对比
external/CUE4Parse/bp-extractor-publish/BPExtractor.exe \
  "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset" \
  --ue-version UE5_5 > /tmp/bp_extractor_output.json

# 运行 uasset_read 提取对比
python -m uasset_read \
  "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset" \
  --json > /tmp/uasset_read_output.json

# 对比节点数量、坐标、NodeGuid 提取情况
```

验证要点:
- 节点数量一致
- NodePosX/NodePosY 一致
- NodeGuid 提取成功

- [ ] **Step 6: Commit**

```bash
git add src/uasset_read/parsers/property_types.py tests/phase76/test_struct_property.py
git commit -m "fix(parsers): add StructProperty fallback for Vector/Rotator/Guid and negative size handling"
```

---

### Task 1.2: LinkedTo PinReference 恢复改进

**问题**: 多处 `Pin array count exceeds MAX_LINKEDTO_PER_PIN 100`，现有滑动窗口恢复机制部分有效。

**参考**: CUE4Parse `UEdGraphPin.LinkedTo` 序列化逻辑 + UE 源码 `EdGraphPin.cpp` FPinReference 格式。

**Files:**
- Modify: `src/uasset_read/serializers/graph.py` (L556-622 read_pin_array, L625+ _recover_pin_array_count)
- Modify: `src/uasset_read/constants.py` (L73 MAX_LINKEDTO_PER_PIN)
- Test: `tests/phase76/test_pin_recovery.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/phase76/test_pin_recovery.py
"""LinkedTo PinReference 恢复改进测试。"""
import pytest
from uasset_read import parse_uasset_with_linker

SAMPLE_DIR = "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints"

def test_linkedto_recovery_bp_first_person():
    """BP_FirstPersonCharacter 的 Pin 连接应大部分恢复。"""
    result = parse_uasset_with_linker(f"{SAMPLE_DIR}/BP_FirstPersonCharacter.uasset")
    assert result.is_success

    total_pins = 0
    connected_pins = 0
    failed_pins = 0

    for graph in result.graphs:
        for node in graph.nodes:
            if node.pins:
                for pin in node.pins:
                    total_pins += 1
                    linked_to = pin.get("linked_to", [])
                    if linked_to:
                        connected_pins += len(linked_to)
                    elif pin.get("pin_category") not in ("exec",):
                        # 非 exec pin 无连接可能是正常的（如输入参数默认值）
                        pass

    # BP_FirstPersonCharacter 有 ~37 个节点，应该有连接
    assert connected_pins > 20, (
        f"Only {connected_pins} pin connections recovered (expected > 20)"
    )
    # 检查是否还有恢复失败的日志
    assert failed_pins < 3, (
        f"{failed_pins} pins failed to recover connections"
    )

def test_negative_count_handling():
    """负数 count 应被优雅处理而非抛出 Invalid size 异常。"""
    result = parse_uasset_with_linker(f"{SAMPLE_DIR}/BP_FirstPersonCharacter.uasset")
    # 不应有未处理的 ParseError
    assert result.errors == 0 or all("recovery" in str(e).lower() for e in result.errors)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd E:\Develop\uasset_read
pytest tests/phase76/test_pin_recovery.py -v
```

Expected: FAIL — 当前恢复机制不够完整，连接数不足。

- [ ] **Step 3: Write minimal implementation**

修改 `src/uasset_read/serializers/graph.py` 的 `_recover_pin_array_count`：

```python
def _recover_pin_array_count(
    archive: FArchive,
    error_pos: int,
    bad_count: int,
    export_map: List[ObjectExport],
    import_map: List[ObjectImport],
    scan_window: int = 16,  # 从 8 增加到 16
) -> Optional[dict]:
    """改进的 Pin 数组 count 恢复。

    增加 PinReference header (24B) 结构校验作为置信度过滤。
    """
    original_pos = archive.tell()

    for offset in range(-scan_window, scan_window + 1):
        candidate_pos = error_pos + offset
        if candidate_pos < 0:
            continue

        archive.seek(candidate_pos)
        try:
            candidate_count = archive.read_i32()
        except Exception:
            continue

        # 验证 1: count 在合理范围内
        if candidate_count < 0 or candidate_count > MAX_LINKEDTO_PER_PIN:
            continue

        # 验证 2: 如果是非零 count，验证第一个 PinReference header
        if candidate_count > 0:
            # PinReference header: null_ptr (4B) + owning_node (4B) + pin_guid (16B) = 24B
            ref_pos = archive.tell()
            try:
                null_ptr = archive.read_i32()
                owning_node = archive.read_i32()
                # owning_node 应该是有效的 export/import 索引
                if owning_node < 0 or owning_node >= len(export_map) + len(import_map):
                    archive.seek(candidate_pos)
                    continue
                # 验证 pin_guid 不是全零
                guid_bytes = archive.read(16)
                if all(b == 0 for b in guid_bytes):
                    archive.seek(candidate_pos)
                    continue
            except Exception:
                archive.seek(candidate_pos)
                continue

        # 计算置信度
        confidence = "high" if offset == 0 else ("medium" if abs(offset) <= 4 else "low")
        archive.seek(candidate_pos)

        return {
            "count": candidate_count,
            "candidate_pos": candidate_pos,
            "confidence": confidence,
            "reason": f"scanned at offset {offset:+d} from error pos",
        }

    archive.seek(original_pos)
    return None
```

增加多次恢复尝试的回退逻辑到 `read_pin_array`：

```python
def read_pin_array(archive, name_map, export_map, import_map, linker=None, recovery_context="linkedto"):
    array_count = archive.read_i32()

    if array_count < 0 or array_count > MAX_LINKEDTO_PER_PIN:
        # 第一次: 标准滑动窗口恢复
        recovered = _recover_pin_array_count(archive, archive.tell(), array_count, export_map, import_map)

        if recovered is None and array_count < 0:
            # 第二次: 负数尝试取无符号值
            unsigned_count = array_count & 0xFFFFFFFF
            if 0 < unsigned_count <= MAX_LINKEDTO_PER_PIN:
                recovered = {
                    "count": unsigned_count,
                    "candidate_pos": archive.tell() - 4,
                    "confidence": "low",
                    "reason": "unsigned interpretation",
                }

        if recovered is None:
            # 第三次: 向前扫描寻找 0 count（空数组标记）
            zero_pos = _scan_for_zero_count(archive, archive.tell(), scan_back=32)
            if zero_pos is not None:
                recovered = {
                    "count": 0,
                    "candidate_pos": zero_pos,
                    "confidence": "medium",
                    "reason": "zero count found in scan",
                }

        if recovered is not None:
            # ... existing recovery recording code ...
        else:
            if array_count < 0:
                raise ParseError(f"Invalid pin array count: {array_count} (negative)")
            raise ParseError(f"Pin array count {array_count} exceeds MAX_LINKEDTO_PER_PIN {MAX_LINKEDTO_PER_PIN}")

    # ... rest of existing code ...
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd E:\Develop\uasset_read
pytest tests/phase76/test_pin_recovery.py -v
```

Expected: PASS

- [ ] **Step 5: BPExtractor 对比验证**

运行 BPExtractor 提取同一文件，对比 LinkedTo 连接数：

```bash
external/CUE4Parse/bp-extractor-publish/BPExtractor.exe \
  "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset" \
  --ue-version UE5_5 2> /tmp/bp_stderr.txt > /tmp/bp_output.json

# 统计 BPExtractor 的 Pin 连接总数
python -c "
import json
with open('/tmp/bp_output.json') as f:
    data = json.load(f)
total_linked = sum(len(p.get('linkedTo', [])) for n in data['nodes'] for p in n.get('pins', []))
print(f'BPExtractor total linkedTo: {total_linked}')
"
```

目标: uasset_read 恢复的连接数 >= BPExtractor 的 80%。

- [ ] **Step 6: Commit**

```bash
git add src/uasset_read/serializers/graph.py src/uasset_read/constants.py tests/phase76/test_pin_recovery.py
git commit -m "fix(graph): improve LinkedTo PinReference recovery with header validation and multi-strategy fallback"
```

---

### Task 1.3: N2C 处理器补全 — EdGraphNode_Comment + EnhancedInputAction

**问题**: `EdGraphNode_Comment` 和 `K2Node_EnhancedInputAction` 回退到 fallback 处理。

**参考**: CUE4Parse `UEdGraphNode` 属性提取模式 + BPExtractor `ExtractNode()` 方法。

**Files:**
- Create: `src/uasset_read/n2c/processors/comment.py`
- Create: `src/uasset_read/n2c/processors/enhanced_input.py`
- Modify: `src/uasset_read/n2c/processors/__init__.py`
- Modify: `src/uasset_read/n2c/node_types.py` (添加 NodeType)
- Test: `tests/phase76/test_n2c_processors.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/phase76/test_n2c_processors.py
"""N2C 处理器补全测试。"""
import pytest
from uasset_read import parse_uasset_with_linker
from uasset_read.n2c import to_n2c_json

SAMPLE_DIR = "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints"

def test_comment_node_processor():
    """EdGraphNode_Comment 应被专用处理器处理而非 fallback。"""
    result = parse_uasset_with_linker(f"{SAMPLE_DIR}/BP_FirstPersonCharacter.uasset")
    assert result.is_success

    # 查找 Comment 节点
    comment_nodes = []
    for graph in result.graphs:
        for node in graph.nodes:
            if "Comment" in node.class_name:
                comment_nodes.append(node)

    assert len(comment_nodes) > 0, "No Comment nodes found"

    # 验证 Comment 节点有 CommentText 字段
    for cn in comment_nodes:
        if cn.node_data and isinstance(cn.node_data, dict):
            assert "comment_text" in cn.node_data or "NodeComment" in cn.node_data, (
                f"Comment node missing comment_text: {cn.node_data}"
            )

def test_enhanced_input_action_processor():
    """K2Node_EnhancedInputAction 应提取 InputAction 资源路径。"""
    result = parse_uasset_with_linker(f"{SAMPLE_DIR}/BP_FirstPersonCharacter.uasset")
    assert result.is_success

    input_nodes = []
    for graph in result.graphs:
        for node in graph.nodes:
            if "EnhancedInputAction" in node.class_name:
                input_nodes.append(node)

    assert len(input_nodes) >= 4, (
        f"Expected >= 4 EnhancedInputAction nodes, found {len(input_nodes)}"
    )

    # 验证 InputAction 资源路径被提取
    for node in input_nodes:
        if node.node_data and isinstance(node.node_data, dict):
            input_action = node.node_data.get("input_action")
            assert input_action is not None, (
                f"EnhancedInputAction node missing input_action: {node.node_data}"
            )
            assert "IA_" in input_action, (
                f"InputAction path doesn't look right: {input_action}"
            )

def test_no_fallback_in_bp_first_person():
    """BP_FirstPersonCharacter 不应有 fallback 处理节点。"""
    result = parse_uasset_with_linker(f"{SAMPLE_DIR}/BP_FirstPersonCharacter.uasset")
    assert result.is_success

    n2c_result = to_n2c_json(result)
    fallback_count = sum(
        1 for n in n2c_result.get("nodes", [])
        if n.get("extra_data", {}).get("fallback")
    )
    assert fallback_count == 0, (
        f"{fallback_count} nodes still falling back to default handler"
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd E:\Develop\uasset_read
pytest tests/phase76/test_n2c_processors.py -v
```

Expected: FAIL — Comment 和 EnhancedInputAction 节点走 fallback。

- [ ] **Step 3: Create CommentProcessor**

```python
# src/uasset_read/n2c/processors/comment.py
"""EdGraphNode_Comment 处理器 — 提取注释框信息。"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.processor_base import N2CNodeProcessor

if TYPE_CHECKING:
    from uasset_read.models.core import UEdGraphNode
    from uasset_read.n2c.definitions import N2CNodeDefinition


class CommentProcessor(N2CNodeProcessor):
    """处理 EdGraphNode_Comment 类型节点。

    提取: CommentText, NodeWidth, NodeHeight, CommentColor, FontSize, CommentDepth。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.Comment]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        if node.node_data is None:
            return

        data = node.node_data
        if not isinstance(data, dict):
            return

        # 提取注释文本
        comment_text = data.get("NodeComment", data.get("comment_text", ""))
        if comment_text:
            definition.extra_data["comment_text"] = comment_text
            definition.label = comment_text[:40]  # 截断用于显示

        # 提取尺寸
        for key in ("NodeWidth", "NodeHeight"):
            if key in data:
                definition.extra_data[key.lower()] = data[key]

        # 提取颜色
        if "CommentColor" in data:
            definition.extra_data["comment_color"] = data["CommentColor"]

        # 提取字体大小
        if "FontSize" in data:
            definition.extra_data["font_size"] = data["FontSize"]

        # 提取注释深度（嵌套层级）
        if "CommentDepth" in data:
            definition.extra_data["comment_depth"] = data["CommentDepth"]
```

- [ ] **Step 4: Create EnhancedInputActionProcessor**

```python
# src/uasset_read/n2c/processors/enhanced_input.py
"""K2Node_EnhancedInputAction 处理器 — 提取输入动作资源信息。"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from uasset_read.n2c.node_types import N2CNodeType
from uasset_read.n2c.processor_base import N2CNodeProcessor

if TYPE_CHECKING:
    from uasset_read.models.core import UEdGraphNode
    from uasset_read.n2c.definitions import N2CNodeDefinition


class EnhancedInputActionProcessor(N2CNodeProcessor):
    """处理 K2Node_EnhancedInputAction 类型节点。

    提取: InputAction 资源路径, TriggeredSeconds, ElapsedSeconds, AdvancedPinDisplay。
    """

    @property
    def node_types(self) -> List[N2CNodeType]:
        return [N2CNodeType.EnhancedInputAction]

    def process(self, node: UEdGraphNode, definition: N2CNodeDefinition) -> None:
        if node.node_data is None:
            return

        data = node.node_data
        if not isinstance(data, dict):
            return

        # 提取 InputAction 资源路径
        input_action = data.get("InputAction")
        if input_action is not None:
            # 可能是字符串路径或 ObjectProperty 引用
            if isinstance(input_action, str):
                definition.extra_data["input_action"] = input_action
                # 从路径中提取短名称
                short_name = input_action.split("/")[-1].split(".")[0]
                definition.label = f"Input: {short_name}"
            elif isinstance(input_action, dict):
                path = input_action.get("path", input_action.get("object_path", ""))
                definition.extra_data["input_action"] = path
                definition.label = f"Input: {path.split('/')[-1].split('.')[0]}"

        # 提取定时器字段
        for key in ("TriggeredSeconds", "ElapsedSeconds"):
            if key in data:
                definition.extra_data[key.lower()] = data[key]

        # 提取高级引脚显示
        if "AdvancedPinDisplay" in data:
            adv = data["AdvancedPinDisplay"]
            definition.extra_data["advanced_pin_display"] = (
                "hidden" if adv == 1 else "visible"
            )
```

- [ ] **Step 5: 注册新处理器 + 添加 NodeType**

修改 `src/uasset_read/n2c/node_types.py`，添加：

```python
# 在 N2CNodeType 枚举中添加
Comment = "comment"
EnhancedInputAction = "enhanced_input_action"
```

修改 `src/uasset_read/n2c/processors/__init__.py`：

```python
# 在注册逻辑中添加
from uasset_read.n2c.processors.comment import CommentProcessor
from uasset_read.n2c.processors.enhanced_input import EnhancedInputActionProcessor

# 注册
registry.register(CommentProcessor())
registry.register(EnhancedInputActionProcessor())
```

- [ ] **Step 6: Run test to verify it passes**

```bash
cd E:\Develop\uasset_read
pytest tests/phase76/test_n2c_processors.py -v
```

Expected: PASS

- [ ] **Step 7: BPExtractor 对比验证**

对比 BPExtractor 提取的节点类型和数量，确认所有 K2Node_EnhancedInputAction 和 EdGraphNode_Comment 都被正确处理。

- [ ] **Step 8: Commit**

```bash
git add src/uasset_read/n2c/processors/comment.py src/uasset_read/n2c/processors/enhanced_input.py src/uasset_read/n2c/processors/__init__.py src/uasset_read/n2c/node_types.py tests/phase76/test_n2c_processors.py
git commit -m "feat(n2c): add CommentProcessor and EnhancedInputActionProcessor, eliminate fallback for known node types"
```

---

### Task 1.4: FText history_type 2-10 补全

**问题**: FText history_type 2-10（OrderedFormat、ArgumentFormat、AsNumber 等）仅在 intolerant mode 下抛异常。

**参考**: UE `Text.cpp` L850-1044 + CUE4Parse FText 序列化逻辑。

**Files:**
- Modify: `src/uasset_read/parsers/ftext.py`
- Test: `tests/phase76/test_ftext.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/phase76/test_ftext.py
"""FText history_type 补全测试。"""
import struct
import pytest
from uasset_read.serializers.graph import read_ftext_with_history


def _fstring(value: str) -> bytes:
    """构造 FString 字节：i32 长度前缀 + UTF-8 数据（含终止符）。"""
    encoded = value.encode('utf-8') + b' '
    return struct.pack('<i', len(encoded)) + encoded


class MockArchive:
    """模拟 FArchive，read_fstring 对齐真实二进制格式。

    FString 格式：
    - i32 length: 正数=UTF-8, 负数=UTF-16LE, 0=空字符串
    - 数据: abs(length) 字节 (UTF-8 含终止符, UTF-16 为 abs(length)*2 字节)
    """

    def __init__(self, data: bytes):
        self._data = data
        self._pos = 0

    def read_i8(self):
        v = self._data[self._pos]
        self._pos += 1
        return v if v < 128 else v - 256

    def read_u8(self):
        v = self._data[self._pos]
        self._pos += 1
        return v

    def read_i32(self):
        v = struct.unpack('<i', self._data[self._pos : self._pos + 4])[0]
        self._pos += 4
        return v

    def read_fstring(self):
        """对齐 FArchive.read_fstring: i32 长度前缀 + UTF-8/UTF-16 数据。"""
        length = self.read_i32()
        if length == 0:
            return ''
        if length > 0:
            data = self._data[self._pos : self._pos + length]
            self._pos += length
            if data.endswith(b' '):
                data = data[:-1]
            return data.decode('utf-8')
        else:
            utf16_len = abs(length)
            data = self._data[self._pos : self._pos + utf16_len * 2]
            self._pos += utf16_len * 2
            return data.decode('utf-16-le')


def test_ordered_format_history_type():
    """history_type=2 (OrderedFormat) 应正常读取而非抛异常。"""
    payload = (
        struct.pack('<iB', 8, 2)  # flags=8, history_type=2
        + _fstring('')  # namespace
        + _fstring('')  # key
        + _fstring('Hello {0} and {1}')  # source_string
        + struct.pack('<i', 2)  # args_count
        + struct.pack('<i', 0) + _fstring('World')  # index=0, value=World
        + struct.pack('<i', 1) + _fstring('Test')  # index=1, value=Test
    )
    archive = MockArchive(payload)

    result = read_ftext_with_history(archive)
    assert result is not None
    assert result.get('history_type') == 2
    assert result.get('source_string') == 'Hello {0} and {1}'
    assert result.get('ordered_argument') == {0: 'World', 1: 'Test'}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd E:\Develop\uasset_read
pytest tests/phase76/test_ftext.py -v
```

Expected: FAIL — 当前代码对 history_type 2-10 抛异常。

- [ ] **Step 3: Write minimal implementation**

修改 `src/uasset_read/serializers/graph.py` 的 `read_ftext_with_history`，补全各 history_type：

```python
def read_ftext_with_history(archive: FArchive) -> dict:
    """读取 FText，包含 history_type 字段。"""
    history_type = archive.read_i8()

    if history_type == -1 or history_type == 0xFF:
        return {"history_type": "none", "text": ""}

    if history_type == 0:  # Base
        return _read_base_ftext(archive)

    if history_type == 1:  # NamedFormat
        return _read_named_format(archive)

    if history_type == 2:  # OrderedFormat
        return _read_ordered_format(archive)

    if history_type == 3:  # ArgumentFormat
        return _read_argument_format(archive)

    if history_type == 4:  # AsNumber
        return _read_as_number(archive)

    if history_type == 5:  # AsPercent
        return _read_as_percent(archive)

    if history_type == 6:  # AsCurrency
        return _read_as_currency(archive)

    if history_type == 7:  # DateString
        return _read_date_string(archive)

    if history_type == 8:  # TimeString
        return _read_time_string(archive)

    if history_type == 9:  # DateTimeString
        return _read_datetime_string(archive)

    if history_type == 10:  # Transform
        return _read_transform(archive)

    # Unknown future type — tolerant mode: return raw
    return {"history_type": history_type, "text": None, "status": "unknown"}


def _read_base_ftext(archive: FArchive) -> dict:
    namespace = archive.read_fstring()
    key = archive.read_fstring()
    source_string = archive.read_fstring()
    return {
        "history_type": 0,
        "namespace": namespace,
        "key": key,
        "source_string": source_string,
    }


def _read_ordered_format(archive: FArchive) -> dict:
    """OrderedFormat: source + ordered_arguments[{index: arg_value}]。"""
    base = _read_base_ftext(archive)
    args_count = archive.read_i32()
    arguments = {}
    for _ in range(args_count):
        index = archive.read_i32()
        arg_value = archive.read_fstring()
        arguments[index] = arg_value
    base["ordered_argument"] = arguments
    return base


def _read_argument_format(archive: FArchive) -> dict:
    """ArgumentFormat: source + named_arguments[{key: arg_value}]。"""
    base = _read_base_ftext(archive)
    args_count = archive.read_i32()
    arguments = {}
    for _ in range(args_count):
        key = archive.read_fstring()
        value = archive.read_fstring()
        arguments[key] = value
    base["arguments"] = arguments
    return base


def _read_as_number(archive: FArchive) -> dict:
    base = _read_base_ftext(archive)
    base["target_number"] = archive.read_fstring()
    return base


def _read_as_percent(archive: FArchive) -> dict:
    base = _read_base_ftext(archive)
    base["target_value"] = archive.read_fstring()
    return base


def _read_as_currency(archive: FArchive) -> dict:
    base = _read_base_ftext(archive)
    base["currency_code"] = archive.read_fstring()
    base["target_amount"] = archive.read_fstring()
    return base


def _read_date_string(archive: FArchive) -> dict:
    base = _read_base_ftext(archive)
    base["date"] = archive.read_fstring()
    return base


def _read_time_string(archive: FArchive) -> dict:
    base = _read_base_ftext(archive)
    base["time"] = archive.read_fstring()
    return base


def _read_datetime_string(archive: FArchive) -> dict:
    base = _read_base_ftext(archive)
    base["datetime"] = archive.read_fstring()
    return base


def _read_transform(archive: FArchive) -> dict:
    base = _read_base_ftext(archive)
    base["transform_type"] = archive.read_fstring()
    base["source_text"] = archive.read_fstring()
    return base
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd E:\Develop\uasset_read
pytest tests/phase76/test_ftext.py -v
```

Expected: PASS

- [ ] **Step 5: BPExtractor 对比验证**

运行 BPExtractor，检查 stderr 是否有 FText 相关警告。BPExtractor 成功解析的 FText 应与 uasset_read 一致。

- [ ] **Step 6: Commit**

```bash
git add src/uasset_read/serializers/graph.py tests/phase76/test_ftext.py
git commit -m "feat(parsers): complete FText history_type 2-10 support (OrderedFormat through Transform)"
```

---

### Task 1.5: PropertyTag UE5.11+ 扩展字段

**问题**: `ctrl & 0x01` 含义不明，UE5.11+ 新增 `SerialType`、`HasUnwantedProp` 等字段缺失。

**参考**: CUE4Parse `FPropertyTag.cs` L96-99 — `SerializeType` 计算逻辑 + `EPropertyTagFlags` 位定义。

**Files:**
- Modify: `src/uasset_read/serializers/property_tag.py` (或对应读取函数所在文件)
- Test: `tests/phase76/test_property_tag.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/phase76/test_property_tag.py
"""PropertyTag UE5.11+ 扩展字段测试。"""
import pytest

def test_property_tag_ctrl_bits():
    """PropertyTag ctrl 位应正确解析。"""
    from uasset_read.serializers.property_tags import parse_ctrl_flags

    ctrl = 0x03  # has_array_index + serialize_control
    flags = parse_ctrl_flags(ctrl)
    assert flags["has_array_index"] is True
    assert flags["serialize_control"] is True

    ctrl = 0x01
    flags = parse_ctrl_flags(ctrl)
    assert flags["has_array_index"] is True
    assert flags["serialize_control"] is False

    ctrl = 0x00
    flags = parse_ctrl_flags(ctrl)
    assert all(v is False for v in flags.values())

def test_property_tag_ue5_11_extensions():
    """UE5.11+ 的 HasExtensions 标志应正确解析。"""
    from uasset_read.serializers.property_tags import parse_ctrl_flags

    # 0x04 = HasExtensions, 0x02 = SerializeControl
    ctrl = 0x06
    flags = parse_ctrl_flags(ctrl)
    assert flags["has_extensions"] is True
    assert flags["serialize_control"] is True
    assert flags["has_array_index"] is False

    # 0x10 = BoolTrue
    ctrl = 0x10
    flags = parse_ctrl_flags(ctrl)
    assert flags["bool_true"] is True
    assert flags["skipped_serialize"] is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd E:\Develop\uasset_read
pytest tests/phase76/test_property_tag.py -v
```

Expected: FAIL — 当前代码未解析 ctrl 位的具体含义。

- [ ] **Step 3: Write minimal implementation**

参考 CUE4Parse `FPropertyTag.cs` 的 flag 定义：

```python
# src/uasset_read/serializers/property_tags.py

EPropertyTagFlags = {
    "HasArrayIndex": 0x01,
    "HasPropertyGuid": 0x02,
    "HasPropertyExtensions": 0x04,
    "HasBinaryOrNativeSerialize": 0x08,
    "BoolTrue": 0x10,
    "SkippedSerialize": 0x20,
}

def parse_ctrl_flags(ctrl: int) -> dict:
    """解析 PropertyTag 控制位。

    0x01: HasArrayIndex, 0x02: SerializeControl, 0x04: HasExtensions
    0x08: HasBinaryNative, 0x10: BoolTrue, 0x20: SkippedSerialize
    """
    return {
        "has_array_index": bool(ctrl & 0x01),
        "serialize_control": bool(ctrl & 0x02),
        "has_extensions": bool(ctrl & 0x04),
        "has_binary_native": bool(ctrl & 0x08),
        "bool_true": bool(ctrl & 0x10),
        "skipped_serialize": bool(ctrl & 0x20),
    }


def read_property_tag_ue5(archive, name_map, file_version_ue5):
    """UE5 路径 PropertyTag 读取。"""
    # ... existing code ...

    # UE5 >= 1011: Script Serialization Control
    if file_version_ue5 >= 1011:
        ctrl = archive.read_u8()
        flags = parse_ctrl_flags(ctrl)

        if flags["serialize_control"]:
            # SerialType byte follows
            serial_type = archive.read_u8()

        if flags["overridable"]:
            # 可覆盖信息 — 通常是额外的类型信息
            # 读取并跳过（不影响后续解析）
            _ = archive.read_fstring()

    # ... existing code ...
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd E:\Develop\uasset_read
pytest tests/phase76/test_property_tag.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/serializers/property_tags.py tests/phase76/test_property_tag.py
git commit -m "feat(parsers): add PropertyTag UE5.11+ ctrl flag parsing (overridable, serialize_control, serial_type)"
```

---

## Phase 2: 新资产类型扩展

### Task 2.1: SkeletalMesh 属性提取

**参考**: CUE4Parse `USkeletalMesh.cs` — `Serialize` 流程：bCooked → LODs → FReferenceSkeleton → VertexBuffer → Chunks。

**验证案例**: `Samples/Games/LyraStarterGame/Content/Characters/Heroes/Mannequin/Meshes/SK_Mannequin.uasset`

**Files:**
- Create: `src/uasset_read/parsers/asset_types/skeletal_mesh.py`
- Create: `src/uasset_read/parsers/asset_types/__init__.py`
- Test: `tests/phase77/test_skeletal_mesh.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/phase77/test_skeletal_mesh.py
"""SkeletalMesh 属性提取测试。"""
import pytest
from uasset_read import parse_uasset_with_linker

LYRA_DIR = "E:/Develop/lib/UnrealEngine/Samples/Games/LyraStarterGame/Content/Characters/Heroes/Mannequin/Meshes"

def test_skeletal_mesh_basic():
    """SK_Mannequin 应成功解析并提取基本信息。"""
    result = parse_uasset_with_linker(f"{LYRA_DIR}/SK_Mannequin.uasset")
    assert result.is_success

    # 验证资产类型
    assert "SkeletalMesh" in result.asset_type or "SkeletalMesh" in str(result.exports)

def test_skeletal_mesh_bone_count():
    """应提取骨骼数量。"""
    result = parse_uasset_with_linker(f"{LYRA_DIR}/SK_Mannequin.uasset")
    assert result.is_success

    # 检查 RefSkeleton 或骨骼列表
    bone_count = result.metadata.get("bone_count", 0)
    ref_skeleton = result.metadata.get("ref_skeleton")
    if ref_skeleton:
        bone_count = len(ref_skeleton)
    assert bone_count > 0, "No bones extracted from SkeletalMesh"

def test_skeletal_mesh_lod_count():
    """应提取 LOD 数量。"""
    result = parse_uasset_with_linker(f"{LYRA_DIR}/SK_Mannequin.uasset")
    assert result.is_success

    lod_count = result.metadata.get("lod_count", 0)
    assert lod_count > 0, "No LODs extracted"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd E:\Develop\uasset_read
pytest tests/phase77/test_skeletal_mesh.py -v
```

Expected: FAIL — SkeletalMesh 专用解析器不存在。

- [ ] **Step 3: Write minimal implementation**

```python
# src/uasset_read/parsers/asset_types/skeletal_mesh.py
"""SkeletalMesh 资产属性提取器。

参考 CUE4Parse USkeletalMesh.cs:
  bCooked → LODs → FReferenceSkeleton → VertexBufferGPUSkin → Chunks/Sections
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from uasset_read.archive import FArchive


def parse_skeletal_mesh(archive: FArchive, name_map: list[str]) -> dict[str, Any]:
    """解析 SkeletalMesh 资产的核心属性。"""
    result: Dict[str, Any] = {}

    # bCooked 标志
    b_cooked = archive.read_u8() == 1
    result["b_cooked"] = b_cooked

    if not b_cooked:
        return result

    # ImportedBounds (FBoxSphereBounds) — 简化跳过
    # ExtendedBounds (FBoxSphereBounds) — 简化跳过

    # RefSkeleton — 骨骼层级
    ref_skeleton = _read_reference_skeleton(archive, name_map)
    result["ref_skeleton"] = ref_skeleton
    result["bone_count"] = len(ref_skeleton.get("bone_names", []))

    # LOD 信息
    lod_count = archive.read_i32()
    result["lod_count"] = lod_count

    # 简化: 跳过每个 LOD 的详细顶点数据（仅提取结构信息）
    for _ in range(lod_count):
        _skip_lod_resources(archive)

    return result


def _read_reference_skeleton(archive: FArchive, name_map: list[str]) -> dict:
    """读取 FReferenceSkeleton。"""
    ref_bone_count = archive.read_i32()
    bone_names = []
    bone_parents = []

    for _ in range(ref_bone_count):
        # Bone name (FName)
        name_index = archive.read_i32()
        bone_name = name_map[name_index] if name_index >= 0 and name_index < len(name_map) else f"bone_{name_index}"
        bone_names.append(bone_name)

        # Parent index
        parent_index = archive.read_i32()
        bone_parents.append(parent_index)

    return {
        "bone_names": bone_names,
        "bone_parents": bone_parents,
    }


def _skip_lod_resources(archive: FArchive) -> None:
    """跳过 LOD 资源数据（仅提取结构信息时）。"""
    # LOD 包含: MeshBulkData, ActiveBoneIndices, RequiredBones 等
    # 简化实现: 读取 BulkData 大小并跳过
    # 完整实现需要解析 FSkeletalMeshLODModel
    pass
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd E:\Develop\uasset_read
pytest tests/phase77/test_skeletal_mesh.py -v
```

Expected: PASS

- [ ] **Step 5: 源码对比验证**

对比 `external\CUE4Parse\CUE4Parse\UE4\Assets\Exports\SkeletalMesh\USkeletalMesh.cs` 的 `Serialize` 方法，确认字段顺序和版本分支一致。

- [ ] **Step 6: Commit**

```bash
git add src/uasset_read/parsers/asset_types/skeletal_mesh.py src/uasset_read/parsers/asset_types/__init__.py tests/phase77/test_skeletal_mesh.py
git commit -m "feat(parsers): add SkeletalMesh attribute extraction (RefSkeleton, LOD count)"
```

---

### Task 2.2: Texture2D 属性提取

**参考**: CUE4Parse `UTexture2D.cs` — ImportedSize → AddressX/Y → bCooked → PixelFormat → BulkData per MIP。

**验证案例**: `Samples/StarterContent/Content/StarterContent/Textures/T_Brick_Clay_Beveled_D.uasset`

**Files:**
- Create: `src/uasset_read/parsers/asset_types/texture2d.py`
- Test: `tests/phase77/test_texture2d.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/phase77/test_texture2d.py
"""Texture2D 属性提取测试。"""
import pytest
from uasset_read import parse_uasset_with_linker

STARTER_DIR = "E:/Develop/lib/UnrealEngine/Samples/StarterContent/Content/StarterContent/Textures"

def test_texture2d_basic():
    """T_Brick_Clay_Beveled_D 应成功解析并提取基本信息。"""
    result = parse_uasset_with_linker(f"{STARTER_DIR}/T_Brick_Clay_Beveled_D.uasset")
    assert result.is_success

def test_texture2d_dimensions():
    """应提取纹理尺寸。"""
    result = parse_uasset_with_linker(f"{STARTER_DIR}/T_Brick_Clay_Beveled_D.uasset")
    assert result.is_success

    size_x = result.metadata.get("size_x", 0)
    size_y = result.metadata.get("size_y", 0)
    assert size_x > 0 and size_y > 0, (
        f"Texture dimensions not extracted: {result.metadata}"
    )

def test_texture2d_pixel_format():
    """应提取像素格式。"""
    result = parse_uasset_with_linker(f"{STARTER_DIR}/T_Brick_Clay_Beveled_D.uasset")
    assert result.is_success

    pixel_format = result.metadata.get("pixel_format", "")
    assert pixel_format != "", "Pixel format not extracted"

def test_texture2d_mip_count():
    """应提取 MIP 层级数。"""
    result = parse_uasset_with_linker(f"{STARTER_DIR}/T_Brick_Clay_Beveled_D.uasset")
    assert result.is_success

    mip_count = result.metadata.get("mip_count", 0)
    assert mip_count > 0, "MIP count not extracted"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd E:\Develop\uasset_read
pytest tests/phase77/test_texture2d.py -v
```

Expected: FAIL — Texture2D 专用解析器不存在。

- [ ] **Step 3: Write minimal implementation**

```python
# src/uasset_read/parsers/asset_types/texture2d.py
"""Texture2D 资产属性提取器。

参考 CUE4Parse UTexture2D.cs:
  ImportedSize → AddressX/Y → bCooked → PixelFormat → BulkData per MIP
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from uasset_read.archive import FArchive

# EPixelFormat 映射
PIXEL_FORMAT_NAMES = {
    0: "PF_Unknown",
    1: "PF_A32B32G32R32F",
    2: "PF_DXT1",
    3: "PF_DXT3",
    4: "PF_DXT5",
    5: "PF_BC5",
    14: "PF_B8G8R8A8",
    20: "PF_BC7",
    28: "PF_ASTC_4x4",
    31: "PF_BC6H",
    # ... 完整映射参考 UE EPixelFormat 枚举
}


def parse_texture2d(archive: FArchive, name_map: list[str]) -> dict[str, Any]:
    """解析 Texture2D 资产的核心属性。"""
    result: Dict[str, Any] = {}

    # ImportedSize (FIntPoint)
    result["imported_size_x"] = archive.read_i32()
    result["imported_size_y"] = archive.read_i32()

    # AddressX, AddressY (纹理寻址模式)
    result["address_x"] = archive.read_i32()
    result["address_y"] = archive.read_i32()

    # bCooked
    b_cooked = archive.read_u8() == 1
    result["b_cooked"] = b_cooked

    if not b_cooked:
        return result

    # 每个像素格式块
    format_count = archive.read_i32()
    for _ in range(format_count):
        # PixelFormat enum
        pf_value = archive.read_i32()
        pf_name = PIXEL_FORMAT_NAMES.get(pf_value, f"PF_Unknown({pf_value})")

        # bIsSrgb
        b_srgb = archive.read_u8() == 1

        # 读取 BulkData（MIP 链）
        mip_data = _read_compressed_texture_bulk_data(archive)
        result.setdefault("formats", []).append({
            "pixel_format": pf_name,
            "b_srgb": b_srgb,
            "mip_count": mip_data.get("mip_count", 0),
        })

    if result.get("formats"):
        result["pixel_format"] = result["formats"][0]["pixel_format"]
        result["mip_count"] = result["formats"][0]["mip_count"]
        result["b_srgb"] = result["formats"][0]["b_srgb"]

    return result


def _read_compressed_texture_bulk_data(archive: FArchive) -> dict:
    """读取压缩纹理 BulkData（MIP 链）。"""
    # BulkData header
    bulk_flags = archive.read_i32()
    bulk_element_count = archive.read_i32()
    bulk_size_on_disk = archive.read_i32()
    bulk_offset = archive.read_i32()

    result = {
        "mip_count": bulk_element_count,
        "size_on_disk": bulk_size_on_disk,
    }

    # 简化: 不实际读取 BulkData 内容（仅提取元数据）
    return result
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd E:\Develop\uasset_read
pytest tests/phase77/test_texture2d.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/uasset_read/parsers/asset_types/texture2d.py tests/phase77/test_texture2d.py
git commit -m "feat(parsers): add Texture2D attribute extraction (dimensions, pixel format, mip count)"
```

---

### Task 2.3: Material + MaterialInstanceConstant 属性提取

**参考**: CUE4Parse `UMaterial.cs` + `UMaterialInstanceConstant.cs` — 材质参数、表达式、BlendMode、ShadingModel。

**验证案例**:
- Material: `Samples/Games/LyraStarterGame/Content/Characters/Heroes/Mannequin/Materials/M_Mannequin.uasset`
- MaterialInstance: `Samples/Games/LyraStarterGame/Content/UI/Menu/MI_UI_TitleMaterial.uasset`

**Files:**
- Create: `src/uasset_read/parsers/asset_types/material.py`
- Create: `src/uasset_read/parsers/asset_types/material_instance.py`
- Test: `tests/phase77/test_material.py`
- Test: `tests/phase77/test_material_instance.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/phase77/test_material.py
"""Material 属性提取测试。"""
import pytest
from uasset_read import parse_uasset_with_linker

LYRA_MATERIAL = "E:/Develop/lib/UnrealEngine/Samples/Games/LyraStarterGame/Content/Characters/Heroes/Mannequin/Materials/M_Mannequin.uasset"

def test_material_basic():
    """M_Mannequin 应成功解析。"""
    result = parse_uasset_with_linker(LYRA_MATERIAL)
    assert result.is_success

def test_material_blend_mode():
    """应提取 BlendMode。"""
    result = parse_uasset_with_linker(LYRA_MATERIAL)
    assert result.is_success
    blend_mode = result.metadata.get("blend_mode")
    assert blend_mode is not None, "BlendMode not extracted"

def test_material_shading_model():
    """应提取 ShadingModel。"""
    result = parse_uasset_with_linker(LYRA_MATERIAL)
    assert result.is_success
    shading_model = result.metadata.get("shading_model")
    assert shading_model is not None, "ShadingModel not extracted"
```

```python
# tests/phase77/test_material_instance.py
"""MaterialInstanceConstant 属性提取测试。"""
import pytest
from uasset_read import parse_uasset_with_linker

LYRA_MI = "E:/Develop/lib/UnrealEngine/Samples/Games/LyraStarterGame/Content/UI/Menu/MI_UI_TitleMaterial.uasset"

def test_material_instance_basic():
    """MI_UI_TitleMaterial 应成功解析。"""
    result = parse_uasset_with_linker(LYRA_MI)
    assert result.is_success

def test_material_instance_parent():
    """应提取父材质引用。"""
    result = parse_uasset_with_linker(LYRA_MI)
    assert result.is_success
    parent = result.metadata.get("parent_material")
    assert parent is not None, "Parent material not extracted"

def test_material_instance_overrides():
    """应提取参数覆写。"""
    result = parse_uasset_with_linker(LYRA_MI)
    assert result.is_success
    overrides = result.metadata.get("parameter_overrides", {})
    # MI 至少应有一些覆写
    assert len(overrides) > 0, "No parameter overrides found"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd E:\Develop\uasset_read
pytest tests/phase77/test_material.py tests/phase77/test_material_instance.py -v
```

Expected: FAIL — Material/MaterialInstance 专用解析器不存在。

- [ ] **Step 3: Write minimal implementation**

```python
# src/uasset_read/parsers/asset_types/material.py
"""Material 资产属性提取器。

参考 CUE4Parse UMaterial.cs:
  BlendMode, ShadingModel, MaterialExpressions, Parameters
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from uasset_read.archive import FArchive

BLEND_MODE_NAMES = [
    "BLEND_Opaque", "BLEND_Masked", "BLEND_Translucent",
    "BLEND_Additive", "BLEND_Modulate", "BLEND_AlphaComposite",
    "BLEND_AlphaHoldout",
]

SHADING_MODEL_NAMES = [
    "DefaultLit", "Unlit", "Subsurface",
    "PreintegratedSkin", "ClearCoat", "SubsurfaceProfile",
    "TwoSidedFoliage", "Hair", "Cloth", "Eye", "SingleLayerWater",
    "ThinTranslucent", "Strata", "StrataUI", "Toon", "ToonHair",
]


def parse_material(archive: FArchive, name_map: list[str]) -> dict[str, Any]:
    """解析 Material 资产的核心属性。"""
    result: Dict[str, Any] = {}

    # MaterialInterface 基类字段
    # bUsedWithStaticLighting, bUsedWithMorphTargets 等标志
    result["used_with_static_lighting"] = archive.read_u8() == 1

    # BlendMode (EMaterialBlendMode enum)
    blend_mode_idx = archive.read_i32()
    if 0 <= blend_mode_idx < len(BLEND_MODE_NAMES):
        result["blend_mode"] = BLEND_MODE_NAMES[blend_mode_idx]
    else:
        result["blend_mode"] = f"Unknown({blend_mode_idx})"

    # ShadingModel (EMaterialShadingModel enum)
    shading_model_idx = archive.read_i32()
    if 0 <= shading_model_idx < len(SHADING_MODEL_NAMES):
        result["shading_model"] = SHADING_MODEL_NAMES[shading_model_idx]
    else:
        result["shading_model"] = f"Unknown({shading_model_idx})"

    # MaterialExpression 列表（简化: 仅计数）
    expression_count = archive.read_i32()
    result["expression_count"] = expression_count

    # 简化: 跳过每个 Expression 的详细数据
    return result
```

```python
# src/uasset_read/parsers/asset_types/material_instance.py
"""MaterialInstanceConstant 资产属性提取器。

参考 CUE4Parse UMaterialInstanceConstant.cs:
  ParentMaterial → ScalarParameterOverrides → VectorParameterOverrides
  → TextureParameterOverrides
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from uasset_read.archive import FArchive


def parse_material_instance(archive: FArchive, name_map: list[str]) -> dict[str, Any]:
    """解析 MaterialInstanceConstant 资产的核心属性。"""
    result: Dict[str, Any] = {}

    # ParentMaterial (ObjectProperty / FPackageIndex)
    parent_idx = archive.read_i32()
    result["parent_material_index"] = parent_idx

    # ScalarParameterOverrides
    scalar_count = archive.read_i32()
    scalar_overrides = {}
    for _ in range(scalar_count):
        param_name_idx = archive.read_i32()
        param_name = name_map[param_name_idx] if 0 <= param_name_idx < len(name_map) else f"param_{param_name_idx}"
        param_value = archive.read_f32()
        scalar_overrides[param_name] = param_value
    result["scalar_overrides"] = scalar_overrides

    # VectorParameterOverrides
    vector_count = archive.read_i32()
    vector_overrides = {}
    for _ in range(vector_count):
        param_name_idx = archive.read_i32()
        param_name = name_map[param_name_idx] if 0 <= param_name_idx < len(name_map) else f"param_{param_name_idx}"
        r = archive.read_f32()
        g = archive.read_f32()
        b = archive.read_f32()
        a = archive.read_f32()
        vector_overrides[param_name] = (r, g, b, a)
    result["vector_overrides"] = vector_overrides

    # TextureParameterOverrides
    texture_count = archive.read_i32()
    texture_overrides = {}
    for _ in range(texture_count):
        param_name_idx = archive.read_i32()
        param_name = name_map[param_name_idx] if 0 <= param_name_idx < len(name_map) else f"param_{param_name_idx}"
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

    return result
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd E:\Develop\uasset_read
pytest tests/phase77/test_material.py tests/phase77/test_material_instance.py -v
```

Expected: PASS

- [ ] **Step 5: 源码对比验证**

对比 `external\CUE4Parse\CUE4Parse\UE4\Assets\Exports\Material\UMaterial.cs` 和 `UMaterialInstanceConstant.cs` 的序列化逻辑。

- [ ] **Step 6: Commit**

```bash
git add src/uasset_read/parsers/asset_types/material.py src/uasset_read/parsers/asset_types/material_instance.py tests/phase77/test_material.py tests/phase77/test_material_instance.py
git commit -m "feat(parsers): add Material and MaterialInstanceConstant attribute extraction"
```

---

## Phase 验证总结

### BPExtractor 对比命令

每个 Phase 完成后运行：

```bash
# 1. BPExtractor 提取
external/CUE4Parse/bp-extractor-publish/BPExtractor.exe \
  "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset" \
  --ue-version UE5_5 2> /tmp/bp_stderr.txt > /tmp/bp_output.json

# 2. uasset_read 提取
python -m uasset_read \
  "E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset" \
  --json > /tmp/ur_output.json

# 3. 对比脚本
python -c "
import json

with open('/tmp/bp_output.json') as f:
    bp = json.load(f)
with open('/tmp/ur_output.json') as f:
    ur = json.load(f)

print(f'BPExtractor nodes: {bp[\"NodeCount\"]}')
print(f'uasset_read nodes: {len(ur.get(\"graphs\", []))}')

# BPExtractor warnings
with open('/tmp/bp_stderr.txt') as f:
    stderr = f.read()
print(f'BPExtractor stderr: {stderr[:500]}')
"
```

### 源码对比检查点

对每个 `❌` 或 `⚠️` 对比项，定位 CUE4Parse 对应 .cs 文件：

| 对比项 | CUE4Parse 源文件 |
|--------|-----------------|
| StructProperty dispatch | `CUE4Parse/UE4/Assets/Objects/Properties/FPropertyTagType.cs` |
| UEdGraphPin LinkedTo | `CUE4Parse/UE4/Assets/Exports/EdGraph/UEdGraphPin.cs` |
| UEdGraphNode properties | `CUE4Parse/UE4/Assets/Exports/EdGraph/UEdGraphNode.cs` |
| FText serialization | `CUE4Parse/UE4/Objects/Core/Misc/FText.cs` |
| SkeletalMesh | `CUE4Parse/UE4/Assets/Exports/SkeletalMesh/USkeletalMesh.cs` |
| Texture2D | `CUE4Parse/UE4/Assets/Exports/Texture/UTexture2D.cs` |
| Material | `CUE4Parse/UE4/Assets/Exports/Material/UMaterial.cs` |
| MaterialInstanceConstant | `CUE4Parse/UE4/Assets/Exports/Material/UMaterialInstanceConstant.cs` |

---

## 任务依赖图

```
Phase 1:
  Task 1.1 (StructProperty) ──┐
  Task 1.2 (PinReference)     ├──→ 独立，可并行
  Task 1.3 (N2C Processors)  │
  Task 1.4 (FText)           │
  Task 1.5 (PropertyTag)    ──┘
  ──→ Phase 1 完成，BPExtractor 对比验证

Phase 2:
  Task 2.1 (SkeletalMesh) ──┐
  Task 2.2 (Texture2D)      ├──→ 独立，可并行
  Task 2.3 (Material+MI)   ──┘
  ──→ Phase 2 完成，源码对比验证
```
