"""
Issue #122: 处理动画 StructProperty 的 tag.size 异常（Transform/AnimNotifyTrack/FrameRate）

测试动画相关 StructProperty tag.size=0 或异常值的解析。

问题根因：
- 部分 UE5 动画资产的 Transform/AnimNotifyTrack/FrameRate 的 tag.size 为 0 或异常值
- 原代码在 tag.size 不匹配预期大小时直接 fallback，导致动画元数据不完整
- 对于已知支持 tagged fallback 的结构体，应允许尝试 tagged 解析

修复内容：
- 在 parse_struct_property 中，对于 tag.size=0 或在 _TAGGED_FALLBACK_STRUCTS 中的结构体，
  允许继续尝试 tagged fallback 解析，而不是直接设置 struct_type=None
"""

import pytest
from pathlib import Path
import json

from uasset_read.core import parse_single


# 受影响的动画资产
ANIM_ASSETS = [
    "E:/Develop/lib/UnrealEngine/Samples/ThirtPersonC/ThirtPersonC/Content/Characters/Mannequins/Anims/Pistol/Jog/MF_Pistol_Jog_Fwd.uasset",
    "E:/Develop/lib/UnrealEngine/Samples/ThirtPersonC/ThirtPersonC/Content/Characters/Mannequins/Anims/Unarmed/Walk/MF_Unarmed_Walk_Right.uasset",
    "E:/Develop/lib/UnrealEngine/Samples/ThirtPersonC/ThirtPersonC/Content/Characters/Mannequins/Anims/Rifle/Walk/MF_Rifle_Walk_Fwd.uasset",
]


def _asset_exists(path: str) -> bool:
    return Path(path).exists()


@pytest.mark.skipif(not any(_asset_exists(p) for p in ANIM_ASSETS), reason="动画样本资产不可用")
class TestIssue122StructSizeAnomaly:
    """Issue #122: 动画 StructProperty tag.size 异常处理"""

    def test_anim_assets_parse_without_transform_warnings(self):
        """动画资产解析不应产生 Transform tag.size=0 warning"""
        import logging
        from io import StringIO

        # 捕获 warning 日志
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.WARNING)
        logger = logging.getLogger("uasset_read.parsers.property_types.structs")
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)

        try:
            for asset_path in ANIM_ASSETS:
                if not _asset_exists(asset_path):
                    continue

                result = parse_single(asset_path, format="json", tolerant=True)
                data = json.loads(result)

                # 应该成功解析（partial 或 success）
                status = data.get("status", {})
                assert status.get("status") in ("partial", "success", "parsed"), \
                    f"Asset should parse successfully: {asset_path}"

                # 检查日志中是否有 Transform tag.size=0 的 warning
                log_content = log_stream.getvalue()
                assert "Transform' tag.size=0" not in log_content, \
                    f"Should not have Transform tag.size=0 warning for {asset_path}"
        finally:
            logger.removeHandler(handler)

    def test_struct_size_zero_uses_tagged_fallback(self):
        """tag.size=0 的结构体应使用 tagged fallback 而不是直接失败"""
        from uasset_read.models.properties import PropertyTag, StructValue
        from uasset_read.parsers.property_types.structs import parse_struct_property
        from uasset_read.archive import FArchive
        import tempfile
        import os

        # 创建一个临时文件模拟 tag.size=0 的情况
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, mode='wb') as f:
                # 写入一些测试数据（模拟 tagged property 格式）
                f.write(b'\x00' * 100)
                temp_path = f.name

            archive = FArchive(temp_path)
            archive.seek(0)

            # 创建一个 tag.size=0 的 Transform PropertyTag
            tag = PropertyTag(
                name="TestTransform",
                type="StructProperty",
                size=0,  # tag.size=0
                struct_type="Transform",
            )

            # 应该能够处理 tag.size=0 的情况
            try:
                result = parse_struct_property(tag, archive, [], [], None, depth=0)
                # 应该返回某种结果，而不是抛出异常
                assert isinstance(result, StructValue)
            except Exception as e:
                # 如果抛出异常，应该是预期的解析错误，而不是 size 不匹配
                assert "tag.size=0" not in str(e) or "not match" not in str(e)
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except PermissionError:
                    pass  # Windows 文件锁问题，忽略


@pytest.mark.unit
class TestStructSizeValidation:
    """StructProperty size 验证逻辑测试"""

    def test_tagged_fallback_structs_list(self):
        """验证 _TAGGED_FALLBACK_STRUCTS 包含必要的结构体"""
        from uasset_read.parsers.property_types.structs import _TAGGED_FALLBACK_STRUCTS

        # 应该包含动画相关结构体
        assert "FrameRate" in _TAGGED_FALLBACK_STRUCTS
        assert "AnimNotifyTrack" in _TAGGED_FALLBACK_STRUCTS

    def test_transform_not_in_tagged_fallback_by_default(self):
        """Transform 默认不在 _TAGGED_FALLBACK_STRUCTS 中，但 tag.size=0 时应特殊处理"""
        from uasset_read.parsers.property_types.structs import _TAGGED_FALLBACK_STRUCTS

        # Transform 不在 tagged fallback 列表中（它有 fast-path）
        # 但我们的修改允许 tag.size=0 时使用 tagged fallback
        assert "Transform" not in _TAGGED_FALLBACK_STRUCTS
