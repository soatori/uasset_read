"""CurveTable semantic content extractor (#557d).

Reads from ExportIR.asset_type_data (parse_curve_table manifest).
Follows the DataTable manifest domain pattern.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR, ExportIR


def build_curve_table_content(
    package_ir: "PackageIR",
    export_ir: "ExportIR",
    coverage_model,
) -> dict:
    """Build the CurveTable domain content dict.

    Reads the manifest from ExportIR.asset_type_data and extracts
    table summary, columns, and row names.
    """
    asset_type_data = getattr(export_ir, "asset_type_data", None)

    if not asset_type_data or not isinstance(asset_type_data, dict):
        coverage_model.track("table_summary", False)
        return {}

    coverage_model.track("table_summary", True)

    row_count = asset_type_data.get("row_count", 0)
    column_count = asset_type_data.get("column_count", 0)
    curve_type = asset_type_data.get("curve_type", "")

    columns = asset_type_data.get("columns", [])
    row_names = asset_type_data.get("row_names", [])

    coverage_model.track("columns", len(columns) > 0)
    coverage_model.track("row_names", len(row_names) > 0)

    return {
        "curve_table": {
            "table_summary": {
                "row_count": row_count,
                "column_count": column_count,
                "curve_type": curve_type,
            },
            "columns": columns,
            "row_names": row_names,
        },
    }
