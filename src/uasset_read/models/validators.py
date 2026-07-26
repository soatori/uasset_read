"""Status value validators."""
from .fallback import ExportParseStatus

VALID_PARSE_STATUSES = {s.value for s in ExportParseStatus}


def validate_parse_status(value: str) -> str:
    """Validate export-level parse_status value.

    Args:
        value: The parse_status string to validate.

    Returns:
        The original value if validation passes.

    Raises:
        ValueError: If the value is not in the valid parse_status set.
    """
    if value not in VALID_PARSE_STATUSES:
        raise ValueError(
            f"Invalid parse_status: {value!r}. Must be one of {VALID_PARSE_STATUSES}"
        )
    return value
