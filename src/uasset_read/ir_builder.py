"""IR builder layer -- converts ParseResult to PackageIR.

Build stage handles all FPackageIndex cross-reference resolution and GUID normalization.
Renderers receive only PackageIR and do not access ParseResult.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from uasset_read.core.utils import (
    safe_str as _safe_str,
    safe_int as _safe_int,
    normalize_hex_guid,
)

logger = logging.getLogger(__name__)

from uasset_read.models.ir import (
    PackageIR,
    PackageHeaderIR,
    PropertyIR,
    ExportIR,
    ExportRawIR,
    ImportIR,
    GraphIR,
    NodeIR,
    PinIR,
    LinkerSummaryIR,
    BlueprintIR,
    BlueprintFunctionIR,
    BlueprintEventIR,
    DecompiledFunctionIR,
    ExecutionChainIR,
    VariableIR,
    HexViewEntryIR,
    DebugIR,
    AnimationDataIR,
    UserDefinedDataIR,
    UserDefinedEnumIR,
    UserDefinedStructIR,
    PackageDependenciesIR,
    DiagnosticsDataIR,
    ScriptMetricsIR,
    MaterialIR,
    MaterialExpressionIR,
    MaterialExpressionInputIR,
    MaterialExpressionOutputIR,
    MaterialInputIR,
)

if TYPE_CHECKING:
    from uasset_read.models.result import ParseResult
    from uasset_read.link.result import LinkerParseResult

from uasset_read.constants import (
    BLUEPRINT_METADATA_KEYS as _BLUEPRINT_METADATA_KEYS,
    CONTAINER_TYPE_MAP,
    CONTAINER_TYPE_PREFIX,
    UE_NONE_SENTINEL,
)
from uasset_read.models.status import _result_status
from uasset_read.serializers.object_resources import PackageIndex, resolve_class_name
from uasset_read.kismet.result import infer_bytecode_confidence


def _classify_variable(var) -> str:
    """Classify blueprint variables."""
    name = getattr(var, "var_name", "") or ""
    if name in _BLUEPRINT_METADATA_KEYS:
        return "metadata"
    if getattr(var, "is_component", False):
        return "component"
    if "InputAction" in name or "InputAxis" in name:
        return "input_action"
    return "user"


def _has_kismet_failure(result: "ParseResult | LinkerParseResult") -> bool:
    """Check if any decompiled function has failed bytecode or partial/failed translation."""
    for func in result.decompiled_functions or []:
        bytecode_status = getattr(func, "bytecode_status", "unknown")
        translation_status = getattr(func, "translation_status", "not_applicable")
        if bytecode_status == "failed":
            return True
        if bytecode_status == "parsed" and translation_status in ("partial", "failed"):
            return True
    return False


def _count_kismet_failed_functions(result: "ParseResult | LinkerParseResult") -> int:
    """Count functions with failed bytecode status."""
    count = 0
    for func in result.decompiled_functions or []:
        if getattr(func, "bytecode_status", "unknown") == "failed":
            count += 1
    return count


def _count_kismet_partial_functions(result: "ParseResult | LinkerParseResult") -> int:
    """Count functions with partial or failed translation status."""
    count = 0
    for func in result.decompiled_functions or []:
        bytecode_status = getattr(func, "bytecode_status", "unknown")
        translation_status = getattr(func, "translation_status", "not_applicable")
        if bytecode_status == "parsed" and translation_status in ("partial", "failed"):
            count += 1
    return count


def _build_statistics(
    result: "ParseResult | LinkerParseResult", exports_built: int
) -> dict:
    """Build statistics dict from parse result for JSON output."""
    export_status_counts: dict[str, int] = {}
    total_props = 0
    parsed_exports = list(result.export_map or [])
    for export in parsed_exports:
        ps = getattr(export, "parse_status", None)
        ps_str = str(ps.value) if hasattr(ps, "value") else str(ps) if ps else "success"
        export_status_counts[ps_str] = export_status_counts.get(ps_str, 0) + 1
        total_props += len(getattr(export, "properties", None) or [])

    declared_export_count = getattr(
        getattr(result, "summary", None), "export_count", None
    )
    if isinstance(declared_export_count, int) and declared_export_count >= 0:
        export_table_total = max(declared_export_count, len(parsed_exports))
    else:
        export_table_total = len(parsed_exports)
    return {
        "total_exports": len(parsed_exports),
        "total_exports_in_table": export_table_total,
        "exports_parsed": len(parsed_exports),
        "exports_built": exports_built,
        "total_properties": total_props,
        "export_status_counts": export_status_counts,
        "warning_count": len(getattr(result, "warnings", None) or []),
        "diagnostic_count": (
            len(getattr(result, "diagnostics", None) or [])
            + len(getattr(result, "structured_diagnostics", None) or [])
        ),
    }


def _build_animation_data(
    result: "ParseResult | LinkerParseResult",
) -> AnimationDataIR | None:
    """Aggregate animation data from ParseResult (anim_blueprint, anim_sequence, anim_montage).

    Animation data originates from each Export's custom_data field and must be aggregated across all exports.
    """
    anim_bp = None
    anim_seq = None
    anim_mon = None
    for export in result.export_map or []:
        custom = getattr(export, "custom_data", None) or {}
        if not anim_bp and custom.get("anim_blueprint"):
            anim_bp = custom["anim_blueprint"]
        if not anim_seq and custom.get("anim_sequence"):
            anim_seq = custom["anim_sequence"]
        if not anim_mon and custom.get("anim_montage"):
            anim_mon = custom["anim_montage"]
    if anim_bp or anim_seq or anim_mon:
        return AnimationDataIR(
            anim_blueprint=anim_bp,
            anim_sequence=anim_seq,
            anim_montage=anim_mon,
        )
    return None


def _build_material_ir(result: "ParseResult | LinkerParseResult") -> MaterialIR | None:
    """Build MaterialIR from ParseResult by scanning exports.

    Scans export_map for Material/MaterialInstance + MaterialExpression* exports.
    Resolves FExpressionInput/FMaterialInput PackageIndex cross-references.
    """
    from uasset_read.constants import (
        MATERIAL_DOMAIN_MAP,
        BLEND_MODE_MAP,
        SHADING_MODEL_MAP,
        MATERIAL_USAGE_FLAG_NAMES,
        classify_expression_type,
    )

    # Find Material/MaterialInstance export
    material_export = None
    expression_exports = []

    for export in result.export_map or []:
        class_name = _safe_str(
            getattr(export, "object_class", None)
        ) or resolve_class_name(
            getattr(export, "class_index", None),
            result.import_map or [],
            result.export_map or [],
        )
        if class_name in ("Material",):
            if getattr(export, "b_is_asset", False) or material_export is None:
                material_export = export
                material_export._resolved_class = "Material"
        elif class_name in ("MaterialInstance", "MaterialInstanceConstant"):
            if getattr(export, "b_is_asset", False) or material_export is None:
                material_export = export
                material_export._resolved_class = "MaterialInstance"
        elif class_name and class_name.startswith("MaterialExpression"):
            expression_exports.append(export)

    if material_export is None:
        return None

    material_type = getattr(material_export, "_resolved_class", "Material")

    # Build expression index -> guid mapping
    # Key by actual export table position, not sequential position in filtered list
    expr_guid_map: dict[int, str] = {}
    for export_idx, export in enumerate(result.export_map or []):
        class_name = _safe_str(
            getattr(export, "object_class", None)
        ) or resolve_class_name(
            getattr(export, "class_index", None),
            result.import_map or [],
            result.export_map or [],
        )
        if class_name and class_name.startswith("MaterialExpression"):
            guid = _extract_expression_guid(export)
            if guid:
                expr_guid_map[export_idx] = guid  # Actual export table index

    # Build expressions with export table indices
    expressions = []
    for export_idx, export in enumerate(result.export_map or []):
        class_name = _safe_str(
            getattr(export, "object_class", None)
        ) or resolve_class_name(
            getattr(export, "class_index", None),
            result.import_map or [],
            result.export_map or [],
        )
        if class_name and class_name.startswith("MaterialExpression"):
            expr_ir = _build_single_expression_ir(
                export_idx, export, expr_guid_map, result
            )
            expressions.append(expr_ir)

    # Build material inputs (Material only)
    material_inputs = []
    if material_type == "Material":
        material_inputs = _build_material_inputs(material_export, expr_guid_map)

    # Build properties
    properties = _build_material_properties(material_export)

    # Build parameters (MaterialInstance only)
    parameters = None
    base_property_overrides = None
    parent = None
    if material_type == "MaterialInstance":
        parameters = _build_material_instance_parameters(material_export)
        base_property_overrides = _build_material_instance_overrides(material_export)
        parent = _resolve_material_parent(material_export, result)

    # Build data_flow
    data_flow = _build_material_data_flow(expressions, material_inputs)

    return MaterialIR(
        material_type=material_type,
        properties=properties,
        expressions=expressions,
        material_inputs=material_inputs,
        parameters=parameters,
        base_property_overrides=base_property_overrides,
        parent=parent,
        data_flow=data_flow,
    )


def _extract_expression_guid(expr_export) -> str | None:
    """Extract MaterialExpressionGuid from export properties."""
    from uasset_read.models.properties import StructValue

    for prop in getattr(expr_export, "properties", None) or []:
        if getattr(prop, "name", None) == "MaterialExpressionGuid":
            val = getattr(prop, "value", None)
            # Handle StructValue (most common case from property parser)
            if isinstance(val, StructValue) and val.struct_type == "Guid":
                fields = val.fields
                a = fields.get("A", 0)
                b = fields.get("B", 0)
                c = fields.get("C", 0)
                d = fields.get("D", 0)
                return f"{a:08x}{b:08x}{c:08x}{d:08x}"
            # Handle string value (legacy/direct)
            if isinstance(val, str):
                return normalize_hex_guid(val)
            # Handle dict value (fallback)
            if isinstance(val, dict):
                guid_str = val.get("guid", "") or val.get("value", "")
                if guid_str:
                    return normalize_hex_guid(guid_str)
    return None


def _build_single_expression_ir(
    export_idx: int,
    expr_export,
    expr_guid_map: dict[int, str],
    result,
) -> MaterialExpressionIR:
    """Build a single MaterialExpressionIR from an export."""
    from uasset_read.constants import classify_expression_type

    class_name = _safe_str(
        getattr(expr_export, "object_class", None)
    ) or resolve_class_name(
        getattr(expr_export, "class_index", None),
        result.import_map or [],
        result.export_map or [],
    )

    guid = expr_guid_map.get(export_idx, "")
    expr_type = classify_expression_type(class_name)

    # Parse inputs (ExpressionInput struct properties)
    inputs = []
    for prop in getattr(expr_export, "properties", None) or []:
        prop_name = getattr(prop, "name", "")
        prop_value = getattr(prop, "value", None)
        # Check struct_type on both StructValue and dict
        struct_type = getattr(prop_value, "struct_type", None)
        if struct_type is None and isinstance(prop_value, dict):
            struct_type = prop_value.get("struct_type")
        if struct_type not in ("ExpressionInput", "FExpressionInput"):
            continue
        # Extract fields: StructValue has .fields attr, dict wraps fields under "fields" key
        if isinstance(prop_value, dict):
            fields = prop_value.get("fields", {})
        else:
            fields = getattr(prop_value, "fields", None)
            if fields is None:
                fields = {}
        if isinstance(fields, dict) and fields:
            expr_idx = fields.get("expression_index", 0)
            source_guid = expr_guid_map.get(expr_idx) if expr_idx else None
            inputs.append(
                MaterialExpressionInputIR(
                    input_name=prop_name,
                    source_expression_guid=source_guid,
                    source_output_index=fields.get("output_index", 0),
                    mask=fields.get("mask", 0),
                    mask_r=fields.get("mask_r", 0),
                    mask_g=fields.get("mask_g", 0),
                    mask_b=fields.get("mask_b", 0),
                    mask_a=fields.get("mask_a", 0),
                )
            )

    # Parse outputs
    outputs = _build_expression_outputs(expr_export)

    # Extract parameter/constant values
    parameter, constant_value = _extract_expression_value(class_name, expr_export)

    # Editor position
    editor_position = _extract_editor_position(expr_export)

    # Description
    description = None
    for prop in getattr(expr_export, "properties", None) or []:
        if getattr(prop, "name", None) == "Desc":
            description = _safe_str(getattr(prop, "value", None)) or None

    return MaterialExpressionIR(
        expression_guid=guid,
        expression_class=class_name,
        expression_type=expr_type,
        inputs=inputs,
        outputs=outputs,
        parameter=parameter,
        constant_value=constant_value,
        editor_position=editor_position,
        description=description,
    )


def _build_expression_outputs(expr_export) -> list:
    """Build MaterialExpressionOutputIR list from export properties."""
    outputs = []
    for prop in getattr(expr_export, "properties", None) or []:
        if getattr(prop, "name", None) == "Outputs":
            val = getattr(prop, "value", None)
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        fields = item.get("fields", item)
                        outputs.append(
                            MaterialExpressionOutputIR(
                                output_name=fields.get("output_name", ""),
                                mask=fields.get("mask", 0),
                                mask_r=fields.get("mask_r", 0),
                                mask_g=fields.get("mask_g", 0),
                                mask_b=fields.get("mask_b", 0),
                                mask_a=fields.get("mask_a", 0),
                            )
                        )
            break
    return outputs


def _extract_expression_value(class_name: str, expr_export) -> tuple:
    """Extract parameter or constant value from expression properties."""
    parameter = None
    constant_value = None

    for prop in getattr(expr_export, "properties", None) or []:
        prop_name = getattr(prop, "name", None)
        prop_value = getattr(prop, "value", None)

        if prop_name == "ParameterName" and prop_value:
            parameter = {"name": _safe_str(prop_value)}
        elif prop_name == "DefaultValue" and prop_value is not None:
            if parameter is None:
                parameter = {}
            if isinstance(prop_value, dict):
                parameter["value"] = prop_value.get("fields", prop_value)
            else:
                parameter["value"] = prop_value
        elif prop_name == "R" and prop_value is not None:
            constant_value = prop_value
        elif prop_name == "X" and constant_value is None and prop_value is not None:
            constant_value = prop_value

    return parameter, constant_value


def _extract_editor_position(expr_export) -> dict | None:
    """Extract MaterialExpressionEditorX/Y from properties."""
    x = None
    y = None
    for prop in getattr(expr_export, "properties", None) or []:
        if getattr(prop, "name", None) == "MaterialExpressionEditorX":
            x = getattr(prop, "value", None)
        elif getattr(prop, "name", None) == "MaterialExpressionEditorY":
            y = getattr(prop, "value", None)
    if x is not None or y is not None:
        return {"x": x or 0, "y": y or 0}
    return None


def _build_material_inputs(material_export, expr_guid_map: dict[int, str]) -> list:
    """Build MaterialInputIR list from Material export properties."""
    inputs = []
    for prop in getattr(material_export, "properties", None) or []:
        prop_name = getattr(prop, "name", "")
        prop_value = getattr(prop, "value", None)
        if isinstance(prop_value, dict):
            struct_type = prop_value.get("struct_type", "")
            if struct_type in (
                "MaterialInput",
                "FMaterialInput",
                "ColorMaterialInput",
                "FColorMaterialInput",
                "ScalarMaterialInput",
                "FScalarMaterialInput",
                "VectorMaterialInput",
                "FVectorMaterialInput",
                "Vector2MaterialInput",
                "FVector2MaterialInput",
            ):
                fields = prop_value.get("fields", {})
                if isinstance(fields, dict):
                    expr_idx = fields.get("expression_index", 0)
                    source_guid = expr_guid_map.get(expr_idx) if expr_idx else None
                    inputs.append(
                        MaterialInputIR(
                            input_name=prop_name,
                            source_expression_guid=source_guid,
                            source_output_index=fields.get("output_index", 0),
                            mask=fields.get("mask", 0),
                            mask_r=fields.get("mask_r", 0),
                            mask_g=fields.get("mask_g", 0),
                            mask_b=fields.get("mask_b", 0),
                            mask_a=fields.get("mask_a", 0),
                        )
                    )
    return inputs


def _build_material_properties(material_export) -> dict:
    """Build material properties dict from tagged properties."""
    from uasset_read.constants import (
        MATERIAL_DOMAIN_MAP,
        BLEND_MODE_MAP,
        SHADING_MODEL_MAP,
        MATERIAL_USAGE_FLAG_NAMES,
    )

    properties: dict = {}
    usage_flags: list[str] = []

    for prop in getattr(material_export, "properties", None) or []:
        prop_name = getattr(prop, "name", "")
        prop_value = getattr(prop, "value", None)

        if prop_name in ("MaterialDomain", "Domain"):
            domain_val = _safe_int(prop_value)
            properties["domain"] = MATERIAL_DOMAIN_MAP.get(domain_val, str(domain_val))
        elif prop_name == "BlendMode":
            # Handle enum dict format from ByteProperty
            if isinstance(prop_value, dict) and "value_name" in prop_value:
                enum_name = prop_value["value_name"]
                # Extract "Masked" from "EBlendMode::BLEND_Masked"
                if "::" in enum_name:
                    enum_name = enum_name.split("::")[-1]
                # Remove "BLEND_" prefix if present
                if enum_name.startswith("BLEND_"):
                    enum_name = enum_name[6:]
                properties["blend_mode"] = enum_name
            else:
                blend_val = _safe_int(prop_value)
                properties["blend_mode"] = BLEND_MODE_MAP.get(blend_val, str(blend_val))
        elif prop_name == "ShadingModel":
            model_val = _safe_int(prop_value)
            properties["shading_model"] = SHADING_MODEL_MAP.get(
                model_val, str(model_val)
            )
        elif prop_name in MATERIAL_USAGE_FLAG_NAMES and prop_value:
            usage_flags.append(prop_name)

    if usage_flags:
        properties["usage_flags"] = usage_flags

    return properties


def _build_material_instance_parameters(material_export) -> dict:
    """Build parameters dict from MaterialInstance export properties."""
    parameters: dict = {}

    for prop in getattr(material_export, "properties", None) or []:
        prop_name = getattr(prop, "name", "")
        prop_value = getattr(prop, "value", None)

        if prop_name == "ScalarParameterValues":
            parameters["scalar"] = _extract_parameter_values(
                prop_value, "ParameterValue"
            )
        elif prop_name == "VectorParameterValues":
            parameters["vector"] = _extract_parameter_values(
                prop_value, "ParameterValue"
            )
        elif prop_name == "TextureParameterValues":
            parameters["texture"] = _extract_parameter_values(
                prop_value, "ParameterValue"
            )
        elif prop_name == "StaticSwitchParameters":
            parameters["static_switch"] = _extract_static_switch_values(prop_value)

    return parameters if parameters else None


def _get_fields(obj):
    """Extract fields from StructValue or dict."""
    from uasset_read.models.properties import StructValue

    if isinstance(obj, StructValue):
        return obj.fields
    if isinstance(obj, dict):
        return obj
    return None


def _extract_parameter_values(source, value_key: str) -> dict:
    """Extract parameter name->value mapping from a parameter array."""
    result: dict = {}
    if isinstance(source, list):
        for item in source:
            fields = _get_fields(item)
            if fields is not None:
                info = fields.get("ParameterInfo", fields.get("Info", {}))
                info_fields = _get_fields(info) if info else {}
                if info_fields:
                    name = _safe_str(
                        info_fields.get("Name", info_fields.get("ParameterName", ""))
                    )
                else:
                    name = _safe_str(info) if info else ""
                if not name:
                    name = _safe_str(
                        fields.get("ParameterName", fields.get("Name", ""))
                    )
                if name:
                    result[name] = {
                        "value": fields.get(value_key, fields.get("Value")),
                        "guid": _safe_str(fields.get("ExpressionGUID", "")),
                    }
    return result


def _extract_static_switch_values(source) -> dict:
    """Extract static switch parameter name->bool mapping."""
    result: dict = {}
    if isinstance(source, list):
        for item in source:
            fields = _get_fields(item)
            if fields is not None:
                info = fields.get("ParameterInfo", fields.get("Info", {}))
                info_fields = _get_fields(info) if info else {}
                if info_fields:
                    name = _safe_str(
                        info_fields.get("Name", info_fields.get("ParameterName", ""))
                    )
                else:
                    name = _safe_str(info) if info else ""
                if not name:
                    name = _safe_str(
                        fields.get("ParameterName", fields.get("Name", ""))
                    )
                if name:
                    val = fields.get("Value", fields.get("value"))
                    result[name] = bool(val) if val is not None else False
    return result


def _build_material_instance_overrides(material_export) -> dict | None:
    """Build base_property_overrides from MaterialInstance export."""
    overrides: dict = {}
    override_names = (
        "OpacityMaskClipValue",
        "BlendMode",
        "ShadingModel",
        "TwoSided",
        "DitheredLODTransition",
        "CastDynamicShadowAsMasked",
        "bIsThinSurface",
        "OutputTranslucentVelocity",
        "bHasPixelAnimation",
        "bEnableTessellation",
        "DisplacementScaling",
        "bEnableDisplacementFade",
        "DisplacementFadeRange",
        "MaxWorldPositionOffsetDisplacement",
        "CompatibleWithLumenCardSharing",
        "UsageFlags",
    )

    for prop in getattr(material_export, "properties", None) or []:
        prop_name = getattr(prop, "name", "")
        if prop_name == "BasePropertyOverrides":
            val = getattr(prop, "value", None)
            fields = _get_fields(val)
            if fields:
                for name in override_names:
                    flag = fields.get(f"bOverride_{name}")
                    if flag:
                        v = fields.get(name)
                        if v is not None:
                            overrides[name] = v

    return overrides if overrides else None


def _resolve_material_parent(material_export, result) -> str | None:
    """Resolve parent material path from MaterialInstance export."""
    for prop in getattr(material_export, "properties", None) or []:
        if getattr(prop, "name", None) == "Parent":
            val = getattr(prop, "value", None)
            if isinstance(val, int):
                return _resolve_package_index(result, val)
            fields = _get_fields(val)
            if fields:
                return _safe_str(
                    fields.get(
                        "ObjectName",
                        fields.get("object_name", fields.get("full_name", "")),
                    )
                )
            if isinstance(val, str):
                return val
    return None


def _build_material_data_flow(
    expressions: list,
    material_inputs: list,
) -> list[dict]:
    """Build data_flow list from resolved expression inputs and material inputs."""
    data_flow: list[dict] = []

    # Expression-to-expression connections
    for expr in expressions:
        for inp in expr.inputs:
            if inp.source_expression_guid:
                data_flow.append(
                    {
                        "source_expression_guid": inp.source_expression_guid,
                        "source_output_index": inp.source_output_index,
                        "target_expression_guid": expr.expression_guid,
                        "target_input_name": inp.input_name,
                    }
                )

    # Expression-to-material connections
    for mi in material_inputs:
        if mi.source_expression_guid:
            data_flow.append(
                {
                    "source_expression_guid": mi.source_expression_guid,
                    "source_output_index": mi.source_output_index,
                    "target_expression_guid": "__material__",
                    "target_input_name": mi.input_name,
                }
            )

    return data_flow


def _build_user_defined_data(
    result: "ParseResult | LinkerParseResult",
) -> UserDefinedDataIR | None:
    """Extract user-defined type semantic data (enum or struct) from exports.

    Scans exports for UserDefinedEnum and UserDefinedStruct types and extracts
    their semantic content (enum entries or struct fields).
    """
    from uasset_read.serializers.object_resources import resolve_class_name

    for export in result.export_map or []:
        class_name = resolve_class_name(
            export.class_index,
            result.import_map or [],
            result.export_map or [],
        )

        if class_name == "UserDefinedEnum":
            try:
                from uasset_read.parsers.asset_types.user_defined import (
                    extract_user_defined_enum,
                )

                enum_data = extract_user_defined_enum(export, result.name_map or [])
                if enum_data:
                    return UserDefinedDataIR(
                        type="enum",
                        enum=UserDefinedEnumIR(
                            enum_name=enum_data.get("enum_name", ""),
                            cpp_type=enum_data.get("cpp_type", ""),
                            entries=enum_data.get("entries", []),
                        ),
                    )
            except (KeyError, TypeError, ValueError, AttributeError) as e:
                logger.debug("UserDefinedEnum extraction failed: %s", e)

        elif class_name == "UserDefinedStruct":
            try:
                from uasset_read.parsers.asset_types.user_defined import (
                    extract_user_defined_struct,
                )

                struct_data = extract_user_defined_struct(export, result.name_map or [])
                if struct_data:
                    return UserDefinedDataIR(
                        type="struct",
                        struct=UserDefinedStructIR(
                            struct_name=struct_data.get("struct_name", ""),
                            struct_flags=struct_data.get("struct_flags", 0),
                            guid=struct_data.get("guid", ""),
                            fields=struct_data.get("fields", []),
                        ),
                    )
            except (KeyError, TypeError, ValueError, AttributeError) as e:
                logger.debug("UserDefinedStruct extraction failed: %s", e)

    return None


def build_package_ir(result: "ParseResult | LinkerParseResult") -> PackageIR:
    """Convert ParseResult to PackageIR.

    Build stages:
    1. Extract header from summary
    2. Convert export_map entries to ExportIR one by one
    3. Resolve import/export paths through linker
    4. Normalize GUIDs to 32-char lowercase hex

    Tolerant mode: skips individual exports that fail to parse.
    """
    header = _build_header(result)
    exports = _build_exports(result)
    linker = _build_linker(result)

    # Build function_graphs (from result.graphs)
    function_graphs = []
    fallback_graphs = getattr(result, "metadata", {}).get("function_graphs_fallback")
    if fallback_graphs:
        function_graphs = list(fallback_graphs)
    elif hasattr(result, "graphs") and result.graphs:
        try:
            function_graphs = _build_function_graphs_safe(result)
        except (KeyError, TypeError, ValueError, AttributeError) as e:
            if hasattr(result, "warnings"):
                result.warnings.append(f"function_graphs generation skipped: {e}")

    status = _result_status(result)
    metadata = getattr(result, "metadata", None) or {}
    errors = list(getattr(result, "errors", None) or [])
    warnings = list(getattr(result, "warnings", None) or [])

    # Aggregate decompiled function-level warnings
    _decompiled_warnings = set()
    for func in result.decompiled_functions or []:
        for w in func.warnings or []:
            if w not in _decompiled_warnings:
                _decompiled_warnings.add(w)
                warnings.append(f"[bytecode] {w}")

    if errors:
        status_code = "PARSE_ERROR"
        status_message = errors[0]
    elif metadata.get("lightweight_tolerant_parse"):
        status_code = "LIGHTWEIGHT_TOLERANT_PARSE"
        status_message = (
            f"Lightweight tolerant parse: too many exports "
            f"({getattr(result.summary, 'export_count', '?')}), using degraded mode"
        )
    elif status == "partial" and _has_kismet_failure(result):
        status_code = "KISMET_PARTIAL"
        failed_count = _count_kismet_failed_functions(result)
        partial_count = _count_kismet_partial_functions(result)
        total_count = len(result.decompiled_functions or [])
        parts = []
        if failed_count:
            parts.append(f"{failed_count} failed")
        if partial_count:
            parts.append(f"{partial_count} partial translation")
        status_message = (
            f"Kismet function status: {', '.join(parts)} out of {total_count}"
        )
    # v0.5.1: export-level partial status message (#432)
    elif any(
        (getattr(export, "parse_status", None) or "success") != "success"
        for export in result.export_map or []
    ):
        # Group by status with fallback_reason examples for easier diagnosis
        status_groups: dict[str, list[str]] = {}
        for export in result.export_map or []:
            ps = getattr(export, "parse_status", None)
            if ps is not None:
                ps_str = str(ps.value) if hasattr(ps, "value") else str(ps)
                if ps_str != "success":
                    reason = str(getattr(export, "fallback_reason", None) or "")
                    status_groups.setdefault(ps_str, []).append(reason)
        parts = []
        for st in sorted(status_groups):
            reasons = status_groups[st]
            unique_reasons = list(dict.fromkeys(r for r in reasons if r))[:3]
            reason_hint = f" ({'; '.join(unique_reasons)})" if unique_reasons else ""
            parts.append(f"{st}×{len(reasons)}{reason_hint}")
        status_message = f"Export-level status: {', '.join(parts)}"
        status_code = "EXPORT_PARTIAL"
    else:
        status_code = None
        status_message = None

    # Build import_map for JSON output
    import_map = []
    for imp in result.import_map or []:
        import_map.append(
            {
                "index": getattr(imp, "index", 0),
                "class_package": getattr(imp, "class_package", ""),
                "class_name": getattr(imp, "class_name", ""),
                "object_name": getattr(imp, "object_name", ""),
                "outer_index": getattr(imp, "outer_index", 0),
            }
        )

    # Build name_map_entries for JSON output
    name_map_entries = list(result.name_map) if result.name_map else []

    ir = PackageIR(
        header=header,
        name_map=tuple(result.name_map) if result.name_map else (),
        imports=_build_imports(result),
        exports=exports,
        linker=linker,
        blueprint=_build_blueprint_ir(result),
        decompiled_functions=_build_decompiled_functions_ir(result),
        execution_chains=_build_execution_chains_ir(result),
        variables=_build_variables_ir(result),
        animation=_build_animation_data(result),
        material=_build_material_ir(result),
        user_defined=_build_user_defined_data(result),
        diagnostics=(result.diagnostics or [])
        + list(getattr(result, "structured_diagnostics", None) or []),
        function_graphs=function_graphs,
        logic_sources=list(getattr(result, "logic_sources", None) or []),
        dependencies=PackageDependenciesIR(
            resolved_parent_assets=list(
                getattr(result, "resolved_parent_assets", None) or []
            ),
            inherited_blueprint_graphs=list(
                getattr(result, "inherited_blueprint_graphs", None) or []
            ),
            depends_map=list(getattr(result.summary, "depends_map", None) or [])
            if result.summary
            else [],
            resolved_depends_map=_build_resolved_depends_map(result),
            soft_object_paths=list(getattr(result, "soft_references", None) or []),
            soft_package_references=list(
                getattr(result, "soft_package_references", None) or []
            ),
            asset_registry_data_offset=_safe_int(
                getattr(result.summary, "asset_registry_data_offset", 0)
            )
            if result.summary
            else 0,
            asset_registry_data=_build_asset_registry_data(result),
        ),
        diagnostics_data=DiagnosticsDataIR(
            errors=errors,
            warnings=warnings,
            status=status,
            status_message=status_message,
            status_code=status_code,
            diagnostics_truncated_count=getattr(result, "diagnostics_dropped_count", 0),
        ),
        debug=_build_debug_ir(
            getattr(result, "hex_view_entries", []),
            hex_view_truncated_count=getattr(result, "hex_view_dropped_count", 0),
        ),
        import_map=import_map,
        name_map_entries=name_map_entries,
        statistics=_build_statistics(result, len(exports)),
    )

    # Bind function/event implementation associations
    if ir.blueprint is not None:
        _bind_implementations(ir.blueprint, ir.decompiled_functions, ir.function_graphs)

    return ir


def _build_function_graphs_safe(
    result: "ParseResult | LinkerParseResult",
) -> list[dict]:
    """Build function_graphs with a simple complexity guard for large graphs."""
    graphs = getattr(result, "graphs", None) or []
    total_nodes = sum(len(getattr(graph, "nodes", None) or []) for graph in graphs)
    total_pins = sum(
        len(getattr(node, "pins", None) or [])
        for graph in graphs
        for node in (getattr(graph, "nodes", None) or [])
    )
    max_nodes = 900
    max_pins = 12000
    if total_nodes > max_nodes or total_pins > max_pins:
        if hasattr(result, "warnings"):
            result.warnings.append(
                "function_graphs generation skipped due to graph complexity "
                f"(nodes={total_nodes}, pins={total_pins})"
            )
        return _build_function_graph_summaries(result)

    from uasset_read.graph import build_function_graphs

    blueprint_functions = None
    if hasattr(result, "blueprint") and result.blueprint:
        blueprint_functions = getattr(result.blueprint, "functions", None)
    return build_function_graphs(graphs, blueprint_functions)


def _build_function_graph_summaries(
    result: "ParseResult | LinkerParseResult",
) -> list[dict]:
    entries = []
    for graph in getattr(result, "graphs", None) or []:
        for node in getattr(graph, "nodes", None) or []:
            if getattr(node, "class_name", "") != "K2Node_FunctionEntry":
                continue
            function_name = "Unknown"
            node_data = getattr(node, "node_data", None)
            ref = None
            if isinstance(node_data, dict):
                ref = node_data.get("function_reference")
            elif node_data is not None:
                ref = getattr(node_data, "function_reference", None)
            raw_name = getattr(ref, "member_name", None) if ref is not None else None
            if raw_name and raw_name != UE_NONE_SENTINEL:
                function_name = raw_name.split("/")[-1]
            entries.append(
                {
                    "function_name": function_name,
                    "graph_source": getattr(graph, "graph_name", ""),
                    "entry_node_guid": getattr(node, "node_guid", ""),
                    "signature": {"return_type": "", "parameters": []},
                    "execution_flows": [],
                    "fallback_reason": "graph_complexity_limit",
                }
            )
    return entries


def _build_header(result: ParseResult) -> PackageHeaderIR:
    summary = result.summary
    version = _get_version_string(result)

    # Helper: safely extract EngineVersion as string
    def _engine_version_str(ev) -> str:
        if ev is None:
            return ""
        major = getattr(ev, "major", 0)
        minor = getattr(ev, "minor", 0)
        patch = getattr(ev, "patch", 0)
        changelist = getattr(ev, "changelist", 0)
        branch = getattr(ev, "branch", "") or ""
        if major or minor or patch:
            base = f"{major}.{minor}.{patch}-{changelist}"
            return f"{base}+{branch}" if branch else base
        return ""

    # Helper: safely extract custom_versions as list of dicts
    def _custom_versions_list(cvs) -> list[dict]:
        result_list = []
        for cv in cvs or []:
            result_list.append(
                {
                    "guid": getattr(cv, "guid", "") or "",
                    "version": getattr(cv, "version", 0),
                }
            )
        return result_list

    # Helper: safely extract generations as list of dicts
    def _generations_list(gens) -> list[dict]:
        result_list = []
        for gen in gens or []:
            result_list.append(
                {
                    "export_count": getattr(gen, "export_count", 0),
                    "name_count": getattr(gen, "name_count", 0),
                }
            )
        return result_list

    # Count total properties across all exports
    total_props = sum(
        len(getattr(e, "properties", []) or []) for e in result.export_map or []
    )

    return PackageHeaderIR(
        package_name=_safe_str(getattr(summary, "package_name", None)),
        package_class=_safe_str(getattr(summary, "package_class", None)),
        package_flags=_safe_int(getattr(summary, "package_flags", 0)),
        total_export_count=_safe_int(getattr(summary, "export_count", 0)),
        total_import_count=_safe_int(getattr(summary, "import_count", 0)),
        ue_version=version,
        saved_hash=getattr(summary, "saved_hash", b"") or b"",
        # File version
        file_version_ue4=_safe_int(getattr(summary, "file_version_ue4", 0)),
        file_version_ue5=_safe_int(getattr(summary, "file_version_ue5", 0)),
        file_version_licensee=_safe_int(getattr(summary, "file_version_licensee", 0)),
        # Header structure offsets
        total_header_size=_safe_int(getattr(summary, "total_header_size", 0)),
        custom_versions=_custom_versions_list(
            getattr(summary, "custom_versions", None)
        ),
        folder_name=_safe_str(getattr(summary, "folder_name", None)),
        # Name table
        name_count=_safe_int(getattr(summary, "name_count", 0)),
        name_offset=_safe_int(getattr(summary, "name_offset", 0)),
        # Soft reference path table
        soft_object_paths_count=_safe_int(
            getattr(summary, "soft_object_paths_count", 0)
        ),
        soft_object_paths_offset=_safe_int(
            getattr(summary, "soft_object_paths_offset", 0)
        ),
        # Localization
        localization_id=_safe_str(getattr(summary, "localization_id", None)),
        # Gatherable text data
        gatherable_text_data_count=_safe_int(
            getattr(summary, "gatherable_text_data_count", 0)
        ),
        gatherable_text_data_offset=_safe_int(
            getattr(summary, "gatherable_text_data_offset", 0)
        ),
        # Export/import table
        export_count=_safe_int(getattr(summary, "export_count", 0)),
        export_offset=_safe_int(getattr(summary, "export_offset", 0)),
        import_count=_safe_int(getattr(summary, "import_count", 0)),
        import_offset=_safe_int(getattr(summary, "import_offset", 0)),
        # Metadata
        metadata_offset=_safe_int(getattr(summary, "metadata_offset", 0)),
        # Dependency table
        depends_offset=_safe_int(getattr(summary, "depends_offset", 0)),
        # Soft package references
        soft_package_references_count=_safe_int(
            getattr(summary, "soft_package_references_count", 0)
        ),
        soft_package_references_offset=_safe_int(
            getattr(summary, "soft_package_references_offset", 0)
        ),
        # Searchable names
        searchable_names_offset=_safe_int(
            getattr(summary, "searchable_names_offset", 0)
        ),
        # Thumbnail table
        thumbnail_table_offset=_safe_int(getattr(summary, "thumbnail_table_offset", 0)),
        # Import type hierarchies
        import_type_hierarchies_count=_safe_int(
            getattr(summary, "import_type_hierarchies_count", 0)
        ),
        import_type_hierarchies_offset=_safe_int(
            getattr(summary, "import_type_hierarchies_offset", 0)
        ),
        # Persistent GUID
        persistent_guid=_safe_str(getattr(summary, "persistent_guid", None)),
        # Version generations
        generations=_generations_list(getattr(summary, "generations", None)),
        # Engine version
        saved_by_engine_version=_engine_version_str(
            getattr(summary, "saved_by_engine_version", None)
        ),
        compatible_with_engine_version=_engine_version_str(
            getattr(summary, "compatible_with_engine_version", None)
        ),
        # Compression
        compression_flags=_safe_int(getattr(summary, "compression_flags", 0)),
        # Package source
        package_source=_safe_int(getattr(summary, "package_source", 0)),
        # Bulk data
        bulk_data_start_offset=_safe_int(getattr(summary, "bulk_data_start_offset", 0)),
        # World tile info
        world_tile_info_data_offset=_safe_int(
            getattr(summary, "world_tile_info_data_offset", 0)
        ),
        # Chunk IDs
        chunk_ids=list(getattr(summary, "chunk_ids", None) or []),
        # Preload dependencies
        preload_dependency_count=_safe_int(
            getattr(summary, "preload_dependency_count", 0)
        ),
        preload_dependency_offset=_safe_int(
            getattr(summary, "preload_dependency_offset", 0)
        ),
        # Names referenced from export data count
        names_referenced_from_export_data_count=_safe_int(
            getattr(summary, "names_referenced_from_export_data_count", 0)
        ),
        # Payload TOC
        payload_toc_offset=_safe_int(getattr(summary, "payload_toc_offset", 0)),
        # Data resource
        data_resource_offset=_safe_int(getattr(summary, "data_resource_offset", 0)),
        # Enriched summary fields
        total_properties=total_props,
        total_name_entries=len(result.name_map) if result.name_map else 0,
    )


def _get_version_string(result: ParseResult) -> str:
    """Extract UE version string from version_container."""
    vc = result.version_container
    if vc is None:
        return "unknown"

    # Prefer get_ue_version_string (if available and callable)
    method = getattr(vc, "get_ue_version_string", None)
    if callable(method):
        try:
            return method()
        except (AttributeError, TypeError, ValueError) as e:
            logger.debug("Failed to get UE version string: %s", e, exc_info=True)

    # Fallback: based on is_ue5 flag
    if getattr(vc, "is_ue5", False):
        return "5.x"
    return "4.x"


def _build_imports(result: ParseResult) -> list[ImportIR]:
    from uasset_read.link.linker import normalize_world_partition_path

    imports = []
    for idx, imp in enumerate(result.import_map or []):
        outer_resolved = _resolve_package_index(
            result, getattr(imp, "outer_index", None)
        )
        cp_raw = _safe_str(getattr(imp, "class_package", None))
        imports.append(
            ImportIR(
                index=idx,
                class_package=normalize_world_partition_path(cp_raw),
                class_name=_safe_str(getattr(imp, "class_name", None)),
                object_name=_safe_str(getattr(imp, "object_name", None)),
                outer_index=getattr(imp, "outer_index", 0) or 0,
                is_asset=bool(getattr(imp, "is_asset", False)),
                package_flags=_safe_int(getattr(imp, "package_flags", 0)),
                outer_index_resolved=outer_resolved,
                package_name=_safe_str(getattr(imp, "package_name", None)),
                b_import_optional=bool(getattr(imp, "b_import_optional", False)),
            )
        )
    return imports


def _build_exports(result: ParseResult) -> list[ExportIR]:
    exports = []
    for idx, export in enumerate(result.export_map or []):
        try:
            export_ir = _build_export_ir(idx, export, result)
            exports.append(export_ir)
        except (KeyError, TypeError, ValueError, AttributeError) as e:
            # Tolerant mode: skip failed exports
            logger.debug("Failed to build export %d IR: %s", idx, e, exc_info=True)
    return exports


_MAX_SERIAL_SIZE = 10 * 1024 * 1024 * 1024  # 10 GB sanity limit


def _clamp_serial_size(size: int) -> int:
    """Clamp corrupted serial_size values (negative or absurdly large)."""
    if size < 0 or size > _MAX_SERIAL_SIZE:
        return 0
    return size


def _resolve_asset_class(export, result: ParseResult) -> str | None:
    """Resolve the nearest owning asset export's class through outer links."""
    exports = result.export_map or []
    import_map = result.import_map or []
    current = export
    seen: set[int] = set()

    while current is not None:
        identity = id(current)
        if identity in seen:
            return None
        seen.add(identity)

        if getattr(current, "b_is_asset", False):
            class_index = getattr(current, "class_index", None)
            if class_index is None:
                return None
            return (
                _safe_str(resolve_class_name(class_index, import_map, exports)) or None
            )

        outer_index = getattr(current, "outer_index", None)
        if not getattr(outer_index, "is_export", False):
            return None
        outer_idx = outer_index.to_export_index()
        if not 0 <= outer_idx < len(exports):
            return None
        current = exports[outer_idx]

    return None


