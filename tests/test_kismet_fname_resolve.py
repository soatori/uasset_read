"""测试 FName 统一解析逻辑"""
import pytest


def test_resolve_fname_basic():
    """测试基本的 FName 解析"""
    from uasset_read.kismet.archive import FKismetArchive

    # 创建带有 name_map 的 archive
    archive = FKismetArchive.__new__(FKismetArchive)
    archive._name_map = ["TestName", "AnotherName"]

    result = archive.resolve_fname(0, 0)
    assert result == "TestName"


def test_resolve_fname_with_number():
    """测试带 number 后缀的 FName"""
    from uasset_read.kismet.archive import FKismetArchive

    archive = FKismetArchive.__new__(FKismetArchive)
    archive._name_map = ["TestName"]

    result = archive.resolve_fname(0, 5)
    assert result == "TestName_5"


def test_resolve_fname_out_of_bounds():
    """测试索引越界的情况"""
    from uasset_read.kismet.archive import FKismetArchive

    archive = FKismetArchive.__new__(FKismetArchive)
    archive._name_map = ["TestName"]

    result = archive.resolve_fname(999, 0)
    assert result == "Unknown_999"
