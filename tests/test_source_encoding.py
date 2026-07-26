"""Regression tests for Python source-file encoding invariants."""

import ast
import codecs
from pathlib import Path


def test_python_sources_are_plain_utf8_and_ast_parseable() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src" / "uasset_read"

    for source_path in sorted(source_root.rglob("*.py")):
        source_bytes = source_path.read_bytes()
        source_text = source_bytes.decode("utf-8")

        assert not source_bytes.startswith(codecs.BOM_UTF8), source_path
        ast.parse(source_text, filename=str(source_path))