def _build_export_ir(idx: int, export, result: ParseResult) -> ExportIR:
    outer_resolved = _resolve_package_index(
        result, getattr(export, "outer_index", None)
    )
    super_resolved = _resolve_package_index(
        result, getattr(export, "super_index", None)
    )

    # parent_class is only set on blueprint exports (fix #252)
    # Blueprint export definition: object_name ends with _C, or has graphs data
    parent_class = None
    if result.blueprint and getattr(result.blueprint, "parent_class", None):
        object_name = _safe_str(getattr(export, "object_name", None))
        has_graphs = bool(getattr(export, "graphs", None))
        if object_name.endswith("_C") or has_graphs:
            parent_class = result.blueprint.parent_class

    properties = []
    for prop in getattr(export, "properties", None) or []:
        properties.append(_build_property_ir(prop))

    graphs = []
    for graph in getattr(export, "graphs", None) or []:
        graphs.append(_build_graph_ir(graph))

    bulk_data = getattr(export, "bulk_data_header", None)
    asset_type_data = getattr(export, "_asset_type_data", None)

    # Build UE raw export table fields
    raw = _build_export_raw_ir(export)

    # ObjectExport does not have an object_class field; resolve from class_index
    resolved_class = getattr(export, "object_class", None)
    if not resolved_class and hasattr(export, "class_index"):
        resolved_class = resolve_class_name(
            export.class_index, result.import_map or [], result.export_map or []
        )

    return ExportIR(
        index=idx,
        object_name=_safe_str(getattr(export, "object_name", None)),
        object_class=_safe_str(resolved_class),
        serial_size=_clamp_serial_size(getattr(export, "serial_size", 0) or 0),
        outer_index_resolved=outer_resolved,
        super_index_resolved=super_resolved,
        parent_class=parent_class,
        properties=properties,
        graphs=graphs,
        bulk_data=bulk_data,
        asset_class=_resolve_asset_class(export, result),
        asset_type_data=asset_type_data,
        parse_status=_safe_str(getattr(export, "parse_status", "success")) or "success",
        fallback_reason=(
            _safe_str(getattr(export, "fallback_reason", None))
            if getattr(export, "fallback_reason", None) is not None
            else None
        ),
        error_message=(
            _safe_str(getattr(export, "error_message", None))
            if getattr(export, "error_message", None) is not None
            else None
        ),
        ue_export_raw=raw,
        diagnostics=_build_export_diagnostics(export),
        anim_blueprint=getattr(export, "custom_data", {}).get("anim_blueprint"),
        anim_sequence=getattr(export, "custom_data", {}).get("anim_sequence"),
        anim_montage=getattr(export, "custom_data", {}).get("anim_montage"),
    )


