"""DataTable semantic JSON domain (#557)."""
from __future__ import annotations

from uasset_read.semantic.extensions import register_extension
from uasset_read.semantic.data_table.extractor import build_data_table_content
from uasset_read.semantic.validator import register_domain_validator, validate_data_table_document

register_extension(
    "DataTable",
    build_data_table_content,
    domain_format="uasset_read.data_table_semantic",
    domain_format_version="1.0.0",
)
register_domain_validator("uasset_read.data_table_semantic", validate_data_table_document)
