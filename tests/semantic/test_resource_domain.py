"""Tests for resource domain extractor."""
from uasset_read.semantic.resource_domain import extract_resource
from uasset_read.models.ir import ExportIR, PropertyIR


class TestExtractResource:
    def test_texture2d_metadata(self):
        export = ExportIR(
            index=0,
            object_name="T_Default",
            object_class="Texture2D",
            serial_size=2048,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class=None,
            properties=[
                PropertyIR(name="SizeX", type="IntProperty", value=1024, array_index=0, guid=None),
                PropertyIR(name="SizeY", type="IntProperty", value=512, array_index=0, guid=None),
            ],
            graphs=[],
            bulk_data=None,
            asset_type_data={
                "parse_status": "partial_metadata",
                "raw_offset": 100,
                "sample_size": 256,
            },
        )
        node = extract_resource(export)
        assert node.key == "root"
        # Should have metadata children
        children = {c.key: c for c in (node.children or [])}
        assert "class_name" in children
        assert children["class_name"].value == "Texture2D"
        assert "serial_size" in children
        assert children["serial_size"].value == 2048

    def test_sound_wave_metadata(self):
        export = ExportIR(
            index=1,
            object_name="SFX_Click",
            object_class="SoundWave",
            serial_size=4096,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class=None,
            properties=[],
            graphs=[],
            bulk_data=None,
            asset_type_data={
                "parse_status": "partial_metadata",
                "raw_offset": 200,
                "sample_size": 256,
            },
        )
        node = extract_resource(export)
        children = {c.key: c for c in (node.children or [])}
        assert children["class_name"].value == "SoundWave"
        assert children["serial_size"].value == 4096

    def test_opaque_resource(self):
        """Resource with no asset_type_data should still produce metadata."""
        export = ExportIR(
            index=2,
            object_name="T_Unknown",
            object_class="Texture2D",
            serial_size=100,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class=None,
            properties=[],
            graphs=[],
            bulk_data=None,
        )
        node = extract_resource(export)
        assert node.key == "root"
        children = {c.key: c for c in (node.children or [])}
        assert "class_name" in children

    def test_properties_filtered_to_known_keys(self):
        """Only known property names should be included as metadata."""
        export = ExportIR(
            index=3,
            object_name="T_Filtered",
            object_class="Texture2D",
            serial_size=500,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class=None,
            properties=[
                PropertyIR(name="SizeX", type="IntProperty", value=256, array_index=0, guid=None),
                PropertyIR(name="UnknownProp", type="StrProperty", value="foo", array_index=0, guid=None),
                PropertyIR(name="Duration", type="FloatProperty", value=3.5, array_index=0, guid=None),
            ],
            graphs=[],
            bulk_data=None,
        )
        node = extract_resource(export)
        children = {c.key: c for c in (node.children or [])}
        assert "SizeX" in children
        assert "Duration" in children
        assert "UnknownProp" not in children

    def test_asset_type_data_children(self):
        """Asset type data fields should appear as children."""
        export = ExportIR(
            index=4,
            object_name="T_AST",
            object_class="Texture2D",
            serial_size=1024,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class=None,
            properties=[],
            graphs=[],
            bulk_data=None,
            asset_type_data={
                "parse_status": "partial_metadata",
                "raw_offset": 50,
                "sample_size": 128,
            },
        )
        node = extract_resource(export)
        children = {c.key: c for c in (node.children or [])}
        assert children["parse_status"].value == "partial_metadata"
        assert children["raw_offset"].value == 50
        assert children["sample_size"].value == 128

    def test_sorted_output(self):
        """Children should be sorted by key for deterministic output."""
        export = ExportIR(
            index=5,
            object_name="T_Sort",
            object_class="Texture2D",
            serial_size=256,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class=None,
            properties=[
                PropertyIR(name="SizeY", type="IntProperty", value=128, array_index=0, guid=None),
                PropertyIR(name="SizeX", type="IntProperty", value=256, array_index=0, guid=None),
            ],
            graphs=[],
            bulk_data=None,
        )
        node = extract_resource(export)
        keys = [c.key for c in (node.children or [])]
        assert keys == sorted(keys)
