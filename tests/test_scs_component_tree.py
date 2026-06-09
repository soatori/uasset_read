"""SCS 组件树序列化测试 — Issue #70。

验证 SimpleConstructionScript (SCS) 组件树的完整序列化：
- USCS_Node 字段提取（ComponentClass, ComponentTemplate, AttachToName 等）
- 父子关系构建（ChildNodes, ParentComponentOrVariableName）
- 树形结构扁平化输出
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from uasset_read.serializers.object_resources import (
    ObjectExport,
    ObjectImport,
    PackageIndex,
)


# ============================================================================
# Mock 辅助
# ============================================================================

def _make_import(object_name: str, class_name: str = "Class",
                 class_package: str = "/Script/Engine") -> ObjectImport:
    """创建模拟 ObjectImport。"""
    return ObjectImport(
        class_package=class_package,
        class_name=class_name,
        outer_index=PackageIndex(0),
        object_name=object_name,
    )


def _make_export(
    object_name: str,
    class_import_idx: int,
    outer_export_idx: int = -1,
    serial_offset: int = 0,
    serial_size: int = 0,
    properties: List[Any] = None,
) -> ObjectExport:
    """创建模拟 ObjectExport。"""
    export = ObjectExport(
        class_index=PackageIndex(-class_import_idx - 1),  # 负数 = import index
        super_index=PackageIndex(0),
        outer_index=PackageIndex(outer_export_idx + 1) if outer_export_idx >= 0 else PackageIndex(0),
        object_name=object_name,
        object_flags=0,
        serial_size=serial_size,
        serial_offset=serial_offset,
    )
    export.properties = properties or []
    return export


def _make_prop(name: str, value: Any, prop_type: str = "ObjectProperty") -> MagicMock:
    """创建模拟 PropertyValue。"""
    prop = MagicMock()
    prop.name = name
    prop.value = value
    prop.type = prop_type
    return prop


# ============================================================================
# SCS 树提取单元测试
# ============================================================================

class TestExtractScsTree:
    """extract_scs_tree 函数测试。"""

    def test_no_bpgc_export_returns_empty(self):
        """没有 BPGC export 时返回空列表。"""
        from uasset_read.blueprint.component_extractor import extract_scs_tree

        import_map = [_make_import("StaticMeshComponent")]
        # 导出只有组件，没有 BPGC
        export_map = [
            _make_export("MyComponent", 0, properties=[
                _make_prop("RelativeLocation", None, "StructProperty"),
            ]),
        ]

        result = extract_scs_tree(export_map, import_map)
        assert result == []

    def test_bpgc_without_scs_property_returns_empty(self):
        """BPGC 没有 SimpleConstructionScript 属性时返回空。"""
        from uasset_read.blueprint.component_extractor import extract_scs_tree

        import_map = [_make_import("BlueprintGeneratedClass")]
        bpgc = _make_export("MyBlueprint_C", 0, properties=[
            _make_prop("ParentClass", {"type": "import", "object_name": "Actor"}),
        ])
        export_map = [bpgc]

        result = extract_scs_tree(export_map, import_map)
        assert result == []

    def test_bpgc_with_scs_outer_relationship(self):
        """通过 outer 关系找到 SCS export。"""
        from uasset_read.blueprint.component_extractor import (
            extract_scs_tree,
            _find_bpgc_export,
            _find_scs_export_from_bpgc,
        )
        from uasset_read.serializers.object_resources import resolve_class_name

        import_map = [
            _make_import("BlueprintGeneratedClass"),
            _make_import("SceneComponent"),
        ]

        # BPGC export (index 0)
        bpgc = _make_export("MyBlueprint_C", 0, properties=[
            _make_prop("SimpleConstructionScript", PackageIndex(2).index),  # 指向 SCS export
        ])

        # SCS export (index 1), outer 指向 BPGC (index 0)
        scs = _make_export("SimpleConstructionScript", 0, outer_export_idx=0, properties=[
            _make_prop("RootNodes", [PackageIndex(3).index]),  # 指向 SCS_Node
            _make_prop("AllNodes", [PackageIndex(3).index]),
        ])

        # SCS_Node export (index 2), outer 指向 SCS (index 1)
        scs_node = _make_export("SCS_Node_0", 1, outer_export_idx=1, properties=[
            _make_prop("ComponentClass", PackageIndex(-1 - 1).index),  # import index 1 = SceneComponent
            _make_prop("ComponentTemplate", PackageIndex(4).index),  # 指向模板
            _make_prop("AttachToName", "None", "NameProperty"),
            _make_prop("ParentComponentOrVariableName", "", "NameProperty"),
            _make_prop("InternalVariableName", "MyComponent", "NameProperty"),
        ])

        export_map = [bpgc, scs, scs_node]

        # 验证 PackageIndex 工作正常
        assert bpgc.class_index.is_import
        assert bpgc.class_index.to_import_index() == 0
        assert resolve_class_name(bpgc.class_index, import_map, export_map) == "BlueprintGeneratedClass"

        # 验证 outer_index 工作正常
        assert scs.outer_index.is_export
        assert scs.outer_index.to_export_index() == 0

        # 验证辅助函数
        found_bpgc = _find_bpgc_export(export_map, import_map)
        assert found_bpgc is not None, "BPGC should be found"
        assert found_bpgc.object_name == "MyBlueprint_C"

        found_scs = _find_scs_export_from_bpgc(found_bpgc, export_map)
        assert found_scs is not None, "SCS export should be found via outer relationship"
        assert found_scs.object_name == "SimpleConstructionScript"

        result = extract_scs_tree(export_map, import_map)
        assert len(result) >= 1
        assert result[0]["name"] == "SCS_Node_0"
        assert result[0]["class"] == "SceneComponent"
        assert result[0]["variable_name"] == "MyComponent"

    def test_scs_node_component_class_resolution(self):
        """SCS_Node 的 ComponentClass 从 import 正确解析。"""
        from uasset_read.blueprint.component_extractor import _extract_scs_node_info

        import_map = [
            _make_import("StaticMeshComponent"),
        ]
        export_map = []

        node_export = _make_export("SCS_Mesh", 0, properties=[
            _make_prop("ComponentClass", PackageIndex(-1 - 0).index),  # import index 0
            _make_prop("AttachToName", "SocketName", "NameProperty"),
            _make_prop("InternalVariableName", "MeshComp", "NameProperty"),
        ])

        info = _extract_scs_node_info(node_export, export_map, import_map)
        assert info["class"] == "StaticMeshComponent"
        assert info["attach_to"] == "SocketName"
        assert info["variable_name"] == "MeshComp"

    def test_scs_node_with_dict_value_resolution(self):
        """SCS_Node 的 ComponentClass 通过 dict 格式解析。"""
        from uasset_read.blueprint.component_extractor import _extract_scs_node_info

        import_map = []
        export_map = []

        node_export = _make_export("SCS_Audio", 0, properties=[
            _make_prop("ComponentClass", {
                "type": "import",
                "object_name": "AudioComponent",
                "full_name": "/Script/Engine.AudioComponent",
            }),
            _make_prop("ParentComponentOrVariableName", "RootComponent", "NameProperty"),
            _make_prop("bIsParentComponentNative", True, "BoolProperty"),
        ])

        info = _extract_scs_node_info(node_export, export_map, import_map)
        assert info["class"] == "AudioComponent"
        assert info["parent_component"] == "RootComponent"
        assert info["is_parent_native"] is True

    def test_collect_scs_node_exports_by_outer(self):
        """通过 outer 关系收集 SCS_Node 导出。"""
        from uasset_read.blueprint.component_extractor import _collect_scs_node_exports

        import_map = []

    def test_scs_node_variable_guid_extraction(self):
        """Issue #70: SCS_Node 的 VariableGuid 字段解析。"""
        from uasset_read.blueprint.component_extractor import (
            _extract_scs_node_info,
            _extract_guid,
        )

        # 测试 _extract_guid 辅助函数
        assert _extract_guid("A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6") == "A1B2C3D4E5F6G7H8I9J0K1L2M3N4O5P6"
        assert _extract_guid({"value": "abc123"}) == "abc123"
        assert _extract_guid({}) == ""

        # 模拟 StructValue 格式的 FGuid
        struct_value = MagicMock()
        struct_value.fields = {"A": 0x12345678, "B": 0x9ABCDEF0, "C": 0x12345678, "D": 0x9ABCDEF0}
        guid_result = _extract_guid(struct_value)
        assert guid_result == "123456789abcdef0123456789abcdef0"

        # 测试完整节点信息提取
        import_map = []
        export_map = []

        node_export = _make_export("SCS_Mesh", 0, properties=[
            _make_prop("ComponentClass", {
                "type": "import",
                "object_name": "StaticMeshComponent",
                "full_name": "/Script/Engine.StaticMeshComponent",
            }),
            _make_prop("VariableGuid", "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"),
            _make_prop("InternalVariableName", "MyMeshComp", "NameProperty"),
        ])

        info = _extract_scs_node_info(node_export, export_map, import_map)
        assert info["variable_guid"] == "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
        assert info["class"] == "StaticMeshComponent"
        assert info["variable_name"] == "MyMeshComp"

    def test_scs_node_category_name_extraction(self):
        """Issue #70: SCS_Node 的 CategoryName 字段解析（FText）。"""
        from uasset_read.blueprint.component_extractor import (
            _extract_scs_node_info,
            _extract_text,
        )

        # 测试 _extract_text 辅助函数
        assert _extract_text("MyCategory") == "MyCategory"
        assert _extract_text({"SourceString": "Transform"}) == "Transform"
        assert _extract_text({}) == ""

        # 模拟 StructValue 格式的 FText
        struct_value = MagicMock()
        struct_value.fields = {"SourceString": "Rendering"}
        assert _extract_text(struct_value) == "Rendering"

        # 测试完整节点信息提取
        import_map = []
        export_map = []

        node_export = _make_export("SCS_Light", 0, properties=[
            _make_prop("ComponentClass", {
                "type": "import",
                "object_name": "PointLightComponent",
                "full_name": "/Script/Engine.PointLightComponent",
            }),
            _make_prop("CategoryName", {"SourceString": "Lights"}, "StructProperty"),
            _make_prop("InternalVariableName", "PointLight", "NameProperty"),
        ])

        info = _extract_scs_node_info(node_export, export_map, import_map)
        assert info["category_name"] == "Lights"
        assert info["class"] == "PointLightComponent"

    def test_scs_node_metadata_array_extraction(self):
        """Issue #70: SCS_Node 的 MetaDataArray 字段解析。"""
        from uasset_read.blueprint.component_extractor import (
            _extract_scs_node_info,
            _extract_metadata_array,
        )

        # 测试 _extract_metadata_array 辅助函数
        metadata_list = [
            {"MetaDataEntryName": "DisplayName", "MetaDataEntryValue": "My Component"},
            {"MetaDataEntryName": "Tooltip", "MetaDataEntryValue": "This is a tooltip"},
        ]
        result = _extract_metadata_array(metadata_list)
        assert result == {
            "DisplayName": "My Component",
            "Tooltip": "This is a tooltip",
        }
        assert _extract_metadata_array([]) == {}
        assert _extract_metadata_array("not_a_list") == {}

        # 测试完整节点信息提取
        import_map = []
        export_map = []

        node_export = _make_export("SCS_Camera", 0, properties=[
            _make_prop("ComponentClass", {
                "type": "import",
                "object_name": "CameraComponent",
                "full_name": "/Script/Engine.CameraComponent",
            }),
            _make_prop("MetaDataArray", [
                {"MetaDataEntryName": "DisplayName", "MetaDataEntryValue": "Player Camera"},
                {"MetaDataEntryName": "Category", "MetaDataEntryValue": "Viewpoint"},
                {"MetaDataEntryName": "ToolTip", "MetaDataEntryValue": "Main player camera component"},
            ], "ArrayProperty"),
            _make_prop("InternalVariableName", "PlayerCamera", "NameProperty"),
        ])

        info = _extract_scs_node_info(node_export, export_map, import_map)
        assert len(info["metadata"]) == 3
        assert info["metadata"]["DisplayName"] == "Player Camera"
        assert info["metadata"]["Category"] == "Viewpoint"
        assert info["metadata"]["ToolTip"] == "Main player camera component"

    def test_scs_node_complete_fields(self):
        """Issue #70: SCS_Node 所有字段的完整性验证。"""
        from uasset_read.blueprint.component_extractor import _extract_scs_node_info

        import_map = [
            _make_import("SceneComponent"),
        ]
        export_map = []

        node_export = _make_export("SCS_Root", 0, properties=[
            _make_prop("ComponentClass", PackageIndex(-1 - 0).index),
            _make_prop("ComponentTemplate", {
                "type": "import",
                "object_name": "SceneComponent_0",
                "full_name": "/Script/Engine.SceneComponent",
            }),
            _make_prop("AttachToName", "None", "NameProperty"),
            _make_prop("ParentComponentOrVariableName", "", "NameProperty"),
            _make_prop("ParentComponentOwnerClassName", "", "NameProperty"),
            _make_prop("bIsParentComponentNative", False, "BoolProperty"),
            _make_prop("InternalVariableName", "DefaultSceneRoot", "NameProperty"),
            _make_prop("VariableGuid", "00000000000000000000000000000001"),
            _make_prop("CategoryName", {"SourceString": "Default"}, "StructProperty"),
            _make_prop("MetaDataArray", [
                {"MetaDataEntryName": "DisplayName", "MetaDataEntryValue": "Scene Root"},
            ], "ArrayProperty"),
        ])

        info = _extract_scs_node_info(node_export, export_map, import_map)

        # 验证所有字段都存在
        assert info["name"] == "SCS_Root"
        assert info["class"] == "SceneComponent"
        assert info["template"] == "SceneComponent_0"  # 应该被解析
        assert info["attach_to"] == "None"
        assert info["parent_component"] == ""
        assert info["parent_owner_class"] == ""
        assert info["is_parent_native"] is False
        assert info["variable_name"] == "DefaultSceneRoot"
        assert info["variable_guid"] == "00000000000000000000000000000001"
        assert info["category_name"] == "Default"
        assert len(info["metadata"]) == 1
        assert info["metadata"]["DisplayName"] == "Scene Root"
        assert info["children"] == []

    def test_collect_scs_node_exports_by_outer(self):
        """通过 outer 关系收集 SCS_Node 导出。"""
        from uasset_read.blueprint.component_extractor import _collect_scs_node_exports

        import_map = []

        scs_export = _make_export("SimpleConstructionScript", 0)

        # SCS_Node export, outer 指向 SCS
        node1 = _make_export("SCS_Node_0", 0, outer_export_idx=0)
        # 另一个 SCS_Node
        node2 = _make_export("SCS_Node_1", 0, outer_export_idx=0)
        # 不相关的 export
        other = _make_export("SomeOther", 0, outer_export_idx=-1)

        export_map = [scs_export, node1, node2, other]

        result = _collect_scs_node_exports(scs_export, None, export_map, import_map)
        assert len(result) == 2
        names = {n.object_name for n in result}
        assert "SCS_Node_0" in names
        assert "SCS_Node_1" in names

    def test_collect_scs_node_exports_from_properties(self):
        """从 SCS 属性的 RootNodes/AllNodes 收集节点引用。"""
        from uasset_read.blueprint.component_extractor import _collect_scs_node_exports

        import_map = []

        scs_export = _make_export("SimpleConstructionScript", 0)

        node1 = _make_export("SCS_Node_0", 0)
        node2 = _make_export("SCS_Node_1", 0)

        export_map = [scs_export, node1, node2]

        # SCS 属性引用这两个节点
        props = [
            _make_prop("RootNodes", [PackageIndex(1).index, PackageIndex(2).index], "ArrayProperty"),
            _make_prop("AllNodes", [PackageIndex(1).index, PackageIndex(2).index], "ArrayProperty"),
        ]

        result = _collect_scs_node_exports(scs_export, props, export_map, import_map)
        assert len(result) == 2

    def test_build_scs_tree_parent_child(self):
        """构建父子关系树。"""
        from uasset_read.blueprint.component_extractor import _build_scs_tree

        import_map = [
            _make_import("SceneComponent"),
            _make_import("StaticMeshComponent"),
        ]

        # Root node
        root = _make_export("SCS_Root", 0, properties=[
            _make_prop("ComponentClass", PackageIndex(-1 - 0).index),
            _make_prop("InternalVariableName", "RootComponent", "NameProperty"),
            _make_prop("ChildNodes", [PackageIndex(2).index], "ArrayProperty"),
        ])

        # Child node, parent is RootComponent
        child = _make_export("SCS_Mesh", 1, properties=[
            _make_prop("ComponentClass", PackageIndex(-1 - 1).index),
            _make_prop("AttachToName", "Socket", "NameProperty"),
            _make_prop("ParentComponentOrVariableName", "RootComponent", "NameProperty"),
            _make_prop("InternalVariableName", "MeshComponent", "NameProperty"),
        ])

        export_map = [root, child]
        node_exports = [root, child]

        result = _build_scs_tree(node_exports, export_map, import_map)
        assert len(result) == 1  # 只有根节点
        assert result[0]["name"] == "SCS_Root"
        assert len(result[0]["children"]) == 1
        assert result[0]["children"][0]["name"] == "SCS_Mesh"
        assert result[0]["children"][0]["attach_to"] == "Socket"

    def test_empty_scs_returns_empty(self):
        """空 SCS export 返回空列表。"""
        from uasset_read.blueprint.component_extractor import extract_scs_tree

        import_map = [_make_import("BlueprintGeneratedClass")]
        bpgc = _make_export("MyBlueprint_C", 0, properties=[
            _make_prop("SimpleConstructionScript", PackageIndex(1).index),
        ])
        # SCS export 没有节点
        scs = _make_export("SimpleConstructionScript", 0, outer_export_idx=0)

        export_map = [bpgc, scs]

        result = extract_scs_tree(export_map, import_map)
        assert result == []


