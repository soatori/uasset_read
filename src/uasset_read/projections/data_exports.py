"""Structured data projections: tables, curves, structs/enums, material instances.

Only projected semantic dictionaries already on PackageDocument.objects are
consumed. Missing required input emits explicit unavailable records; no
projector invents field lists from positional package bytes.
"""

from __future__ import annotations

import csv
from io import StringIO
from typing import Any

from uasset_read.models.document import PackageDocument
from uasset_read.models.object_model import ObjectRecord
from uasset_read.projections.records import (
    ProjectionRecord,
    ProjectionStatus,
    dependency_ids,
    matches_family,
    semantic_dict,
    unavailable_records,
)

_JSON = "application/json"
_CSV = "text/csv"

_DATA_TABLE_PAIRS = (
    ("data_table", _JSON),
    ("data_table_csv", _CSV),
    ("data_table_json", _JSON),
)
_CURVE_TABLE_PAIRS = (
    ("curve_table", _JSON),
    ("curve_table_csv", _CSV),
    ("curve_table_json", _JSON),
)
_STRUCT_PAIRS = (("defaults_json", _JSON),)
_ENUM_PAIRS = (("defaults_json", _JSON),)
_MATERIAL_INSTANCE_PAIRS = (("material_instance", _JSON), ("material_parameters", _JSON))


def _field_columns(row: Any) -> list[dict[str, str]]:
    if not isinstance(row, dict):
        return []
    fields = row.get("fields")
    if not isinstance(fields, dict):
        return []
    columns: list[dict[str, str]] = []
    for name, value in fields.items():
        type_name = ""
        if isinstance(value, dict):
            type_name = str(value.get("type") or "")
        columns.append({"name": str(name), "type": type_name})
    return columns


def _projected_field_value(raw: Any) -> Any:
    """Copy one evidenced field entry without inventing a cell value."""
    if isinstance(raw, dict):
        if "value" in raw:
            return raw["value"]
        # Handler-decoded field maps carry type/size descriptors — copy them.
        return {key: raw[key] for key in ("type", "size", "struct_type", "name") if key in raw} or raw
    return raw


def _row_has_evidenced_fields(row: Any) -> bool:
    return isinstance(row, dict) and bool(row.get("fields"))


def _data_table_payload(semantic: dict[str, Any]) -> tuple[dict[str, Any], ProjectionStatus, float | None] | None:
    """Return (payload, status, completeness) or None when unavailable.

    Matrix rule: row struct + values decoded, else unavailable. Non-empty
    field maps are the handler's decoded evidence and are copied verbatim;
    empty/missing field maps never claim a represented projection.
    """
    if semantic.get("kind") != "data_table":
        return None
    rows = [r for r in semantic.get("rows") or [] if isinstance(r, dict)]
    evidenced = [r for r in rows if _row_has_evidenced_fields(r)]
    if not evidenced:
        return None
    columns: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in evidenced:
        for column in _field_columns(row):
            if column["name"] not in seen:
                seen.add(column["name"])
                columns.append(column)
    projected_rows = []
    any_cell_value = False
    for row in evidenced:
        fields = row.get("fields")
        if not isinstance(fields, dict):
            fields = {}
        values = {str(k): _projected_field_value(v) for k, v in fields.items()}
        if any(isinstance(v, dict) and "value" in v for v in fields.values()):
            any_cell_value = True
        projected_rows.append({"name": str(row.get("name") or ""), "values": values})
    payload = {
        "kind": "data_table",
        "row_struct": semantic.get("row_struct") or semantic.get("row_struct_ref") or "",
        "columns": columns,
        "rows": projected_rows,
        "row_count": semantic.get("row_count", len(projected_rows)),
        "row_names": list(semantic.get("row_names") or []),
        "values_decoded": any_cell_value,
    }
    # Evidenced field maps count as decoded schema; cell payloads upgrade status.
    status: ProjectionStatus = "translated" if any_cell_value else "represented"
    completeness = 1.0 if any_cell_value else 0.5
    return payload, status, completeness


def _csv_from_table(payload: dict[str, Any]) -> str:
    columns = payload.get("columns") or []
    buf = StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["name"] + [str(c.get("name") or "") for c in columns])
    for row in payload.get("rows") or []:
        values = row.get("values") if isinstance(row, dict) else {}
        values = values if isinstance(values, dict) else {}
        cells = [str(row.get("name") or "")]
        for column in columns:
            raw = values.get(column.get("name"))
            cells.append("" if raw is None else str(raw))
        writer.writerow(cells)
    return buf.getvalue()


def _explicit_curve_keys(row: Any) -> list[dict[str, Any]] | None:
    """Return decoded curve keys when keys/interp are explicit; else None."""
    if not isinstance(row, dict):
        return None
    fields = row.get("fields")
    if not isinstance(fields, dict):
        fields = {}
    keys_raw = fields.get("Keys")
    if isinstance(keys_raw, dict):
        inner = keys_raw.get("value", keys_raw.get("keys"))
        if isinstance(inner, list) and inner:
            return [k for k in inner if isinstance(k, dict)]
        return None
    if isinstance(keys_raw, list) and keys_raw:
        return [k for k in keys_raw if isinstance(k, dict)]
    if isinstance(row.get("keys"), list) and row["keys"]:
        return [k for k in row["keys"] if isinstance(k, dict)]
    return None


