"""N2C 中间格式导出器 — 包装 to_n2c_json + validate_n2c_json。"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

from uasset_read.exporter.base import ExportOptions, IExporter
from uasset_read.n2c.serializer import to_n2c_json
from uasset_read.n2c.validation import validate_n2c_json

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult
    from uasset_read.link.result import LinkerParseResult


class N2CExporter(IExporter):
    """N2C 中间格式 JSON 导出器。

    支持输出验证（validate_n2c_json）。
    """

    def export(self, result: ParseResult | LinkerParseResult, options: ExportOptions) -> str:
        data = to_n2c_json(result=result)

        # 验证
        if options.validate_output:
            errors = validate_n2c_json(data)
            if errors:
                from uasset_read.exporter.base import ExportValidationError
                raise ExportValidationError(f"N2C validation failed: {'; '.join(errors)}")

        return json.dumps(data, indent=2, ensure_ascii=False)

    def validate(self, result: ParseResult | LinkerParseResult, options: ExportOptions) -> list[str]:
        data = to_n2c_json(result=result)
        return validate_n2c_json(data)

    @property
    def format_name(self) -> str:
        return "n2c"

    @property
    def validates_against_schema(self) -> bool:
        return True


# Auto-registration
from uasset_read.exporter.registry import ExporterRegistry
ExporterRegistry.register("n2c", N2CExporter)
