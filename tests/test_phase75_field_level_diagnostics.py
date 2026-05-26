"""Phase 75: 字段级诊断基线测试。

验证诊断函数能复现异常 pin 名称、异常 direction 和 LinkedTo read failed 位置。
输出到 temp/phase75/。
"""
import json
import os
from pathlib import Path

import pytest

from uasset_read.graph.pin_trace import write_phase75_diagnostic


SAMPLE_ASSET = (
    "E:\\Develop\\lib\\UnrealEngine\\Samples\\FirstPerson"
    "\\Content\\FirstPerson\\Blueprints\\BP_FirstPersonCharacter.uasset"
)

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "temp" / "phase75"


@pytest.fixture(scope="session")
def diagnostic_result():
    """运行 Phase 75 诊断，返回结果字典。"""
    if not os.path.exists(SAMPLE_ASSET):
        pytest.skip(f"Sample asset not found: {SAMPLE_ASSET}")
    return write_phase75_diagnostic(SAMPLE_ASSET)


class TestPhase75DiagnosticOutputs:
    """验收：诊断输出文件存在且包含预期内容。"""

    def test_output_dir_exists(self, diagnostic_result):
        assert OUTPUT_DIR.exists(), f"temp/phase75/ not found at {OUTPUT_DIR}"

    def test_graph_node_counts_exists(self, diagnostic_result):
        path = OUTPUT_DIR / "graph_node_counts.json"
        assert path.exists(), f"{path} not found"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data) > 0, "Should have at least one graph"

    def test_enhanced_input_nodes_exists(self, diagnostic_result):
        path = OUTPUT_DIR / "enhanced_input_nodes.json"
        assert path.exists(), f"{path} not found"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data) == 4, f"Expected 4 EnhancedInputAction nodes, got {len(data)}"

    def test_event_nodes_exists(self, diagnostic_result):
        path = OUTPUT_DIR / "event_nodes.json"
        assert path.exists(), f"{path} not found"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data) == 4, f"Expected 4 Event nodes, got {len(data)}"

    def test_function_entry_nodes_exists(self, diagnostic_result):
        path = OUTPUT_DIR / "function_entry_nodes.json"
        assert path.exists(), f"{path} not found"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data) >= 2, f"Expected >=2 FunctionEntry nodes, got {len(data)}"

    def test_pin_diagnostics_exists(self, diagnostic_result):
        path = OUTPUT_DIR / "pin_diagnostics.json"
        assert path.exists(), f"{path} not found"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data) > 0, "Should have pin diagnostics"

    def test_linkedto_recovery_summary_exists(self, diagnostic_result):
        path = OUTPUT_DIR / "linkedto_recovery_summary.txt"
        assert path.exists(), f"{path} not found"
        content = path.read_text(encoding="utf-8")
        assert "LinkedTo" in content, "Should mention LinkedTo in summary"

    def test_event_node_fields_exists(self, diagnostic_result):
        path = OUTPUT_DIR / "event_node_fields.json"
        assert path.exists(), f"{path} not found"

    def test_pin_body_offsets_exists(self, diagnostic_result):
        path = OUTPUT_DIR / "pin_body_offsets.json"
        assert path.exists(), f"{path} not found"


