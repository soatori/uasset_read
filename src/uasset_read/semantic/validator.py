"""Semantic document validator — lightweight structural and cross-ref checks.

Called in production before rendering. Does NOT perform JSON Schema validation
(that is test-only via jsonschema).
"""
from __future__ import annotations

import re as _re

from uasset_read.semantic.models import SemanticIR

_VALID_MODES = {"standard", "debug"}
_VALID_PARSES = {"complete", "partial", "failed"}
_VALID_REPRESENTATIONS = {"full", "partial", "opaque"}
_VALID_SEVERITIES = {"error", "warning", "info"}

_FORMAT_VERSIONS = {
    "uasset_read.asset_semantic": "1.0",
    "uasset_read.blueprint_semantic": "1.0.0",
    "uasset_read.anim_blueprint_semantic": "1.0.0",
}

_DOMAIN_VALIDATORS: dict[str, object] = {}


def register_domain_validator(fmt: str, validator) -> None:
    """Register a format-specific semantic validator."""
    _DOMAIN_VALIDATORS[fmt] = validator


def validate_semantic_document(ir: SemanticIR) -> list[str]:
    """Validate a SemanticIR against the public contract.

    Returns:
        List of error messages (empty = valid).
    """
    errors: list[str] = []

    expected_version = _FORMAT_VERSIONS.get(ir.format)
    if expected_version is None:
        errors.append(f"Invalid format: '{ir.format}' is not a known semantic format")
    elif ir.format_version != expected_version:
        errors.append(
            f"Invalid format_version for '{ir.format}': expected '{expected_version}', got '{ir.format_version}'")

    if ir.mode not in _VALID_MODES:
        errors.append(f"Invalid mode: expected one of {_VALID_MODES}, got '{ir.mode}'")

    if not ir.asset.name:
        errors.append("asset.name must not be empty")

    if not ir.asset.package:
        errors.append("asset.package must not be empty")

    if ir.status.parse not in _VALID_PARSES:
        errors.append(f"Invalid status.parse: expected one of {_VALID_PARSES}, got '{ir.status.parse}'")

    if ir.status.representation not in _VALID_REPRESENTATIONS:
        errors.append(f"Invalid status.representation: expected one of {_VALID_REPRESENTATIONS}, got '{ir.status.representation}'")

    if ir.mode == "standard" and ir.evidence:
        errors.append("Standard mode must not contain evidence entries")

    if ir.status.representation == "full" and ir.coverage is not None:
        if ir.coverage.scopes_available < ir.coverage.scopes_expected:
            errors.append(
                f"representation='full' but coverage is {ir.coverage.scopes_available}/{ir.coverage.scopes_expected}"
            )

    for diag in ir.diagnostics:
        if diag.severity not in _VALID_SEVERITIES:
            errors.append(f"Invalid diagnostic severity: '{diag.severity}'")

    # Reference index uniqueness (within kind)
    seen_refs: set[tuple[str, int]] = set()
    for ref in ir.references:
        key = (ref.kind, ref.index)
        if key in seen_refs:
            errors.append(f"Reference index not unique: kind={ref.kind}, index={ref.index}")
        seen_refs.add(key)

    # Opaque representation must have at least one diagnostic
    if ir.status.representation == "opaque" and not ir.diagnostics and ir.format == "uasset_read.asset_semantic":
        errors.append("Opaque representation must have at least one diagnostic")

    domain_validator = _DOMAIN_VALIDATORS.get(ir.format)
    if domain_validator is not None:
        errors.extend(domain_validator(ir))

    return errors


# ---------------------------------------------------------------------------
# Blueprint-specific semantic rules (BP-§18)
# ---------------------------------------------------------------------------

_GRAPH_ID_FULL = _re.compile(r"^blueprint://graph/[A-Za-z][A-Za-z0-9_.-]*$")
_NODE_ID_FULL = _re.compile(
    r"^blueprint://graph/[A-Za-z][A-Za-z0-9_.-]*/node/[a-z][a-z0-9-]*/[A-Za-z][A-Za-z0-9_.-]*/[0-9]+$")
_ENDPOINT_FULL = _re.compile(r"^(input|output|exec)\.[A-Za-z][A-Za-z0-9_.-]*$")


def _validate_type_refs(value, known: set, errors: list, ctx: str) -> None:
    if isinstance(value, dict):
        if "$type" in value and value["$type"] not in known:
            errors.append(f"Type closure violation at {ctx}: unknown '{value['$type']}'")
        for v in value.values():
            _validate_type_refs(v, known, errors, ctx)
    elif isinstance(value, list):
        for item in value:
            _validate_type_refs(item, known, errors, ctx)


