"""Regression coverage for #516 plugin package mount-path derivation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from shutil import copyfile
from types import SimpleNamespace

from uasset_read import parse_single
from uasset_read.pipeline.stages import _derive_package_name


ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "tests" / "samples" / "Lyra_B_Rifle.uasset"
SOURCE_FIXTURE_SHA256 = (
    "584E26FFA27CAC2431E514BE620DA120E8CA44734F12714ED954F49F2F9005F6"
)


def _derive(path: Path, package_name: str | None = None) -> str | None:
    summary = SimpleNamespace(package_name=package_name)
    _derive_package_name(str(path), summary)
    return summary.package_name


def test_derives_plugin_mount_path_from_adjacent_descriptor(tmp_path: Path) -> None:
    plugin_root = tmp_path / "Plugins" / "GameFeatures" / "ShooterCore"
    asset_path = plugin_root / "Content" / "Weapons" / "Rifle" / "B_Rifle.uasset"
    asset_path.parent.mkdir(parents=True)
    asset_path.touch()
    (plugin_root / "ShooterCore.uplugin").touch()

    assert _derive(asset_path) == "/ShooterCore/Weapons/Rifle/B_Rifle"


def test_derives_game_mount_path_for_regular_content(tmp_path: Path) -> None:
    asset_path = (
        tmp_path / "Project" / "Content" / "Weapons" / "Rifle" / "B_Rifle.uasset"
    )

    assert _derive(asset_path) == "/Game/Weapons/Rifle/B_Rifle"


def test_nested_content_without_adjacent_descriptor_uses_game_mount(tmp_path: Path) -> None:
    asset_path = (
        tmp_path
        / "Plugins"
        / "GameFeatures"
        / "ShooterCore"
        / "Content"
        / "Nested"
        / "Content"
        / "Weapons"
        / "Rifle"
        / "B_Rifle.uasset"
    )

    assert _derive(asset_path) == "/Game/Weapons/Rifle/B_Rifle"


def test_preserves_existing_package_name(tmp_path: Path) -> None:
    asset_path = tmp_path / "Content" / "Weapons" / "Rifle" / "B_Rifle.uasset"

    assert _derive(asset_path, package_name="/Stored") == "/Stored"


def test_real_plugin_fixture_derives_public_mount_path(tmp_path: Path) -> None:
    assert hashlib.sha256(SAMPLE.read_bytes()).hexdigest().upper() == SOURCE_FIXTURE_SHA256

    plugin_root = tmp_path / "Plugins" / "GameFeatures" / "ShooterCore"
    asset_path = plugin_root / "Content" / "Weapons" / "Rifle" / "B_Rifle.uasset"
    asset_path.parent.mkdir(parents=True)
    copyfile(SAMPLE, asset_path)
    (plugin_root / "ShooterCore.uplugin").touch()

    payload = json.loads(parse_single(str(asset_path), format="json", log_enabled=False))

    assert payload["summary"]["package_name"] == "/ShooterCore/Weapons/Rifle/B_Rifle"
