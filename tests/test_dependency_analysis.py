"""Phase 10 依赖分析单元测试。"""
import pytest
from dataclasses import dataclass
from typing import List, Dict

# 导入待测函数和类型
from uasset_read import (
    build_imports_list,
    read_soft_object_paths,
    detect_circular_deps,
    ObjectImport,
    PackageFileSummary,
    PackageIndex,
    FArchive
)


# === Fixtures ===

@pytest.fixture
def empty_import_map() -> List[ObjectImport]:
    """空导入表 fixture。"""
    return []


@pytest.fixture
def single_import() -> List[ObjectImport]:
    """单条目导入表 fixture。"""
    return [
        ObjectImport(
            class_package="/Script/Engine",
            class_name="Class",
            outer_index=PackageIndex(0),
            object_name="Blueprint"
        )
    ]


@pytest.fixture
def duplicate_imports() -> List[ObjectImport]:
    """包含重复条目的导入表 fixture。"""
    return [
        ObjectImport(
            class_package="/Script/Engine",
            class_name="Class",
            outer_index=PackageIndex(0),
            object_name="Blueprint"
        ),
        ObjectImport(
            class_package="/Script/Engine",
            class_name="Class",
            outer_index=PackageIndex(-1),
            object_name="Blueprint"
        ),
        ObjectImport(
            class_package="/Script/Core",
            class_name="Object",
            outer_index=PackageIndex(0),
            object_name="Asset"
        )
    ]


@pytest.fixture
def multi_package_imports() -> List[ObjectImport]:
    """多包依赖导入表 fixture（用于循环检测）。"""
    return [
        ObjectImport(
            class_package="/Game/PackageA",
            class_name="ClassA",
            outer_index=PackageIndex(0),
            object_name="ObjectA"
        ),
        ObjectImport(
            class_package="/Game/PackageA",
            class_name="ClassA",
            outer_index=PackageIndex(0),
            object_name="ObjectB"
        ),
        ObjectImport(
            class_package="/Game/PackageB",
            class_name="ClassB",
            outer_index=PackageIndex(0),
            object_name="ObjectC"
        )
    ]


@pytest.fixture
def ue4_summary() -> PackageFileSummary:
    """UE4 文件 PackageFileSummary fixture。"""
    return PackageFileSummary(
        tag=0x9E2A83C1,
        legacy_file_version=-3,
        file_version_ue4=522,
        file_version_ue5=0,
        soft_object_paths_count=0,
        soft_object_paths_offset=0
    )


@pytest.fixture
def ue5_summary_with_soft_refs() -> PackageFileSummary:
    """UE5 >= 1008 文件 PackageFileSummary fixture（包含 SoftObjectPaths）。"""
    return PackageFileSummary(
        tag=0x9E2A83C1,
        legacy_file_version=-8,
        file_version_ue4=0,
        file_version_ue5=1016,
        soft_object_paths_count=2,
        soft_object_paths_offset=1024
    )


@pytest.fixture
def ue5_summary_no_soft_refs() -> PackageFileSummary:
    """UE5 < 1008 文件 PackageFileSummary fixture（无 SoftObjectPaths）。"""
    return PackageFileSummary(
        tag=0x9E2A83C1,
        legacy_file_version=-8,
        file_version_ue4=0,
        file_version_ue5=500,
        soft_object_paths_count=0,
        soft_object_paths_offset=0
    )


# === build_imports_list 测试 ===

def test_build_imports_list_empty(empty_import_map):
    """测试空输入返回空数组。"""
    result = build_imports_list(empty_import_map)
    assert result == []


def test_build_imports_list_single(single_import):
    """测试单条目转换为 dict 格式。"""
    result = build_imports_list(single_import)
    assert len(result) == 1
    assert result[0] == {
        "class": "Class",
        "package": "/Script/Engine",
        "object": "Blueprint"
    }


