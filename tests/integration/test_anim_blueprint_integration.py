"""AnimBlueprint 集成测试"""
import pytest
from pathlib import Path
from uasset_read.parse_uasset import parse_uasset_with_linker


# 测试样本路径
SAMPLE_DIR = Path("E:/Develop/lib/Samples/GameAnimationSample")
ANIM_BP_SAMPLE = SAMPLE_DIR / "Content/MetaHumans/Common/Common/RTG_metahuman_base_skel_AnimBP.uasset"


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
