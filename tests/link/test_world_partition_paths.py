"""tests/link/test_world_partition_paths.py — World Partition hashed 路径规范化测试。

验证 normalize_world_partition_path() 函数和 _verify_imports() 对
hashed 路径的容错处理。

World Partition 子包路径格式：/Script/Engine_3103784960
    其中 _3103784960 是基于 MD5 的数字哈希后缀。
"""
import pytest
from unittest.mock import MagicMock

from uasset_read.link.linker import (
    PackageLinker,
    normalize_world_partition_path,
)
from uasset_read.link.object_instance import UObjectInstance
from uasset_read.serializers.object_resources import (
    PackageIndex,
    ObjectImport,
    ObjectExport,
)


# ─── normalize_world_partition_path 测试 ────────────────────────────

class TestNormalizeWorldPartitionPath:
    """normalize_world_partition_path() 正确去除哈希后缀。"""

    def test_engine_hash_suffix(self):
        """去除 /Script/Engine_3103784960 → /Script/Engine"""
        assert normalize_world_partition_path("/Script/Engine_3103784960") == "/Script/Engine"

    def test_coreuobject_hash_suffix(self):
        """去除 /Script/CoreUObject_12345 → /Script/CoreUObject"""
        assert normalize_world_partition_path("/Script/CoreUObject_12345") == "/Script/CoreUObject"

    def test_controlrig_hash_suffix(self):
        """去除 /Script/ControlRig_123456 → /Script/ControlRig"""
        assert normalize_world_partition_path("/Script/ControlRig_123456") == "/Script/ControlRig"

    def test_long_hash_suffix(self):
        """去除 10 位数字后缀"""
        assert normalize_world_partition_path("/Script/Engine_3724541952") == "/Script/Engine"

    def test_no_hash_suffix_unchanged(self):
        """无哈希后缀时原样返回"""
        assert normalize_world_partition_path("/Script/Engine") == "/Script/Engine"

    def test_no_hash_suffix_short_digits(self):
        """少于 3 位数字的后缀不被去除"""
        assert normalize_world_partition_path("/Script/Engine_12") == "/Script/Engine_12"

    def test_empty_string(self):
        """空字符串原样返回"""
        assert normalize_world_partition_path("") == ""

    def test_none_like_empty(self):
        """None 值原样返回"""
        assert normalize_world_partition_path(None) is None

    def test_no_slash_prefix(self):
        """无斜杠前缀的路径也能正确处理"""
        assert normalize_world_partition_path("Engine_12345") == "Engine"

    def test_non_script_path(self):
        """非 /Script/ 路径也能正确处理"""
        assert normalize_world_partition_path(
            "/ControlRig/Controls/DefaultGizmoLibraryNormalized_1258291200"
        ) == "/ControlRig/Controls/DefaultGizmoLibraryNormalized"

    def test_object_name_with_hash(self):
        """object_name 含哈希后缀"""
        assert normalize_world_partition_path(
            "/Script/ControlRig.EControlRigVectorKind_2063597568"
        ) == "/Script/ControlRig.EControlRigVectorKind"

    def test_game_path_unchanged(self):
        """Game 路径不含数字后缀时不被修改"""
        assert normalize_world_partition_path("/Game/Maps/MyMap") == "/Game/Maps/MyMap"

    def test_consecutive_underscores(self):
        """连续下划线只影响最后一个段落的数字后缀"""
        assert normalize_world_partition_path("/Script/Engine_Core_12345") == "/Script/Engine_Core"


# ─── _verify_imports World Partition 容错测试 ───────────────────────