def _build_export_raw_ir(export) -> ExportRawIR:
    """Build UE raw export table fields from ObjectExport."""

    def _pkg_index_raw(pi) -> int:
        """Extract raw integer value from PackageIndex."""
        if pi is None:
            return 0
        return getattr(pi, "index", 0)

    return ExportRawIR(
        class_index=_pkg_index_raw(getattr(export, "class_index", None)),
        super_index=_pkg_index_raw(getattr(export, "super_index", None)),
        outer_index=_pkg_index_raw(getattr(export, "outer_index", None)),
        template_index=_pkg_index_raw(getattr(export, "template_index", None)),
        object_flags=getattr(export, "object_flags", 0) or 0,
        serial_offset=getattr(export, "serial_offset", 0) or 0,
        package_flags=getattr(export, "package_flags", 0) or 0,
        b_forced_export=bool(getattr(export, "b_forced_export", False)),
        b_not_for_client=bool(getattr(export, "b_not_for_client", False)),
        b_not_for_server=bool(getattr(export, "b_not_for_server", False)),
        b_is_inherited_instance=bool(getattr(export, "b_is_inherited_instance", False)),
        b_not_always_loaded_for_editor_game=bool(
            getattr(export, "b_not_always_loaded_for_editor_game", True)
        ),
        b_is_asset=bool(getattr(export, "b_is_asset", False)),
        b_generate_public_hash=bool(getattr(export, "b_generate_public_hash", False)),
        script_serialization_start_offset=getattr(
            export, "script_serialization_start_offset", 0
        )
        or 0,
        script_serialization_end_offset=getattr(
            export, "script_serialization_end_offset", 0
        )
        or 0,
        guid=_safe_str(getattr(export, "guid", "")) or "",
    )


