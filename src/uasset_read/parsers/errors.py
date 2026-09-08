"""Shared error type tuples for parser modules."""

import struct

from uasset_read.exceptions import ParseError

BINARY_READ_ERRORS: tuple[type[BaseException], ...] = (struct.error, OSError, ValueError)
BINARY_PARSE_ERRORS: tuple[type[BaseException], ...] = (struct.error, OSError, ValueError, ParseError)
PROPERTY_ACCESS_ERRORS: tuple[type[BaseException], ...] = (KeyError, TypeError, ValueError)
REFERENCE_RESOLVE_ERRORS: tuple[type[BaseException], ...] = (KeyError, IndexError, AttributeError)
