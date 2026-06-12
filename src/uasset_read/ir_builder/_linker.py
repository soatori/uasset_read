"""IR 构建层 — 链接器摘要。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from uasset_read.ir_builder._utils import _safe_str
from uasset_read.models.ir import LinkerSummaryIR

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult


def _build_linker(result: "ParseResult") -> LinkerSummaryIR | None:
    linker = result.linker
    if linker is None:
        return None

    import_paths = []
    for imp in result.import_map or []:
        path = f"{_safe_str(getattr(imp, 'class_package', None))}.{_safe_str(getattr(imp, 'class_name', None))}"
        if path.strip("."):
            import_paths.append(path)

    export_paths = []
    for exp in result.export_map or []:
        name = getattr(exp, "object_name", "")
        if name:
            export_paths.append(name)

    return LinkerSummaryIR(
        has_linker=True,
        import_paths=import_paths,
        export_paths=export_paths,
    )
