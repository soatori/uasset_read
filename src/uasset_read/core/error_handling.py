"""Unified error handling pattern — fault-tolerant parse context manager.

Consolidates the repeated try/except ParseError + result.errors.append pattern
into a declarative context manager, reducing boilerplate and unifying error message format.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult

from uasset_read.exceptions import ParseError

logger = logging.getLogger(__name__)


@contextmanager
def tolerant_parse(
    result: "ParseResult",
    stage: str,
):
    """Fault-tolerant parse context manager.

    Usage::

        with tolerant_parse(result, "blueprint extraction"):
            do_something()

    Behavior:
        Catch ParseError -> log to result.errors -> re-raise

    Args:
        result: ParseResult object (must have errors attribute)
        stage: Stage name, used as error message prefix
    """
    try:
        yield
    except ParseError as e:
        error_msg = f"{stage} error: {e}"
        if error_msg not in result.errors:
            result.errors.append(error_msg)
        raise
