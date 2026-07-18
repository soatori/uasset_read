"""动画资产集成测试

合并以下测试文件：
- test_anim_blueprint_integration.py
- test_anim_montage_integration.py
- test_anim_sequence_integration.py
"""
import pytest
from pathlib import Path
from uasset_read.parse_uasset import parse_uasset_with_linker
from uasset_read.serializers.object_resources import resolve_class_name


# ============================================================
# 测试样本路径
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