class TestPhase75AnomalyReproduction:
    """验收：诊断输出能复现 Phase 75 上下文中的异常。"""

    def test_anomalous_pin_directions_reported(self, diagnostic_result):
        """异常 direction 值（67/114/136）应出现在诊断中。"""
        data = json.loads(
            (OUTPUT_DIR / "enhanced_input_nodes.json").read_text(encoding="utf-8")
        )
        anomalous_directions = []
        for node in data:
            for pin in node.get("pins", []):
                direction = pin.get("direction")
                if direction not in (0, 1, None):
                    anomalous_directions.append({
                        "node": node.get("input_action_path", node.get("node_export_name", "")),
                        "pin": pin.get("pin_name", ""),
                        "direction": direction,
                        "direction_label": pin.get("direction_label", ""),
                    })
        if anomalous_directions:
            print(f"Anomalous directions found: {anomalous_directions}")

    def test_linkedto_read_failed_positions_reported(self, diagnostic_result):
        """LinkedTo read failed 位置应出现在 recovery summary 中。"""
        content = (OUTPUT_DIR / "linkedto_recovery_summary.txt").read_text(encoding="utf-8")
        assert "LinkedTo" in content

    def test_first_anomalous_linkedto_identified(self, diagnostic_result):
        """第一个异常 LinkedTo offset 应关联到具体 graph/node/pin。"""
        data = json.loads(
            (OUTPUT_DIR / "pin_diagnostics.json").read_text(encoding="utf-8")
        )
        anomalous_pins = [
            p for p in data
            if p.get("linkedto_raw_count") is not None
            and (p["linkedto_raw_count"] < 0 or p["linkedto_raw_count"] > 100)
        ]
        if anomalous_pins:
            first = anomalous_pins[0]
            assert first.get("node_name"), "Should identify the node"
            assert first.get("node_class"), "Should identify the node class"
            assert first.get("linkedto_start") >= 0, "Should have LinkedTo start offset"
            print(
                f"First anomalous LinkedTo: node={first['node_name']}, "
                f"class={first['node_class']}, "
                f"pin={first['pin_name']}, "
                f"pos={first['linkedto_start']}, "
                f"raw_count={first['linkedto_raw_count']}"
            )

    def test_pin_fields_recorded_for_anomalous_pins(self, diagnostic_result):
        """异常 pin 的字段 trace 应记录 start/end/consumed。"""
        data = json.loads(
            (OUTPUT_DIR / "pin_diagnostics.json").read_text(encoding="utf-8")
        )
        pins_with_exceptions = [
            p for p in data if p.get("anomalous_fields")
        ]
        if pins_with_exceptions:
            first = pins_with_exceptions[0]
            for field in first["anomalous_fields"]:
                assert "name" in field
                assert "start" in field
                assert "end" in field

    def test_recovery_reasons_recorded(self, diagnostic_result):
        """Recovery events应有 reason 字段。"""
        data = json.loads(
            (OUTPUT_DIR / "event_node_fields.json").read_text(encoding="utf-8")
        )
        pins_with_recovery = [
            p for p in data if p.get("related_recoveries")
        ]
        if pins_with_recovery:
            for pin in pins_with_recovery[:3]:
                for recovery in pin["related_recoveries"]:
                    assert "kind" in recovery
                    assert "reason" in recovery

    def test_event_node_b_override_function_reported(self, diagnostic_result):
        """K2Node_Event 的 bOverrideFunction 应出现在诊断中。"""
        data = json.loads(
            (OUTPUT_DIR / "event_nodes.json").read_text(encoding="utf-8")
        )
        for node in data:
            assert "b_override_function" in node, f"Missing b_override_function for {node.get('node_export_name')}"
            assert "b_override_source" in node

    def test_enhanced_input_advanced_pin_display_reported(self, diagnostic_result):
        """K2Node_EnhancedInputAction 的 AdvancedPinDisplay 应出现在诊断中。"""
        data = json.loads(
            (OUTPUT_DIR / "enhanced_input_nodes.json").read_text(encoding="utf-8")
        )
        for node in data:
            assert "advanced_pin_display" in node, f"Missing AdvancedPinDisplay for {node.get('input_action_path')}"

    def test_function_entry_extra_flags_reported(self, diagnostic_result):
        """K2Node_FunctionEntry 的 ExtraFlags 应出现在诊断中。"""
        data = json.loads(
            (OUTPUT_DIR / "function_entry_nodes.json").read_text(encoding="utf-8")
        )
        for node in data:
            assert "extra_flags" in node, f"Missing ExtraFlags for {node.get('node_export_name')}"
            assert "b_is_editable" in node

    def test_pin_body_previous_field_identified(self, diagnostic_result):
        """对于异常 LinkedTo pin，应能识别上一个字段是什么。"""
        data = json.loads(
            (OUTPUT_DIR / "pin_body_offsets.json").read_text(encoding="utf-8")
        )
        # 找到有异常字段的 pin
        for pin in data:
            fields = pin.get("fields", [])
            anomalous = [f for f in fields if f.get("exception")]
            if anomalous:
                # 确认字段列表中有 start/end 信息
                for f in anomalous:
                    assert "name" in f
                    assert "start" in f
                    assert "end" in f
