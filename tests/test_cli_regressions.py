from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from uasset_read.formatters import format_json_full

SAMPLE_ASSET = Path(
    r"E:\Develop\lib\UnrealEngine\Samples\FirstPerson\Content\FirstPerson\Blueprints\BP_FirstPersonCharacter.uasset"
)


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    src_root = os.path.join(os.getcwd(), "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_root if not existing else f"{src_root}{os.pathsep}{existing}"
    return subprocess.run(
        [sys.executable, "-m", "uasset_read", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )


def test_format_json_full_blueprint_defaults_are_json_serializable(sample_result) -> None:
    data = format_json_full(sample_result)
    encoded = json.dumps(data, ensure_ascii=False)
    decoded = json.loads(encoded)

    blueprint_vars = decoded["blueprint"]["variables"]
    system_version = next(var for var in blueprint_vars if var["name"] == "BlueprintSystemVersion")
    assert system_version["default_value"] == 2


def test_cli_blueprint_ue_text_output(sample_result) -> None:
    asset_path = str(SAMPLE_ASSET)
    result = _run_cli(asset_path, "--blueprint-ue-text")

    assert result.returncode == 0, result.stderr
    assert "Begin Object Class=" in result.stdout
    assert 'FunctionReference=(MemberName="Jump",bSelfContext=True)' in result.stdout


def test_cli_graph_json_output_is_serializable(sample_result) -> None:
    asset_path = str(SAMPLE_ASSET)
    result = _run_cli(asset_path, "--graph", "--json")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "status" in payload
    assert "blueprint" in payload
    assert "graphs_summary" in payload

    blueprint_vars = payload["blueprint"]["variables"]
    system_version = next(var for var in blueprint_vars if var["name"] == "BlueprintSystemVersion")
    assert system_version["default_value"] == 2