class TestExtractComponentsExisting:
    """验证 extract_components 原有功能未被破坏。"""

    def test_extract_components_returns_flat_list(self):
        """extract_components 返回扁平组件列表。"""
        from uasset_read.blueprint.component_extractor import extract_components

        import_map = [_make_import("StaticMeshComponent")]
        export = _make_export("MyMesh", 0, properties=[
            _make_prop("RelativeLocation", None, "StructProperty"),
        ])

        result = extract_components([export], import_map)
        assert len(result) == 1
        assert result[0]["name"] == "MyMesh"
        assert "Component" in result[0]["class"]


class TestScsTreeInIR:
    """验证 SCS 树在 IR 中正确传递。"""

    def test_blueprint_ir_has_scs_tree_field(self):
        """BlueprintIR 包含 scs_tree 字段。"""
        from uasset_read.models.ir import BlueprintIR

        bp = BlueprintIR(
            parent_class="Actor",
            functions=[],
            events=[],
            components=[],
            scs_tree=[{"name": "SCS_Root", "class": "SceneComponent"}],
        )
        assert len(bp.scs_tree) == 1
        assert bp.scs_tree[0]["name"] == "SCS_Root"

    def test_blueprint_ir_scs_tree_default_empty(self):
        """BlueprintIR.scs_tree 默认为空列表。"""
        from uasset_read.models.ir import BlueprintIR

        bp = BlueprintIR(
            parent_class="Actor",
            functions=[],
            events=[],
            components=[],
        )
        assert bp.scs_tree == []


class TestJsonRendererScs:
    """验证 JSON 渲染器输出 SCS 树。"""

    def test_blueprint_dict_includes_scs_tree(self):
        """_blueprint_to_dict 包含 scs_tree。"""
        from uasset_read.renderers.json_renderer import JSONRenderer

        renderer = JSONRenderer.__new__(JSONRenderer)
        bp = MagicMock()
        bp.parent_class = "Actor"
        bp.functions = []
        bp.events = []
        bp.components = []
        bp.scs_tree = [{"name": "SCS_Root", "class": "SceneComponent"}]

        d = renderer._blueprint_to_dict(bp)
        assert "scs_tree" in d
        assert len(d["scs_tree"]) == 1

    def test_blueprint_dict_no_scs_tree_if_empty(self):
        """空 scs_tree 时不包含在输出中。"""
        from uasset_read.renderers.json_renderer import JSONRenderer

        renderer = JSONRenderer.__new__(JSONRenderer)
        bp = MagicMock()
        bp.parent_class = "Actor"
        bp.functions = []
        bp.events = []
        bp.components = []
        bp.scs_tree = []

        d = renderer._blueprint_to_dict(bp)
        assert "scs_tree" not in d
