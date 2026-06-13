"""parsers 模块的共享辅助函数"""
from typing import Any, List, Optional
import logging

from uasset_read.exceptions import ParseError, ErrorContext

logger = logging.getLogger(__name__)


def resolve_name_from_index(
    archive: Any,
    name_map: List[str],
    index: int,
    fallback_prefix: str = "param",
) -> str:
    """统一的名称索引解析逻辑

    Args:
        archive: FArchive 实例
        name_map: 名称映射表
        index: 索引值
        fallback_prefix: 索引越界时的回退前缀

    Returns:
        解析后的名称字符串
    """
    if 0 <= index < len(name_map):
        return name_map[index]
    return f"{fallback_prefix}_{index}"


def read_validated_count(
    archive: Any,
    max_count: int,
    label: str,
) -> int:
    """读取并验证数量值。

    当 count 为负数或超过 max_count 时，记录诊断日志并返回 0（跳过后续循环），
    而非抛出 ParseError。这样调用方的 ``for _ in range(count)`` 循环不会执行，
    返回空集合，同时保留父级属性结构的完整性。

    Args:
        archive: FArchive 实例
        max_count: 最大允许值
        label: 用于错误消息的标签

    Returns:
        验证后的数量值（无效时返回 0）
    """
    offset = archive.tell()
    count = archive.read_i32()

    # 检查 struct.unpack 读取的值是否在 i32 范围内（Python 自动处理大整数，
    # 但 read_i32 使用 '<i' 有符号格式，所以负数已正确表示）
    if count < 0:
        logger.warning(
            "%s: 数量为负数 (%d)，跳过 | 位置=0x%X, 上限=%d",
            label, count, offset, max_count,
        )
        return 0
    if count > max_count:
        logger.warning(
            "%s: 数量超过最大值 (%d > %d)，跳过 | 位置=0x%X",
            label, count, max_count, offset,
        )
        return 0
    return count


def make_enum_value(enum_type: str, value_name: str) -> dict:
    """创建 EnumValue 字典

    Args:
        enum_type: 枚举类型名称
        value_name: 枚举值名称

    Returns:
        EnumValue 字典
    """
    # #143: 当 enum_type 未知时，不添加 "UnknownEnum::" 前缀
    if enum_type and enum_type != "UnknownEnum":
        full_name = f"{enum_type}::{value_name}"
    else:
        full_name = value_name
    return {
        "enum_type": enum_type,
        "value_name": full_name,
    }


def extract_inner_from_tag(tag_type: str) -> Optional[str]:
    """从 tag.type 字符串中提取括号内的内容

    Args:
        tag_type: 类型字符串，如 "ArrayProperty(IntProperty)"

    Returns:
        括号内的内容，无括号则返回 None
    """
    start = tag_type.find("(")
    end = tag_type.rfind(")")
    if start != -1 and end != -1 and end > start:
        return tag_type[start + 1:end]
    return None
