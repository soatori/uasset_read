"""AnimSequence 集成测试"""
import pytest
from pathlib import Path
from uasset_read.parse_uasset import parse_uasset_with_linker


# 测试样本路径
SAMPLE_DIR = Path("E:/Develop/lib/Samples/GameAnimationSample")
ANIM_SEQUENCE_SAMPLE = SAMPLE_DIR / "Content/Characters/UEFN_Mannequin/Animations/Idle/M_Neutral_Stand_Idle_Loop.uasset"


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
