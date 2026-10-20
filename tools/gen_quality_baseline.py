"""Aggregate helper for the trailing-by-reason quality gate.

tests/samples/quality_baseline.json is the committed ceiling fixture; raise a
number in it so growth shows up as a reviewable diff, same as size-baseline.json.
"""

from __future__ import annotations

from typing import Any


def aggregate_trailing_report(docs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Aggregate EXPORT_TRAILING_BYTES_UNCONSUMED across (name, doc) pairs.

    Deterministic ceilings keyed by reason and (reason, class): counts and
    unresolved bytes. Non-trailing diagnostics and missing sizes are ignored
    (size gating is enforced by test_trailing_diagnostics_carry_structured_size).
    """
    totals = {"count": 0, "bytes": 0}
    by_reason = {}
    by_reason_class = {}
    for _name, doc in docs:
        class_by_id = {o.id: (o.class_name or "?") for o in doc.objects}
        for d in doc.diagnostics:
            if d.code != "EXPORT_TRAILING_BYTES_UNCONSUMED":
                continue
            reason = d.reason or "unexpected"
            cls = class_by_id.get(d.object_id, "?")
            size = d.size or 0
            totals["count"] += 1
            totals["bytes"] += size
            r = by_reason.setdefault(reason, {"max_count": 0, "max_bytes": 0})
            r["max_count"] += 1
            r["max_bytes"] += size
            key = f"{reason}/{cls}"
            rc = by_reason_class.setdefault(key, {"max_count": 0, "max_bytes": 0})
            rc["max_count"] += 1
            rc["max_bytes"] += size
    return {
        "scope": "manifest",
        "sample_count": len(docs),
        "max_total_warnings": totals["count"],
        "max_total_bytes": totals["bytes"],
        "by_reason": dict(sorted(by_reason.items())),
        "by_reason_class": dict(sorted(by_reason_class.items())),
    }
