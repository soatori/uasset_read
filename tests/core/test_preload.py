"""Tests for PackageLinker.preload() NoneType 防护 (#328)."""
import pytest
from unittest.mock import MagicMock, PropertyMock


def test_preload_none_serial_offset():
    """preload() 应处理 serial_offset 为 None 的情况。"""
    from uasset_read.link.linker import PackageLinker

    mock_archive = MagicMock()
    mock_archive.total_size.return_value = 1000

    linker = PackageLinker.__new__(PackageLinker)
    linker._archive = mock_archive
    linker._file_size = 1000
    linker._preload_cache = {}
    linker._export_objects = []
    linker._export_map = []
    linker._import_objects = []
    linker._import_map = []
    linker._name_map = []
    linker._summary = MagicMock()
    linker._diagnostics = []

    # 创建一个 mock export object with None serial_offset
    mock_instance = MagicMock()
    mock_instance.serial_offset = None
    mock_instance.serial_size = 100
    mock_instance.object_name = "TestExport"
    mock_instance._preloaded = False

    linker._export_objects = [mock_instance]
    linker._export_map = [MagicMock()]

    # 不应抛出异常
    linker.preload(0)
    assert mock_instance._preloaded == True


def test_preload_none_archive():
    """preload() 应处理 archive 为 None 的情况。"""
    from uasset_read.link.linker import PackageLinker

    linker = PackageLinker.__new__(PackageLinker)
    linker._archive = None  # archive 为 None
    linker._file_size = 1000
    linker._preload_cache = {}
    linker._export_objects = []
    linker._export_map = []
    linker._import_objects = []
    linker._import_map = []
    linker._name_map = []
    linker._summary = MagicMock()
    linker._diagnostics = []

    # 创建一个 mock export object
    mock_instance = MagicMock()
    mock_instance.serial_offset = 100
    mock_instance.serial_size = 100
    mock_instance.object_name = "TestExport"
    mock_instance._preloaded = False

    linker._export_objects = [mock_instance]
    linker._export_map = [MagicMock()]

    # 不应抛出异常
    linker.preload(0)
    assert mock_instance._preloaded == True


def test_preload_none_serial_size():
    """preload() 应处理 serial_size 为 None 的情况。"""
    from uasset_read.link.linker import PackageLinker

    mock_archive = MagicMock()
    mock_archive.total_size.return_value = 1000

    linker = PackageLinker.__new__(PackageLinker)
    linker._archive = mock_archive
    linker._file_size = 1000
    linker._preload_cache = {}
    linker._export_objects = []
    linker._export_map = []
    linker._import_objects = []
    linker._import_map = []
    linker._name_map = []
    linker._summary = MagicMock()
    linker._diagnostics = []

    # 创建一个 mock export object with None serial_size
    mock_instance = MagicMock()
    mock_instance.serial_offset = 100
    mock_instance.serial_size = None
    mock_instance.object_name = "TestExport"
    mock_instance._preloaded = False

    linker._export_objects = [mock_instance]
    linker._export_map = [MagicMock()]

    # 不应抛出异常
    linker.preload(0)
    assert mock_instance._preloaded == True
