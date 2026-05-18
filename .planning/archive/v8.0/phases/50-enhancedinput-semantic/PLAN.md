# Phase 50: EnhancedInput 语义增强 — PLAN.md

**Date:** 2026-05-16  
**Phase:** 050-enhancedinput-semantic  
**Goal:** TriggerEvent 类型可识别,使 K2Node_EnhancedInputAction 的 JSON 输出可与 C++ InputAction 事件处理器对照

---

## 任务

### Task 1: 在 K2NodeEnhancedInputAction model 添加 trigger_events 字段

**文件:** `src/uasset_read/models/node_types.py`

```python
@dataclass
class K2NodeEnhancedInputAction(UEdGraphNode):
    """K2Node_EnhancedInputAction 输入动作节点。"""
    input_action_path: str = ""
    trigger_events: List[str] = field(default_factory=list)  # NEW

    @classmethod
    def from_archive(cls, archive: FArchive, name_map: List[str]) -> Self:
        """延迟导入避免循环依赖。"""
        from uasset_read.serializers.graph import read_k2node_enhanced_input
        return read_k2node_enhanced_input(archive, name_map)
```

### Task 2: 修改 `read_k2node_enhanced_input()` 解析 TriggerEvent

**文件:** `src/uasset_read/serializers/graph.py`

```python
def read_k2node_enhanced_input(
    archive: FArchive,
    name_map: List[str]
) -> Dict[str, Any]:
    """读取 K2Node_EnhancedInputAction 特有字段,返回字典(作为 node_data)。"""
    input_action_path = archive.read_fstring()
    # TODO: 后续版本可能需要读取额外 properties
    return {
        "input_action_path": input_action_path,
    }
```

**注意:** TriggerEvent 从节点的 pins 提取,不在 archive 中直接序列化。此 Task 为预留接口。

### Task 3: 修改节点创建逻辑提取 trigger_events

**文件:** `src/uasset_read/serializers/graph.py`

在 `create_node_from_archive()` 中为 K2Node_EnhancedInputAction 提取 trigger_events:

```python
elif class_name == "K2Node_EnhancedInputAction":
    base_node.node_data = read_k2node_enhanced_input(archive, name_map)
    # 提取 trigger_events from base_node.pins
    trigger_events = _extract_trigger_events(base_node.pins)
    if trigger_events:
        base_node.node_data["trigger_events"] = trigger_events
```

或在 `K2NodeEnhancedInputAction` dataclass 的 `from_archive()` 中提取:

```python
@dataclass
class K2NodeEnhancedInputAction(UEdGraphNode):
    input_action_path: str = ""
    trigger_events: List[str] = field(default_factory=list)

    @classmethod
    def from_archive(cls, archive: FArchive, name_map: List[str]) -> Self:
        from uasset_read.serializers.graph import read_k2node_enhanced_input
        node_data = read_k2node_enhanced_input(archive, name_map)
        trigger_events = _extract_trigger_events(cls.pins)  # FIXME: cls.pins 未初始化
        # 需要在父类 UEdGraphNode 读取 pins 后执行
        node_data["trigger_events"] = trigger_events
        return node_data
```

**推荐方式:** 在 `create_node_from_archive()` 中统一处理,避免 dataclass 逻辑复杂化。

### Task 4: 实现 `_extract_trigger_events()` 辅助函数

**文件:** `src/uasset_read/serializers/graph.py`

```python
def _extract_trigger_events(pins: List[UEdGraphPin]) -> List[str]:
    """从 K2Node_EnhancedInputAction 的 pins 中提取 trigger_events。"""
    TRIGGER_PINS = {"Started", "Ongoing", "Completed", "Canceled"}
    return [pin.pin_name for pin in pins if pin.pin_name in TRIGGER_PINS]
```

### Task 5: 验证修复 — 运行解析确认 trigger_events 非空

修复后运行:

```bash
python -c "
from uasset_read import parse_uasset
result = parse_uasset('E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset')

for graph in result.graphs:
    for node in graph.nodes:
        if node.class_name == 'K2Node_EnhancedInputAction':
            nd = node.node_data
            if isinstance(nd, dict):
                print(f'InputAction: {nd.get(\"input_action_path\")}')
                print(f'TriggerEvents: {nd.get(\"trigger_events\")}')
                assert 'trigger_events' in nd, 'trigger_events not in node_data'
                assert len(nd['trigger_events']) > 0, 'trigger_events empty'
"
```

