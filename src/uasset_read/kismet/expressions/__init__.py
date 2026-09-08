"""Kismet expression classes and token-to-class mapping.

Re-exports ``EXPR_CLASS_MAP`` from ``_map`` for backward compatibility.
Individual expression classes live in submodules (literals, variables, etc.)
— prefer importing from those in new code.
"""

from uasset_read.kismet.expressions._map import EXPR_CLASS_MAP

__all__ = ["EXPR_CLASS_MAP"]
