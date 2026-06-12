"""
Issue #123: UE4 legacy Blueprint_CeilingLight 解析失败 - Negative generations count

测试 UE4 旧版本资产（LegacyFileVersion=-6, FileVersionUE4=490）的 PackageFileSummary 解析。

问题根因：
1. LegacyFileVersion=-6 被错误分类为 UE5，实际是 UE4.11 资产
2. UE4 PackageName 字段被跳过（UE 源码中 PackageName 和 FolderName 是同一字段）
3. SavedByEngineVersion 版本门控错误（真实 enum 值应为 336）
4. CompatibleWithEngineVersion 版本门控错误（真实 enum 值应为 444）
5. CompressedChunks count 异常时无安全检查

验收标准：
- Blueprint_CeilingLight.uasset 在 strict/tolerant 下不再因为 negative generations count 失败
- 添加回归测试覆盖该样本
"""

import pytest
from pathlib import Path

from uasset_read.core import parse_single


# UE4.11 StarterContent 资产（LegacyFileVersion=-6, FileVersionUE4=490）
UE4_LEGACY_ASSET = Path("E:/Develop/lib/UnrealEngine/Samples/StarterContent/Content/StarterContent/Blueprints/Blueprint_CeilingLight.uasset")


@pytest.mark.skipif(not UE4_LEGACY_ASSET.exists(), reason="UE4 legacy sample asset not available")
class TestIssue123UE4LegacySummary:
    """Issue #123: UE4 legacy PackageFileSummary 解析"""

    def test_ue4_legacy_asset_parses_successfully(self):
        """UE4.11 资产应成功解析，不返回 failed 状态"""
        result = parse_single(str(UE4_LEGACY_ASSET), format="json", tolerant=False)
        import json
        data = json.loads(result)

        # 不应返回 failed 状态
        status = data.get("status", {})
        assert status.get("status") != "failed", f"Asset should not fail: {status.get('message')}"

        # 应包含有效的 summary 信息
        summary = data.get("summary", {})
        assert summary.get("total_export_count", 0) > 0, "Should have exports"
        assert summary.get("total_import_count", 0) > 0, "Should have imports"

    def test_ue4_legacy_asset_tolerant_mode(self):
        """UE4.11 资产在 tolerant 模式下应成功解析"""
        result = parse_single(str(UE4_LEGACY_ASSET), format="json", tolerant=True)
        import json
        data = json.loads(result)

        status = data.get("status", {})
        # tolerant 模式下不应返回 failed
        assert status.get("status") != "failed", f"Asset should not fail in tolerant mode: {status.get('message')}"

    def test_ue4_legacy_summary_fields(self):
        """验证 UE4.11 资产的 summary 字段正确读取"""
        from uasset_read.archive import FArchive
        from uasset_read.serializers.package_summary import read_package_summary

        archive = FArchive(str(UE4_LEGACY_ASSET))
        summary = read_package_summary(archive)

        # 验证版本信息
        assert summary.legacy_file_version == -6
        assert summary.file_version_ue4 == 490
        assert summary.file_version_ue5 == 0  # UE4 没有 UE5 版本

        # 验证对象计数
        assert summary.export_count == 53
        assert summary.import_count == 34
        assert summary.name_count == 142

        # 验证 generations
        assert len(summary.generations) == 1
        assert summary.generations[0].export_count == 53
        assert summary.generations[0].name_count == 142

        # 验证引擎版本
        assert summary.saved_by_engine_version.major == 4
        assert summary.saved_by_engine_version.minor == 11
        assert summary.saved_by_engine_version.changelist == 2713022


@pytest.mark.unit
class TestUE4VersionConstants:
    """UE4 版本常量测试"""

    def test_version_constants_defined(self):
        """验证 UE4 版本常量已正确定义"""
        from uasset_read.constants import (
            VER_UE4_ENGINE_VERSION_OBJECT,
            VER_UE4_PACKAGE_SUMMARY_HAS_COMPATIBLE_ENGINE_VERSION,
        )

        assert VER_UE4_ENGINE_VERSION_OBJECT == 336
        assert VER_UE4_PACKAGE_SUMMARY_HAS_COMPATIBLE_ENGINE_VERSION == 444