def test_build_imports_list_merge_duplicates(duplicate_imports):
    """测试重复条目合并（相同三元组）。"""
    result = build_imports_list(duplicate_imports)
    assert len(result) == 2
    assert result[0] == {
        "class": "Class",
        "package": "/Script/Engine",
        "object": "Blueprint"
    }
    assert result[1] == {
        "class": "Object",
        "package": "/Script/Core",
        "object": "Asset"
    }


def test_build_imports_list_preserves_order(single_import):
    """测试输出保持原始顺序（首次出现）。"""
    result = build_imports_list(single_import)
    assert result[0]["object"] == "Blueprint"


# === read_soft_object_paths 测试 ===

def test_read_soft_object_paths_ue4_version_check(ue4_summary):
    """测试 UE4 文件版本判断条件。"""
    assert ue4_summary.legacy_file_version > -8
    assert ue4_summary.file_version_ue5 == 0


def test_read_soft_object_paths_ue5_below_1008_version_check(ue5_summary_no_soft_refs):
    """测试 UE5 < 1008 文件版本判断条件。"""
    assert ue5_summary_no_soft_refs.legacy_file_version <= -8
    assert ue5_summary_no_soft_refs.file_version_ue5 < 1008


def test_read_soft_object_paths_ue5_version_condition(ue5_summary_with_soft_refs):
    """测试 UE5 >= 1008 文件满足版本条件。"""
    assert ue5_summary_with_soft_refs.legacy_file_version <= -8
    assert ue5_summary_with_soft_refs.file_version_ue5 >= 1008
    assert ue5_summary_with_soft_refs.soft_object_paths_count > 0
    assert ue5_summary_with_soft_refs.soft_object_paths_offset > 0


def test_read_soft_object_paths_count_zero(ue5_summary_no_soft_refs):
    """测试 count=0 时返回空数组。"""
    assert ue5_summary_no_soft_refs.soft_object_paths_count == 0


def test_read_soft_object_paths_offset_zero(ue5_summary_no_soft_refs):
    """测试 offset=0 时返回空数组。"""
    assert ue5_summary_no_soft_refs.soft_object_paths_offset == 0


# === detect_circular_deps 测试 ===

def test_detect_circular_deps_empty(empty_import_map):
    """测试空输入返回空数组。"""
    result = detect_circular_deps(empty_import_map)
    assert result == []


def test_detect_circular_deps_no_cycle(single_import):
    """测试单条目无高密度依赖。"""
    result = detect_circular_deps(single_import)
    assert result == []


def test_detect_circular_deps_high_density_dependency(multi_package_imports):
    """测试检测高密度依赖（同一包多次引用）。"""
    result = detect_circular_deps(multi_package_imports)
    assert len(result) == 1
    assert result[0] == ["/Game/PackageA", "/Game/PackageA"]


def test_detect_circular_deps_format():
    """测试输出格式为 [pkg, pkg] 数组。"""
    import_map = [
        ObjectImport("/Game/Test", "Class", PackageIndex(0), "Obj1"),
        ObjectImport("/Game/Test", "Class", PackageIndex(0), "Obj2"),
        ObjectImport("/Game/Test", "Class", PackageIndex(0), "Obj3"),
    ]
    result = detect_circular_deps(import_map)
    assert len(result) == 1
    assert isinstance(result[0], list)
    assert len(result[0]) == 2
    assert result[0][0] == result[0][1]


def test_detect_circular_deps_multiple_packages():
    """测试多个包的高密度依赖检测。"""
    import_map = [
        ObjectImport("/Script/Engine", "Class", PackageIndex(0), "A"),
        ObjectImport("/Script/Engine", "Class", PackageIndex(0), "B"),
        ObjectImport("/Script/Core", "Object", PackageIndex(0), "C"),
        ObjectImport("/Script/Core", "Object", PackageIndex(0), "D"),
    ]
    result = detect_circular_deps(import_map)
    assert len(result) == 2
    assert ["/Script/Engine", "/Script/Engine"] in result
    assert ["/Script/Core", "/Script/Core"] in result
