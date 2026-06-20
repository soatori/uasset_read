from __future__ import annotations

import http.client
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

import pytest

from uasset_read.parse_uasset import parse_uasset_with_linker


BLUEPRINT_TOOLSET = "editor_toolset.toolsets.blueprint.BlueprintTools"


@dataclass(frozen=True)
class BlueprintMcpComparisonAsset:
    label: str
    relative_asset_path: Path
    expected_editor_variables: frozenset[str]
    expected_graph_names: frozenset[str]


FIRST_PERSON_BLUEPRINT = BlueprintMcpComparisonAsset(
    label="first_person_character",
    relative_asset_path=Path(
        "FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset"
    ),
    expected_editor_variables=frozenset({"Target Touch UI"}),
    expected_graph_names=frozenset(
        {"UserConstructionScript", "Move", "Aim", "EventGraph"}
    ),
)


class UnrealMcpError(RuntimeError):
    pass


class UnrealMcpClient:
    def __init__(self, endpoint: str, session_id: str) -> None:
        self.endpoint = endpoint
        self.session_id = session_id
        self._next_id = 2

    @classmethod
    def connect(cls, endpoint: str, timeout: float = 10.0) -> "UnrealMcpClient":
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "uasset-read-tests", "version": "0.1"},
            },
        }
        response, headers = _post_mcp(endpoint, payload, timeout=timeout)
        session_id = headers.get("Mcp-Session-Id")
        if not session_id:
            raise UnrealMcpError(f"Unreal MCP did not return a session id: {response!r}")

        client = cls(endpoint, session_id)
        client.notify_initialized(timeout=timeout)
        return client

    def notify_initialized(self, timeout: float = 10.0) -> None:
        payload = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        _post_mcp(self.endpoint, payload, session_id=self.session_id, timeout=timeout)

    def call_meta_tool(self, name: str, arguments: dict | None = None, timeout: float = 60.0):
        payload = {
            "jsonrpc": "2.0",
            "id": self._allocate_id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        }
        response, _ = _post_mcp(
            self.endpoint,
            payload,
            session_id=self.session_id,
            timeout=timeout,
        )
        return _decode_tool_result(response)

    def call_blueprint_tool(
        self,
        tool_name: str,
        arguments: dict,
        timeout: float = 60.0,
    ) -> dict:
        return self.call_meta_tool(
            "call_tool",
            {
                "toolset_name": BLUEPRINT_TOOLSET,
                "tool_name": tool_name,
                "arguments": arguments,
            },
            timeout=timeout,
        )

    def require_blueprint_tools(
        self,
        required_tools: set[str],
        timeout: float = 60.0,
    ) -> None:
        deadline = time.monotonic() + timeout
        last_reason = ""

        while time.monotonic() < deadline:
            try:
                toolsets = self.call_meta_tool("list_toolsets")
                if BLUEPRINT_TOOLSET not in str(toolsets):
                    last_reason = f"{BLUEPRINT_TOOLSET} is not available"
                    time.sleep(5)
                    continue

                described = self.call_meta_tool(
                    "describe_toolset",
                    {"toolset_name": BLUEPRINT_TOOLSET},
                )
                exposed_tools = {
                    tool["name"].rsplit(".", 1)[-1]
                    for tool in described.get("tools", [])
                }
                missing = required_tools - exposed_tools
                if not missing:
                    return
                last_reason = f"{BLUEPRINT_TOOLSET} is missing tools: {sorted(missing)}"
            except UnrealMcpError as exc:
                last_reason = str(exc)
            time.sleep(5)

        pytest.skip(f"Unreal MCP BlueprintTools not ready: {last_reason}")

    def _allocate_id(self) -> int:
        request_id = self._next_id
        self._next_id += 1
        return request_id


def test_first_person_blueprint_relative_path_maps_to_project_and_ref() -> None:
    relative_path = FIRST_PERSON_BLUEPRINT.relative_asset_path

    assert not relative_path.is_absolute()
    assert _owning_project_relative_path(relative_path) == Path(
        "FirstPerson/FirstPerson.uproject"
    )
    assert _blueprint_ref_path(relative_path) == (
        "/Game/FirstPerson/Blueprints/"
        "BP_FirstPersonCharacter.BP_FirstPersonCharacter"
    )


@pytest.mark.integration
@pytest.mark.regression
@pytest.mark.slow
def test_real_blueprint_parser_matches_unreal_mcp_graphs_and_variables(
    sample_root: Path,
) -> None:
    spec = FIRST_PERSON_BLUEPRINT
    asset_path = sample_root / spec.relative_asset_path
    if not asset_path.exists():
        pytest.skip(f"sample asset not found: {spec.relative_asset_path}")

    project_path = sample_root / _owning_project_relative_path(spec.relative_asset_path)
    if not project_path.exists():
        pytest.skip(
            "owning Unreal project not found: "
            f"{_owning_project_relative_path(spec.relative_asset_path)}"
        )

    parse_result = parse_uasset_with_linker(str(asset_path), tolerant=True)
    assert parse_result.is_success, parse_result.errors
    assert parse_result.blueprint is not None

    client = _connect_or_launch_mcp_for_project(project_path)
    client.require_blueprint_tools({"list_variables", "list_graphs"})

    blueprint = {"refPath": _blueprint_ref_path(spec.relative_asset_path)}
    try:
        editor_variables = set(
            client.call_blueprint_tool("list_variables", {"blueprint": blueprint})[
                "returnValue"
            ]
        )
        editor_graphs = {
            _graph_name_from_ref(item["refPath"])
            for item in client.call_blueprint_tool("list_graphs", {"blueprint": blueprint})[
                "returnValue"
            ]
        }
    except UnrealMcpError as exc:
        pytest.skip(
            "Unreal MCP is not connected to the owning project "
            f"{_owning_project_relative_path(spec.relative_asset_path)} for "
            f"{spec.relative_asset_path}: {exc}"
        )

    parser_variables = {variable.var_name for variable in parse_result.blueprint.variables}
    parser_graphs = {graph.graph_name for graph in parse_result.graphs}

    assert spec.expected_editor_variables <= editor_variables
    assert editor_variables <= parser_variables
    assert spec.expected_graph_names <= editor_graphs
    assert editor_graphs <= parser_graphs


