"""Size ratchet: source tree, test tree and the built wheel cannot grow silently.

Implements the "size baseline recorded and gated" item of the canonical
refactor's Migration Completion Gate
(`docs/designs/2026-08-26-package-first-uasset-parser-refactor.md`).

Ceilings are the *measured* values in ``tests/size-baseline.json``. Exceeding
one is a deliberate act: raise the number in that file so the growth shows up
as a reviewable diff. Lowering a ceiling is expected — tighten the numbers
after a deletion wave.

``min_files`` guards the check's own premise: a .gitignore regression that
silently untracks a subtree would otherwise satisfy a max-only ceiling.

The built-wheel ceiling is asserted by the CI ``package-smoke`` job (which is
where a wheel exists), not here. Line ceilings need no slack because they are
counted, not packaged.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = json.loads((Path(__file__).parent / "size-baseline.json").read_text(encoding="utf-8"))


def _tracked_files() -> list[str]:
    # -z, not plain ls-files: the default core.quotePath escapes non-ASCII paths
    # (docs/reference has a CJK filename), which would silently drop ~4.7k lines
    # from the count depending on the caller's git config.
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    return [entry for entry in out.stdout.decode("utf-8").split("\0") if entry]


def _line_count(relpath: str) -> int:
    path = ROOT / relpath
    try:
        with path.open("rb") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return 0


def _area_lines(prefix: str, suffix: str) -> tuple[int, int]:
    """Return (file_count, total_lines) for tracked files under prefix with suffix."""
    files = [f for f in _tracked_files() if f.startswith(prefix) and f.endswith(suffix)]
    return len(files), sum(_line_count(f) for f in files)


def test_source_tree_within_baseline():
    _assert_area("src_python", "src/", ".py")


def test_test_tree_within_baseline():
    _assert_area("tests_python", "tests/", ".py")


def test_docs_tree_within_baseline():
    _assert_area("docs_markdown", "docs/", ".md")


def _assert_area(key: str, prefix: str, suffix: str) -> None:
    limit = BASELINE[key]
    count, lines = _area_lines(prefix, suffix)
    assert count >= limit["min_files"], f"{key}: {count} tracked files, baseline expects at least {limit['min_files']}"
    assert lines <= limit["max_lines"], (
        f"{key}: {lines} tracked lines exceeds baseline {limit['max_lines']} "
        f"(files={count}). Shrink the tree, or raise max_lines in "
        f"tests/size-baseline.json so the growth is reviewed."
    )
