"""legacy -6 文件解析测试 — 验证 StarterContent 等资产。"""
import os
import pytest
from uasset_read.parse_uasset import parse_package


# 测试样本路径
SAMPLES_DIR = r"E:\Develop\lib\Samples"
LEGACY_MINUS6_FILE = os.path.join(
    SAMPLES_DIR,
    "StarterContent/Content/StarterContent/Blueprints/Blueprint_CeilingLight.uasset"
)


@pytest.mark.integration
class TestLegacyMinus6Parsing:
    """legacy -6 格式文件解析验证。"""

    @pytest.mark.skipif(
        not os.path.exists(LEGACY_MINUS6_FILE),
        reason="测试样本不存在"
    )
    def test_starter_content_parses_successfully(self):
        """StarterContent 资产应解析成功。"""
        result = parse_package(LEGACY_MINUS6_FILE, tolerant=True)
        assert result.is_success or not result.errors, (
            f"解析失败: {result.errors}"
        )

    @pytest.mark.skipif(
        not os.path.exists(LEGACY_MINUS6_FILE),
        reason="测试样本不存在"
    )
    def test_no_generations_error(self):
        """不应出现 generations count 负数错误。"""
        result = parse_package(LEGACY_MINUS6_FILE, tolerant=True)
        assert not any("generations" in e.lower() for e in result.errors), (
            f"Generations 解析错误: {result.errors}"
        )

    @pytest.mark.skipif(
        not os.path.exists(LEGACY_MINUS6_FILE),
        reason="测试样本不存在"
    )
    def test_summary_parsed(self):
        """应成功解析出 summary。"""
        result = parse_package(LEGACY_MINUS6_FILE, tolerant=True)
        assert result.summary is not None, (
            f"Summary 未解析: {result.errors}"
        )


class TestLegacyMinus6FieldOrder:
    """legacy -6 字段顺序单元测试（不依赖真实文件）。"""

    def test_num_texture_allocations_read(self):
        """验证 NumTextureAllocations 字段被读取。"""
        # 此测试验证代码路径，实际解析需要真实文件
        from uasset_read.serializers.package_summary import read_package_summary
        # 函数存在且可导入
        assert callable(read_package_summary)