def _build_export_diagnostics(export) -> dict | None:
    """Build diagnostic info from ObjectExport.transforms."""
    transforms = getattr(export, "transforms", None) or {}
    if not transforms:
        return None
    return dict(transforms)


def _build_property_ir(prop) -> PropertyIR:
    return PropertyIR(
        name=_safe_str(getattr(prop, "name", None)),
        type=_safe_str(getattr(prop, "type", None)),
        value=getattr(prop, "value", None),
        array_index=getattr(prop, "array_index", -1) or -1,
        guid=_normalize_guid(getattr(prop, "guid", None)),
    )


def _build_graph_ir(graph) -> GraphIR:
    nodes = []
    for node in getattr(graph, "nodes", None) or []:
        nodes.append(_build_node_ir(node))

    # Recursively build nested subgraphs
    subgraphs = []
    for subgraph in getattr(graph, "subgraphs", None) or []:
        subgraphs.append(_build_graph_ir(subgraph))

    execution_chains = list(getattr(graph, "execution_chains", None) or [])
    if not execution_chains:
        from uasset_read.graph.chain_builder import build_execution_chains

        execution_chains = build_execution_chains(graph)

    # Infer graph type (ordered by priority: more specific patterns before broader ones)
    graph_type = None
    graph_class = _safe_str(getattr(graph, "graph_class", None))
    if graph_class:
        for kw, gtype in (
            ("StateMachine", "state_machine"),
            ("Transition", "transition"),
            ("Conduit", "conduit"),
            ("State", "state"),
            ("AnimGraph", "animation"),
            ("Animation", "animation"),
        ):
            if kw in graph_class:
                graph_type = gtype
                break

    return GraphIR(
        graph_guid=_normalize_guid(getattr(graph, "graph_guid", None)),
        graph_name=_safe_str(getattr(graph, "graph_name", None)),
        graph_class=graph_class,
        nodes=nodes,
        execution_chains=execution_chains,
        subgraphs=subgraphs,
        graph_type=graph_type,
    )


