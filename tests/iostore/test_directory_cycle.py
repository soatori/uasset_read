"""IoStore 目录索引环检测测试。"""
import struct
import subprocess
import sys
import pytest

from uasset_read.iostore.reader import IoStoreReader
from uasset_read.exceptions import ParseError


def _build_cyclic_directory_index() -> bytes:
    """构造一个包含环的目录索引 buffer。

    结构：mount_point + directory_entries + file_entries + string_table
    环：entry 0 的 first_child_entry = 0（指向自身）
    """
    buf = bytearray()

    # mount_point: FString "Test/"
    mount = b"Test/\x00"
    buf += struct.pack("<i", len(mount))  # length (positive = UTF-8)
    buf += mount

    # directory_entries: 1 entry
    buf += struct.pack("<i", 1)  # count = 1
    # FIoDirectoryIndexEntry: name(4) + first_child_entry(4) + next_sibling_entry(4) + first_file_entry(4)
    buf += struct.pack("<i", 0)   # name = string_table[0]
    buf += struct.pack("<i", 0)   # first_child_entry = 0 → 环！
    buf += struct.pack("<i", -1)  # next_sibling_entry = invalid
    buf += struct.pack("<i", -1)  # first_file_entry = invalid

    # file_entries: 0 entries
    buf += struct.pack("<i", 0)

    # string_table: 1 entry
    buf += struct.pack("<i", 1)  # count = 1
    name = b"dir\x00"
    buf += struct.pack("<i", len(name))
    buf += name

    return bytes(buf)


def test_cyclic_directory_index_raises_parse_error():
    """目录索引环应抛出 ParseError，而非 RecursionError。"""
    reader = IoStoreReader.__new__(IoStoreReader)
    reader._directory_index_buffer = _build_cyclic_directory_index()
    reader._header = None
    reader._aes_key = None
    reader._chunk_ids = []
    reader._directory_index = {}
    reader._mount_point = ""

    # 不应是 RecursionError
    with pytest.raises(ParseError, match="环|cycle|深度"):
        reader._parse_directory_index()


def test_file_chain_cycle_raises():
    """文件链环应抛出 ParseError。"""
    buf = bytearray()
    # mount_point
    mount = b"/\x00"
    buf += struct.pack("<i", len(mount))
    buf += mount

    # directory_entries: 1 entry（无子目录）
    buf += struct.pack("<i", 1)
    buf += struct.pack("<i", -1)  # name = invalid
    buf += struct.pack("<i", -1)  # first_child_entry = invalid
    buf += struct.pack("<i", -1)  # next_sibling_entry = invalid
    buf += struct.pack("<i", 0)   # first_file_entry = 0

    # file_entries: 1 entry，next_file_entry = 0（环）
    buf += struct.pack("<i", 1)
    buf += struct.pack("<i", 0)   # name
    buf += struct.pack("<i", 0)   # user_data
    buf += struct.pack("<i", 0)   # next_file_entry = 0 → 环！

    # string_table
    buf += struct.pack("<i", 1)
    fname = b"test.uasset\x00"
    buf += struct.pack("<i", len(fname))
    buf += fname

    reader = IoStoreReader.__new__(IoStoreReader)
    reader._directory_index_buffer = bytes(buf)
    reader._header = None
    reader._aes_key = None
    reader._chunk_ids = []
    reader._directory_index = {}
    reader._mount_point = ""

    with pytest.raises(ParseError, match="环|cycle|深度"):
        reader._parse_directory_index()


def _build_sibling_cycle_index() -> bytes:
    """构造一个 next_sibling_entry 自环的目录索引 buffer。

    结构：mount_point + directory_entries + file_entries + string_table
    环：entry 0 的 next_sibling_entry = 0（指向自身）
    """
    buf = bytearray()

    # mount_point: FString "Test/"
    mount = b"Test/\x00"
    buf += struct.pack("<i", len(mount))  # length (positive = UTF-8)
    buf += mount

    # directory_entries: 1 entry
    buf += struct.pack("<i", 1)  # count = 1
    # FIoDirectoryIndexEntry: name(4) + first_child_entry(4) + next_sibling_entry(4) + first_file_entry(4)
    buf += struct.pack("<i", 0)   # name = string_table[0]
    buf += struct.pack("<i", -1)  # first_child_entry = invalid
    buf += struct.pack("<i", 0)   # next_sibling_entry = 0 → 环！
    buf += struct.pack("<i", -1)  # first_file_entry = invalid

    # file_entries: 0 entries
    buf += struct.pack("<i", 0)

    # string_table: 1 entry
    buf += struct.pack("<i", 1)  # count = 1
    name = b"dir\x00"
    buf += struct.pack("<i", len(name))
    buf += name

    return bytes(buf)


def test_sibling_cycle_raises_parse_error():
    """next_sibling_entry 自环应抛出 ParseError，而非无限循环。"""
    reader = IoStoreReader.__new__(IoStoreReader)
    reader._directory_index_buffer = _build_sibling_cycle_index()
    reader._header = None
    reader._aes_key = None
    reader._chunk_ids = []
    reader._directory_index = {}
    reader._mount_point = ""

    with pytest.raises(ParseError, match="环|cycle|深度"):
        reader._parse_directory_index()


def test_sibling_cycle_no_hang_subprocess():
    """子进程隔离验证：修复后 sibling 自环不应导致进程挂起。

    使用 subprocess.run 超时检测，确保 _parse_directory_index 不死循环。
    """
    code = """
import sys
sys.path.insert(0, "src")
from uasset_read.iostore.reader import IoStoreReader
from uasset_read.exceptions import ParseError
import struct

# 构造 next_sibling_entry 自环 buffer
buf = bytearray()
mount = b"Test/\\x00"
buf += struct.pack("<i", len(mount))
buf += mount
buf += struct.pack("<i", 1)      # directory_entries count = 1
buf += struct.pack("<i", 0)      # name = 0
buf += struct.pack("<i", -1)     # first_child_entry = invalid
buf += struct.pack("<i", 0)      # next_sibling_entry = 0 → 环！
buf += struct.pack("<i", -1)     # first_file_entry = invalid
buf += struct.pack("<i", 0)      # file_entries count = 0
buf += struct.pack("<i", 1)      # string_table count = 1
name = b"dir\\x00"
buf += struct.pack("<i", len(name))
buf += name

reader = IoStoreReader.__new__(IoStoreReader)
reader._directory_index_buffer = bytes(buf)
reader._header = None
reader._aes_key = None
reader._chunk_ids = []
reader._directory_index = {}
reader._mount_point = ""

try:
    reader._parse_directory_index()
    sys.exit(1)  # 应该抛出异常，不应正常返回
except ParseError:
    sys.exit(0)  # 预期行为：ParseError
except Exception:
    sys.exit(1)  # 其他异常视为失败
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        timeout=3.0,
        cwd="E:/Develop/uasset_read",
    )
    assert result.returncode == 0, (
        f"子进程应正常退出（ParseError），实际退出码: {result.returncode}\n"
        f"stdout: {result.stdout.decode()}\n"
        f"stderr: {result.stderr.decode()}"
    )
