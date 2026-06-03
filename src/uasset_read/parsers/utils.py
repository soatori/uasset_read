"""parsers 模块的共享辅助函数"""
from typing import Any, List, Optional

from uasset_read.exceptions import ParseError, ErrorContext


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
    """读取并验证数量值

    Args:
        archive: FArchive 实例
        max_count: 最大允许值
        label: 用于错误消息的标签

    Returns:
        验证后的数量值

    Raises:
        ParseError: 数量无效（可被 smart continue 机制捕获）
    """
    count = archive.read_i32()
    if count < 0:
        raise ParseError(
            f"{label}: 数量不能为负数 ({count})",
            context=ErrorContext(
                offset=archive.tell() - 4,
                phase="properties",
                operation="read_validated_count",
                context_name=label,
            ),
        )
    if count > max_count:
        raise ParseError(
            f"{label}: 数量超过最大值 ({count} > {max_count})",
            context=ErrorContext(
                offset=archive.tell() - 4,
                phase="properties",
                operation="read_validated_count",
                context_name=label,
            ),
        )
    return count


def make_enum_value(enum_type: str, value_name: str) -> dict:
    """创建 EnumValue 字典

    Args:
        enum_type: 枚举类型名称
        value_name: 枚举值名称

    Returns:
        EnumValue 字典
    """
    return {
        "enum_type": enum_type,
        "value_name": f"{enum_type}::{value_name}",
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
