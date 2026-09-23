"""Generate tests/samples/quality_baseline.json from tracked fixtures.

Usage (from repo root):
  PYTHONPATH=src python tools/gen_quality_baseline.py
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from uasset_read.package import parse_package_document

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "tests" / "samples"
OUT = SAMPLES / "quality_baseline.json"

SEED = [
    "FirstPerson_DT_WeaponList.uasset",
    "FirstPerson_T_GridChecker_A.uasset",
    "FirstPerson_BS_Idle_Walk_Run.uasset",
    "ALS_Mannequin_Skeleton.uasset",
    "BP_CombatCharacter.uasset",
    # R5 gate samples (plan Task 12 acceptance table).
    "StackOBot_BP_Drone.uasset",
    "MyProject_UE58_TestBlueprint.uasset",
    "StackOBot_M_BotBase.uasset",
    "BP_UnversionedTest.uasset",
    "DA_UnversionedTest.uasset",
]

OPT_IN_SEED = [
    "ALS_AnimBP.uasset",
]


def build_sample_entry(doc, name: str, *, opt_in: bool = False) -> dict:
    counts: Counter[tuple[str, str | None]] = Counter()
    for d in doc.diagnostics:
        counts[(d.code, d.reason)] += 1
    max_by: dict[str, dict[str, dict[str, int]]] = {}
    for (code, reason), n in sorted(counts.items(), key=lambda item: (item[0][0], item[0][1] or "")):
        key = reason or "_"
        max_by.setdefault(code, {})[key] = {"max": n}
    entry = {
        "depth": "asset",
        "forbidden_codes": ["EXPORT_PROPERTY_PARSE_FAILED", "HANDLER_FAILURE"],
        "forbid_unlisted": True,
        "max_by_code_reason": max_by,
    }
    if opt_in:
        entry["opt_in"] = True
    if name == "FirstPerson_DT_WeaponList.uasset":
        entry["max_total_diagnostics"] = 0
    return entry


def aggregate_trailing_report(docs):
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


def main() -> None:
    samples: dict[str, object] = {}
    for name in SEED:
        path = SAMPLES / name
        doc = parse_package_document(str(path), depth="asset")
        samples[name] = build_sample_entry(doc, name, opt_in=False)
        print(f"{name}: {sum(1 for _ in samples[name]['max_by_code_reason'].values())} codes")
    for name in OPT_IN_SEED:
        path = SAMPLES / name
        doc = parse_package_document(str(path), depth="asset")
        samples[name] = build_sample_entry(doc, name, opt_in=True)
        print(f"{name} (opt-in): diagnostics={len(doc.diagnostics)}")
    manifest = json.loads((SAMPLES / "manifest.json").read_text(encoding="utf-8"))
    manifest_docs = []
    for entry in manifest["samples"]:
        path = SAMPLES / entry["name"]
        manifest_docs.append((entry["name"], parse_package_document(str(path), depth="asset")))
    aggregate = aggregate_trailing_report(manifest_docs)
    OUT.write_text(
        json.dumps({"version": 1, "samples": samples, "aggregate": aggregate}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
