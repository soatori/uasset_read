"""Opaque struct scan script for Issue #515.

Traverses all version-controlled sample files, parses each in tolerant mode,
and extracts StructProperty candidates from exports whose parse_status is
"opaque" or "partial_metadata" (B1-pre intake fix: partial_metadata exports
were structurally missed before).
Outputs deduplicated results as JSON to stdout.
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

# Add src to path so uasset_read can be imported
SRC_DIR = Path(__file__).resolve().parents[2] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from uasset_read import parse_single


SAMPLES_DIR = Path(__file__).resolve().parents[2] / "tests" / "samples"


def _collect_struct_props(
    properties: list[dict], path_prefix: str = ""
) -> list[dict]:
    """Recursively collect StructProperty entries from a properties list.

    Returns a list of dicts with keys: struct_type, outer_path, raw_size.
    """
    results: list[dict] = []
    for prop in properties:
        pname = prop.get("name", "?")
        ptype = prop.get("type", "")
        current_path = f"{path_prefix}.{pname}" if path_prefix else pname

        if ptype == "StructProperty":
            value = prop.get("value", {})
            if isinstance(value, dict):
                struct_type = value.get("struct_type", "Unknown")
                raw_size = value.get("raw_size")
                results.append({
                    "struct_type": struct_type,
                    "outer_path": current_path,
                    "raw_size": raw_size,
                })

        # Descend into ArrayProperty items
        if ptype == "ArrayProperty":
            inner_val = prop.get("value", {})
            items = inner_val.get("items", []) if isinstance(inner_val, dict) else []
            for i, item in enumerate(items):
                if isinstance(item, dict) and item.get("type") == "StructProperty":
                    item_path = f"{current_path}[{i}]"
                    item_value = item.get("value", {})
                    if isinstance(item_value, dict):
                        struct_type = item_value.get("struct_type", "Unknown")
                        raw_size = item_value.get("raw_size")
                        results.append({
                            "struct_type": struct_type,
                            "outer_path": item_path,
                            "raw_size": raw_size,
                        })

    return results


def scan_opaque_structs() -> dict:
    """Scan all tracked sample files and collect opaque StructProperty candidates.

    Returns a dict with:
      - candidates: deduplicated list of struct entries
      - summary: statistics about the scan
    """
    sample_files = sorted(
        str(p) for p in SAMPLES_DIR.iterdir()
        if p.suffix in (".uasset", ".umap")
    )

    # Raw collection: struct_type -> list of occurrence records
    by_type: dict[str, list[dict]] = defaultdict(list)
    total_opaque_exports = 0
    total_struct_entries = 0
    files_with_opaque: set[str] = set()

    for file_path in sample_files:
        rel_path = os.path.relpath(file_path, str(SAMPLES_DIR.parent))
        try:
            result = parse_single(
                file_path,
                format="json",
                tolerant=True,
                log_enabled=False,
                output_level="debug",
            )
        except Exception as e:
            print(f"WARNING: Failed to parse {rel_path}: {e}", file=sys.stderr)
            continue

        data = json.loads(result)
        exports = data.get("exports", [])

        for exp in exports:
            ps = exp.get("parse_status", "success")
            if ps not in ("opaque", "partial_metadata"):
                continue

            total_opaque_exports += 1
            files_with_opaque.add(rel_path)
            export_status = ps
            properties = exp.get("properties", [])
            struct_entries = _collect_struct_props(properties)

            for entry in struct_entries:
                total_struct_entries += 1
                by_type[entry["struct_type"]].append({
                    "file": rel_path,
                    "object_name": exp.get("object_name", "?"),
                    "outer_path": entry["outer_path"],
                    "raw_size": entry["raw_size"],
                    "export_status": export_status,
                })

    # Build deduplicated candidate table
    candidates = []
    for struct_type in sorted(by_type.keys()):
        occurrences = by_type[struct_type]
        # Deduplicate by (file, outer_path)
        seen: set[tuple[str, str]] = set()
        unique_occurrences = []
        for occ in occurrences:
            key = (occ["file"], occ["outer_path"])
            if key not in seen:
                seen.add(key)
                unique_occurrences.append(occ)

        candidates.append({
            "struct_type": struct_type,
            "occurrence_count": len(occurrences),
            "unique_locations": len(unique_occurrences),
            "locations": unique_occurrences,
        })

    # Sort by frequency descending
    candidates.sort(key=lambda c: c["occurrence_count"], reverse=True)

    return {
        "candidates": candidates,
        "summary": {
            "total_samples_scanned": len(sample_files),
            "files_with_opaque_exports": len(files_with_opaque),
            "total_opaque_exports": total_opaque_exports,
            "total_struct_entries": total_struct_entries,
            "unique_struct_types": len(candidates),
            "top_struct_types": [
                {"struct_type": c["struct_type"], "count": c["occurrence_count"]}
                for c in candidates[:10]
            ],
        },
    }


def main() -> None:
    result = scan_opaque_structs()
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # Print summary to stderr for human readability
    summary = result["summary"]
    print(f"\n--- Summary ---", file=sys.stderr)
    print(f"Samples scanned:        {summary['total_samples_scanned']}", file=sys.stderr)
    print(f"Files with opaque exp:  {summary['files_with_opaque_exports']}", file=sys.stderr)
    print(f"Total opaque exports:   {summary['total_opaque_exports']}", file=sys.stderr)
    print(f"Total struct entries:   {summary['total_struct_entries']}", file=sys.stderr)
    print(f"Unique struct types:    {summary['unique_struct_types']}", file=sys.stderr)
    print(f"\nTop types by frequency:", file=sys.stderr)
    for item in summary["top_struct_types"]:
        print(f"  {item['struct_type']}: {item['count']}", file=sys.stderr)


if __name__ == "__main__":
    main()
