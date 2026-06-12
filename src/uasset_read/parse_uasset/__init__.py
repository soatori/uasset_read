"""Main parsing pipeline entry — parse_uasset() function.

Migrated from uasset_read.py §6223-6412.
"""
from ._core import (
    parse_package,
    parse_uasset,
    parse_uasset_with_linker,
)

__all__ = [
    "parse_package",
    "parse_uasset",
    "parse_uasset_with_linker",
]
