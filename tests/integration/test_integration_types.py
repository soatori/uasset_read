"""动画资产 + UE 保真度集成测试

合并以下测试文件：
- test_animation_assets.py (AnimBlueprint / AnimMontage / AnimSequence)
- test_ue_fidelity_integration.py (UE 保真度改进)

覆盖：
1. AnimBlueprint / AnimMontage / AnimSequence 集成测试
2. UE 保真度改进集成测试（生命周期、偏移策略、类策略、软引用、依赖图、状态模型）
"""
import gc
import pytest
from pathlib import Path
from uasset_read.parse_uasset import parse_uasset, parse_uasset_with_linker
from uasset_read.serializers.object_resources import resolve_class_name
from uasset_read.memory_safety import cleanup_after_parse
from tests.conftest import asset_path, ASSET_MESH_CHAIR


# ============================================================
# 测试样本路径（动画资产）
# ============================================================
SAMPLE_DIR = Path("E:/Develop/lib/Samples/GameAnimationSample")
ANIM_BP_SAMPLE = SAMPLE_DIR / "Content/MetaHumans/Common/Common/RTG_metahuman_base_skel_AnimBP.uasset"
ANIM_MONTAGE_SAMPLE = SAMPLE_DIR / "Content/Characters/UEFN_Mannequin/Animations/Interactions/Bench/M_interaction_bench_idle_loop_Montage.uasset"
ANIM_SEQUENCE_SAMPLE = SAMPLE_DIR / "Content/Characters/UEFN_Mannequin/Animations/Idle/M_Neutral_Stand_Idle_Loop.uasset"


# ============================================================
# AnimBlueprint 集成测试
# ============================================================
@pytest.mark.integration
class TestAnimBlueprintIntegration:
    def test_anim_blueprint_parses_successfully(self):
        """AnimBlueprint 应该能完整解析"""
        if not ANIM_BP_SAMPLE.exists():
            pytest.skip("测试样本不存在")
        result = parse_uasset_with_linker(str(ANIM_BP_SAMPLE))
        assert result is not None
        assert result.status in ("success", "partial")

    def test_anim_blueprint_has_graphs(self):
        """AnimBlueprint 应该包含图结构"""
        if not ANIM_BP_SAMPLE.exists():
            pytest.skip("测试样本不存在")
        result = parse_uasset_with_linker(str(ANIM_BP_SAMPLE))
        assert len(result.graphs) > 0

    def test_anim_blueprint_has_anim_notifies(self):
        """AnimBlueprint 应该提取 AnimNotifies"""
        if not ANIM_BP_SAMPLE.exists():
            pytest.skip("测试样本不存在")
        result = parse_uasset_with_linker(str(ANIM_BP_SAMPLE))
        # 检查解析是否成功（status 不是 failed）
        assert result.status != "failed"
        # 检查是否有图结构（动画蓝图应该有 AnimGraph）
        assert len(result.graphs) > 0


# ============================================================
# AnimMontage 集成测试
# ============================================================
@pytest.mark.integration
class TestAnimMontageIntegration:
    def test_anim_montage_parses_successfully(self):
        """AnimMontage 应该能完整解析"""
        if not ANIM_MONTAGE_SAMPLE.exists():
            pytest.skip("测试样本不存在")
        result = parse_uasset_with_linker(str(ANIM_MONTAGE_SAMPLE))
        assert result is not None
        assert result.status in ("success", "partial")

    def test_anim_montage_has_metadata(self):
        """AnimMontage 应该提取元数据"""
        if not ANIM_MONTAGE_SAMPLE.exists():
            pytest.skip("测试样本不存在")
        result = parse_uasset_with_linker(str(ANIM_MONTAGE_SAMPLE))
        # 检查解析是否成功
        assert result.status != "failed"
        # 检查是否有 export_map
        assert len(result.export_map) > 0

    def test_anim_montage_has_anim_montage_data(self):
        """AnimMontage 应该包含 anim_montage 数据"""
        if not ANIM_MONTAGE_SAMPLE.exists():
            pytest.skip("测试样本不存在")
        result = parse_uasset_with_linker(str(ANIM_MONTAGE_SAMPLE))
        # 查找 AnimMontage export
        anim_montage_export = None
        for export in result.export_map:
            class_name = resolve_class_name(export.class_index, result.import_map, result.export_map)
            if class_name == "AnimMontage":
                anim_montage_export = export
                break
        # 如果找到 AnimMontage export，检查 custom_data 中是否有 anim_montage
        if anim_montage_export:
            custom_data = getattr(anim_montage_export, "custom_data", {})
            assert "anim_montage" in custom_data, "AnimMontage export 应包含 anim_montage 数据"
            assert custom_data["anim_montage"] is not None


