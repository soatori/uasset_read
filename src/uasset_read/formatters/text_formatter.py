"""Text 格式化 — YAML 风格完整输出、精简输出。

等价迁移 uasset_read_legacy.py L7431-7571。
"""
from __future__ import annotations

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult
    from uasset_read.models.core import UEdGraph

from uasset_read.serializers.object_resources import get_asset_class, get_asset_class_with_linker
from uasset_read.graph import build_connections_map, build_execution_chains


def format_text_full(result: ParseResult) -> str:
    """
    YAML 风格完整文本输出（OUT-02, OUT2-03）。

    Per D-17: YAML 风格层级，2 空格缩进
    Per D-19: ERRORS 区块在末尾
    Per D-21: Blueprint 元数据嵌入
    Per D-22: 嵌套 YAML 缩进

    Args:
        result: ParseResult 来自 parse_uasset()

    Returns:
        str: YAML 风格文本输出
    """
    lines = []

    # Package header
    if result.summary:
        package_name = result.summary.package_name or "Unknown"
        lines.append(f"Package: {package_name}")
        lines.append(f"  Version: UE5={result.summary.file_version_ue5}")
        lines.append(f"  Flags: 0x{result.summary.package_flags:08X}")
        lines.append(f"  Imports: {len(result.import_map)}")
        lines.append(f"  Exports: {len(result.export_map) if result.export_map else 0}")
        lines.append(f"  NameMap: {len(result.name_map)}")
        lines.append("")
    else:
        lines.append("Package: Unknown")
        lines.append("  Version: Unknown")
        lines.append("  Flags: Unknown")
        lines.append("  Imports: 0")
        lines.append("  Exports: 0")
        lines.append("  NameMap: 0")
        lines.append("")

    # Exports section
    lines.append("Exports:")

    # Extract linker for class resolution (may be None for legacy ParseResult)
    linker = getattr(result, 'linker', None)

    for i, exp in enumerate(result.export_map or []):
        asset_class = (get_asset_class_with_linker(exp, linker) if linker else get_asset_class(exp, result.import_map, result.export_map or []))
        lines.append(f"  - Name: {exp.object_name}")
        lines.append(f"    Class: {asset_class}")
        lines.append(f"    SerialSize: {exp.serial_size}")

        if exp.properties:
            lines.append(f"    Properties:")
            for prop in exp.properties:
                lines.append(f"      - Name: {prop.name}")
                lines.append(f"        Type: {prop.type}")
                value_str = str(prop.value) if prop.value is not None else "null"
                lines.append(f"        Value: {value_str}")

        lines.append("")  # Blank line between exports

    # Blueprint section
    if result.blueprint and result.blueprint.is_blueprint:
        lines.append("Blueprint:")
        parent = result.blueprint.parent_class or "Unknown"
        lines.append(f"  ParentClass: {parent}")
        lines.append(f"  Variables: {len(result.blueprint.variables)}")

        for var in result.blueprint.variables:
            lines.append(f"  - Name: {var.var_name}")
            lines.append(f"    Type: {var.var_type.pin_category}")
            default = var.default_value or "None"
            lines.append(f"    Default: {default}")
            category = var.category or "Default"
            lines.append(f"    Category: {category}")

        lines.append("")  # Blank line after blueprint

    # Graphs section (OUT2-03)
    if result.graphs:
        lines.append("Graphs:")
        for graph in result.graphs:
            # 获取连接数量
            connections, _ = build_connections_map(graph)

            # 获取执行流链式表达
            execution_chains = build_execution_chains(graph)

            lines.append(f"  - Name: {graph.graph_name}")
            lines.append(f"    Class: {graph.graph_class}")
            lines.append(f"    Nodes: {len(graph.nodes)}")
            lines.append(f"    Connections: {len(connections)}")

            # 执行流链式概览
            lines.append(f"    ExecutionChains: {len(execution_chains)}")
            for chain_entry in execution_chains:
                start_event = chain_entry.get("start_event", "Unknown")
                chains = chain_entry.get("chains", [])
                has_cycle = chain_entry.get("has_cycle", False)
                # 直接展示链式字符串
                for chain_str in chains:
                    cycle_marker = " (cycle)" if has_cycle else ""
                    lines.append(f"      - {start_event}: {chain_str}{cycle_marker}")

        lines.append("")  # Graphs 区块后的空行

    # Linker section
    lines.append("Linker:")
    linker = getattr(result, 'linker', None)
    if linker is not None:
        export_count = len(getattr(linker, '_export_objects', []))
        import_count = len(getattr(linker, '_import_objects', []))
        root_count = len(getattr(linker, '_root_objects', []))
        lines.append(f"  ImportObjects: {import_count}")
        lines.append(f"  ExportObjects: {export_count}")
        lines.append(f"  RootObjects: {root_count}")
    else:
        lines.append(f"  ImportMap: {len(result.import_map)}")
        lines.append(f"  ExportMap: {len(result.export_map) if result.export_map else 0}")
        lines.append(f"  Status: not_available")
    lines.append("")

    # ERRORS block
    if result.errors:
        lines.append("ERRORS:")
        for err in result.errors:
            lines.append(f"  - {err}")
    else:
        lines.append("ERRORS:")
        lines.append("  (none)")

    return "\n".join(lines)


def format_text_summary(result: ParseResult) -> str:
    """
    精简 YAML 风格摘要（OUT-02）。

    Per D-18: 每个 export 一行: "Name (Type)"
    Per D-22: YAML 缩进

    Args:
        result: ParseResult 来自 parse_uasset()

    Returns:
        str: 精简 YAML 风格摘要
    """
    lines = []

    # Package header
    package_name = result.summary.package_name if result.summary else "Unknown"
    lines.append(f"Package: {package_name}")
    lines.append(f"Exports: {len(result.export_map) if result.export_map else 0}")
    lines.append("")  # Blank line

    # Exports: one line each
    # Extract linker for class resolution (may be None for legacy ParseResult)
    linker = getattr(result, 'linker', None)

    for exp in result.export_map or []:
        asset_class = (get_asset_class_with_linker(exp, linker) if linker else get_asset_class(exp, result.import_map, result.export_map or []))
        lines.append(f"  - {exp.object_name} ({asset_class})")

    # Blueprint summary
    if result.blueprint and result.blueprint.is_blueprint:
        lines.append("")
        lines.append("Blueprint:")
        parent = result.blueprint.parent_class or "Unknown"
        lines.append(f"  Parent: {parent}")
        lines.append(f"  Variables: {len(result.blueprint.variables)}")

    return "\n".join(lines)