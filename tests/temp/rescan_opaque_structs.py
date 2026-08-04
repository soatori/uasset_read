"""Re-scan: which StructProperty values are themselves opaque with the current parser.

Unlike the 2026-08-02 scan (which listed structs embedded in opaque exports), this
records only struct values whose own parse_status is 'opaque'. Diagnostic only;
does not modify parsing. Issue #515.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from uasset_read import parse_single

SAMPLES = Path(__file__).resolve().parents[2] / "tests" / "samples"


def _collect(props, path, hits):
    for prop in props if isinstance(props, list) else []:
        if not isinstance(prop, dict):
            continue
        name = prop.get("name", "?")
        ptype = prop.get("type", "")
        cur = f"{path}.{name}" if path else name
        if ptype == "StructProperty":
            val = prop.get("value", {})
            if isinstance(val, dict) and val.get("parse_status") == "opaque":
                hits.append({
                    "struct_type": val.get("struct_type"),
                    "path": cur,
                    "raw_size": val.get("raw_size"),
                })
        elif ptype == "ArrayProperty":
            inner = prop.get("value", {})
            items = inner.get("items", []) if isinstance(inner, dict) else []
            for i, item in enumerate(items):
                if isinstance(item, dict):
                    _collect([item], f"{cur}[{i}]", hits)


def main():
    by_type = defaultdict(list)
    for fpath in sorted(SAMPLES.iterdir()):
        if fpath.suffix not in (".uasset", ".umap"):
            continue
        try:
            data = json.loads(parse_single(
                str(fpath), format="json", tolerant=True,
                log_enabled=False, output_level="debug",
            ))
        except Exception as e:
            print(f"PARSE-ERROR {fpath.name}: {e}", file=sys.stderr)
            continue
        for exp in data.get("exports", []):
            hits = []
            _collect(exp.get("properties", []), "", hits)
            for h in hits:
                h["file"] = fpath.name
                h["export"] = exp.get("object_name")
                by_type[h["struct_type"]].append(h)

    for st, recs in sorted(by_type.items(), key=lambda kv: -len(kv[1])):
        print(f"\n[{st}] x{len(recs)}")
        for r in recs[:6]:
            print(f"  {r['file']} :: {r['export']} :: {r['path']} raw_size={r['raw_size']}")
    if not by_type:
        print("(none)")


if __name__ == "__main__":
    main()