def _build_node_ir(node) -> NodeIR:
    pins = []
    for pin in getattr(node, "pins", None) or []:
        pins.append(_build_pin_ir(pin))

    # Extract Enhanced Input related fields
    input_action_path = None
    trigger_events = []
    event_type = None

    node_class = _safe_str(getattr(node, "class_name", None))
    if "EnhancedInputAction" in node_class:
        # Extract from node_data
        node_data = getattr(node, "node_data", None)
        if isinstance(node_data, dict):
            input_action_path = node_data.get("input_action_path")
            raw_triggers = node_data.get("trigger_events", {})
            # Convert dict[str, str] from serializer to list[dict] per IR contract
            if isinstance(raw_triggers, dict):
                trigger_events = [
                    {"trigger_name": k, "event_type": v}
                    for k, v in raw_triggers.items()
                ]
            elif isinstance(raw_triggers, list):
                trigger_events = raw_triggers
            else:
                trigger_events = []
            event_type = node_data.get("event_type")

        # Extract from node attributes (fallback path)
        if not input_action_path:
            input_action_path = getattr(node, "input_action_path", None)
        if not trigger_events:
            trigger_events = getattr(node, "trigger_events", []) or []
        if not event_type:
            event_type = getattr(node, "event_type", None)

    # Extract member references from node_data (function_reference, event_reference, variable_reference)
    member_name = None
    member_parent = None
    node_data = getattr(node, "node_data", None)
    if isinstance(node_data, dict):
        for ref_attr in ("function_reference", "event_reference", "variable_reference"):
            ref = node_data.get(ref_attr)
            if ref is not None and getattr(ref, "member_name", ""):
                member_name = _safe_str(ref.member_name)
                member_parent = _safe_str(getattr(ref, "member_parent", None))
                break

    return NodeIR(
        node_guid=_normalize_guid(getattr(node, "node_guid", None)),
        node_class=node_class,
        node_comment=getattr(node, "node_comment", None),
        pins=pins,
        execution_flow=getattr(node, "execution_flow", None) or [],
        macro_expansion=getattr(node, "macro_expansion", None),
        input_action_path=input_action_path,
        trigger_events=trigger_events,
        event_type=event_type,
        member_name=member_name,
        member_parent=member_parent,
    )


