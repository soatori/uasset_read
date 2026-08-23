"""DataTable semantic content extractor (#557).

Reads from ExportIR.asset_type_data (parse_data_table output).
Projects row summary, row names, and row struct information.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR, ExportIR


def build_data_table_content(
    package_ir: "PackageIR",
    export_ir: "ExportIR",
    coverage_model,
    evidence_list,
) -> dict:
    """Build the DataTable domain content dict.

    Reads the manifest from ExportIR.asset_type_data and extracts
    row summary, row names, and row struct information.
    """
    asset_type_data = getattr(export_ir, "asset_type_data", None)

    if not asset_type_data or not isinstance(asset_type_data, dict):
        coverage_model.track("table_summary", False)
        return {}

    coverage_model.track("table_summary", True)

    row_count = asset_type_data.get("row_count", 0)
    rows = asset_type_data.get("rows", [])

    coverage_model.track("rows", len(rows) > 0)

    # Extract row names for summary
    row_names = [row.get("name", "") for row in rows]

    # Extract row struct info if available
    row_struct = None
    if "row_struct" in asset_type_data:
        row_struct = asset_type_data["row_struct"]

    content: dict = {"data_table": {}}

    # Top-level row_count (validator reads data_table.get("row_count"))
    content["data_table"]["row_count"] = row_count

    # Table summary
    table_summary: dict = {
        "row_count": row_count,
    }
    if row_struct:
        table_summary["row_struct"] = row_struct
    content["data_table"]["table_summary"] = table_summary

    # Row names
    if row_names:
        content["data_table"]["row_names"] = row_names

    # Rows with payload sizes
    row_details = []
    for row in rows:
        row_detail: dict = {
            "name": row.get("name", ""),
            "payload_size": row.get("payload_size", 0),
        }
        row_details.append(row_detail)
    if row_details:
        content["data_table"]["rows"] = row_details

    return content
