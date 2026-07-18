"""PackageArchive.read() 短读校验。"""
import pytest
from uasset_read.package import PackageArchive
from uasset_read.exceptions import ParseError


class ShortReadArchive:
    """模拟短读的底层 archive。"""
    def __init__(self):
        self.pos = 0
    def read(self, size):
        return b"X"  # 总是只返回 1 字节
    def seek(self, pos):
        self.pos = pos
    def tell(self):
        return self.pos
    def close(self):
        pass
    def total_size(self):
        return 4
    def set_byte_swapping(self, enabled):
        pass


def test_package_archive_short_read_raises():
    """短读应抛 ParseError 而非静默推进位置。"""
    archive = PackageArchive(ShortReadArchive())
    with pytest.raises(ParseError, match="short read"):
        archive.read(4)


def test_package_archive_normal_read_ok():
    """正常读取应正常工作。"""
    class GoodArchive:
        def __init__(self):
            self.pos = 0
        def read(self, size):
            return b"\x00" * size
        def seek(self, pos):
            self.pos = pos
        def tell(self):
            return self.pos
        def close(self):
            pass
        def total_size(self):
            return 4
        def set_byte_swapping(self, enabled):
            pass

    archive = PackageArchive(GoodArchive())
    data = archive.read(4)
    assert len(data) == 4
