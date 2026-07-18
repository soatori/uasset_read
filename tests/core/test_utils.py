"""utils.py 单元测试"""

import struct
import pytest
from unittest.mock import MagicMock, PropertyMock
from uasset_read.core.utils import safe_str, safe_int, normalize_hex_guid
from uasset_read.archive import ByteArchive
from uasset_read.exceptions import ParseError


# --- safe_str ---

def test_safe_str_none():
    assert safe_str(None) == ""


def test_safe_str_default_override():
    assert safe_str(None, "N/A") == "N/A"


def test_safe_str_int():
    assert safe_str(42) == "42"


def test_safe_str_str():
    assert safe_str("hello") == "hello"


def test_safe_str_bool():
    assert safe_str(True) == "True"


def test_safe_str_float():
    assert safe_str(3.14) == "3.14"


# --- safe_int ---

def test_safe_int_none():
    assert safe_int(None) == 0


def test_safe_int_default_override():
    assert safe_int(None, -1) == -1


def test_safe_int_int():
    assert safe_int(42) == 42


def test_safe_int_str_valid():
    assert safe_int("123") == 123


def test_safe_int_str_invalid():
    assert safe_int("abc") == 0


def test_safe_int_str_invalid_with_default():
    assert safe_int("xyz", -99) == -99


def test_safe_int_bool_returns_default():
    """bool is subclass of int in Python, but the isinstance guard only allows int/str."""
    # Note: bool is a subclass of int, so isinstance(True, int) is True.
    # This means safe_int(True) returns 1 (True).
    assert safe_int(True) == 1


def test_safe_int_float_returns_default():
    assert safe_int(3.14) == 0


def test_safe_int_list_returns_default():
    assert safe_int([1, 2]) == 0


def test_safe_int_negative_str():
    assert safe_int("-5") == -5


def test_safe_int_empty_str():
    assert safe_int("") == 0


# --- normalize_hex_guid ---

def test_normalize_hex_guid_none():
    assert normalize_hex_guid(None) is None


def test_normalize_hex_guid_empty():
    result = normalize_hex_guid("")
    assert result == ""


def test_normalize_hex_guid_with_dashes():
    assert normalize_hex_guid("A1B2C3D4-E5F6-7890-ABCD-EF1234567890") == \
        "a1b2c3d4e5f67890abcdef1234567890"


def test_normalize_hex_guid_without_dashes():
    assert normalize_hex_guid("A1B2C3D4E5F67890ABCDEF1234567890") == \
        "a1b2c3d4e5f67890abcdef1234567890"


def test_normalize_hex_guid_lowercase():
    assert normalize_hex_guid("a1b2c3d4-e5f6-7890-abcd-ef1234567890") == \
        "a1b2c3d4e5f67890abcdef1234567890"


def test_normalize_hex_guid_already_normalized():
    assert normalize_hex_guid("a1b2c3d4e5f67890abcdef1234567890") == \
        "a1b2c3d4e5f67890abcdef1234567890"


def test_normalize_hex_guid_mixed_case():
    """测试混合大小写 GUID 归一化为小写"""
    assert normalize_hex_guid("A1b2C3d4-E5f6-7890-aBcD-eF1234567890") == \
        "a1b2c3d4e5f67890abcdef1234567890"


def test_normalize_hex_guid_all_uppercase_no_dashes():
    """测试全大写无连字符 GUID 归一化为小写"""
    assert normalize_hex_guid("A1B2C3D4E5F67890ABCDEF1234567890") == \
        "a1b2c3d4e5f67890abcdef1234567890"


# --- UTF-8 字符串长度越界验证测试 (#407) ---


def test_utf8_length_exceeds_remaining_bytes_tolerant():
    """UTF-8 长度超过剩余字节时，tolerant 模式应返回空字符串"""
    # length=1000, 但只剩 10 字节（不含 length 字段本身的 4 字节）
    # 构造: i32 length (1000) + 10 bytes of padding
    data = struct.pack('<i', 1000) + b'\x00' * 10
    archive = ByteArchive(data, tolerant=True)
    result = archive.read_utf8_string(tolerant=True)
    assert result == ""


def test_utf8_length_exceeds_remaining_bytes_strict():
    """UTF-8 长度超过剩余字节时，strict 模式应抛出 ParseError"""
    data = struct.pack('<i', 1000) + b'\x00' * 10
    archive = ByteArchive(data, tolerant=False)
    with pytest.raises(ParseError, match="UTF-8 length 1000 exceeds remaining"):
        archive.read_utf8_string(tolerant=False)


def test_utf8_length_within_remaining_bytes():
    """UTF-8 长度在剩余字节范围内，应正常读取"""
    # length=5, 后跟 5 字节有效数据 + null terminator
    content = b'hello'
    data = struct.pack('<i', len(content) + 1) + content + b'\x00'
    archive = ByteArchive(data, tolerant=True)
    result = archive.read_utf8_string(tolerant=True)
    assert result == "hello"


def test_utf8_length_zero():
    """UTF-8 长度为 0，应返回空字符串"""
    data = struct.pack('<i', 0)
    archive = ByteArchive(data, tolerant=True)
    result = archive.read_utf8_string(tolerant=True)
    assert result == ""


