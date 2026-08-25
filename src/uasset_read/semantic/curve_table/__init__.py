"""CurveTable semantic JSON domain (#557d)."""
from __future__ import annotations

from uasset_read.semantic.extensions import register_extension
from uasset_read.semantic.curve_table.extractor import build_curve_table_content

register_extension(
    "CurveTable",
    build_curve_table_content,
    domain_format="uasset_read.curve_table_semantic",
    domain_format_version="1.0.0",
)