def _curve_table_payload(semantic: dict[str, Any]) -> tuple[dict[str, Any], ProjectionStatus, float | None] | None:
    """Return (payload, status, completeness) or None when unavailable.

    Matrix rule: keys/interp explicit; compressed-only unavailable unless decoded.
    """
    if semantic.get("kind") != "curve_table":
        return None
    rows = [r for r in semantic.get("rows") or [] if isinstance(r, dict)]
    curves = []
    any_keys = False
    for row in rows:
        keys = _explicit_curve_keys(row)
        if keys:
            any_keys = True
        fields = row.get("fields")
        if not isinstance(fields, dict):
            fields = {}
        curves.append(
            {
                "name": str(row.get("name") or ""),
                "field_types": {str(k): (v.get("type") if isinstance(v, dict) else None) for k, v in fields.items()},
                "keys": keys or [],
            }
        )
    if not curves:
        return None
    if not any_keys:
        # Row names/type skeletons without explicit keys stay unavailable.
        return None
    payload = {
        "kind": "curve_table",
        "mode": semantic.get("curve_table_mode") or "",
        "curves": curves,
        "keys_decoded": True,
    }
    return payload, "translated", 1.0


def _csv_from_curves(payload: dict[str, Any]) -> str:
    lines = ["name,key_count"]
    for curve in payload.get("curves") or []:
        lines.append(f"{curve.get('name')},{len(curve.get('keys') or [])}")
    return "\n".join(lines) + "\n"


class DataTableProjector:
    asset_kinds = ("data_table",)
    _CLASS_NAMES = ("DataTable",)

    def can_project(self, obj: ObjectRecord) -> bool:
        return matches_family(obj, self.asset_kinds, self._CLASS_NAMES)

    def project(self, document: PackageDocument, obj: ObjectRecord) -> list[ProjectionRecord]:
        semantic = semantic_dict(obj)
        deps = dependency_ids(document, obj.id)
        projected = _data_table_payload(semantic)
        if projected is None:
            return unavailable_records(
                obj.id,
                _DATA_TABLE_PAIRS,
                code="data_table_rows_unavailable",
                message=(
                    "DataTable row struct/values were not decoded into semantic "
                    "(matrix requires evidenced field values or unavailable)"
                ),
                stage="projection.data_exports",
                dependencies=deps,
            )
        payload, status, completeness = projected
        return [
            ProjectionRecord(
                kind="data_table",
                source_object_id=obj.id,
                media_type=_JSON,
                content=payload,
                embedded=True,
                status=status,
                completeness=completeness,
                dependencies=deps,
                diagnostics=[],
            ),
            ProjectionRecord(
                kind="data_table_csv",
                source_object_id=obj.id,
                media_type=_CSV,
                content=_csv_from_table(payload),
                embedded=True,
                status=status,
                completeness=completeness,
                dependencies=deps,
                diagnostics=[],
            ),
            ProjectionRecord(
                kind="data_table_json",
                source_object_id=obj.id,
                media_type=_JSON,
                content=payload,
                embedded=True,
                status=status,
                completeness=completeness,
                dependencies=deps,
                diagnostics=[],
            ),
        ]


class CurveTableProjector:
    asset_kinds = ("curve_table",)
    _CLASS_NAMES = ("CurveTable",)

    def can_project(self, obj: ObjectRecord) -> bool:
        return matches_family(obj, self.asset_kinds, self._CLASS_NAMES)

    def project(self, document: PackageDocument, obj: ObjectRecord) -> list[ProjectionRecord]:
        semantic = semantic_dict(obj)
        deps = dependency_ids(document, obj.id)
        projected = _curve_table_payload(semantic)
        if projected is None:
            return unavailable_records(
                obj.id,
                _CURVE_TABLE_PAIRS,
                code="curve_table_keys_unavailable",
                message=(
                    "CurveTable keys/interpolation were not decoded into semantic "
                    "(matrix requires explicit keys or unavailable)"
                ),
                stage="projection.data_exports",
                dependencies=deps,
            )
        payload, status, completeness = projected
        return [
            ProjectionRecord(
                kind="curve_table",
                source_object_id=obj.id,
                media_type=_JSON,
                content=payload,
                embedded=True,
                status=status,
                completeness=completeness,
                dependencies=deps,
                diagnostics=[],
            ),
            ProjectionRecord(
                kind="curve_table_csv",
                source_object_id=obj.id,
                media_type=_CSV,
                content=_csv_from_curves(payload),
                embedded=True,
                status=status,
                completeness=completeness,
                dependencies=deps,
                diagnostics=[],
            ),
            ProjectionRecord(
                kind="curve_table_json",
                source_object_id=obj.id,
                media_type=_JSON,
                content=payload,
                embedded=True,
                status=status,
                completeness=completeness,
                dependencies=deps,
                diagnostics=[],
            ),
        ]