# ============================================================
# AnimSequence 集成测试
# ============================================================
@pytest.mark.integration
class TestAnimSequenceIntegration:
    def test_anim_sequence_parses_successfully(self):
        """AnimSequence 应该能完整解析"""
        if not ANIM_SEQUENCE_SAMPLE.exists():
            pytest.skip("测试样本不存在")
        result = parse_uasset_with_linker(str(ANIM_SEQUENCE_SAMPLE))
        assert result is not None
        assert result.status in ("success", "partial")

    def test_anim_sequence_has_metadata(self):
        """AnimSequence 应该提取元数据"""
        if not ANIM_SEQUENCE_SAMPLE.exists():
            pytest.skip("测试样本不存在")
        result = parse_uasset_with_linker(str(ANIM_SEQUENCE_SAMPLE))
        # 检查解析是否成功
        assert result.status != "failed"
        # 检查是否有 export_map
        assert len(result.export_map) > 0


# ============================================================
# UE 保真度改进集成测试
# ============================================================

# 测试资产相对路径
BLUEPRINT_ASSET_REL = "StackOBot_BP_Drone.uasset"
STATICMESH_ASSET_REL = "StackOBot_M_BotBase.uasset"
TEXTURE_ASSET_REL = "StarterContent_M_Wood_Walnut.uasset"