def test_utf8_length_exactly_matches_remaining():
    """UTF-8 长度恰好等于剩余字节，应正常读取"""
    content = b'test\x00'
    data = struct.pack('<i', len(content)) + content
    archive = ByteArchive(data, tolerant=True)
    result = archive.read_utf8_string(tolerant=True)
    assert result == "test"


def test_utf8_length_one_byte_over():
    """UTF-8 长度比剩余字节多 1，应触发越界"""
    data = struct.pack('<i', 11) + b'\x00' * 10
    archive = ByteArchive(data, tolerant=True)
    result = archive.read_utf8_string(tolerant=True)
    assert result == ""


def test_utf8_length_records_diagnostic():
    """tolerant 模式下应记录诊断信息"""
    data = struct.pack('<i', 500) + b'\x00' * 5
    archive = ByteArchive(data, tolerant=True)
    archive.read_utf8_string(tolerant=True)
    diagnostics = archive.get_diagnostics()
    assert len(diagnostics) > 0
    assert any("UTF-8 length" in d.error for d in diagnostics)


# --- Tests for PackageLinker.preload() NoneType 防护 (#328) ---


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


# --- DependsMap 异常数量防护测试 (#336) ---


# depends_offset 必须 > 0（函数入口检查），但 ByteArchive 会 seek 到该位置
# 所以数据需要在 offset=1 处开始，前 1 字节是填充
_PADDING = b'\x00'


def _make_summary(export_count: int, depends_offset: int = 1):
    """创建用于测试的最小化 PackageFileSummary。"""
    from uasset_read.serializers.package_summary import PackageFileSummary
    summary = PackageFileSummary.__new__(PackageFileSummary)
    summary.depends_offset = depends_offset
    summary.export_count = export_count
    return summary


def _i32_le(value: int) -> bytes:
    """将 int32 编码为小端字节序列。"""
    return struct.pack('<i', value)


def test_depends_map_abnormal_count():
    """DependsMap 异常数量（>10000）应跳过该条目，返回空列表。"""
    from uasset_read.serializers.package_summary import read_depends_map
    # dep_count = 100000 (超出 10000 限制)
    data = _PADDING + _i32_le(100000)

    archive = ByteArchive(data, tolerant=True)
    summary = _make_summary(export_count=1)

    result = read_depends_map(archive, summary)
    assert result == [[]], "异常数量条目应跳过，返回空列表"


def test_depends_map_negative_count():
    """DependsMap 负数数量应跳过该条目。"""
    from uasset_read.serializers.package_summary import read_depends_map
    data = _PADDING + _i32_le(-1)

    archive = ByteArchive(data, tolerant=True)
    summary = _make_summary(export_count=1)

    result = read_depends_map(archive, summary)
    assert result == [[]], "负数数量条目应跳过，返回空列表"


def test_depends_map_boundary_count():
    """DependsMap 边界值（正好 10000）应正常解析。"""
    from uasset_read.serializers.package_summary import read_depends_map
    # dep_count = 10000, 后续跟 10000 个 i32 依赖值（全为 0）
    dep_count_bytes = _i32_le(10000)
    deps_bytes = _i32_le(0) * 10000
    data = _PADDING + dep_count_bytes + deps_bytes

    archive = ByteArchive(data, tolerant=True)
    summary = _make_summary(export_count=1)

    result = read_depends_map(archive, summary)
    assert len(result) == 1
    assert len(result[0]) == 10000


def test_depends_map_mixed_normal_and_abnormal():
    """混合正常和异常条目时，仅跳过异常条目。"""
    from uasset_read.serializers.package_summary import read_depends_map
    # export_count = 3
    # 条目 0: dep_count = 2 (正常) → 两个依赖值 0, 0
    # 条目 1: dep_count = 50000 (异常) → 跳过
    # 条目 2: dep_count = 1 (正常) → 一个依赖值 0
    data = (
        _PADDING
        + _i32_le(2)       # dep_count = 2
        + _i32_le(0) * 2   # 2 deps
        + _i32_le(50000)   # dep_count = 50000 (异常)
        + _i32_le(1)       # dep_count = 1
        + _i32_le(0)       # 1 dep
    )

    archive = ByteArchive(data, tolerant=True)
    summary = _make_summary(export_count=3)

    result = read_depends_map(archive, summary)
    assert len(result) == 3, "应返回 3 个条目"
    assert len(result[0]) == 2, "条目 0 应有 2 个依赖"
    assert result[1] == [], "条目 1（异常）应被跳过"
    assert len(result[2]) == 1, "条目 2 应有 1 个依赖"


def test_depends_map_empty():
    """DependsMap 无数据时返回空列表。"""
    from uasset_read.serializers.package_summary import read_depends_map
    summary = _make_summary(export_count=0, depends_offset=0)

    result = read_depends_map(ByteArchive(b''), summary)
    assert result == []


def test_depends_map_zero_offset():
    """DependsMap offset 为 0 时返回空列表。"""
    from uasset_read.serializers.package_summary import read_depends_map
    summary = _make_summary(export_count=5, depends_offset=0)
    result = read_depends_map(ByteArchive(b'\x00' * 100), summary)
    assert result == []
