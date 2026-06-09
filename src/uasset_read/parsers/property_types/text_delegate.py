"""文本/枚举/委托属性类型解析函数。

从 _all_types.py 拆分出的 text, enum, delegate 系列解析器。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Any

if TYPE_CHECKING:
    from uasset_read.archive import FArchive

from uasset_read.models.properties import (
    PropertyTag, EnumValue, TextValue, DelegateValue,
)
from uasset_read.parsers.utils import make_enum_value


def _extract_enum_type_from_tag(tag: PropertyTag) -> str:
    """从 PropertyTag 提取枚举类型名（D-08）。"""
    from uasset_read.parsers.utils import extract_inner_from_tag
    inner = extract_inner_from_tag(tag.type)
    if inner is not None:
        if "." in inner:
            return inner.split(".")[-1]
        return inner
    return "UnknownEnum"


def parse_enum_property(
    tag: PropertyTag,
    archive: FArchive,
    name_map: List[str],
    summary: Optional[Any] = None
) -> EnumValue:
    """解析 EnumProperty（ADVP-04）。"""
    enum_type = _extract_enum_type_from_tag(tag)
    enum_value_name = archive.read_name(name_map)
    return make_enum_value(enum_type, enum_value_name)


def _read_ftext_base(archive: "FArchive") -> tuple[str, str, str]:
    """读取 Base FText: namespace + key + source_string。"""
    namespace = archive.read_fstring()
    key = archive.read_fstring()
    source_string = archive.read_fstring()
    return namespace, key, source_string


def _read_ftext_args(archive: "FArchive") -> None:
    """读取 FText 参数字典并丢弃（仅消耗字节）。"""
    from uasset_read.parsers.utils import read_validated_count
    count = read_validated_count(archive, 10_000, "FText args")
    for _ in range(count):
        archive.read_fstring()  # key
        archive.read_fstring()  # value


def parse_text_property(tag: PropertyTag, archive: "FArchive") -> TextValue:
    """解析 TextProperty（ADVP-05）。

    UE FText 序列化格式:
      - flags: i32 (4 bytes)
      - history_type: u8 (1 byte) — FTextHistory 类型标识
      - body: 根据 history_type 不同而不同
    """
    _flags = archive.read_i32()       # FText flags (unused)
    history_type = archive.read_u8()  # FTextHistory type

    if history_type == 0:  # Base
        namespace, key, source_string = _read_ftext_base(archive)
    elif history_type == 1:  # NamedFormat
        namespace = archive.read_fstring()
        key = archive.read_fstring()
        _read_ftext_args(archive)
        source_string = ""
    elif history_type == 2:  # OrderedFormat
        namespace, key, source_string = _read_ftext_base(archive)
        _read_ftext_args(archive)
    elif history_type == 3:  # ArgumentFormat
        namespace, key, source_string = _read_ftext_base(archive)
        _read_ftext_args(archive)
    elif history_type == 4:  # AsNumber
        namespace, key, source_string = _read_ftext_base(archive)
        archive.read_fstring()  # target_number
    elif history_type == 5:  # AsPercent
        namespace, key, source_string = _read_ftext_base(archive)
        archive.read_fstring()  # target_value
    elif history_type == 6:  # AsCurrency
        namespace, key, source_string = _read_ftext_base(archive)
        archive.read_fstring()  # currency_code
        archive.read_fstring()  # target_amount
    elif history_type == 7:  # DateString
        namespace, key, source_string = _read_ftext_base(archive)
        archive.read_fstring()  # date
    elif history_type == 8:  # TimeString
        namespace, key, source_string = _read_ftext_base(archive)
        archive.read_fstring()  # time
    elif history_type == 9:  # DateTimeString
        namespace, key, source_string = _read_ftext_base(archive)
        archive.read_fstring()  # datetime
    elif history_type == 10:  # Transform
        namespace, key, source_string = _read_ftext_base(archive)
        archive.read_fstring()  # transform_type
    else:
        # Unknown history type: skip remaining data
        remaining = tag.size - 5  # 5 = flags(4) + history_type(1)
        if remaining > 0:
            archive.read(remaining)
        namespace = ""
        key = ""
        source_string = ""

    return TextValue(
        namespace=namespace or "",
        key=key or "",
        source_string=source_string or ""
    )


def parse_delegate_property(
    tag: PropertyTag,
    archive: "FArchive",
    name_map: List[str]
) -> DelegateValue:
    """解析 DelegateProperty（ADVP-06）。"""
    object_ref = archive.read_i32()
    function_name = archive.read_name(name_map)
    return DelegateValue(object_ref=object_ref, function_name=function_name)


def parse_multicast_delegate_property(tag: PropertyTag, archive: "FArchive") -> list:
    """解析 MulticastDelegateProperty"""
    from uasset_read.parsers.utils import read_validated_count
    count = read_validated_count(archive, 10_000, "MulticastDelegate")
    delegates = []
    for _ in range(count):
        obj_index = archive.read_i32()
        func_name = archive.read_fstring()
        delegates.append({"object": obj_index, "function": func_name})
    return delegates


def parse_multicast_inline_delegate_property(tag: PropertyTag, archive: "FArchive") -> list:
    """解析 MulticastInlineDelegateProperty"""
    return parse_multicast_delegate_property(tag, archive)


def parse_multicast_sparse_delegate_property(tag: PropertyTag, archive: "FArchive") -> list:
    """解析 MulticastSparseDelegateProperty"""
    return parse_multicast_delegate_property(tag, archive)
