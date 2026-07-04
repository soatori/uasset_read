"""动画蓝图 IR Builder 单元测试"""
import pytest
from unittest.mock import MagicMock
from uasset_read.ir_builder import _build_export_ir
from uasset_read.models.ir import AnimBlueprintIR, AnimSequenceIR, AnimMontageIR, BakedStateMachineIR


class TestAnimIRBuilder:
    def test_anim_blueprint_ir_attached(self):
        """AnimBlueprintIR 应该附加到 ExportIR"""
        export = MagicMock()
        export.object_name = "TestAnimBP"
        export.class_index = MagicMock()
        export.class_index.index = 0
        export.super_index = MagicMock()
        export.super_index.index = -1
        export.outer_index = MagicMock()
        export.outer_index.index = -1
        export.template_index = MagicMock()
        export.template_index.index = -1
        export.object_flags = 0
        export.serial_size = 100
        export.serial_offset = 0
        export.package_flags = 0
        export.b_forced_export = False
        export.b_not_for_client = False
        export.b_not_for_server = False
        export.b_is_inherited_instance = False
        export.b_not_always_loaded_for_editor_game = True
        export.b_is_asset = True
        export.b_generate_public_hash = False
        export.script_serialization_start_offset = 0
        export.properties = []
        export.graphs = []
        export.bulk_data_header = None
        export._asset_type_data = None
        export.parse_status = "success"
        export.fallback_reason = None
        export.error_message = None
        export.custom_data = {
            "anim_blueprint": AnimBlueprintIR(
                baked_state_machines=[BakedStateMachineIR(machine_name="Locomotion")]
            )
        }

        result = MagicMock()
        result.blueprint = None
        result.import_map = []
        result.export_map = []

        ir = _build_export_ir(0, export, result)
        assert hasattr(ir, "anim_blueprint")
        assert ir.anim_blueprint is not None
        assert len(ir.anim_blueprint.baked_state_machines) == 1
        assert ir.anim_blueprint.baked_state_machines[0].machine_name == "Locomotion"

    def test_anim_sequence_ir_attached(self):
        """AnimSequenceIR 应该附加到 ExportIR"""
        export = MagicMock()
        export.object_name = "TestAnimSeq"
        export.class_index = MagicMock()
        export.class_index.index = 0
        export.super_index = MagicMock()
        export.super_index.index = -1
        export.outer_index = MagicMock()
        export.outer_index.index = -1
        export.template_index = MagicMock()
        export.template_index.index = -1
        export.object_flags = 0
        export.serial_size = 100
        export.serial_offset = 0
        export.package_flags = 0
        export.b_forced_export = False
        export.b_not_for_client = False
        export.b_not_for_server = False
        export.b_is_inherited_instance = False
        export.b_not_always_loaded_for_editor_game = True
        export.b_is_asset = True
        export.b_generate_public_hash = False
        export.script_serialization_start_offset = 0
        export.properties = []
        export.graphs = []
        export.bulk_data_header = None
        export._asset_type_data = None
        export.parse_status = "success"
        export.fallback_reason = None
        export.error_message = None
        export.custom_data = {
            "anim_sequence": AnimSequenceIR(
                target_skeleton="/Game/Skeletons/SK_Hero",
                sequence_length=10.0,
            )
        }

        result = MagicMock()
        result.blueprint = None
        result.import_map = []
        result.export_map = []

        ir = _build_export_ir(0, export, result)
        assert hasattr(ir, "anim_sequence")
        assert ir.anim_sequence is not None
        assert ir.anim_sequence.target_skeleton == "/Game/Skeletons/SK_Hero"

    def test_anim_montage_ir_attached(self):
        """AnimMontageIR 应该附加到 ExportIR"""
        export = MagicMock()
        export.object_name = "TestAnimMontage"
        export.class_index = MagicMock()
        export.class_index.index = 0
        export.super_index = MagicMock()
        export.super_index.index = -1
        export.outer_index = MagicMock()
        export.outer_index.index = -1
        export.template_index = MagicMock()
        export.template_index.index = -1
        export.object_flags = 0
        export.serial_size = 100
        export.serial_offset = 0
        export.package_flags = 0
        export.b_forced_export = False
        export.b_not_for_client = False
        export.b_not_for_server = False
        export.b_is_inherited_instance = False
        export.b_not_always_loaded_for_editor_game = True
        export.b_is_asset = True
        export.b_generate_public_hash = False
        export.script_serialization_start_offset = 0
        export.properties = []
        export.graphs = []
        export.bulk_data_header = None
        export._asset_type_data = None
        export.parse_status = "success"
        export.fallback_reason = None
        export.error_message = None
        export.custom_data = {
            "anim_montage": AnimMontageIR(
                sync_group="DefaultSlot",
                rate_scale=1.5,
                composite_sections=[{"section_name": "Section1", "next_section_name": "Section2"}],
                slot_anim_tracks=[{"slot_node_name": "DefaultSlot"}],
                branching_point_markers=[{"notify_index": 0, "trigger_time": 0.5}],
                blend_in_option="Linear",
                blend_out_option="Linear",
                float_curve_names=["Curve1", "Curve2"],
            )
        }

        result = MagicMock()
        result.blueprint = None
        result.import_map = []
        result.export_map = []

        ir = _build_export_ir(0, export, result)
        assert hasattr(ir, "anim_montage")
        assert ir.anim_montage is not None
        assert ir.anim_montage.sync_group == "DefaultSlot"
        assert ir.anim_montage.rate_scale == 1.5
        assert len(ir.anim_montage.composite_sections) == 1
        assert ir.anim_montage.composite_sections[0]["section_name"] == "Section1"
        assert len(ir.anim_montage.slot_anim_tracks) == 1
        assert ir.anim_montage.slot_anim_tracks[0]["slot_node_name"] == "DefaultSlot"
        assert len(ir.anim_montage.branching_point_markers) == 1
        assert ir.anim_montage.branching_point_markers[0]["trigger_time"] == 0.5
        assert ir.anim_montage.blend_in_option == "Linear"
        assert ir.anim_montage.blend_out_option == "Linear"
        assert len(ir.anim_montage.float_curve_names) == 2
        assert ir.anim_montage.float_curve_names == ["Curve1", "Curve2"]