def _build_pin_ir(pin) -> PinIR:
    # Extract pin_guid — pin_id is the canonical field; pin_guid is a legacy alias
    pin_guid = _normalize_guid(getattr(pin, "pin_id", None)) or _normalize_guid(
        getattr(pin, "pin_guid", None)
    )

    linked_to = []
    for ref in getattr(pin, "linked_to_raw", None) or []:
        guid = _extract_pin_guid(ref)
        if guid:
            linked_to.append(guid)

    direction = "EGPD_Input"
    if getattr(pin, "direction", 0) == 1:
        direction = "EGPD_Output"

    # Extract structured fields from FEdGraphPinType
    pin_type_obj = getattr(pin, "pin_type", None)
    pin_category = ""
    pin_subcategory = ""
    pin_subcategory_object = None
    container_type = "None"
    is_reference = False
    is_const = False
    is_weak_pointer = False
    is_uobject_wrapper = False
    is_map_key = False
    is_map_value = False
    map_key_pin_category = ""
    map_key_pin_subcategory = ""
    map_key_pin_subcategory_object = None

    if pin_type_obj is not None:
        pin_category = _safe_str(getattr(pin_type_obj, "pin_category", None))
        pin_subcategory = _safe_str(getattr(pin_type_obj, "pin_subcategory", None))
        pin_subcategory_object = getattr(
            pin_type_obj, "pin_subcategory_object_name", None
        )
        container_type = CONTAINER_TYPE_MAP.get(
            getattr(pin_type_obj, "container_type", 0), "None"
        )
        is_reference = bool(getattr(pin_type_obj, "is_reference", False))
        is_const = bool(getattr(pin_type_obj, "is_const", False))
        is_weak_pointer = bool(getattr(pin_type_obj, "is_weak_pointer", False))
        is_uobject_wrapper = bool(getattr(pin_type_obj, "is_uobject_wrapper", False))
        is_map_key = bool(getattr(pin_type_obj, "is_map_key", False))
        is_map_value = bool(getattr(pin_type_obj, "is_map_value", False))

        # Map terminal type (key type info)
        if getattr(pin_type_obj, "container_type", 0) == 3:
            map_key_pin_category = _safe_str(
                getattr(pin_type_obj, "map_key_terminal_category", None)
            )
            map_key_pin_subcategory = _safe_str(
                getattr(pin_type_obj, "map_key_terminal_sub_category", None)
            )
            map_key_pin_subcategory_object = getattr(
                pin_type_obj, "map_key_terminal_sub_category_object_name", None
            )

    return PinIR(
        pin_guid=pin_guid,
        pin_name=_safe_str(getattr(pin, "pin_name", None)),
        pin_type=_safe_str(pin_type_obj),
        linked_to=linked_to,
        direction=direction,
        default_value=getattr(pin, "default_value", None),
        pin_category=pin_category,
        pin_subcategory=pin_subcategory,
        pin_subcategory_object_name=pin_subcategory_object,
        container_type=container_type,
        is_reference=is_reference,
        is_const=is_const,
        is_weak_pointer=is_weak_pointer,
        is_uobject_wrapper=is_uobject_wrapper,
        is_map_key=is_map_key,
        is_map_value=is_map_value,
        map_key_pin_category=map_key_pin_category,
        map_key_pin_subcategory=map_key_pin_subcategory,
        map_key_pin_subcategory_object_name=map_key_pin_subcategory_object,
        # Pin identity fields (Task 2)
        friendly_name=_safe_str(getattr(pin, "pin_friendly_name", None)) or None,
        source_index=getattr(pin, "source_index", None),
        persistent_guid=_normalize_guid(getattr(pin, "persistent_guid", None)) or "",
        default_text_value=_safe_str(getattr(pin, "default_text_value", None)) or None,
        auto_default_value=_safe_str(getattr(pin, "auto_default_value", None)) or None,
        default_object_name=_resolve_default_object_name(
            getattr(pin, "default_object_ref", None)
        ),
        parent_pin_guid=_extract_pin_guid(getattr(pin, "parent_pin", None)) or "",
        sub_pin_guids=[
            g
            for g in (
                _extract_pin_guid(ref) for ref in getattr(pin, "sub_pins", None) or []
            )
            if g
        ],
        ref_pass_through_guid=_extract_pin_guid(getattr(pin, "ref_pass_through", None))
        or "",
        hidden=bool(getattr(pin, "hidden", False)),
        not_connectable=bool(getattr(pin, "not_connectable", False)),
        advanced_view=bool(getattr(pin, "advanced_view", False)),
        orphaned=bool(getattr(pin, "orphaned_pin", False)),
    )


def _resolve_package_index(result: ParseResult, pkg_index) -> str | None:
    """Resolve PackageIndex to a human-readable path string."""
    if pkg_index is None or result.linker is None:
        return None
    try:
        obj_ref = result.linker.resolve_package_index(pkg_index)
        if obj_ref is None:
            return None
        # UObjectInstance has get_full_name() method
        if hasattr(obj_ref, "get_full_name"):
            return obj_ref.get_full_name()
        return str(obj_ref)
    except (KeyError, IndexError, AttributeError, ValueError):
        return None


def _build_resolved_depends_map(result: "ParseResult") -> list[list[dict]]:
    """Resolve raw PackageIndex values in DependsMap to human-readable paths.

    Returns:
        2D list: outer level indexed by export, inner level is a list of [{index, path}].
    """
    if not result.summary:
        return []
    raw_map = getattr(result.summary, "depends_map", None) or []
    if not raw_map:
        return []

    resolved: list[list[dict]] = []
    for dep_indices in raw_map:
        row: list[dict] = []
        for idx in dep_indices:
            pkg_idx = PackageIndex(idx)
            path = _resolve_package_index(result, pkg_idx)
            row.append({"index": idx, "path": path})
        resolved.append(row)
    return resolved


def _build_linker(result: ParseResult) -> LinkerSummaryIR | None:
    linker = result.linker
    if linker is None:
        return None

    from uasset_read.link.linker import normalize_world_partition_path

    import_paths = []
    for imp in result.import_map or []:
        cp = _safe_str(getattr(imp, "class_package", None))
        cn = _safe_str(getattr(imp, "class_name", None))
        path = f"{normalize_world_partition_path(cp)}.{cn}"
        if path.strip():
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


