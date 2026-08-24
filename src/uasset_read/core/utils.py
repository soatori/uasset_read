"""Core utility functions."""


def safe_str(value: object, default: str = "") -> str:
    """Safely convert to string."""
    if value is None:
        return default
    return str(value)


def safe_int(value: object, default: int = 0) -> int:
    """Safely convert to integer, only accepts int and str types."""
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
    """Normalize hexadecimal GUID to lowercase hyphen-free format."""
    if not guid_str:
        return guid_str
    return guid_str.replace("-", "").lower()


def normalize_path(s: str) -> str:
    """Normalize Windows backslashes to forward slashes and strip trailing slashes."""
    return s.replace("\\", "/").rstrip("/")
