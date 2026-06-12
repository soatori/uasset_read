"""
Issue #126: 处理 ArrayProperty tag.size=0（Animations 等 UI 蓝图数组）

测试 ArrayProperty tag.size=0 的处理逻辑。

问题根因：
- UI 蓝图 W_DashCooldown 的 Animations 数组 tag.size=0
- 原代码对 tag.size<4 直接 warning 并返回空数组，但未区分 empty/omitted/damaged
- 需要更明确的诊断输出

修复内容：
- 对 tag.size=0 特殊处理，尝试读取 count 判断是空数组还是省略编码
- 输出更明确的 diagnostic 信息
"""

import pytest
from pathlib import Path
import json

from uasset_read.core import parse_single


W_DASH_COOLDOWN = Path(
    "E:/Develop/lib/UnrealEngine/Samples/Games/LyraStarterGame/Plugins/GameFeatures/"
    "ShooterCore/Content/Game/Dash/W_DashCooldown.uasset"
)


@pytest.mark.skipif(not W_DASH_COOLDOWN.exists(), reason="W_DashCooldown.uasset not available")
class TestIssue126ArraySizeZero:
    """Issue #126: ArrayProperty tag.size=0 处理"""

    def test_w_dash_cooldown_no_crash(self):
        """W_DashCooldown 解析不崩溃"""
        result = parse_single(str(W_DASH_COOLDOWN), format="json", tolerant=True)
        data = json.loads(result)

        # 应该成功解析（可能是 partial 但不应该是 failed）
        status = data.get("status", {})
        assert status.get("status") != "failed", \
            f"W_DashCooldown should not fail: {status.get('message')}"

    def test_w_dash_cooldown_parse_status(self):
        """W_DashCooldown 解析状态应为 success 或 partial"""
        result = parse_single(str(W_DASH_COOLDOWN), format="json", tolerant=True)
        data = json.loads(result)

        status = data.get("status", {})
        assert status.get("status") in ("success", "partial", "parsed"), \
            f"W_DashCooldown status should be success/partial: {status.get('status')}"


@pytest.mark.unit
class TestArraySizeZeroLogic:
    """ArrayProperty tag.size=0 逻辑测试"""

    def test_array_size_zero_returns_empty(self):
        """tag.size=0 应返回空数组或正确处理"""
        from uasset_read.models.properties import PropertyTag
        from uasset_read.parsers.property_types.containers import parse_array_property
        from uasset_read.archive import FArchive
        import tempfile
        import os

        # 创建一个临时文件模拟 tag.size=0 的情况
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, mode='wb') as f:
                f.write(b'\x00\x00\x00\x00')  # count = 0
                temp_path = f.name

            archive = FArchive(temp_path)
            archive.seek(0)

            tag = PropertyTag(
                name="TestArray",
                type="ArrayProperty",
                size=0,  # tag.size=0
            )

            result = parse_array_property(tag, archive, [], [], None, depth=0)
            assert isinstance(result, list)
            assert len(result) == 0
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except PermissionError:
                    pass
