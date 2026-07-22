"""状态值验证器。"""
from .fallback import ExportParseStatus

VALID_PARSE_STATUSES = {s.value for s in ExportParseStatus}


def validate_parse_status(value: str) -> str:
    """验证 export 级 parse_status 值。

    Args:
        value: 待验证的 parse_status 字符串。

    Returns:
        验证通过的原始值。

    Raises:
        ValueError: 值不在合法的 parse_status 集合中。
    """
    if value not in VALID_PARSE_STATUSES:
        raise ValueError(
            f"Invalid parse_status: {value!r}. Must be one of {VALID_PARSE_STATUSES}"
        )
    return value
