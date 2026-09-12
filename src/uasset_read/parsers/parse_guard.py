"""Safe parse context manager for binary reading."""

from contextlib import contextmanager

from uasset_read.parsers.errors import BINARY_READ_ERRORS


@contextmanager
def safe_parse(archive):
    """Context manager that seeks back to start on binary read errors.

    Args:
        archive: FArchive instance with tell()/seek() methods
    """
    start = archive.tell()
    try:
        yield
    except BINARY_READ_ERRORS:
        archive.seek(start)
        raise
