"""字段级 acceptance 测试 — 验证输出内容正确性。"""
import json
import os
import pytest
from uasset_read.core import parse_single

SAMPLES = os.environ.get("UE_ASSET_ROOT", r"E:\Develop\lib\UnrealEngine\Samples")
FIRST_PERSON_BP = os.path.join(
    SAMPLES, "FirstPerson", "Content", "FirstPerson", "Blueprints",
    "BP_FirstPersonCharacter.uasset",
)
_has_bp = os.path.isfile(FIRST_PERSON_BP)


@pytest.mark.skipif(not _has_bp, reason="真实资产不可用")
class TestJsonFieldLevel:
    """JSON 输出字段级断言"""

    def test_json_has_required_sections(self):
        output = parse_single(FIRST_PERSON_BP, format="json", tolerant=True)
        data = json.loads(output)
        assert "summary" in data
        assert "exports" in data
        assert "name_map" in data

    def test_json_summary_has_key_fields(self):
        output = parse_single(FIRST_PERSON_BP, format="json", tolerant=True)
        data = json.loads(output)
        summary = data["summary"]
        assert summary.get("package_name") is not None
        assert summary.get("total_export_count", 0) >= 1
        assert summary.get("total_import_count", 0) >= 1

    def test_json_exports_have_required_fields(self):
        output = parse_single(FIRST_PERSON_BP, format="json", tolerant=True)
        data = json.loads(output)
        for export in data["exports"]:
            assert "object_name" in export
            assert "object_class" in export
            assert "serial_size" in export


@pytest.mark.skipif(not _has_bp, reason="真实资产不可用")
class TestBlueprintTextFieldLevel:
    """blueprint_text 输出字段级断言"""

    def test_contains_event_graph_nodes(self):
        output = parse_single(FIRST_PERSON_BP, format="blueprint_text", tolerant=True)
        assert "Event" in output or "K2Node" in output

    def test_output_not_empty_and_reasonable(self):
        output = parse_single(FIRST_PERSON_BP, format="blueprint_text", tolerant=True)
        assert len(output) > 200


@pytest.mark.skipif(not _has_bp, reason="真实资产不可用")
class TestCppSkeletonFieldLevel:
    """cpp_skeleton 输出字段级断言"""

    def test_contains_class_declaration(self):
        output = parse_single(FIRST_PERSON_BP, format="cpp_skeleton", tolerant=True)
        assert "class" in output.lower()

    def test_contains_function_definitions(self):
        output = parse_single(FIRST_PERSON_BP, format="cpp_skeleton", tolerant=True)
        assert "void" in output


@pytest.mark.skipif(not _has_bp, reason="真实资产不可用")
class TestStatusConsistency:
    """状态一致性"""

    def test_json_status_field_present(self):
        output = parse_single(FIRST_PERSON_BP, format="json", tolerant=True)
        data = json.loads(output)
        assert "status" in data
        status = data["status"]
        assert isinstance(status, dict)
        assert status.get("status") in ("success", "partial", "failed")