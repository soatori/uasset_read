"""Shared error type tuples for parser modules."""

import struct

BINARY_READ_ERRORS: tuple[type[BaseException], ...] = (struct.error, OSError, ValueError)
REFERENCE_RESOLVE_ERRORS: tuple[type[BaseException], ...] = (KeyError, IndexError, AttributeError)
