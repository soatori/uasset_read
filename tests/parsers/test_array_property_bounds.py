"""ArrayProperty tag.size < 4 在读取 count 前返回。"""
from uasset_read.parsers.property_types import parse_array_property
from uasset_read.models.properties import PropertyTag


class TrackingArchive:
    """记录 read_i32 调用次数。"""
    def __init__(self):
        self.pos = 0
        self.read_count = 0
    def tell(self):
        return self.pos
    def read_i32(self):
        self.read_count += 1
        self.pos += 4
        return 0
    def read_fstring(self):
        return ""
    def read_byte(self):
        return 0


def test_small_tag_size_skips_count_read():
    """tag.size < 4 不应读取 count。"""
    for size in (0, 1, 3):
        a = TrackingArchive()
        tag = PropertyTag(name="A", type="ArrayProperty", size=size)
        result = parse_array_property(tag, a, [], [])
        assert result == [], f"size={size}: 应返回空数组"
        assert a.read_count == 0, f"size={size}: 不应调用 read_i32 (count)"
