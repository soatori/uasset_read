"""Safe parse context manager for binary reading."""

from contextlib import contextmanager

from uasset_read.parsers.errors import BINARY_READ_ERRORS


@contextmanager
def safe_parse(archive, *, on_error=None):
    """Context manager that seeks back to start on binary read errors.

    Args:
        archive: FArchive instance with tell()/seek() methods
        on_error: optional callback invoked with the exception before re-raising
    """
    start = archive.tell()
    try:
        yield
    except BINARY_READ_ERRORS as e:
        archive.seek(start)
        if on_error:
            on_error(e)
        raise
