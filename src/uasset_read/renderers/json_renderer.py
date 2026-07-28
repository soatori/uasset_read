from __future__ import annotations

"""JSON renderer — Recursively serializes PackageIR to JSON.

Only registers the json format: full analysis format, most comprehensive fields.
"""

import json
import re
import dataclasses
from typing import IO, TYPE_CHECKING, Any

from uasset_read.renderers.base import (
    IRenderer, RenderOptions,
    EDITOR_PROPERTY_NAMES,
    filter_editor_items, filter_variables,
)
from uasset_read.renderers import register_renderer
from uasset_read.constants import decode_package_flags
from uasset_read.models.asset_metadata import sanitize_asset_metadata
from uasset_read.models.ir import HexViewEntryIR

if TYPE_CHECKING:
    from uasset_read.models.ir import PackageIR


class _JSONEncoder(json.JSONEncoder):
    """Custom JSON encoder, handles non-native types like dataclass."""

    def default(self, o):
        to_dict = getattr(type(o), "to_dict", None)
        if callable(to_dict):
            return to_dict(o)
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        if isinstance(o, bytes):
            return o.hex()
        return super().default(o)


class JSONRenderer(IRenderer):
    """JSON renderer — Full analysis format. Recursively serializes IR to JSON."""

    def render(self, ir: PackageIR, options: RenderOptions) -> str:
        data = self._build_data(ir, options)
        return json.dumps(data, indent=options.indent, ensure_ascii=False, cls=_JSONEncoder)

    def render_to(self, ir: PackageIR, writer: IO[str], options: RenderOptions | None = None) -> None:
        """Stream IR to writer, avoiding building the full JSON string.

        Output format is consistent with render(), uses json.dump to write directly to writer.
        Suitable for large files or pipeline output scenarios (no intermediate string memory usage).

        Args:
            ir: PackageIR instance
            writer: Writable text stream (StringIO, file object, etc.)
            options: Render options, defaults to RenderOptions() when None
        """
        if options is None:
            options = RenderOptions()
        data = self._build_data(ir, options)
        json.dump(data, writer, indent=options.indent, ensure_ascii=False, cls=_JSONEncoder)
        writer.write("\n")

    def _build_data(self, ir: PackageIR, options: RenderOptions) -> dict[str, Any]:
        """Build the render data dictionary (shared by render() and render_to())."""
        is_debug = options.output_level == "debug"

        data: dict[str, Any] = {}
        if options.include_schema:
            data["$schema"] = "package.schema.json"
        data["status"] = {
            "status": ir.diagnostics_data.status if ir.diagnostics_data else "success",
            "message": ir.diagnostics_data.status_message if ir.diagnostics_data else None,
            "code": ir.diagnostics_data.status_code if ir.diagnostics_data else None,
        }
        data["metadata"] = {}
        data["summary"] = {
            "package_name": ir.header.package_name,
            "package_class": ir.header.package_class,
            "package_flags": ir.header.package_flags,
            "package_flags_decoded": decode_package_flags(ir.header.package_flags),
            "total_export_count": ir.header.total_export_count,
            "total_import_count": ir.header.total_import_count,
            "ue_version": ir.header.ue_version,
            "saved_hash": ir.header.saved_hash.hex() if ir.header.saved_hash else None,
            "total_properties": ir.header.total_properties,
            "total_name_entries": ir.header.total_name_entries,
        }
        all_exports = ir.exports if is_debug else filter_editor_items(ir.exports)
        # Filter exports with absurd serial_size (corrupted metadata)
        if not is_debug:
            all_exports = [e for e in all_exports if e.serial_size > 0]
        data["exports"] = [
            self._export_to_dict(e, options, is_debug, name_map=ir.name_map)
            for e in all_exports
        ]
        data["import_map"] = [
            {"index": i["index"], "class_package": i["class_package"],
             "class_name": i["class_name"], "object_name": i["object_name"]}
            for i in ir.import_map
        ]
        data["name_map"] = ir.name_map_entries
        if ir.blueprint is not None:
            data["blueprint"] = self._blueprint_to_dict(ir.blueprint)
        if ir.decompiled_functions:
            data["decompiled_functions"] = [self._decompiled_function_to_dict(f) for f in ir.decompiled_functions]
        if ir.execution_chains:
            chains = [{"event": c.event, "chain": c.chain} for c in ir.execution_chains]
            if is_debug:
                data["execution_chains"] = chains
            else:
                chains_with_content = [c for c in chains if c.get("chain")]
                if chains_with_content:
                    data["execution_chains"] = chains_with_content
        if ir.variables:
            if is_debug:
                data["variables"] = [self._variable_to_dict(v) for v in ir.variables]
            else:
                variables = [
                    self._variable_to_dict(v) for v in filter_variables(ir.variables)
                ]
                if variables:
                    data["variables"] = variables
        if ir.dependencies and ir.dependencies.resolved_parent_assets:
            data["resolved_parent_assets"] = ir.dependencies.resolved_parent_assets
        if ir.dependencies and ir.dependencies.inherited_blueprint_graphs:
            data["inherited_blueprint_graphs"] = ir.dependencies.inherited_blueprint_graphs
        if ir.logic_sources:
            data["logic_sources"] = ir.logic_sources
        if ir.diagnostics_data and ir.diagnostics_data.errors:
            data["errors"] = ir.diagnostics_data.errors
        data["warnings"] = ir.diagnostics_data.warnings if ir.diagnostics_data else []
        if ir.diagnostics_data and ir.diagnostics_data.diagnostics_truncated_count > 0:
            data["diagnostics_truncated_count"] = ir.diagnostics_data.diagnostics_truncated_count
        all_diags = [d.to_dict() for d in ir.diagnostics] if ir.diagnostics else []
        all_diags = [
            self._normalize_structured_diagnostic(diagnostic, ir.header.ue_version)
            if diagnostic.get("code") else diagnostic
            for diagnostic in all_diags
        ]
        if is_debug:
            data["diagnostics"] = all_diags
        else:
            structured = [diagnostic for diagnostic in all_diags if diagnostic.get("code")]
            legacy = [diagnostic for diagnostic in all_diags if not diagnostic.get("code")]
            data["diagnostics"] = (
                self._fold_diagnostics(legacy)
                + self._aggregate_structured_diagnostics(structured)
            )
        if ir.dependencies and ir.dependencies.asset_registry_data:
            data["asset_registry_data"] = ir.dependencies.asset_registry_data
        if ir.animation and ir.animation.anim_blueprint:
            data["anim_blueprint"] = self._anim_blueprint_to_dict(ir.animation.anim_blueprint)
        if ir.animation and ir.animation.anim_sequence:
            data["anim_sequence"] = self._anim_sequence_to_dict(ir.animation.anim_sequence)
        if ir.animation and ir.animation.anim_montage:
            data["anim_montage"] = self._anim_montage_to_dict(ir.animation.anim_montage)
        if (options.hex_view or options.output_level == "debug") and ir.debug:
            debug_dict: dict[str, Any] = {}
            if ir.debug.hex_view:
                debug_dict["hex_view"] = [self._hex_view_entry_to_dict(e) for e in ir.debug.hex_view]
            if ir.debug.hex_view_truncated_count > 0:
                debug_dict["hex_view_truncated_count"] = ir.debug.hex_view_truncated_count
            if debug_dict:
                data["debug"] = debug_dict
        if options.include_function_graphs:
            data["function_graphs"] = self._build_function_graphs(ir)
        stats = dict(ir.statistics)
        total_in_table = stats.get("total_exports_in_table", ir.header.total_export_count)
        exports_parsed = stats.get("exports_parsed", len(ir.exports))
        exports_built = stats.get("exports_built", len(ir.exports))
        exports_rendered = len(data["exports"])
        omitted_by_reason: dict[str, int] = {}
        export_table_parse_failed = max(total_in_table - exports_parsed, 0)
        if export_table_parse_failed:
            omitted_by_reason["export_table_parse_failed"] = export_table_parse_failed
        ir_build_failed = max(exports_parsed - exports_built, 0)
        if ir_build_failed:
            omitted_by_reason["ir_build_failed"] = ir_build_failed
        if not is_debug:
            editor_filtered = exports_built - len(filter_editor_items(ir.exports))
            if editor_filtered:
                omitted_by_reason["editor_filtered"] = editor_filtered
            corrupted = len(filter_editor_items(ir.exports)) - exports_rendered
            if corrupted:
                omitted_by_reason["corrupted_serial_size"] = corrupted
        stats["total_exports_in_table"] = total_in_table
        stats["exports_parsed"] = exports_parsed
        stats["exports_built"] = exports_built
        stats["exports_rendered"] = exports_rendered
        stats["exports_omitted"] = max(total_in_table - exports_rendered, 0)
        stats["omitted_by_reason"] = omitted_by_reason
        data["statistics"] = stats
        return data

    def _export_to_dict(self, export, options: RenderOptions, is_debug: bool = False, name_map: tuple = ()) -> dict[str, Any]:
        # Filter editor layout properties in standard mode
        if is_debug:
            properties = [self._property_to_dict(p, is_debug=True, name_map=name_map) for p in export.properties]
        else:
            properties = [
                self._property_to_dict(p, is_debug=False, name_map=name_map) for p in export.properties
                if p.name not in EDITOR_PROPERTY_NAMES
            ]

        # Standard output keeps only graphs with nodes; compact output keeps summaries.
        graphs = [self._graph_to_dict(g, options) for g in export.graphs]
        if not is_debug and options.output_level != "compact":
            graphs = [g for g in graphs if g.get("nodes")]

        d = {
            "object_name": export.object_name,
            "object_class": export.object_class,
            "serial_size": export.serial_size,
        }
        # parent_class: always included in debug mode, only included when non-None in standard mode
        if is_debug or export.parent_class is not None:
            d["parent_class"] = export.parent_class
        # In standard mode, only add non-empty fields
        if properties or is_debug:
            d["properties"] = properties
        if graphs or is_debug:
            d["graphs"] = graphs
        if export.parse_status != "success":
            d["parse_status"] = export.parse_status
        if export.fallback_reason:
            d["fallback_reason"] = export.fallback_reason
        if export.error_message:
            d["error_message"] = export.error_message
        if export.asset_type_data:
            d["asset_type_data"] = sanitize_asset_metadata(export.asset_type_data)
        return d

    def _property_to_dict(self, prop, is_debug: bool = False, name_map: tuple[str, ...] = ()) -> dict[str, Any]:
        d: dict[str, Any] = {"name": prop.name, "type": prop.type, "value": prop.value}
        # Omit default value fields in standard mode
        if is_debug or prop.array_index != -1:
            d["array_index"] = prop.array_index
        if is_debug or prop.guid is not None:
            d["guid"] = prop.guid
        # StructValue metadata trimming (standard mode)
        if not is_debug and hasattr(prop.value, "__dataclass_fields__"):
            value_dict = dataclasses.asdict(prop.value)
            for field_name, default in [
                ("parse_status", "success"),
                ("property_type", "StructProperty"),
                ("kind", "struct_binary_decoded"),
            ]:
                if value_dict.get(field_name) == default:
                    value_dict.pop(field_name, None)
            d["value"] = value_dict
        # ObjectProperty full_name omission (standard mode)
        if not is_debug and d.get("type") == "ObjectProperty" and isinstance(d.get("value"), dict):
            val = d["value"]
            if "full_name" in val and "object_name" in val:
                d["value"] = {k: v for k, v in val.items() if k != "full_name"}
        # ObjectProperty resolved_name: resolve numeric index to human-readable string
        if d.get("type") == "ObjectProperty" and isinstance(d.get("value"), dict):
            val = d["value"]
            obj_name = val.get("object_name", "")
            if obj_name and obj_name.lstrip("-").isdigit() and name_map:
                idx = int(obj_name)
                if 0 <= idx < len(name_map):
                    d["value"]["resolved_name"] = name_map[idx]
        return d

    def _graph_to_dict(self, graph, options: RenderOptions) -> dict[str, Any]:
        result = {
            "graph_name": graph.graph_name,
            "graph_guid": graph.graph_guid,
            "execution_chains": graph.execution_chains,
        }
        if options.output_level == "compact":
            result["node_summary"] = self._aggregate_nodes(graph.nodes)
        else:
            result["nodes"] = [self._node_to_dict(n, options.output_level) for n in graph.nodes]
        if graph.graph_type:
            result["graph_type"] = graph.graph_type
        if graph.subgraphs:
            result["subgraphs"] = [self._graph_to_dict(sg, options) for sg in graph.subgraphs]
        return result

    @staticmethod
    def _pin_semantic_key(pin) -> str:
        """Return a stable, compact pin-type key for graph summaries."""
        category = getattr(pin, "pin_category", "") or ""
        subcategory = getattr(pin, "pin_subcategory", "") or ""
        container = getattr(pin, "container_type", "None") or "None"
        parts = [category]
        if subcategory and subcategory != "None":
            parts.append(subcategory)
        if container != "None":
            parts.append(container)
        return ":".join(parts) if parts else "unknown"

    def _aggregate_nodes(self, nodes: list) -> dict[str, Any]:
        """Summarize graph nodes without serializing their full pin records."""
        from collections import Counter

        node_types = Counter()
        pin_types = Counter()
        referenced_functions: set[str] = set()
        for node in nodes:
            node_types[getattr(node, "node_class", "") or "unknown"] += 1
            for pin in node.pins:
                pin_types[self._pin_semantic_key(pin)] += 1
                referenced = getattr(pin, "pin_subcategory_object_name", None)
                if isinstance(referenced, str) and referenced:
                    referenced_functions.add(referenced)

        summary: dict[str, Any] = {
            "total_nodes": len(nodes),
            "by_type": dict(node_types.most_common()),
        }
        if pin_types:
            summary["pin_types"] = dict(pin_types.most_common())
        if referenced_functions:
            summary["referenced_functions"] = sorted(referenced_functions)
        return summary

    def _node_to_dict(self, node, output_level: str = "standard") -> dict[str, Any]:
        is_debug = output_level == "debug"
        d: dict[str, Any] = {
            "node_guid": node.node_guid,
            "node_class": node.node_class,
            "pins": [self._pin_to_dict(p, output_level) for p in node.pins],
        }
        # node_comment: omit null in standard mode
        if is_debug or node.node_comment is not None:
            d["node_comment"] = node.node_comment
        # execution_flow: omit empty list in standard mode
        if is_debug or node.execution_flow:
            d["execution_flow"] = node.execution_flow
        if node.macro_expansion is not None:
            d["macro_expansion"] = node.macro_expansion
        # Enhanced Input fields: omit null/empty in standard mode
        if is_debug or node.input_action_path is not None:
            d["input_action_path"] = node.input_action_path
        if is_debug or node.trigger_events:
            d["trigger_events"] = node.trigger_events
        if is_debug or node.event_type is not None:
            d["event_type"] = node.event_type
        return d

    def _pin_to_dict(self, pin, output_level: str = "standard") -> dict[str, Any]:
        is_debug = output_level == "debug"
        d: dict[str, Any] = {
            "pin_name": pin.pin_name,
            "linked_to": pin.linked_to,
            "direction": pin.direction,
            "pin_category": pin.pin_category,
        }
        # container_type: omit default value "None" in standard mode
        if is_debug or pin.container_type != "None":
            d["container_type"] = pin.container_type
        if is_debug:
            # debug mode: keep all fields
            d["pin_type"] = pin.pin_type
            d["default_value"] = pin.default_value
            d["pin_subcategory"] = pin.pin_subcategory
            d["is_reference"] = pin.is_reference
            d["is_const"] = pin.is_const
            d["is_weak_pointer"] = pin.is_weak_pointer
            d["is_uobject_wrapper"] = pin.is_uobject_wrapper
        else:
            # standard mode: only output non-default values
            if pin.default_value:
                d["default_value"] = pin.default_value
            if pin.pin_subcategory:
                d["pin_subcategory"] = pin.pin_subcategory
            if pin.is_reference:
                d["is_reference"] = True
            if pin.is_const:
                d["is_const"] = True
            if pin.is_weak_pointer:
                d["is_weak_pointer"] = True
            if pin.is_uobject_wrapper:
                d["is_uobject_wrapper"] = True
        # Conditional fields (applicable in both modes)
        if pin.pin_subcategory_object_name is not None:
            d["pin_subcategory_object"] = pin.pin_subcategory_object_name
        if pin.is_map_key:
            d["is_map_key"] = True
        if pin.is_map_value:
            d["is_map_value"] = True
        # Map terminal type
        if pin.container_type == "Map":
            if pin.map_key_pin_category:
                d["map_key_pin_category"] = pin.map_key_pin_category
            if pin.map_key_pin_subcategory:
                d["map_key_pin_subcategory"] = pin.map_key_pin_subcategory
            if pin.map_key_pin_subcategory_object_name is not None:
                d["map_key_pin_subcategory_object"] = pin.map_key_pin_subcategory_object_name
        return d

    def _extract_error_pattern(self, error: str) -> str:
        """Extract error pattern, replacing numbers with {n} placeholders."""
        return re.sub(r'\d+', '{n}', error)

    def _extract_position(self, diag: dict) -> int | None:
        """Extract position from a diagnostic dictionary (uses the current_pos field)."""
        return diag.get("current_pos")

    def _fold_diagnostics(self, diagnostics: list) -> list:
        """Fold diagnostics with the same (kind, field) pattern.

        Single entries are not folded; multiple entries are folded into one record with count and pos_range.
        """
        if not diagnostics:
            return diagnostics

        # Group by (kind, field)
        groups: dict[tuple[str, str], list] = {}
        for diag in diagnostics:
            key = (diag.get("kind", ""), diag.get("field", ""))
            if key not in groups:
                groups[key] = []
            groups[key].append(diag)

        folded = []
        for (kind, field), items in groups.items():
            if len(items) == 1:
                folded.append(items[0])
            else:
                first_error = items[0].get("error", "")
                error_pattern = self._extract_error_pattern(first_error)
                positions = []
                for item in items:
                    pos = self._extract_position(item)
                    if pos is not None:
                        positions.append(pos)
                folded_item: dict[str, Any] = {
                    "kind": kind,
                    "field": field,
                    "error": first_error,
                    "error_pattern": error_pattern,
                    "count": len(items),
                }
                if positions:
                    folded_item["pos_range"] = {
                        "min": min(positions),
                        "max": max(positions),
                    }
                folded.append(folded_item)

        return folded

    @staticmethod
    def _normalize_structured_diagnostic(diagnostic: dict[str, Any], ue_version: str) -> dict[str, Any]:
        """Hydrate render-only structured diagnostic context without mutating the IR."""
        normalized = dict(diagnostic)
        if not normalized.get("ue_version"):
            normalized["ue_version"] = ue_version
        return normalized

    @staticmethod
    def _aggregate_structured_diagnostics(diagnostics: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Aggregate repeated structured diagnostics while preserving concise evidence."""
        groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
        for diagnostic in diagnostics:
            key = (
                diagnostic.get("code", ""),
                diagnostic.get("severity", ""),
                diagnostic.get("stage", ""),
                diagnostic.get("fallback", ""),
            )
            groups.setdefault(key, []).append(diagnostic)

        aggregated: list[dict[str, Any]] = []
        for items in groups.values():
            if len(items) == 1:
                aggregated.append(items[0])
                continue

            first = items[0]
            entry: dict[str, Any] = {
                "code": first.get("code", ""),
                "severity": first.get("severity", ""),
                "stage": first.get("stage", ""),
                "fallback": first.get("fallback", ""),
                "count": len(items),
            }
            for field in ("asset", "ue_version"):
                values = [item.get(field) for item in items]
                if all(value == values[0] for value in values):
                    entry[field] = values[0]
                else:
                    examples: list[Any] = []
                    for value in values:
                        if value not in examples:
                            examples.append(value)
                        if len(examples) == 3:
                            break
                    entry[f"{field}_examples"] = examples
            messages: list[Any] = []
            for item in items:
                message = item.get("message")
                if message is not None and message not in messages:
                    messages.append(message)
                if len(messages) == 3:
                    break
            if messages:
                entry["message_examples"] = messages
            raw_values = [item.get("raw_value") for item in items if item.get("raw_value") is not None]
            if raw_values and all(isinstance(value, (int, float)) for value in raw_values):
                entry["raw_value_range"] = {"min": min(raw_values), "max": max(raw_values)}
            elif raw_values:
                entry["raw_value_examples"] = raw_values[:3]
            offsets = [item.get("offset") for item in items if item.get("offset") is not None]
            if offsets:
                entry["offset_range"] = {"min": min(offsets), "max": max(offsets)}
                entry["offset_examples"] = offsets[:3]
            aggregated.append(entry)

        return aggregated

    def _blueprint_to_dict(self, blueprint) -> dict[str, Any]:
        """Serialize BlueprintIR to a dictionary (full metadata)."""
        d: dict[str, Any] = {"parent_class": blueprint.parent_class}
        if getattr(blueprint, "description", ""):
            d["description"] = blueprint.description
        if getattr(blueprint, "interfaces", []):
            # interfaces is already a list of dicts (from IR builder)
            d["interfaces"] = blueprint.interfaces
        if blueprint.functions:
            d["functions"] = [self._function_to_dict(f) for f in blueprint.functions]
        if blueprint.events:
            d["events"] = [self._event_to_dict(e) for e in blueprint.events]
        if blueprint.components:
            d["components"] = blueprint.components
        return d

    def _variable_to_dict(self, var) -> dict[str, Any]:
        """Serialize VariableIR to a dictionary (full metadata, omit default value fields)."""
        d: dict[str, Any] = {"name": var.name, "type": var.type, "kind": var.kind}
        if var.default_value is not None:
            d["default_value"] = var.default_value
        if var.guid:
            d["guid"] = var.guid
        if var.category:
            d["category"] = var.category
        if var.property_flags:
            d["property_flags"] = var.property_flags
        if var.replication_condition:
            d["replication_condition"] = var.replication_condition
        if var.rep_notify_func:
            d["rep_notify_func"] = var.rep_notify_func
        if var.friendly_name:
            d["friendly_name"] = var.friendly_name
        if var.metadata:
            d["metadata"] = var.metadata
        if var.flags_labels:
            d["flags_labels"] = var.flags_labels
        if var.edit_condition:
            d["edit_condition"] = var.edit_condition
        # Boolean flags only output when True, reducing noise
        for flag in (
            "is_edit_anywhere", "is_visible_anywhere", "is_blueprint_read_only",
            "is_transient", "is_replicated", "is_rep_notify",
            "is_expose_on_spawn", "is_save_game",
        ):
            if getattr(var, flag, False):
                d[flag] = True
        return d

    def _function_to_dict(self, func) -> dict[str, Any]:
        """Serialize BlueprintFunctionIR to a dictionary (full metadata + implementation association)."""
        d: dict[str, Any] = {
            "name": func.name,
            "return_type": func.return_type,
            "parameters": func.parameters,
        }
        if func.function_flags:
            d["function_flags"] = func.function_flags
        if not getattr(func, "is_implemented", True):
            d["is_implemented"] = False
        for flag in (
            "is_pure", "is_blueprint_callable", "is_const", "is_static",
            "is_net", "is_net_reliable", "is_blueprint_private",
        ):
            if getattr(func, flag, False):
                d[flag] = True
        if func.access_specifier and func.access_specifier != "Public":
            d["access_specifier"] = func.access_specifier
        if func.meta_data:
            d["meta_data"] = func.meta_data
        # Implementation association
        if func.implementation:
            d["implementation"] = func.implementation
        if func.function_graph:
            d["function_graph"] = func.function_graph
        d["implementation_status"] = func.implementation_status
        return d

    def _event_to_dict(self, evt) -> dict[str, Any]:
        """Serialize BlueprintEventIR to a dictionary (full metadata + implementation association)."""
        d: dict[str, Any] = {
            "name": evt.name,
            "event_type": evt.event_type,
            "parameters": evt.parameters,
        }
        if evt.function_flags:
            d["function_flags"] = evt.function_flags
        if evt.is_override:
            d["is_override"] = True
        if evt.override_parent_class:
            d["override_parent_class"] = evt.override_parent_class
        if evt.override_parent_event:
            d["override_parent_event"] = evt.override_parent_event
        if evt.is_interface_event:
            d["is_interface_event"] = True
        if evt.interface_class:
            d["interface_class"] = evt.interface_class
        for flag in (
            "is_net", "is_net_multicast", "is_replicated",
            "is_cosmetic", "is_static",
        ):
            if getattr(evt, flag, False):
                d[flag] = True
        if evt.meta_data:
            d["meta_data"] = evt.meta_data
        # Implementation association
        if evt.implementation:
            d["implementation"] = evt.implementation
        if evt.function_graph:
            d["function_graph"] = evt.function_graph
        d["implementation_status"] = evt.implementation_status
        return d

    def _decompiled_function_to_dict(self, func) -> dict[str, Any]:
        """Serialize DecompiledFunctionIR to a dictionary."""
        d = {"name": func.name, "signature": func.signature, "cpp_code": func.cpp_code, "parameters": func.parameters, "return_type": func.return_type}
        if func.fallback_reasons:
            d["fallback_reasons"] = func.fallback_reasons
        if func.bytecode_confidence != "verified":
            d["bytecode_confidence"] = func.bytecode_confidence
        return d

    def _calculate_statistics(self, ir: PackageIR) -> dict:
        """Calculate export statistics, including opaque class distribution."""
        stats = {
            "total_exports": len(ir.exports),
            "success_count": 0,
            "partial_count": 0,
            "opaque_count": 0,
            "failed_count": 0,
            "opaque_classes": {},
        }

        for export in ir.exports:
            status = getattr(export, 'parse_status', 'success')
            if status == 'success':
                stats["success_count"] += 1
            elif status in ('partial', 'partial_metadata'):
                stats["partial_count"] += 1
            elif status == 'opaque':
                stats["opaque_count"] += 1
                cls = getattr(export, 'object_class', 'unknown')
                stats["opaque_classes"][cls] = stats["opaque_classes"].get(cls, 0) + 1
            elif status == 'failed':
                stats["failed_count"] += 1

        return stats

    def _build_function_graphs(self, ir: PackageIR) -> list[dict]:
        """Directly return the already-built function_graphs data from IR."""
        return ir.function_graphs

    @property
    def format_name(self) -> str:
        return "json"

    def _anim_blueprint_to_dict(self, anim_ir) -> dict[str, Any]:
        """Serialize AnimBlueprintIR to a dictionary."""
        d: dict[str, Any] = {}
        if anim_ir.target_skeleton:
            d["target_skeleton"] = anim_ir.target_skeleton
        if anim_ir.baked_state_machines:
            d["baked_state_machines"] = [
                self._baked_state_machine_to_dict(sm) for sm in anim_ir.baked_state_machines
            ]
        if anim_ir.anim_notifies:
            d["anim_notifies"] = [
                self._anim_notify_to_dict(n) for n in anim_ir.anim_notifies
            ]
        if anim_ir.sync_group_names:
            d["sync_group_names"] = anim_ir.sync_group_names
        if anim_ir.graph_asset_player_info:
            d["graph_asset_player_info"] = anim_ir.graph_asset_player_info
        if anim_ir.graph_blend_options:
            d["graph_blend_options"] = anim_ir.graph_blend_options
        if anim_ir.anim_node_data:
            d["anim_node_data"] = anim_ir.anim_node_data
        return d

    def _baked_state_machine_to_dict(self, sm) -> dict[str, Any]:
        """Serialize BakedStateMachineIR to a dictionary."""
        return {
            "machine_name": sm.machine_name,
            "initial_state": sm.initial_state,
            "states": [
                {
                    "state_name": s.state_name,
                    "state_root_node_index": s.state_root_node_index,
                    "b_is_a_conduit": s.b_is_a_conduit,
                }
                for s in sm.states
            ],
            "transitions": [
                {
                    "previous_state": t.previous_state,
                    "next_state": t.next_state,
                    "crossfade_duration": t.crossfade_duration,
                    "blend_mode": t.blend_mode,
                }
                for t in sm.transitions
            ],
        }

    def _anim_notify_to_dict(self, notify) -> dict[str, Any]:
        """Serialize AnimNotifyIR to a dictionary."""
        return {
            "notify_name": notify.notify_name,
            "trigger_time_offset": notify.trigger_time_offset,
            "duration": notify.duration,
            "notify_class": notify.notify_class,
            "track_index": notify.track_index,
        }

    def _anim_sequence_to_dict(self, anim_ir) -> dict[str, Any]:
        """Serialize AnimSequenceIR to a dictionary."""
        d: dict[str, Any] = {}
        if anim_ir.target_skeleton:
            d["target_skeleton"] = anim_ir.target_skeleton
        if anim_ir.additive_anim_type:
            d["additive_anim_type"] = anim_ir.additive_anim_type
        if anim_ir.sequence_length:
            d["sequence_length"] = anim_ir.sequence_length
        if anim_ir.rate_scale:
            d["rate_scale"] = anim_ir.rate_scale
        if anim_ir.notifies:
            d["notifies"] = [self._anim_notify_to_dict(n) for n in anim_ir.notifies]
        if anim_ir.float_curve_names:
            d["float_curve_names"] = anim_ir.float_curve_names
        d["has_compressed_data"] = anim_ir.has_compressed_data
        return d

    def _anim_montage_to_dict(self, anim_ir) -> dict[str, Any]:
        """Serialize AnimMontageIR to a dictionary."""
        d: dict[str, Any] = {}
        if anim_ir.blend_mode_in:
            d["blend_mode_in"] = anim_ir.blend_mode_in
        if anim_ir.blend_mode_out:
            d["blend_mode_out"] = anim_ir.blend_mode_out
        if anim_ir.blend_in_option:
            d["blend_in_option"] = anim_ir.blend_in_option
        if anim_ir.blend_out_option:
            d["blend_out_option"] = anim_ir.blend_out_option
        if anim_ir.sync_group:
            d["sync_group"] = anim_ir.sync_group
        if anim_ir.rate_scale:
            d["rate_scale"] = anim_ir.rate_scale
        if anim_ir.composite_sections:
            d["composite_sections"] = anim_ir.composite_sections
        if anim_ir.slot_anim_tracks:
            d["slot_anim_tracks"] = anim_ir.slot_anim_tracks
        if anim_ir.branching_point_markers:
            d["branching_point_markers"] = anim_ir.branching_point_markers
        if anim_ir.notifies:
            d["notifies"] = [self._anim_notify_to_dict(n) for n in anim_ir.notifies]
        if anim_ir.float_curve_names:
            d["float_curve_names"] = anim_ir.float_curve_names
        return d

    def _hex_view_entry_to_dict(self, entry: "HexViewEntryIR") -> dict[str, Any]:
        """Serialize HexViewEntryIR to a dictionary."""
        d: dict[str, Any] = {
            "key": entry.key,
            "type": entry.type,
            "start": entry.start,
            "stop": entry.stop,
            "size": entry.size,
        }
        if entry.field_path is not None:
            d["field_path"] = entry.field_path
        if entry.semantic_type is not None:
            d["semantic_type"] = entry.semantic_type
        if isinstance(entry.value, bytes):
            d["value_hex"] = entry.value.hex()
            d["value_size"] = len(entry.value)
        elif isinstance(entry.value, str):
            d["value"] = entry.value
        else:
            d["value"] = entry.value
        return d


register_renderer("json", JSONRenderer)