def _build_blueprint_ir(result: ParseResult) -> BlueprintIR | None:
    """Build BlueprintIR from ParseResult.blueprint (full metadata)."""
    bp = result.blueprint
    if bp is None:
        return None

    functions = []
    for func in bp.functions:
        functions.append(
            BlueprintFunctionIR(
                name=func.name,
                return_type=func.return_type,
                parameters=[
                    {
                        "name": p.name,
                        "param_type": p.param_type,
                        "default_value": p.default_value,
                        "is_input": p.is_input,
                        "is_output": p.is_output,
                    }
                    for p in func.parameters
                ],
                function_flags=getattr(func, "function_flags", 0) or 0,
                is_implemented=getattr(func, "is_implemented", True),
                is_pure=getattr(func, "is_pure", False),
                is_blueprint_callable=getattr(func, "is_blueprint_callable", False),
                is_const=getattr(func, "is_const", False),
                is_static=getattr(func, "is_static", False),
                is_net=getattr(func, "is_net", False),
                is_net_reliable=getattr(func, "is_net_reliable", False),
                is_blueprint_private=getattr(func, "is_blueprint_private", False),
                access_specifier=getattr(func, "access_specifier", "Public")
                or "Public",
                meta_data=dict(getattr(func, "meta_data", None) or {}),
            )
        )

    events = []
    for evt in bp.events:
        events.append(
            BlueprintEventIR(
                name=evt.name,
                event_type=evt.event_type,
                parameters=[
                    {
                        "name": p.name,
                        "param_type": p.param_type,
                        "default_value": p.default_value,
                        "is_input": p.is_input,
                        "is_output": p.is_output,
                    }
                    for p in evt.parameters
                ],
                function_flags=getattr(evt, "function_flags", 0) or 0,
                is_override=getattr(evt, "is_override", False),
                override_parent_class=_safe_str(
                    getattr(evt, "override_parent_class", None)
                ),
                override_parent_event=_safe_str(
                    getattr(evt, "override_parent_event", None)
                ),
                is_interface_event=getattr(evt, "is_interface_event", False),
                interface_class=_safe_str(getattr(evt, "interface_class", None)),
                is_net=getattr(evt, "is_net", False),
                is_net_multicast=getattr(evt, "is_net_multicast", False),
                is_replicated=getattr(evt, "is_replicated", False),
                is_cosmetic=getattr(evt, "is_cosmetic", False),
                is_static=getattr(evt, "is_static", False),
                meta_data=dict(getattr(evt, "meta_data", None) or {}),
            )
        )

    components = list(result.components) if result.components else []

    # Extract description and interfaces
    description = getattr(bp, "description", "") or ""
    interfaces = [
        {"name": iface.name, "guid": iface.guid}
        for iface in getattr(bp, "interfaces", []) or []
    ]

    return BlueprintIR(
        parent_class=bp.parent_class,
        description=description,
        interfaces=interfaces,
        functions=functions,
        events=events,
        components=components,
    )


def _build_decompiled_functions_ir(result: ParseResult) -> list[DecompiledFunctionIR]:
    """Build DecompiledFunctionIR list from ParseResult.decompiled_functions."""
    decompiled = []
    for func in result.decompiled_functions or []:
        # Prefer native field-derived parameters and return_type when available
        native_signature = getattr(func, "native_signature", False)
        if native_signature:
            return_type = getattr(func, "return_type", "void")
            parameters = getattr(func, "parameters", [])
        else:
            # Fallback: parse return_type from signature (format: "ReturnType FuncName(params)")
            return_type = _extract_return_type(func.signature)
            parameters = _extract_parameters(func)
        confidence = _infer_bytecode_confidence(
            func.fallback_reasons,
            bytecode_status=func.bytecode_status,
            logic_source=func.logic_source,
        )
        # Convert script_metrics dict to ScriptMetricsIR
        raw_metrics = getattr(func, "script_metrics", None)
        script_metrics = None
        if raw_metrics is not None:
            script_metrics = ScriptMetricsIR(
                bytecode_buffer_size=raw_metrics.get("bytecode_buffer_size", 0),
                serialized_script_size=raw_metrics.get("serialized_script_size", 0),
                serialized_bytes_consumed=raw_metrics.get(
                    "serialized_bytes_consumed", 0
                ),
                bytecode_bytes_consumed=raw_metrics.get("bytecode_bytes_consumed", 0),
            )
        decompiled.append(
            DecompiledFunctionIR(
                name=func.function_name,
                signature=func.signature,
                cpp_code=func.cpp_code,
                parameters=parameters,
                return_type=return_type,
                local_variables=getattr(func, "local_variables", []),
                fallback_reasons=func.fallback_reasons,
                bytecode_confidence=confidence,
                bytecode_status=func.bytecode_status,
                translation_status=getattr(
                    func, "translation_status", "not_applicable"
                ),
                bytecode_source=func.bytecode_source,
                logic_source=func.logic_source,
                warnings=func.warnings,
                error_code=getattr(func, "error_code", None),
                error_message=getattr(func, "error_message", None),
                error_context=getattr(func, "error_context", None),
                script_metrics=script_metrics,
            )
        )
    return decompiled


def _infer_bytecode_confidence(
    fallback_reasons: list[str],
    bytecode_status: str = "unknown",
    logic_source: str = "current_asset",
) -> str:
    """Backward-compatible local alias for shared provenance inference."""
    return infer_bytecode_confidence(
        fallback_reasons,
        bytecode_status=bytecode_status,
        logic_source=logic_source,
    )


def _extract_return_type(signature: str) -> str:
    """Extract return type from a C++ function signature.

    Signature format: "ReturnType FuncName(params)"
    """
    if not signature:
        return "void"
    # Find the first space (separator between return type and function name)
    space_idx = signature.find(" ")
    if space_idx > 0:
        return signature[:space_idx]
    return "void"


def _extract_parameters_from_signature(signature: str) -> list[dict]:
    """Parse parameter list from a C++ function signature.

    Signature format: "ReturnType FuncName(param1, param2, ...)"
    Returns: [{"name": "param1", "type": "int32"}, ...]
    """
    if not signature:
        return []

    # Extract the parameter portion inside parentheses
    match = re.search(r"\(([^)]*)\)", signature)
    if not match:
        return []

    params_str = match.group(1).strip()
    if not params_str:
        return []

    params = []
    for param in params_str.split(","):
        param = param.strip()
        if not param:
            continue
        # Separate type and name: "int32 EntryPoint" -> ("int32", "EntryPoint")
        parts = param.rsplit(None, 1)
        if len(parts) == 2:
            params.append({"name": parts[1], "type": parts[0]})
        elif len(parts) == 1:
            # Type only, no name
            params.append({"name": "", "type": parts[0]})
    return params


def _extract_parameters(func) -> list[dict]:
    """Extract parameter information from KismetDecompiledResult.

    Priority: semantic_calls -> signature parsing. Local variables are
    function-scoped temporaries, not parameter declarations.
    """
    # 1) Arguments from semantic_calls
    if func.semantic_calls:
        for call in func.semantic_calls:
            args = call.get("arguments")
            if args:
                return [{"name": a, "type": ""} for a in args]

    # 2) Parse from signature string
    if func.signature:
        return _extract_parameters_from_signature(func.signature)

    return []


def _build_execution_chains_ir(result: ParseResult) -> list[ExecutionChainIR]:
    """Build ExecutionChainIR list from execution chains in all graphs."""
    chains = []
    for graph in result.graphs or []:
        for node in graph.nodes or []:
            # Find event nodes as chain starting points
            class_name = getattr(node, "class_name", "") or ""
            if "Event" not in class_name:
                continue
            # Get event name from the event node's pins
            event_name = _get_event_name_from_node(node)
            # Build execution chain starting from this event
            chain = _trace_execution_from_node(node, graph)
            if chain:
                chains.append(ExecutionChainIR(event=event_name, chain=chain))
    return chains


def _build_variables_ir(result: ParseResult) -> list[VariableIR]:
    """Build VariableIR list from ParseResult.blueprint.variables (full metadata)."""
    variables = []
    bp = result.blueprint
    if bp is None:
        return variables
    for var in bp.variables or []:
        kind = _classify_variable(var)
        if kind == "metadata":
            continue  # Skip metadata variables
        var_type = _format_var_type(var)
        default_value = _safe_str(getattr(var, "default_value", None)) or None
        variables.append(
            VariableIR(
                name=_safe_str(getattr(var, "var_name", None)),
                type=var_type,
                default_value=default_value,
                kind=kind,
                guid=_normalize_guid(getattr(var, "var_guid", None)),
                category=_safe_str(getattr(var, "category", None)),
                property_flags=getattr(var, "property_flags", 0) or 0,
                replication_condition=getattr(var, "replication_condition", 0) or 0,
                rep_notify_func=_safe_str(getattr(var, "rep_notify_func", None)),
                friendly_name=_safe_str(getattr(var, "friendly_name", None)),
                metadata=dict(getattr(var, "metadata", None) or {}),
                flags_labels=list(getattr(var, "flags_labels", None) or []),
                edit_condition=_safe_str(getattr(var, "edit_condition", None)),
                is_edit_anywhere=getattr(var, "is_edit_anywhere", False),
                is_visible_anywhere=getattr(var, "is_visible_anywhere", False),
                is_blueprint_read_only=getattr(var, "is_blueprint_read_only", False),
                is_transient=getattr(var, "is_transient", False),
                is_replicated=getattr(var, "is_replicated", False),
                is_rep_notify=getattr(var, "is_rep_notify", False),
                is_expose_on_spawn=getattr(var, "is_expose_on_spawn", False),
                is_save_game=getattr(var, "is_save_game", False),
            )
        )
    return variables


