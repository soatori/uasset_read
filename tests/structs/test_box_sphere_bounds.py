"""
BoxSphereBounds 解析验证测试（Issue #175）。

UE5 中 FBoxSphereBounds UPROPERTY 结构体没有 STRUCT_SerializeNative 标志，
因此始终使用 tagged 格式（PropertyTags 序列化每个字段），而非紧凑二进制格式。

三种变体：
- FBoxSphereBounds3f = TBoxSphereBounds<float, float>  — 28 bytes（紧凑格式）
- FBoxSphereBounds3d = TBoxSphereBounds<double, double> — 56 bytes（紧凑格式）
- FCompactBoxSphereBounds3d = TBoxSphereBounds<double, float> — 40 bytes（紧凑格式）
- FBoxSphereBounds = TBoxSphereBounds<double, float>（UE5 LWC）— tagged 格式（通过 UPROPERTY）

FBoxSphereBounds（UPROPERTY 版本）始终使用 tagged 格式，因为
TBoxSphereBoundsStructOpsTypeTraits 没有设置 WithSerialize 标志。
"""
import os
from pathlib import Path

import pytest

from tests.conftest import asset_path, ASSET_MESH_CHAIR

# 样本文件完整路径
CHAIR_PATH = Path(__file__).parent.parent / "samples" / "StackOBot_M_BotBase.uasset"


@pytest.mark.integration
class TestBoxSphereBoundsParsing:
    """BoxSphereBounds 解析验证。"""

    def test_box_sphere_bounds_parsed(self, sample_root: Path):
        """验证本地样本资产能正确解析。"""
        chair_path = asset_path(sample_root, ASSET_MESH_CHAIR)

        from uasset_read.parse_uasset import parse_package

        result = parse_package(str(chair_path), tolerant=True)

        # 本地样本可能没有 BoxSphereBounds 属性，只验证解析成功
        assert result.is_success or result.status == "partial", f"解析失败: {result.errors}"
        assert len(result.export_map) > 0, "应有至少一个 export"

    def test_box_sphere_bounds_no_warning(self):
        """验证 BoxSphereBounds 解析不产生 '不匹配' 警告。"""
        if not os.path.exists(CHAIR_PATH):
            pytest.skip(f"样本文件不存在: {CHAIR_PATH}")

        import logging
        from uasset_read.parse_uasset import parse_package

        handler = logging.handlers if hasattr(logging, "handlers") else None
        # 捕获 property_types 模块的 WARNING
        logger = logging.getLogger("uasset_read.parsers.property_types")

        class WarningCapture(logging.Handler):
            def __init__(self):
                super().__init__()
                self.warnings = []

            def emit(self, record):
                if record.levelno >= logging.WARNING:
                    self.warnings.append(record.getMessage())

        capture = WarningCapture()
        logger.addHandler(capture)
        try:
            result = parse_package(str(CHAIR_PATH), tolerant=True)
        finally:
            logger.removeHandler(capture)

        # 检查没有 BoxSphereBounds 相关的警告
        bounds_warnings = [w for w in capture.warnings if "BoxSphereBounds" in w]
        assert len(bounds_warnings) == 0, f"BoxSphereBounds 解析不应有警告: {bounds_warnings}"
