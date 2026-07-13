"""核心工具函数"""


def safe_str(value: object, default: str = "") -> str:
    """安全转换为字符串"""
    if value is None:
        return default
    return str(value)


def safe_int(value: object, default: int = 0) -> int:
    """安全转换为整数，仅接受 int 和 str 类型"""
    if value is None:
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def normalize_hex_guid(guid_str: str | None) -> str | None:
    """归一化十六进制 GUID 为小写无连字符格式"""
    if not guid_str:
        return guid_str
    return guid_str.replace("-", "").lower()