# Event alias mapping: Blueprint event names -> common C++/Blueprint implementation function names
_EVENT_ALIASES: dict[str, list[str]] = {
    "ReceiveBeginPlay": ["BeginPlay"],
    "ReceiveTick": ["Tick"],
    "ReceiveEndPlay": ["EndPlay"],
    "ReceiveAnyDamage": ["AnyDamage"],
    "ReceivePointDamage": ["PointDamage"],
    "ReceiveRadialDamage": ["RadialDamage"],
    "ReceiveActorBeginOverlap": ["ActorBeginOverlap"],
    "ReceiveActorEndOverlap": ["ActorEndOverlap"],
    "ReceiveActorBeginCursorOver": ["ActorBeginCursorOver"],
    "ReceiveActorEndCursorOver": ["ActorEndCursorOver"],
    "ReceiveHit": ["Hit"],
    "ReceiveDestroyed": ["Destroyed"],
}


def _bind_implementations(
    blueprint: BlueprintIR,
    decompiled: list[DecompiledFunctionIR],
    function_graphs: list[dict],
) -> None:
    """Bind decompiled_functions and function_graphs to blueprint functions/events.

    Matching priority:
    1. Exact function name match with decompiled_functions.name
    2. Event alias match (e.g. ReceiveBeginPlay -> BeginPlay)
    3. function_graphs[].function_name match
    4. No match -> implementation_status stays "missing"
    """
    # Build lookup indices
    decompiled_by_name: dict[str, DecompiledFunctionIR] = {}
    for f in decompiled:
        if f.name not in decompiled_by_name:
            decompiled_by_name[f.name] = f

    graph_by_name: dict[str, dict] = {}
    for g in function_graphs:
        fn = g.get("function_name", "")
        if fn and fn not in graph_by_name:
            graph_by_name[fn] = g

    for func in blueprint.functions:
        _bind_single_implementation(
            func, decompiled_by_name, graph_by_name, [func.name]
        )

    for evt in blueprint.events:
        candidates = [evt.name]
        aliases = _EVENT_ALIASES.get(evt.name)
        if aliases:
            candidates.extend(aliases)
        _bind_single_implementation(evt, decompiled_by_name, graph_by_name, candidates)


def _bind_single_implementation(
    item,
    decompiled_by_name: dict[str, DecompiledFunctionIR],
    graph_by_name: dict[str, dict],
    candidate_names: list[str],
) -> None:
    """Bind implementation for a single function/event."""
    matched_decompiled = None
    match_count = 0

    for name in candidate_names:
        df = decompiled_by_name.get(name)
        if df:
            matched_decompiled = df
            match_count += 1

    if matched_decompiled:
        item.implementation = {
            "name": matched_decompiled.name,
            "signature": matched_decompiled.signature,
            "cpp_code": matched_decompiled.cpp_code,
            "parameters": matched_decompiled.parameters,
            "return_type": matched_decompiled.return_type,
            "bytecode_confidence": matched_decompiled.bytecode_confidence,
            "bytecode_status": matched_decompiled.bytecode_status,
            "translation_status": matched_decompiled.translation_status,
            "bytecode_source": matched_decompiled.bytecode_source,
            "logic_source": matched_decompiled.logic_source,
            "warnings": matched_decompiled.warnings,
            "fallback_reasons": matched_decompiled.fallback_reasons,
        }
        if matched_decompiled.error_code is not None:
            item.implementation["error_code"] = matched_decompiled.error_code
        if matched_decompiled.error_message is not None:
            item.implementation["error_message"] = matched_decompiled.error_message
        if matched_decompiled.error_context is not None:
            item.implementation["error_context"] = matched_decompiled.error_context
        if matched_decompiled.script_metrics is not None:
            item.implementation["script_metrics"] = {
                "bytecode_buffer_size": matched_decompiled.script_metrics.bytecode_buffer_size,
                "serialized_script_size": matched_decompiled.script_metrics.serialized_script_size,
                "serialized_bytes_consumed": matched_decompiled.script_metrics.serialized_bytes_consumed,
                "bytecode_bytes_consumed": matched_decompiled.script_metrics.bytecode_bytes_consumed,
            }
        item.implementation_status = "decompiled"
        if match_count > 1:
            item.implementation["ambiguous_match"] = True
        return

    # Try function_graphs
    for name in candidate_names:
        fg = graph_by_name.get(name)
        if fg:
            item.function_graph = {
                "function_name": fg.get("function_name", ""),
                "graph_source": fg.get("graph_source", ""),
                "entry_node_guid": fg.get("entry_node_guid", ""),
            }
            item.implementation_status = "graph_only"
            return

    # No match, keep "missing"


def _format_var_type(var) -> str:
    """Format BlueprintVariable's var_type into a human-readable string."""
    pin_type = getattr(var, "var_type", None)
    if pin_type is None:
        return "Unknown"
    category = getattr(pin_type, "pin_category", "") or ""
    subcategory = getattr(pin_type, "pin_subcategory", "") or ""
    object_name = getattr(pin_type, "pin_subcategory_object_name", None) or ""
    container = getattr(pin_type, "container_type", 0)

    # Container type prefix (EPinContainerType: None=0, Array=1, Set=2, Map=3)
    prefix = CONTAINER_TYPE_PREFIX.get(container, "")

    # Base type
    if category == "struct" and object_name:
        base = object_name
    elif category == "class" and object_name:
        base = object_name
    elif category == "enum" and subcategory:
        base = subcategory
    elif subcategory:
        base = subcategory
    elif category:
        base = category
    else:
        base = "Unknown"

    if prefix:
        return f"{prefix}<{base}>"
    return base


def _get_event_name_from_node(node) -> str:
    """Extract event name from an event node."""
    # Prefer node_comment (event node comments are typically the event name)
    comment = getattr(node, "node_comment", None)
    if comment:
        return comment
    # Fall back to class name
    return getattr(node, "class_name", "Unknown") or "Unknown"


def _trace_execution_from_node(start_node, graph) -> list[str]:
    """Trace execution flow chain from a starting node."""
    visited = set()
    chain = []
    current = start_node
    while current:
        guid = getattr(current, "node_guid", None)
        if not guid or guid in visited:
            break
        visited.add(guid)
        class_name = getattr(current, "class_name", "") or "Unknown"
        chain.append(class_name)
        # Find the next execution node
        next_node = _find_next_exec_node(current, graph, visited)
        current = next_node
    return chain


def _find_next_exec_node(node, graph, visited) -> object | None:
    """Find the next node from a node's execution output pin."""
    for pin in node.pins or []:
        # Execution output pin (direction=1 means output)
        direction = getattr(pin, "direction", 0)
        if direction != 1:
            continue
        pin_type = getattr(pin, "pin_type", None)
        pin_category = ""
        if pin_type:
            pin_category = getattr(pin_type, "pin_category", "") or ""
        if pin_category != "exec":
            continue
        # Traverse linked_to_raw to find the next node
        for ref in pin.linked_to_raw or []:
            target_pin_id = None
            if isinstance(ref, dict):
                target_pin_id = ref.get("pin_guid") or ref.get("pin_id")
            elif isinstance(ref, str):
                target_pin_id = ref
            else:
                target_pin_id = getattr(ref, "pin_guid", None) or getattr(
                    ref, "pin_id", None
                )
            if not target_pin_id:
                continue
            # Find the node containing the target pin
            target_node = _find_node_by_pin_id(target_pin_id, graph, visited)
            if target_node:
                return target_node
    return None


def _find_node_by_pin_id(pin_id: str, graph, visited) -> object | None:
    """Find the corresponding node by pin ID (unvisited only)."""
    for node in graph.nodes or []:
        node_guid = getattr(node, "node_guid", None)
        if node_guid in visited:
            continue
        for pin in node.pins or []:
            pin_guid = getattr(pin, "pin_id", None)
            if pin_guid == pin_id:
                return node
    return None


def _normalize_guid(guid: str | None) -> str | None:
    """Normalize GUID to 32-character lowercase hex (no dashes)."""
    if not guid:
        return None
    cleaned = normalize_hex_guid(str(guid))
    if cleaned and len(cleaned) == 32 and all(c in "0123456789abcdef" for c in cleaned):
        return cleaned
    return None


def _extract_pin_guid(ref) -> str | None:
    """Extract and normalize GUID from a Pin reference."""
    if isinstance(ref, dict):
        raw = ref.get("pin_guid") or ref.get("pin_id")
        return _normalize_guid(raw) if raw else None
    if isinstance(ref, str):
        return _normalize_guid(ref)
    raw = getattr(ref, "pin_guid", None) or getattr(ref, "pin_id", None)
    return _normalize_guid(raw) if raw else None


def _resolve_default_object_name(ref) -> str | None:
    """Object name of a linker-resolved pin DefaultObject, or None."""
    if ref is None:
        return None
    if isinstance(ref, dict):
        return ref.get("object_name") or ref.get("name") or None
    return _safe_str(getattr(ref, "object_name", None)) or None


def _build_asset_registry_data(result) -> dict | None:
    """Build asset_registry_data dictionary from ParseResult."""
    asset_registry_data = getattr(result, "asset_registry_data", None)
    if asset_registry_data is None:
        return None
    try:
        return asset_registry_data.to_dict()
    except (AttributeError, TypeError, ValueError):
        return None


def _build_debug_ir(
    hex_view_entries: list,
    hex_view_truncated_count: int = 0,
) -> DebugIR | None:
    """Convert ParseResult.hex_view_entries to DebugIR.

    Returns None if there are no hex_view entries and no truncation count.
    """
    if not hex_view_entries and hex_view_truncated_count == 0:
        return None
    entries = []
    for e in hex_view_entries:
        entry = HexViewEntryIR(
            key=e.key,
            type=e.type,
            value=e.value,
            start=e.start,
            stop=e.stop,
            size=e.size,
            field_path=getattr(e, "field_path", None),
            semantic_type=getattr(e, "semantic_type", None),
        )
        entries.append(entry)
    return DebugIR(
        hex_view=entries,
        hex_view_truncated_count=hex_view_truncated_count,
    )