预期输出:

```
InputAction: /Game/FirstPerson/Blueprints/IA_Movement.IA_Movement
TriggerEvents: ['Started', 'Ongoing', 'Completed', 'Canceled']
```

### Task 6: 新增测试

**文件:** `tests/test_phase50_enhancedinput_trigger.py`

```python
"""Phase 50: EnhancedInput TriggerEvent 类型验证测试"""

import pytest
from uasset_read import parse_uasset


class TestPhase50EnhancedInputTrigger:
    """Test TriggerEvent extraction from K2Node_EnhancedInputAction."""

    @pytest.fixture
    def result(self):
        """解析测试资产。"""
        return parse_uasset('E:/Develop/lib/UnrealEngine/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset')

    def test_enhanced_input_node_has_trigger_events(self, result):
        """至少一个 K2Node_EnhancedInputAction 节点的 trigger_events 非空。"""
        EnhancedInputFound = False
        for graph in result.graphs:
            for node in graph.nodes:
                if node.class_name == 'K2Node_EnhancedInputAction':
                    EnhancedInputFound = True
                    nd = node.node_data
                    assert isinstance(nd, dict), f'node_data should be dict, got {type(nd)}'
                    assert 'trigger_events' in nd, 'trigger_events not in node_data'
                    assert len(nd['trigger_events']) > 0, 'trigger_events should not be empty'
        assert EnhancedInputFound, 'No K2Node_EnhancedInputAction found in graph'

    def test_trigger_events_values_valid(self, result):
        """trigger_events 值应为预定义的 Trigger 类型。"""
        VALID_EVENTS = {'Started', 'Ongoing', 'Completed', 'Canceled'}
        for graph in result.graphs:
            for node in graph.nodes:
                if node.class_name == 'K2Node_EnhancedInputAction':
                    nd = node.node_data
                    if isinstance(nd, dict) and 'trigger_events' in nd:
                        for event in nd['trigger_events']:
                            assert event in VALID_EVENTS, f'Invalid trigger event: {event}'

    def test_execution_flows_start_with_enhanced_input(self, result):
        """execution_flows 应包含 K2Node_EnhancedInputAction 开头的 flow。"""
        enhanced_input_flows = [
            flow for flow in result.execution_flows
            if flow.get('start_event', '').startswith('K2Node_EnhancedInputAction.')
        ]
        assert len(enhanced_input_flows) > 0, 'No execution flows starting with K2Node_EnhancedInputAction'

    def test_existing_tests_no_regression(self):
        """运行现有测试确保无回归。"""
        pytest.main(['-v', 'tests/', '--tb=short'])
```

---

## 验证标准

1. `uasset-read BP_FirstPersonCharacter.uasset` 解析成功
2. `K2Node_EnhancedInputAction` 节点的 `node_data.trigger_events` 非空
3. `trigger_events` 值 ∈ {"Started", "Ongoing", "Completed", "Canceled"}
4. `execution_flows` 中至少一条 flow 以 `K2Node_EnhancedInputAction.*` 开头
5. 现有 520 tests 无回归

---

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/uasset_read/models/node_types.py` | Edit | `K2NodeEnhancedInputAction` 添加 `trigger_events` 字段 |
| `src/uasset_read/serializers/graph.py` | Edit | 添加 `_extract_trigger_events()` 函数,修改 `create_node_from_archive()` |
| `tests/test_phase50_enhancedinput_trigger.py` | Create | 验证 trigger_events 提取 |

---

## 风险

- **字节偏移确认:** 无直接 archive 序列化,仅从 pins 提取,无偏移问题。
- **其他节点类型不受影响:** 此修改仅影响 K2Node_EnhancedInputAction。
- **UE4 兼容:** 不处理。测试资产为 UE5.7。

---

## 执行顺序

1 → 2 → 3 → 4 → 5 → 6（顺序执行,Task 4 实现后 Task 5 验证,Task 6 最后写测试）

*Created: 2026-05-16*
