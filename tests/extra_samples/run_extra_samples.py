"""Manually trigger the extra sample list (tests/extra_samples/manifest.json).

Not collected by pytest — run on demand:

    python tests/extra_samples/run_extra_samples.py [--limit N] [--type CLASS] [--depth decode]

Each listed package is parsed from E:\\Develop\\lib\\Samples; the run fails
(non-zero exit) if any sample fails to parse.
Results are written to temp/extra_samples_results.csv plus a summary in
temp/extra_samples_report.md. The results include per-sample diagnostics
(warnings/recovered gaps), not just pass/fail.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from contextlib import nullcontext
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "manifest.json"
REPO = HERE.resolve().parents[1]
TEMP = REPO / "temp"
RESULTS_CSV = TEMP / "extra_samples_results.csv"
REPORT_MD = TEMP / "extra_samples_report.md"


def _parse_sample(task: tuple[str, dict, str, bool]) -> tuple[dict, float]:
    root, sample, depth, clear_parse_cache = task
    sample_root = Path(root).resolve()
    path = sample_root / sample["relpath"]
    if not path.resolve().is_relative_to(sample_root):
        raise ValueError(f"relpath escapes root: {sample['relpath']}")

    from uasset_read import parse_package_document
    from uasset_read.package import _parse_cached

    if clear_parse_cache:
        _parse_cached.cache_clear()

    started = time.perf_counter()
    diag_count, diag_codes = "", ""
    try:
        out_doc = parse_package_document(path, depth=depth, tolerant=False)
        mark, error = "ok", ""
        diagnostics = list(out_doc.diagnostics or []) + list(out_doc.reader_diagnostics or [])
        if diagnostics:
            diag_count = len(diagnostics)
            diag_codes = ";".join(sorted({str(getattr(item, "code", "?")) for item in diagnostics}))
    except Exception as exc:
        mark = "FAIL"
        error = f"{type(exc).__name__}: {exc}"
    elapsed = time.perf_counter() - started
    return (
        {
            "status": mark,
            "primary_class": sample["primary_class"],
            "relpath": sample["relpath"],
            "size_bytes": sample["size_bytes"],
            "seconds": f"{elapsed:.3f}",
            "error": error,
            "diag_count": diag_count,
            "diag_codes": diag_codes,
        },
        elapsed,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0, help="only first N samples")
    ap.add_argument("--type", default=None, help="only this primary_class")
    ap.add_argument("--depth", default="decode", choices=["package", "object", "asset", "decode"])
    ap.add_argument("--workers", type=int, default=1, help="separate worker processes (default: 1)")
    args = ap.parse_args()
    if args.workers < 1:
        ap.error("--workers must be at least 1")

    doc = json.loads(MANIFEST.read_text(encoding="utf-8"))
    root = Path(doc["root"])
    samples = doc["samples"]
    if args.type:
        samples = [s for s in samples if s["primary_class"] == args.type]
    if args.limit:
        samples = samples[: args.limit]

    failures: list[tuple[str, str]] = []
    rows: list[dict] = []
    t0 = time.time()
    tasks = ((str(root.resolve()), sample, args.depth, False) for sample in samples)
    executor_context = nullcontext(None) if args.workers == 1 else ProcessPoolExecutor(max_workers=args.workers)
    with executor_context as executor:
        results = map(_parse_sample, tasks) if executor is None else executor.map(_parse_sample, tasks)
        for i, (row, _elapsed) in enumerate(results, 1):
            rows.append(row)
            if row["status"] != "ok":
                failures.append((row["relpath"], row["error"]))
            if i % 200 == 0 or row["status"] == "FAIL":
                print(f"[{i}/{len(samples)}] {row['status']} {row['primary_class']} {row['relpath']}", flush=True)
    dt = time.time() - t0

    TEMP.mkdir(exist_ok=True)
    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "status",
                "primary_class",
                "relpath",
                "size_bytes",
                "seconds",
                "error",
                "diag_count",
                "diag_codes",
            ],
        )
        w.writeheader()
        w.writerows(rows)
    status = Counter(r["status"] for r in rows)
    fail_by_type = Counter(r["primary_class"] for r in rows if r["status"] != "ok")
    with_diag = [r for r in rows if r["diag_count"] not in ("", "0")]
    code_files: Counter = Counter()
    code_occ: Counter = Counter()
    for r in with_diag:
        seen = set()
        for c in r["diag_codes"].split(";"):
            if c:
                code_occ[c] += 1  # occurrence count not split per code; counts files below
                seen.add(c)
        for c in seen:
            code_files[c] += 1
    lines = [
        "# Extra samples full-run report",
        "",
        f"- manifest: {MANIFEST} ({doc['types']} types)",
        f"- depth: {args.depth}, tolerant=False",
        f"- samples: {len(rows)}, {dict(status)}, time: {dt:.1f}s",
        f"- results: {RESULTS_CSV}",
        f"- samples with diagnostics (parsed ok but not fully clean): {len(with_diag)} / {len(rows)}",
        "",
    ]
    if code_files:
        lines += ["## diagnostics by code (files affected)", ""]
        lines += [f"- {k}: {v}" for k, v in code_files.most_common()]
        lines += [""]
    if failures:
        lines += ["## failures by type", ""]
        lines += [f"- {k}: {v}" for k, v in fail_by_type.most_common()]
        lines += ["", "## failures", ""]
        lines += [f"- {rel}: {err}" for rel, err in failures]
    else:
        lines.append("All samples parsed cleanly.")
    report = REPO / "temp" / "extra_samples_report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\ntypes={doc['types']} samples={len(samples)} failures={len(failures)} time={dt:.1f}s")
    print(f"-> {RESULTS_CSV}\n-> {report}")
    for rel, err in failures[:50]:
        print(f"FAIL {rel}: {err}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