def _post_mcp(
    endpoint: str,
    payload: dict,
    *,
    session_id: str | None = None,
    timeout: float,
) -> tuple[dict, dict[str, str]]:
    url = urlsplit(endpoint)
    if url.scheme != "http" or not url.hostname:
        raise UnrealMcpError(f"unsupported Unreal MCP endpoint: {endpoint}")

    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id

    path = url.path or "/mcp"
    if url.query:
        path = f"{path}?{url.query}"

    connection = http.client.HTTPConnection(
        url.hostname,
        url.port or 80,
        timeout=timeout,
    )
    try:
        connection.request(
            "POST",
            path,
            body=json.dumps(payload),
            headers=headers,
        )
        response = connection.getresponse()
        body = response.read().decode("utf-8", errors="replace")
        if response.status >= 400:
            raise UnrealMcpError(f"HTTP {response.status}: {body}")
        return _decode_mcp_response(body), dict(response.headers.items())
    except OSError as exc:
        raise UnrealMcpError(str(exc)) from exc
    finally:
        connection.close()


def _decode_mcp_response(body: str) -> dict:
    text = body.strip()
    if text.startswith("event:"):
        data_lines = [
            line[5:].lstrip()
            for line in body.splitlines()
            if line.startswith("data:")
        ]
        text = "\n".join(data_lines)
    if not text:
        return {}
    return json.loads(text)


def _decode_tool_result(response: dict):
    if "error" in response:
        raise UnrealMcpError(str(response["error"]))

    result = response.get("result", {})
    content = result.get("content", [])
    text = content[0].get("text", "") if content else ""
    if result.get("isError"):
        raise UnrealMcpError(text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _connect_or_launch_mcp_for_project(project_path: Path) -> UnrealMcpClient:
    endpoint = os.environ.get("UE_MCP_URL", "http://127.0.0.1:8000/mcp")
    try:
        return UnrealMcpClient.connect(endpoint)
    except UnrealMcpError:
        pass

    editor = _find_unreal_editor()
    if editor is None:
        pytest.skip(
            "Unreal MCP is not running and UnrealEditor.exe was not found. "
            "Set UE_EDITOR_EXE or start the owning project editor."
        )

    port = _port_from_endpoint(endpoint)
    subprocess.Popen(
        [
            str(editor),
            str(project_path),
            "-ModelContextProtocolStartServer",
            f"-ModelContextProtocolPort={port}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return _wait_for_mcp(endpoint)


def _wait_for_mcp(endpoint: str) -> UnrealMcpClient:
    deadline = time.monotonic() + float(os.environ.get("UE_MCP_STARTUP_TIMEOUT", "300"))
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return UnrealMcpClient.connect(endpoint)
        except UnrealMcpError as exc:
            last_error = exc
            time.sleep(5)
    raise UnrealMcpError(f"Unreal MCP did not start before timeout: {last_error}")


def _find_unreal_editor() -> Path | None:
    for env_name in ("UE_EDITOR_EXE", "UNREAL_EDITOR_EXE"):
        value = os.environ.get(env_name)
        if value and Path(value).exists():
            return Path(value)

    found = shutil.which("UnrealEditor.exe")
    if found:
        return Path(found)

    for drive in ("C", "D", "E", "F"):
        for base in (
            Path(f"{drive}:/Program Files/Epic Games"),
            Path(f"{drive}:/Program Files/Epic Games/Engine"),
        ):
            if not base.exists():
                continue
            candidates = sorted(
                base.glob("UE_*/Engine/Binaries/Win64/UnrealEditor.exe"),
                reverse=True,
            )
            if candidates:
                return candidates[0]
    return None


def _port_from_endpoint(endpoint: str) -> int:
    return urlsplit(endpoint).port or 8000


def _owning_project_relative_path(relative_asset_path: Path) -> Path:
    project_dir = relative_asset_path.parts[0]
    return Path(project_dir) / f"{project_dir}.uproject"


def _blueprint_ref_path(relative_asset_path: Path) -> str:
    parts = relative_asset_path.parts
    try:
        content_index = parts.index("Content")
    except ValueError as exc:
        raise AssertionError(f"asset path has no Content segment: {relative_asset_path}") from exc

    object_parts = parts[content_index + 1:]
    package_path = PurePosixPath(*object_parts).with_suffix("")
    asset_name = Path(object_parts[-1]).stem
    return f"/Game/{package_path.as_posix()}.{asset_name}"


def _graph_name_from_ref(ref_path: str) -> str:
    return ref_path.rsplit(":", 1)[-1]
