"""JSON 渲染器输出测试。"""
from __future__ import annotations

import json
import pytest

from uasset_read.core import parse_single

SAMPLE_TEXTURE = "E:/Develop/lib/Samples/StarterContent/Content/StarterContent/Textures/T_Brick_Clay_New_D.uasset"
SAMPLE_MATERIAL = "E:/Develop/lib/Samples/StarterContent/Content/StarterContent/Materials/M_Rock_Basalt.uasset"
SAMPLE_MESH = "E:/Develop/lib/Samples/StarterContent/Content/StarterContent/Props/SM_Chair.uasset"


class TestJSONRendererExports:
    """验证 JSON 渲染器对不同资产类型 exports 的输出。"""

    def test_json_renderer_includes_non_blueprint_exports(self):
        """非蓝图资产应输出所有 exports"""
        output = json.loads(parse_single(SAMPLE_TEXTURE))
        assert len(output.get("exports", [])) > 0, "非蓝图资产应有 exports"

    def test_json_renderer_object_class_populated(self):
        """exports 的 object_class 应从 class_index 正确解析"""
        output = json.loads(parse_single(SAMPLE_TEXTURE))
        exports = output["exports"]
        assert len(exports) >= 1
        main_export = exports[-1]
        assert main_export["object_class"] == "Texture2D"

    def test_json_renderer_package_name_correct(self):
        """package_name 应正确填充（非 None 字符串）"""
        output = json.loads(parse_single(SAMPLE_TEXTURE))
        pkg = output["summary"]["package_name"]
        assert pkg is not None
        assert pkg != "None"
        assert "T_Brick_Clay_New_D" in pkg

    def test_json_renderer_material_exports(self):
        """Material 资产应有多个 exports 且 object_class 正确"""
        output = json.loads(parse_single(SAMPLE_MATERIAL))
        exports = output["exports"]
        assert len(exports) > 10, f"Material 应有大量 exports，实际 {len(exports)}"
        main_export = next(e for e in exports if e["object_name"] == "M_Rock_Basalt")
        assert main_export["object_class"] == "Material"

    def test_json_renderer_staticmesh_exports(self):
        """StaticMesh 资产应有 exports 且 object_class 正确"""
        output = json.loads(parse_single(SAMPLE_MESH))
        exports = output["exports"]
        assert len(exports) > 0
        main_export = next(e for e in exports if e["object_name"] == "SM_Chair")
        assert main_export["object_class"] == "StaticMesh"

    def test_json_renderer_opaque_export_has_partial_status(self):
        """Opaque 类主 export 应标记 partial_metadata"""
        output = json.loads(parse_single(SAMPLE_TEXTURE))
        main_export = output["exports"][-1]
        assert main_export.get("parse_status") == "partial_metadata"
        assert "opaque_payload" in main_export.get("fallback_reason", "")