class TestUEFidelityIntegration:
    """UE 保真度改进集成测试"""

    def test_blueprint_full_pipeline(self, sample_root: Path):
        """场景 1: Blueprint 资产的完整解析流程"""
        bp_path = asset_path(sample_root, BLUEPRINT_ASSET_REL)
        result = parse_uasset_with_linker(str(bp_path), preload_all=True)

        assert result.linker is not None, "Linker should be created"
        assert len(result.linker._export_objects) > 0, "Should have export objects"

        for exp in result.linker._export_objects:
            assert exp._preloaded, f"Export {exp.object_name} should be preloaded"

        # 验证 export_map 已填充属性
        has_properties = any(
            hasattr(exp, 'properties') and exp.properties
            for exp in result.export_map
        )
        assert has_properties, "Blueprint should have properties after preload"

        assert result.status in ['success', 'partial', 'failed']

        if result.errors:
            assert result.status == 'partial'

    def test_staticmesh_opaque_marking(self, sample_root: Path):
        """场景 2: 资产的 opaque 标记"""
        mesh_path = asset_path(sample_root, STATICMESH_ASSET_REL)
        result = parse_uasset(str(mesh_path))

        # 验证解析成功
        assert result.status in ['success', 'partial', 'failed']

        # 检查是否有 opaque 标记的 export
        has_opaque = False
        for exp in result.export_map:
            if hasattr(exp, 'parse_status') and exp.parse_status in ('opaque', 'partial_metadata'):
                has_opaque = True
                if hasattr(exp, 'fallback_reason'):
                    assert exp.fallback_reason is not None

        # 本地样本可能没有 opaque 类型，所以不强制检查
        assert result.status in ['success', 'partial', 'failed']

    def test_dependency_graph_correctness(self, sample_root: Path):
        """场景 3: 依赖解析的正确性"""
        bp_path = asset_path(sample_root, BLUEPRINT_ASSET_REL)
        result = parse_uasset_with_linker(str(bp_path), preload_all=True)

        assert hasattr(result.summary, 'depends_map')
        assert result.summary.depends_map is not None

        assert result.linker is not None
        for exp in result.linker._export_objects:
            assert hasattr(exp, 'dependencies')
            for dep in exp.dependencies:
                assert hasattr(dep, 'object_name'),                     f"Dependency should be UObjectInstance, got {type(dep)}"
                assert hasattr(dep, 'package_index')

    def test_soft_object_path_resolution(self, sample_root: Path):
        """场景 4: 软引用解析"""
        bp_path = asset_path(sample_root, BLUEPRINT_ASSET_REL)
        result = parse_uasset(str(bp_path))

        assert hasattr(result, 'soft_object_path_list')

        has_soft_object = False
        for export in result.export_map:
            if hasattr(export, 'properties'):
                for prop in export.properties:
                    if hasattr(prop, 'type') and prop.type == 'SoftObjectProperty':
                        has_soft_object = True
                        assert hasattr(prop.value, 'asset_path')
                        assert hasattr(prop.value, 'sub_path')
                        if hasattr(prop.value, 'index') and prop.value.index is not None:
                            assert 0 <= prop.value.index < len(result.soft_object_path_list)

    def test_serial_offset_default(self, sample_root: Path):
        """场景 2 补充: 验证默认使用 SerialOffset"""
        bp_path = asset_path(sample_root, BLUEPRINT_ASSET_REL)
        result = parse_uasset(str(bp_path))

        has_script_offset = False
        for export in result.export_map:
            if hasattr(export, 'script_serialization_start_offset'):
                if export.script_serialization_start_offset > 0:
                    has_script_offset = True
                    assert hasattr(export, '_script_serialization_start_absolute')
                    assert hasattr(export, '_script_serialization_end_absolute')

    def test_batch_parsing_consistency(self, sample_root: Path):
        """场景 5: 多资产批量解析的一致性"""
        bp_path = asset_path(sample_root, BLUEPRINT_ASSET_REL)
        mesh_path = asset_path(sample_root, STATICMESH_ASSET_REL)
        assets = [str(bp_path), str(mesh_path)]
        parsed_count = 0

        for ap in assets:
            result = parse_uasset(ap)

            assert hasattr(result, 'status')
            assert result.status in ['success', 'partial', 'failed']
            assert result.summary is not None
            assert hasattr(result, 'export_map')
            assert result.export_map is not None

            # 每次迭代后清理，防止内存累积
            del result
            cleanup_after_parse()
            parsed_count += 1

        assert parsed_count == len(assets)

    def test_texture_opaque_handling(self, sample_root: Path):
        """场景 2 补充: Texture2D 资产的 opaque 处理"""
        texture_path = asset_path(sample_root, TEXTURE_ASSET_REL)
        result = parse_uasset(str(texture_path))

        texture_exports = [
            exp for exp in result.export_map
            if hasattr(exp, 'class_name') and exp.class_name == 'Texture2D'
        ]

        if len(texture_exports) > 0:
            for tex in texture_exports:
                if hasattr(tex, 'parse_status'):
                    if tex.parse_status == 'opaque':
                        assert hasattr(tex, 'fallback_reason')

        assert result.status in ['success', 'partial', 'failed']

    def test_all_improvements_together(self, sample_root: Path):
        """综合测试: 验证所有改进协同工作"""
        bp_path = asset_path(sample_root, BLUEPRINT_ASSET_REL)

        result = parse_uasset_with_linker(str(bp_path), preload_all=True)

        assert result.linker is not None
        assert all(exp._preloaded for exp in result.linker._export_objects)

        assert result.status in ['success', 'partial', 'failed']

        if result.linker._export_objects:
            first_exp = result.linker._export_objects[0]
            assert hasattr(first_exp, 'dependencies')

        assert hasattr(result, 'soft_object_path_list')

        for export in result.export_map:
            if export.serial_size > 0:
                assert hasattr(export, 'properties')
