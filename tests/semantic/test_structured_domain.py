"""Tests for structured domain extractor."""
from uasset_read.semantic.structured_domain import extract_structured
from uasset_read.models.ir import ExportIR, PropertyIR


class TestExtractStructured:
    def test_skeleton(self):
        export = ExportIR(
            index=0,
            object_name="SK_Default",
            object_class="Skeleton",
            serial_size=8192,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class=None,
            properties=[
                PropertyIR(
                    name="BoneTree", type="ArrayProperty",
                    value=[{"Name": "root"}], array_index=0, guid=None,
                ),
            ],
            graphs=[],
            bulk_data=None,
            asset_type_data={
                "parse_status": "success",
                "reference_skeleton": {
                    "names": ["root", "spine", "head"],
                    "parents": [-1, 0, 1],
                    "bone_count": 3,
                },
                "retarget_source_count": 0,
            },
        )
        node = extract_structured(export)
        assert node.key == "root"
        children = {c.key: c for c in (node.children or [])}
        assert "class_name" in children
        assert children["class_name"].value == "Skeleton"
        assert "reference_skeleton" in children

    def test_data_table(self):
        export = ExportIR(
            index=1,
            object_name="DT_Config",
            object_class="DataTable",
            serial_size=4096,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class=None,
            properties=[],
            graphs=[],
            bulk_data=None,
            asset_type_data={
                "parse_status": "success",
                "row_count": 42,
                "rows": [{"name": "Row1"}, {"name": "Row2"}],
            },
        )
        node = extract_structured(export)
        children = {c.key: c for c in (node.children or [])}
        assert "row_count" in children
        assert children["row_count"].value == 42

    def test_static_mesh_opaque(self):
        """StaticMesh is opaque -- should still produce metadata."""
        export = ExportIR(
            index=2,
            object_name="SM_Cube",
            object_class="StaticMesh",
            serial_size=16384,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class=None,
            properties=[],
            graphs=[],
            bulk_data=None,
            asset_type_data={
                "parse_status": "partial_metadata",
                "raw_offset": 0,
                "sample_size": 256,
            },
        )
        node = extract_structured(export)
        children = {c.key: c for c in (node.children or [])}
        assert children["class_name"].value == "StaticMesh"
        assert children["serial_size"].value == 16384
