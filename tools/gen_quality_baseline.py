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
]


def main() -> None:
    samples: dict[str, object] = {}
    for name in SEED:
        path = SAMPLES / name
        doc = parse_package_document(str(path), depth="asset")
        counts: Counter[tuple[str, str | None]] = Counter()
        for d in doc.diagnostics:
            counts[(d.code, getattr(d, "reason", None))] += 1
        max_by: dict[str, dict[str, dict[str, int]]] = {}
        for (code, reason), n in sorted(
            counts.items(),
            key=lambda item: (item[0][0], item[0][1] or ""),
        ):
            key = reason or "_"
            max_by.setdefault(code, {})[key] = {"max": n}
        samples[name] = {
            "depth": "asset",
            "forbidden_codes": ["EXPORT_PROPERTY_PARSE_FAILED", "HANDLER_FAILURE"],
            "forbid_unlisted": True,
            "max_by_code_reason": max_by,
        }
        if name == "FirstPerson_DT_WeaponList.uasset":
            # Explicit zero-diag pin: this seed exists to stay clean.
            samples[name]["max_total_diagnostics"] = 0
        print(f"{name}: {sum(counts.values())} diagnostics")

    OUT.write_text(json.dumps({"version": 1, "samples": samples}, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
