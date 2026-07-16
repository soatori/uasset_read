"""max_reasonable 动态阈值测试 — UE5 大型属性类型 (#404)"""
from uasset_read.constants import (
    get_max_reasonable,
    MAX_REASONABLE_CAP,
    UE5_LARGE_PROPERTY_MAX_REASONABLE,
)


class TestGetMaxReasonable:
    """get_max_reasonable 动态阈值函数测试。"""

    def test_default_property_returns_standard_cap(self):
        """普通属性类型返回默认阈值。"""
        result = get_max_reasonable("IntProperty", engine_version=5)
        assert result == MAX_REASONABLE_CAP

    def test_struct_property_returns_standard_cap(self):
        """StructProperty 返回默认阈值（非已知大型类型）。"""
        result = get_max_reasonable("StructProperty", engine_version=5)
        assert result == MAX_REASONABLE_CAP

    def test_bone_animation_tracks_allows_large_size(self):
        """UE5 BoneAnimationTracks 应允许更大的属性大小。"""
        result = get_max_reasonable("BoneAnimationTracks", engine_version=5)
        assert result == UE5_LARGE_PROPERTY_MAX_REASONABLE

    def test_pose_container_allows_large_size(self):
        """UE5 PoseContainer 应允许更大的属性大小。"""
        result = get_max_reasonable("PoseContainer", engine_version=5)
        assert result == UE5_LARGE_PROPERTY_MAX_REASONABLE

    def test_array_connection_map_allows_large_size(self):
        """UE5 ArrayConnectionMap 应允许更大的属性大小。"""
        result = get_max_reasonable("ArrayConnectionMap", engine_version=5)
        assert result == UE5_LARGE_PROPERTY_MAX_REASONABLE

    def test_rigvm_allows_large_size(self):
        """UE5 RigVM 应允许更大的属性大小。"""
        result = get_max_reasonable("RigVM", engine_version=5)
        assert result == UE5_LARGE_PROPERTY_MAX_REASONABLE

    def test_ue4_large_type_still_uses_standard_cap(self):
        """UE4 版本即使类型在大型列表中，也应使用标准阈值。"""
        result = get_max_reasonable("BoneAnimationTracks", engine_version=4)
        assert result == MAX_REASONABLE_CAP

    def test_ue5_non_large_type_uses_standard_cap(self):
        """UE5 版本但非大型类型，应使用标准阈值。"""
        result = get_max_reasonable("SomeOtherType", engine_version=5)
        assert result == MAX_REASONABLE_CAP

    def test_engine_version_zero_uses_standard_cap(self):
        """engine_version=0 时使用标准阈值。"""
        result = get_max_reasonable("BoneAnimationTracks", engine_version=0)
        assert result == MAX_REASONABLE_CAP

    def test_large_property_max_is_500mb(self):
        """大型属性阈值应为 500MB。"""
        assert UE5_LARGE_PROPERTY_MAX_REASONABLE == 500 * 1024 * 1024

    def test_standard_cap_is_100mb(self):
        """标准阈值应为 100MB。"""
        assert MAX_REASONABLE_CAP == 100 * 1024 * 1024


class TestValidateSizeWithPropertyType:
    """validate_size 带属性类型的动态阈值测试。"""

    def test_validate_size_accepts_large_struct(self):
        """validate_size 对已知大型属性类型应接受超过标准阈值的大小。"""
        from uasset_read.archive import FArchive
        from uasset_read.exceptions import ParseError
        import tempfile
        import os

        # 创建临时文件模拟大文件
        file_size = 600 * 1024 * 1024  # 600MB
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * min(file_size, 1024))  # 实际写入少量数据
            temp_path = f.name

        try:
            archive = FArchive(temp_path, tolerant=False)
            # 手动设置文件大小以模拟大文件
            archive._file_size = file_size
            # 设置引擎版本为 UE5
            archive._file_version_ue5 = 5

            # 对于大型属性类型，500MB 应该通过验证
            # 注意：剩余空间检查会先于 max_reasonable 检查，所以需要模拟剩余空间足够大
            archive.validate_size(
                500 * 1024 * 1024,  # 500MB
                context="TestProp",
                tolerant=False,
                property_type="BoneAnimationTracks",
            )
            # 不应抛出异常
        finally:
            archive.close()
            os.unlink(temp_path)

    def test_validate_size_rejects_large_normal_property(self):
        """validate_size 对普通属性类型应拒绝超过标准阈值的大小。"""
        from uasset_read.archive import FArchive
        from uasset_read.exceptions import ParseError
        import tempfile
        import os

        # 创建临时文件模拟大文件
        file_size = 600 * 1024 * 1024  # 600MB
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'\x00' * min(file_size, 1024))
            temp_path = f.name

        try:
            archive = FArchive(temp_path, tolerant=False)
            archive._file_size = file_size
            # 设置引擎版本为 UE5
            archive._file_version_ue5 = 5

            # 对于普通属性类型，500MB 应该超过标准阈值
            # 注意：剩余空间检查会先于 max_reasonable 检查，所以需要模拟剩余空间足够大
            try:
                archive.validate_size(
                    500 * 1024 * 1024,  # 500MB
                    context="TestProp",
                    tolerant=False,
                    property_type="IntProperty",
                )
                # 应该抛出异常
                assert False, "应抛出 ParseError"
            except ParseError as e:
                assert "max_reasonable" in str(e)
        finally:
            archive.close()
            os.unlink(temp_path)
