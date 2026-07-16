"""属性提取辅助函数 — 消除 asset_types 处理器中的重复模式。"""
from typing import Any, Callable, TypeVar

T = TypeVar("T")


def build_properties_dict(properties_list: list) -> dict[str, Any]:
    """将属性列表转换为字典格式（name -> value）。

    所有 handler 都需要将 export.properties（属性对象列表）转换为
    name -> value 的字典，以便 extract_* 函数使用。

    Args:
        properties_list: 属性对象列表（每个有 name 和 value 属性）

    Returns:
        name -> value 的字典
    """
    properties: dict[str, Any] = {}
    for prop in properties_list:
        if hasattr(prop, "name") and hasattr(prop, "value"):
            properties[prop.name] = prop.value
    return properties


def parse_dict_list(
    data: Any,
    parser: Callable[[dict], Any],
) -> list[Any]:
    """解析字典列表，跳过非字典元素。

    Args:
        data: 待解析数据（列表或任意类型）
        parser: 字典解析函数

    Returns:
        解析后的列表，data 非列表时返回空列表
    """
    if not isinstance(data, list):
        return []
    return [parser(item) for item in data if isinstance(item, dict)]


def extract_property(
    properties: dict[str, Any],
    prop_name: str,
    target: Any,
    field_name: str,
    transform: Callable[[Any], Any] | None = None,
) -> bool:
    """从 properties 字典提取属性值到目标对象字段。

    Args:
        properties: 属性字典 (name -> value)
        prop_name: 要提取的属性名
        target: 目标对象（将通过 setattr 设置字段）
        field_name: 目标字段名
        transform: 可选的值转换函数

    Returns:
        True 如果属性存在且已设置，False 否则
    """
    if prop_name not in properties:
        return False
    value = properties[prop_name]
    if transform is not None:
        value = transform(value)
    setattr(target, field_name, value)
    return True


def extract_object_ref(
    properties: dict[str, Any],
    prop_name: str,
    target: Any,
    field_name: str,
    ref_key: str = "object_path",
) -> bool:
    """从 properties 提取对象引用。

    对象引用通常以 dict 形式存储，包含 "object_path"、"full_name" 等键。
    此函数提取指定键的值并设置到目标字段。

    Args:
        properties: 属性字典
        prop_name: 要提取的属性名
        target: 目标对象
        field_name: 目标字段名
        ref_key: 引用 dict 中的键名，默认 "object_path"

    Returns:
        True 如果属性存在且是 dict 类型，False 否则
    """
    if prop_name not in properties:
        return False
    ref = properties[prop_name]
    if isinstance(ref, dict):
        setattr(target, field_name, ref.get(ref_key))
    return True


def extract_array_property(
    properties: dict[str, Any],
    prop_name: str,
    parser: Callable[[Any], list[Any]],
) -> list[Any]:
    """从 properties 提取数组属性并解析。

    Args:
        properties: 属性字典
        prop_name: 要提取的属性名
        parser: 解析函数，接收属性值并返回解析后的列表

    Returns:
        解析后的列表，属性不存在时返回空列表
    """
    if prop_name not in properties:
        return []
    return parser(properties[prop_name])