class UserDefinedStructProjector:
    asset_kinds = ("user_defined_struct",)
    _CLASS_NAMES = ("UserDefinedStruct",)

    def can_project(self, obj: ObjectRecord) -> bool:
        return matches_family(obj, self.asset_kinds, self._CLASS_NAMES)

    def project(self, document: PackageDocument, obj: ObjectRecord) -> list[ProjectionRecord]:
        semantic = semantic_dict(obj)
        deps = dependency_ids(document, obj.id)
        fields = [f for f in semantic.get("fields") or [] if isinstance(f, dict)]
        if semantic.get("kind") != "user_defined_struct" or not fields:
            return unavailable_records(
                obj.id,
                _STRUCT_PAIRS,
                code="user_defined_struct_fields_unavailable",
                message="UserDefinedStruct reflected fields were not decoded into semantic",
                stage="projection.data_exports",
                dependencies=deps,
            )
        name = str(semantic.get("struct_name") or obj.name or "UserDefinedStruct")
        defaults = {
            "kind": "user_defined_struct",
            "struct_name": name,
            "fields": fields,
        }
        return [
            ProjectionRecord(
                kind="defaults_json",
                source_object_id=obj.id,
                media_type=_JSON,
                content=defaults,
                embedded=True,
                status="translated",
                completeness=1.0,
                dependencies=deps,
                diagnostics=[],
            ),
        ]


class UserDefinedEnumProjector:
    asset_kinds = ("user_defined_enum",)
    _CLASS_NAMES = ("UserDefinedEnum",)

    def can_project(self, obj: ObjectRecord) -> bool:
        return matches_family(obj, self.asset_kinds, self._CLASS_NAMES)

    def project(self, document: PackageDocument, obj: ObjectRecord) -> list[ProjectionRecord]:
        semantic = semantic_dict(obj)
        deps = dependency_ids(document, obj.id)
        entries = [e for e in semantic.get("entries") or [] if isinstance(e, dict)]
        if semantic.get("kind") != "user_defined_enum" or not entries:
            return unavailable_records(
                obj.id,
                _ENUM_PAIRS,
                code="user_defined_enum_entries_unavailable",
                message="UserDefinedEnum enumerators were not decoded into semantic",
                stage="projection.data_exports",
                dependencies=deps,
            )
        name = str(semantic.get("enum_name") or obj.name or "UserDefinedEnum")
        defaults = {
            "kind": "user_defined_enum",
            "enum_name": name,
            "enumerators": entries,
        }
        return [
            ProjectionRecord(
                kind="defaults_json",
                source_object_id=obj.id,
                media_type=_JSON,
                content=defaults,
                embedded=True,
                status="translated",
                completeness=1.0,
                dependencies=deps,
                diagnostics=[],
            ),
        ]


class MaterialInstanceProjector:
    asset_kinds = ("material_instance",)
    _CLASS_NAMES = ("MaterialInstance", "MaterialInstanceConstant")

    def can_project(self, obj: ObjectRecord) -> bool:
        return matches_family(obj, self.asset_kinds, self._CLASS_NAMES)

    def project(self, document: PackageDocument, obj: ObjectRecord) -> list[ProjectionRecord]:
        semantic = semantic_dict(obj)
        deps = dependency_ids(document, obj.id)
        if semantic.get("kind") != "material_instance":
            return unavailable_records(
                obj.id,
                _MATERIAL_INSTANCE_PAIRS,
                code="material_instance_semantic_unavailable",
                message="MaterialInstance parent/parameter overrides were not projected into semantic",
                stage="projection.data_exports",
                dependencies=deps,
            )
        parent_resolved = bool(semantic.get("has_parent"))
        instance = {
            "kind": "material_instance",
            "name": semantic.get("name") or obj.name,
            "parent_resolved": parent_resolved,
            "parent": None if not parent_resolved else semantic.get("parent"),
        }
        parameters = {
            "kind": "material_parameters",
            "scalar_parameters": semantic.get("scalar_param_count"),
            "vector_parameters": semantic.get("vector_param_count"),
            "resolved": parent_resolved,
        }
        status = "represented" if parent_resolved else "untranslated"
        completeness = 0.5 if parent_resolved else None
        return [
            ProjectionRecord(
                kind="material_instance",
                source_object_id=obj.id,
                media_type=_JSON,
                content=instance,
                embedded=True,
                status=status,
                completeness=completeness,
                dependencies=deps,
                diagnostics=[],
            ),
            ProjectionRecord(
                kind="material_parameters",
                source_object_id=obj.id,
                media_type=_JSON,
                content=parameters,
                embedded=True,
                status=status,
                completeness=completeness,
                dependencies=deps,
                diagnostics=[],
            ),
        ]
