"""Tests for graph domain extractor."""
from uasset_read.semantic.graph_domain import extract_graph
from uasset_read.models.ir import ExportIR, GraphIR, NodeIR, PinIR, PropertyIR


class TestExtractGraph:
    def test_sound_cue_with_graphs(self):
        graph = GraphIR(
            graph_guid="00000000000000000000000000000001",
            graph_name="SoundCueGraph",
            graph_class="EdGraph",
            nodes=[
                NodeIR(
                    node_guid="0000000000000000000000000000abc1",
                    node_class="SoundCueNode_Mixer",
                    node_comment=None,
                    pins=[
                        PinIR(
                            pin_name="Output",
                            pin_type="exec",
                            linked_to=[],
                            direction="EGPD_Output",
                            default_value=None,
                        ),
                    ],
                    execution_flow=[],
                ),
            ],
            execution_chains=[],
        )
        export = ExportIR(
            index=0,
            object_name="SFX_Explosion",
            object_class="SoundCue",
            serial_size=2048,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class=None,
            properties=[
                PropertyIR(name="VolumeMultiplier", type="FloatProperty", value=0.8, array_index=0, guid=None),
                PropertyIR(name="PitchMultiplier", type="FloatProperty", value=1.0, array_index=0, guid=None),
            ],
            graphs=[graph],
            bulk_data=None,
            asset_type_data={
                "parse_status": "success",
                "first_node": 1,
                "volume_multiplier": 0.8,
                "pitch_multiplier": 1.0,
                "node_count": 3,
            },
        )
        node = extract_graph(export)
        assert node.key == "root"
        children = {c.key: c for c in (node.children or [])}
        assert "class_name" in children
        assert children["class_name"].value == "SoundCue"
        assert "graphs" in children

    def test_material_opaque(self):
        """Material is a graph type but currently opaque -- should still work."""
        export = ExportIR(
            index=1,
            object_name="M_Default",
            object_class="Material",
            serial_size=4096,
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
        node = extract_graph(export)
        children = {c.key: c for c in (node.children or [])}
        assert children["class_name"].value == "Material"
        assert children["parse_status"].value == "partial_metadata"

    def test_no_graphs_no_asset_type_data(self):
        """Graph type with no data should produce minimal output."""
        export = ExportIR(
            index=2,
            object_name="NS_Default",
            object_class="NiagaraSystem",
            serial_size=100,
            outer_index_resolved=None,
            super_index_resolved=None,
            parent_class=None,
            properties=[],
            graphs=[],
            bulk_data=None,
        )
        node = extract_graph(export)
        children = {c.key: c for c in (node.children or [])}
        assert "class_name" in children
        assert "serial_size" in children