def _make_linker_with_wp_import(
    wp_object_name: str,
    outer_index_value: int,
) -> PackageLinker:
    """创建一个带有 World Partition hashed 路径 import 的 linker。"""
    archive = MagicMock()
    archive._file_size = 1024
    summary = MagicMock()
    summary.depends_map = None
    name_map = ["TestName"]

    import_map = []

    # 先添加一个 Package import (root)
    root_imp = MagicMock(spec=ObjectImport)
    root_imp.class_package = "/Script/CoreUObject"
    root_imp.class_name = "Package"
    root_imp.object_name = "Engine"
    root_imp.outer_index = PackageIndex(0)  # null
    root_imp.package_name = None
    root_imp.b_import_optional = False
    import_map.append(root_imp)

    # 添加 World Partition hashed import
    wp_imp = MagicMock(spec=ObjectImport)
    wp_imp.class_package = "/Script/CoreUObject"
    wp_imp.class_name = "Class"
    wp_imp.object_name = wp_object_name
    wp_imp.outer_index = PackageIndex(outer_index_value)
    wp_imp.package_name = None
    wp_imp.b_import_optional = False
    import_map.append(wp_imp)

    export_map = []
    linker = PackageLinker(archive, summary, name_map, import_map, export_map)
    linker.link()
    return linker


class TestVerifyImportsWorldPartition:
    """_verify_imports() 对 World Partition hashed 路径的容错处理。"""

    def test_hashed_path_outer_index_error_downgraded(self):
        """hashed 路径的 outer_index 无法解析时降级为 debug 而非 error。"""
        linker = _make_linker_with_wp_import(
            wp_object_name="/Script/Engine_3103784960",
            outer_index_value=999,  # out of bounds
        )
        linker.post_load()
        # 不应有 outer_index 错误（hashed 路径被降级为 debug）
        errors = linker._import_verification_errors
        assert not any("outer_index" in e and "3103784960" in e for e in errors)

    def test_non_hashed_path_outer_index_error_preserved(self):
        """非 hashed 路径的 outer_index 无法解析时保留为 error。"""
        linker = _make_linker_with_wp_import(
            wp_object_name="/Script/Engine",
            outer_index_value=999,  # out of bounds
        )
        linker.post_load()
        errors = linker._import_verification_errors
        assert any("outer_index" in e and "无法解析" in e for e in errors)

    def test_hashed_path_valid_outer_index_no_error(self):
        """hashed 路径的 outer_index 有效时无错误。"""
        linker = _make_linker_with_wp_import(
            wp_object_name="/Script/Engine_3103784960",
            outer_index_value=-1,  # valid: points to import 0
        )
        linker.post_load()
        errors = linker._import_verification_errors
        assert errors == []

    def test_multiple_hashed_imports(self):
        """多个 hashed 路径 import 的 outer_index 错误都被降级。"""
        archive = MagicMock()
        archive._file_size = 1024
        summary = MagicMock()
        summary.depends_map = None
        name_map = ["TestName"]

        import_map = []
        for i in range(5):
            imp = MagicMock(spec=ObjectImport)
            imp.class_package = f"/Script/Engine_{100000 + i}"
            imp.class_name = "Class"
            imp.object_name = f"/Script/Engine_{100000 + i}"
            imp.outer_index = PackageIndex(999)  # all out of bounds
            imp.package_name = None
            imp.b_import_optional = False
            import_map.append(imp)

        linker = PackageLinker(archive, summary, name_map, import_map, [])
        linker.link()
        linker.post_load()

        # 所有 hashed 路径的 outer_index 错误都应被降级
        errors = linker._import_verification_errors
        assert not any("outer_index" in e and "无法解析" in e for e in errors)


# ─── UObjectInstance.get_full_name() 规范化测试 ───────────────────

class TestGetFullNameWorldPartition:
    """UObjectInstance.get_full_name() 对 hashed 路径的规范化。"""

    def test_hashed_class_package_normalized(self):
        """hashed class_package 在 full_name 中被规范化。"""
        inst = UObjectInstance(
            package_index=-1,
            object_name="Actor",
            object_class="Class",
            class_package="/Script/Engine_3103784960",
            outer_index=PackageIndex(0),
            is_import=True,
            linker=None,
        )
        full_name = inst.get_full_name()
        assert full_name == "/Script/Engine.Actor"

    def test_non_hashed_class_package_unchanged(self):
        """非 hashed class_package 在 full_name 中不变。"""
        inst = UObjectInstance(
            package_index=-1,
            object_name="Actor",
            object_class="Class",
            class_package="/Script/Engine",
            outer_index=PackageIndex(0),
            is_import=True,
            linker=None,
        )
        full_name = inst.get_full_name()
        assert full_name == "/Script/Engine.Actor"
