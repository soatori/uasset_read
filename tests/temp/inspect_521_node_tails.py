"""Diagnostic for #521 B0a: inspect native tails of Niagara exports.

Read-only: parses the fixture, then hex-inspects the native-tail byte ranges
already recorded by the handlers. Prints a report to stdout. Does NOT modify
parse behavior or source code.

Usage: python tests/temp/inspect_521_node_tails.py > temp/b0a_report.txt
"""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from uasset_read import parse_single

SAMPLE = ROOT / "tests" / "samples" / "NM_BPSystemEvent.uasset"
EXPECTED_SHA256 = "B182D85907E858086E8B4BA8CC3D527D1DFBA21CA450ADDC2481A5053CE24FBF"


def _hexdump(data: bytes, limit: int = 64) -> str:
    rows = []
    for off in range(0, min(len(data), limit), 16):
        chunk = data[off:off + 16]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        rows.append(f"  {off:08x}  {hex_part:<47}  {ascii_part}")
    return "\n".join(rows)


def main() -> None:
    sha = hashlib.sha256(SAMPLE.read_bytes()).hexdigest().upper()
    assert sha == EXPECTED_SHA256, f"fixture mismatch: {sha}"
    raw = SAMPLE.read_bytes()

    payload = json.loads(parse_single(
        str(SAMPLE), format="json", tolerant=True, log_enabled=False,
    ))

    print("=== B0a native-tail inventory ===")
    for exp in payload["exports"]:
        cls = exp.get("object_class", "")
        if not cls.startswith("Niagara"):
            continue
        atd = exp.get("asset_type_data", {})
        tail = atd.get("native_tail") or {}
        size = tail.get("size", 0)
        print(f"\n[{cls}] {exp.get('object_name')} "
              f"tail offset={tail.get('offset')} size={size}")
        if size <= 0:
            continue
        data = raw[tail["offset"]:tail["offset"] + size]
        print(_hexdump(data, limit=64))
        # int32 scan: candidate name indices / export refs / counts
        n = size // 4
        ints = struct.unpack(f"<{n}i", data[:n * 4])
        small = [v for v in ints if 0 <= v < 200000]
        print(f"  int32 values: {len(ints)} total, {len(small)} in [0, 200000)")
        if small:
            print(f"  small-int range: {min(small)}..{max(small)}")
        # repeated 16-byte runs: candidate GUID arrays (pin persistent ids)
        seen: dict[bytes, int] = {}
        for off in range(0, size - 16, 4):
            block = data[off:off + 16]
            if any(block):
                seen[block] = seen.get(block, 0) + 1
        repeats = {k: v for k, v in seen.items() if v > 1}
        if repeats:
            print(f"  repeated 16-byte blocks: {len(repeats)} distinct")

    print("\n=== Outputs/OutputVars UnknownStruct elements ===")
    for exp in payload["exports"]:
        atd = exp.get("asset_type_data", {})
        tagged = atd.get("tagged_properties", {})
        for prop_name in ("Outputs", "OutputVars"):
            value = tagged.get(prop_name)
            if not isinstance(value, dict):
                continue
            items = value.get("items", [])
            for i, item in enumerate(items):
                iv = item.get("value", item) if isinstance(item, dict) else item
                if isinstance(iv, dict) and iv.get("struct_type") in (
                    None, "UnknownStruct", "Unknown",
                ):
                    print(f"\n[{exp.get('object_name')}] {prop_name}[{i}]:")
                    print(json.dumps(iv, indent=2, default=str)[:2000])


if __name__ == "__main__":
    main()