def validate_blueprint_document(ir) -> list[str]:
    """BP-§18 semantic rules for uasset_read.blueprint_semantic content."""
    errors: list[str] = []
    content = ir.content or {}
    graphs = content.get("graphs", []) or []
    types = content.get("types", {}) or {}

    graph_ids: set[str] = set()
    node_ids: set[str] = set()
    endpoints: set[tuple[str, str, str]] = set()  # (graph_id, node_id, endpoint)
    for graph in graphs:
        gid = graph.get("id", "")
        if not _GRAPH_ID_FULL.match(gid):
            errors.append(f"Invalid graph id format: '{gid}'")
        if gid in graph_ids:
            errors.append(f"Duplicate graph id: '{gid}'")
        graph_ids.add(gid)
        entry_nodes = [n for n in graph.get("nodes", []) or [] if n.get("kind") == "function_entry"]
        if len(entry_nodes) > 1:
            errors.append(f"Function graph '{gid}' has {len(entry_nodes)} entry nodes")
        for node in graph.get("nodes", []) or []:
            nid = node.get("id", "")
            if not _NODE_ID_FULL.match(nid):
                errors.append(f"Invalid node id format: '{nid}'")
            if nid in node_ids:
                errors.append(f"Duplicate node id: '{nid}'")
            node_ids.add(nid)
            for endpoint in list(node.get("data_pins", {}) or {}) + list(node.get("control_ports", {}) or {}):
                if not _ENDPOINT_FULL.match(endpoint):
                    errors.append(f"Invalid endpoint id format: '{endpoint}' on node '{nid}'")
                endpoints.add((gid, nid, endpoint))

    for section, key in (("control_flow", "port"), ("data_flow", "pin")):
        for graph in graphs:
            gid = graph.get("id", "")
            flow = graph.get(section, {}) or {}
            for entry in flow.get("entries", []) or []:
                if (gid, entry.get("node", ""), entry.get(key, "")) not in endpoints:
                    errors.append(f"Endpoint closure violation: {section} entry {entry} in '{gid}'")
            for edge in flow.get("edges", []) or []:
                for side in ("from", "to"):
                    ref = edge.get(side, {}) or {}
                    if (gid, ref.get("node", ""), ref.get(key, "")) not in endpoints:
                        errors.append(f"Endpoint closure violation: {section} edge {side} in '{gid}'")

    _validate_type_refs(content, set(types.keys()), errors, "content")

    component_ids = {c.get("id") for c in content.get("components", []) or []}
    parent_of: dict[str, str] = {}
    for comp in content.get("components", []) or []:
        parent = comp.get("parent")
        if parent is not None:
            if parent not in component_ids:
                errors.append(f"Component parent closure violation: '{comp.get('id')}' -> '{parent}'")
            parent_of[comp.get("id")] = parent
    for start in parent_of:
        seen: set[str] = set()
        cur = start
        while cur in parent_of:
            if cur in seen:
                errors.append(f"Component hierarchy cycle at '{start}'")
                break
            seen.add(cur)
            cur = parent_of[cur]

    if ir.status.representation == "opaque" and not content.get("diagnostics"):
        errors.append("Opaque blueprint representation must have at least one diagnostic")
    if ir.mode == "standard":
        def _has_evidence(value) -> bool:
            if isinstance(value, dict):
                return "evidence" in value or any(_has_evidence(v) for v in value.values())
            if isinstance(value, list):
                return any(_has_evidence(v) for v in value)
            return False
        if _has_evidence(content):
            errors.append("Standard blueprint content must not contain evidence")

    return errors

# Registration is handled by blueprint/__init__.py via register_domain_validator()


# ---------------------------------------------------------------------------
# Animation Blueprint-specific semantic rules (#555)
# ---------------------------------------------------------------------------

_ANIM_GRAPH_ID_FULL = _re.compile(r"^animblueprint://graph/[A-Za-z][A-Za-z0-9_.-]*$")
_ANIM_NODE_ID_FULL = _re.compile(
    r"^animblueprint://graph/[A-Za-z][A-Za-z0-9_.-]*/node/[a-z][a-z0-9-]*/[A-Za-z][A-Za-z0-9_.-]*/[0-9]+$")
_ANIM_ENDPOINT_FULL = _re.compile(r"^(input|output|exec|pose)\.[A-Za-z][A-Za-z0-9_.-]*$")
_ANIM_STATE_MACHINE_ID_FULL = _re.compile(r"^animblueprint://state_machine/[A-Za-z][A-Za-z0-9_.-]*$")
_ANIM_STATE_ID_FULL = _re.compile(
    r"^animblueprint://state_machine/[A-Za-z][A-Za-z0-9_.-]*/state/[A-Za-z][A-Za-z0-9_.-]*$")


