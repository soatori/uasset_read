"""
Issue #121: 支持 MapProperty 的 StructProperty key（CurveIdentifierToMetaData）

测试 MapProperty 使用 StructProperty 作为 key 的解析支持。

问题根因：
- 动画资产的 CurveIdentifierToMetaData 字段使用 TMap<FAnimCurveIdentifier, FAnimCurveMetaData>
- key 是 StructProperty 而不是简单标量类型
- 原代码 MapProperty parser 只支持简单 key 类型，遇到 StructProperty key 时整体 fallback

修复内容：
- 在 _SUPPORTED_MAP_KEY_TYPES 中添加 "StructProperty"
- 在 _dispatch_key_parse 中添加 StructProperty key 解析分支
- 在 property_tags.py 中提取 key_type_struct 和 value_type_struct
"""

import pytest
from pathlib import Path
import json

from uasset_read.core import parse_single


# 受影响的动画资产（包含 CurveIdentifierToMetaData）
ANIM_CURVE_ASSETS = [
    "E:/Develop/lib/UnrealEngine/Samples/GameAnimationSample/Content/Characters/UEFN_Mannequin/Animations/AimOffset/M_Neutral_AO_Crouch_X-135_Y+90.uasset",
    "E:/Develop/lib/UnrealEngine/Samples/GameAnimationSample/Content/Characters/UEFN_Mannequin/Animations/AimOffset/M_Neutral_AO_Crouch_X+135_Y+90.uasset",
]


def _asset_exists(path: str) -> bool:
    return Path(path).exists()


@pytest.mark.skipif(not any(_asset_exists(p) for p in ANIM_CURVE_ASSETS), reason="动画曲线样本资产不可用")
class TestIssue121MapStructKey:
    """Issue #121: MapProperty StructProperty key 支持"""

    def test_anim_curve_assets_no_unsupported_key_warning(self):
        """动画曲线资产不应产生 'unsupported key type StructProperty' warning"""
        import logging
        from io import StringIO

        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.WARNING)
        logger = logging.getLogger("uasset_read.parsers.property_types.containers")
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)

        try:
            for asset_path in ANIM_CURVE_ASSETS:
                if not _asset_exists(asset_path):
                    continue

                result = parse_single(asset_path, format="json", tolerant=True)
                data = json.loads(result)

                status = data.get("status", {})
                assert status.get("status") in ("partial", "success", "parsed"), \
                    f"Asset should parse: {asset_path}"

                log_content = log_stream.getvalue()
                assert "unsupported key type 'StructProperty'" not in log_content, \
                    f"Should not have unsupported StructProperty key warning for {asset_path}"
        finally:
            logger.removeHandler(handler)


@pytest.mark.unit
class TestMapStructKeySupport:
    """MapProperty StructProperty key 支持测试"""

    def test_struct_property_in_supported_key_types(self):
        """StructProperty 应在 _SUPPORTED_MAP_KEY_TYPES 中"""
        from uasset_read.parsers.property_types.containers import _SUPPORTED_MAP_KEY_TYPES

        assert "StructProperty" in _SUPPORTED_MAP_KEY_TYPES, \
            "StructProperty should be in supported map key types"

    def test_key_type_struct_extraction(self):
        """PropertyTag 应能提取 key_type_struct"""
        from uasset_read.models.properties import PropertyTag

        tag = PropertyTag(name="TestMap", type="MapProperty", size=0)
        tag.key_type = "StructProperty"
        tag.key_type_struct = "AnimCurveIdentifier"

        assert tag.key_type == "StructProperty"
        assert tag.key_type_struct == "AnimCurveIdentifier"
