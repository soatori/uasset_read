"""Structural contracts for the verified dead-code cleanup."""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path
import sys

import pytest
import uasset_read.cli as cli_module
from uasset_read.cli import create_parser


SOURCE_ROOT = Path(__file__).parents[1] / "src" / "uasset_read"


def _iter_scopes(
    body: list[ast.stmt],
    scope: str = "module",
) -> Iterable[tuple[str, list[ast.stmt]]]:
    yield scope, body
    for node in body:
        if isinstance(node, ast.ClassDef):
            yield from _iter_scopes(node.body, f"{scope}.{node.name}")


def _assigned_names(target: ast.expr) -> Iterable[str]:
    if isinstance(target, ast.Name):
        yield target.id
    elif isinstance(target, (ast.List, ast.Tuple)):
        for element in target.elts:
            yield from _assigned_names(element)


def test_source_has_no_shadowed_same_scope_definitions() -> None:
    duplicates: list[str] = []

    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        for scope, body in _iter_scopes(tree.body):
            definitions: dict[str, list[int]] = {}
            for node in body:
                if isinstance(node, (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef)):
                    definitions.setdefault(node.name, []).append(node.lineno)
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        for name in _assigned_names(target):
                            definitions.setdefault(name, []).append(node.lineno)
                elif isinstance(node, ast.AnnAssign):
                    for name in _assigned_names(node.target):
                        definitions.setdefault(name, []).append(node.lineno)
            for name, lines in definitions.items():
                if len(lines) > 1:
                    relative_path = path.relative_to(SOURCE_ROOT)
                    duplicates.append(f"{relative_path}:{scope}:{name}:{lines}")

    assert duplicates == []


def test_shadowed_struct_fast_path_helpers_are_removed() -> None:
    path = SOURCE_ROOT / "parsers" / "property_types.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    dead_names = {
        "_FAST_PATH_STRUCT_HANDLERS",
        "_fp_box",
        "_fp_box2d",
        "_fp_box_sphere_bounds",
        "_fp_color",
        "_fp_i32_pair",
        "_fp_i32_triple",
        "_fp_matrix",
        "_fp_oriented_box",
        "_fp_ptr_uber",
        "_fp_sphere",
        "_fp_top_level_path",
        "_fp_transform",
        "_fp_two_vectors",
        "_fp_u32_quad",
        "_fp_u8color",
        "_fp_vec2",
        "_fp_vec3",
        "_fp_vec4",
        "_make_fp_vec3",
    }
    defined_names = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.AsyncFunctionDef, ast.ClassDef, ast.FunctionDef))
    }
    assigned_names = {
        target.id
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
        if isinstance(target, ast.Name)
    }

    assert dead_names.isdisjoint(defined_names | assigned_names)


def test_cli_does_not_expose_noop_tolerant_flag() -> None:
    actions = create_parser()._option_string_actions

    assert "--tolerant" not in actions
    assert "--strict" in actions


@pytest.mark.parametrize(
    ("cli_args", "expected_tolerant"),
    [
        pytest.param([], True, id="default"),
        pytest.param(["--strict"], False, id="strict"),
    ],
)
def test_cli_forwards_strict_mode_to_parse_single(
    cli_args: list[str],
    expected_tolerant: bool,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    asset_path = tmp_path / "asset.uasset"
    asset_path.write_bytes(b"")
    forwarded: dict[str, object] = {}

    def fake_parse_single(file_path: str, **kwargs: object) -> str:
        forwarded["file_path"] = file_path
        forwarded["tolerant"] = kwargs["tolerant"]
        return "{}"

    monkeypatch.setattr(cli_module, "parse_single", fake_parse_single)
    monkeypatch.setattr(
        sys,
        "argv",
        ["uasset_read", str(asset_path), *cli_args],
    )

    with pytest.raises(SystemExit) as exit_info:
        cli_module.main()

    assert exit_info.value.code == 0
    assert forwarded == {
        "file_path": str(asset_path),
        "tolerant": expected_tolerant,
    }