def validate_anim_blueprint_document(ir) -> list[str]:
    """Animation Blueprint-specific semantic rules for uasset_read.anim_blueprint_semantic content."""
    errors: list[str] = []
    content = ir.content or {}
    graphs = content.get("graphs", []) or []
    types = content.get("types", {}) or {}

    graph_ids: set[str] = set()
    node_ids: set[str] = set()
    endpoints: set[tuple[str, str, str]] = set()

    for graph in graphs:
        gid = graph.get("id", "")
        if not _ANIM_GRAPH_ID_FULL.match(gid):
            errors.append(f"Invalid graph id format: '{gid}'")
        if gid in graph_ids:
            errors.append(f"Duplicate graph id: '{gid}'")
        graph_ids.add(gid)

        for node in graph.get("nodes", []) or []:
            nid = node.get("id", "")
            if not _ANIM_NODE_ID_FULL.match(nid):
                errors.append(f"Invalid node id format: '{nid}'")
            if nid in node_ids:
                errors.append(f"Duplicate node id: '{nid}'")
            node_ids.add(nid)
            for endpoint in (list(node.get("data_pins", {}) or {})
                             + list(node.get("control_ports", {}) or {})
                             + list(node.get("pose_pins", {}) or {})):
                if not _ANIM_ENDPOINT_FULL.match(endpoint):
                    errors.append(f"Invalid endpoint id format: '{endpoint}' on node '{nid}'")
                endpoints.add((gid, nid, endpoint))

    # Validate control/data flow endpoint closure
    for section, key in (("control_flow", "port"), ("data_flow", "pin")):
        for graph in graphs:
            gid = graph.get("id", "")
            flow = graph.get(section, {}) or {}
            for entry in flow.get("entries", []) or []:
                if (gid, entry.get("node", ""), entry.get(key, "")) not in endpoints:
                    errors.append(f"Endpoint closure violation: {section} entry {entry} in '{gid}'")
            for edge in flow.get("edges", []) or []:
                for side in ("from", "to"):
                    ref = edge.get(side, {}) or {}
                    if (gid, ref.get("node", ""), ref.get(key, "")) not in endpoints:
                        errors.append(f"Endpoint closure violation: {section} edge {side} in '{gid}'")

    # Validate pose flow endpoint closure
    for graph in graphs:
        gid = graph.get("id", "")
        pose_flow = graph.get("pose_flow", {}) or {}
        for entry in pose_flow.get("entries", []) or []:
            if (gid, entry.get("node", ""), entry.get("pose_pin", "")) not in endpoints:
                errors.append(f"Pose endpoint closure violation: pose_flow entry {entry} in '{gid}'")
        for edge in pose_flow.get("edges", []) or []:
            for side in ("from", "to"):
                ref = edge.get(side, {}) or {}
                if (gid, ref.get("node", ""), ref.get("pose_pin", "")) not in endpoints:
                    errors.append(f"Pose endpoint closure violation: pose_flow edge {side} in '{gid}'")

    # Validate state machine IDs
    state_machine_ids: set[str] = set()
    state_ids: set[str] = set()
    for sm in content.get("state_machines", []) or []:
        sm_id = sm.get("id", "")
        if not _ANIM_STATE_MACHINE_ID_FULL.match(sm_id):
            errors.append(f"Invalid state machine id format: '{sm_id}'")
        if sm_id in state_machine_ids:
            errors.append(f"Duplicate state machine id: '{sm_id}'")
        state_machine_ids.add(sm_id)

        for state in sm.get("states", []) or []:
            sid = state.get("id", "")
            if not _ANIM_STATE_ID_FULL.match(sid):
                errors.append(f"Invalid state id format: '{sid}'")
            if sid in state_ids:
                errors.append(f"Duplicate state id: '{sid}'")
            state_ids.add(sid)

    _validate_type_refs(content, set(types.keys()), errors, "content")

    # Component hierarchy validation (reused from blueprint)
    component_ids = {c.get("id") for c in content.get("components", []) or []}
    parent_of: dict[str, str] = {}
    for comp in content.get("components", []) or []:
        parent = comp.get("parent")
        if parent is not None:
            if parent not in component_ids:
                errors.append(f"Component parent closure violation: '{comp.get('id')}' -> '{parent}'")
            parent_of[comp.get("id")] = parent
    for start in parent_of:
        seen: set[str] = set()
        cur = start
        while cur in parent_of:
            if cur in seen:
                errors.append(f"Component hierarchy cycle at '{start}'")
                break
            seen.add(cur)
            cur = parent_of[cur]

    if ir.status.representation == "opaque" and not content.get("diagnostics"):
        errors.append("Opaque animation blueprint representation must have at least one diagnostic")
    if ir.mode == "standard":
        def _has_evidence(value) -> bool:
            if isinstance(value, dict):
                return "evidence" in value or any(_has_evidence(v) for v in value.values())
            if isinstance(value, list):
                return any(_has_evidence(v) for v in value)
            return False
        if _has_evidence(content):
            errors.append("Standard animation blueprint content must not contain evidence")

    return errors

# Registration is handled by anim_blueprint/__init__.py via register_domain_validator()
