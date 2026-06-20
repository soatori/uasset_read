---
name: ue-mcp
description: Guide agents in using Epic's UE 5.8 Unreal MCP, ModelContextProtocol, ToolsetRegistry, Tool Search, AgentSkillToolset, EditorToolset, AutomationTestToolset, LiveCodingToolset, MCPClientToolset, and custom MCP Tool development. Use when Codex needs to connect to a UE Editor MCP server, discover available Unreal toolsets, call MCP tools safely, create or update UE AgentSkill assets with permission, or debug Unreal MCP configuration and tool availability.
---

# UE 5.8 Unreal MCP

## Overview

Use this skill to operate a UE 5.8 editor through Epic's official Unreal MCP. The Plugin Browser and Epic documentation use the friendly name **Unreal MCP**; the engine source tree, `.uplugin` files, C++ symbols, console commands, and settings use the identifier `ModelContextProtocol`.

Treat Unreal MCP as a local HTTP/SSE MCP server embedded in the editor process. It synchronizes external tool calls onto the Unreal game thread and executes tool invocations serially, so do not issue overlapping dependent calls.

Useful editor operations usually come from `ToolsetRegistry` plus enabled `Experimental/Toolsets/*` plugins. `ModelContextProtocol` itself is primarily the transport, server, settings, and protocol layer.

Do not infer UE MCP capability from third-party Unreal MCP servers or Jianying/CapCut MCP projects. Those can suggest automation patterns, but official UE 5.8 behavior must come from Epic docs, local UE 5.8 source, schemas returned by `describe_toolset`, or live editor evidence.

Read `references/mcp-tools.md` when you need concrete setup details, built-in toolset domains, configuration keys, console commands, custom Toolset patterns, runtime limits, or known call-shape pitfalls.

## Skill Activation

Use this project skill when the user explicitly invokes `/ue-mcp` or `$ue-mcp`, asks to control or inspect the currently running UE editor through MCP, asks how to enable Unreal MCP, or asks which UE MCP Toolset should handle an editor task.

The tracked source lives at `skills/ue-mcp/`. The installed runtime copy currently lives at `C:\Users\cbsjz\.cc-switch\skills\ue-mcp\`. Keep both copies synchronized after edits.

This skill does not start inside Unreal by itself. Unreal MCP must be enabled in the editor, the MCP server must be running, and the agent must be connected from the project root where the client config was generated.

Keep these activation layers separate:

- Agent skill activation: the external agent loads this file when `$ue-mcp` or the skill name is used.
- Unreal plugin enablement: UE Editor must have the **Unreal MCP** plugin enabled; source, settings, and commands call it `ModelContextProtocol`.
- MCP server startup: Auto Start must be enabled or `ModelContextProtocol.StartServer [port]` must run in the editor.
- Client connection: generate config with `ModelContextProtocol.GenerateClientConfig Codex|ClaudeCode|All`, then launch the agent from the project root that received the config.
- UE `UAgentSkill` assets: these are ToolsetRegistry-managed Blueprint-backed editor assets. They are not the same thing as this filesystem skill and must not be created or updated without explicit user permission.

## Workflow

1. Confirm Unreal MCP tools are exposed in the current agent session.
2. If no Unreal MCP tools are exposed, guide the user to enable **Unreal MCP**, configure Auto Start or run `ModelContextProtocol.StartServer [port]`, generate client config with `ModelContextProtocol.GenerateClientConfig Codex|ClaudeCode|All`, and restart/connect the agent from the project root where the config was written.
3. Prefer Tool Search mode. Call `list_toolsets`, choose the capability domain, call `describe_toolset` for the exact Toolset, then call the desired tool through `call_tool`.
4. In this MCP wrapper, pass the full Toolset name as `toolset_name` and the short tool name as `tool_name`. For example, use `toolset_name: "editor_toolset.toolsets.scene.SceneTools"` and `tool_name: "get_current_level"`, not the fully qualified tool name.
5. Do not assume a documented Toolset is enabled. Use the current `list_toolsets` result as truth, then inspect schemas with `describe_toolset` before forming arguments.
6. Before any scene, asset, config, plugin, file, PIE, compile, save, or AgentSkill mutation, state the expected effect and use read-only inspection tools first when available.
7. Execute dependent tool calls serially. Wait for asynchronous results, saving, compiling, Live Coding, PIE, and automation test state before starting the next dependent action.
8. After a mutating call, verify with a separate read/query action.

## Choosing Toolsets

Currently enabled Toolsets are only the live `list_toolsets` result, not every plugin found in the engine source. As an observed baseline example from the FirstPerson MCP session, the enabled set was the base editor stack: `ToolsetRegistry.AgentSkillToolset`, `EditorToolset.EditorAppToolset`, `EditorToolset.LogsToolset`, `AutomationTestToolset.AutomationTestToolset`, `LiveCodingToolset.LiveCodingToolset`, and `editor_toolset.toolsets.*` Python tools. Re-check every project with `list_toolsets`.

- General editor state, viewport, selection, camera, PIE, screenshots, or Content Browser tasks: use `EditorToolset.EditorAppToolset`.
- Scene, actor, component, asset, material, Blueprint, table, mesh, texture, or object tasks: use the corresponding `editor_toolset.toolsets.*` Toolset discovered at runtime.
- Logs and diagnostics: use `EditorToolset.LogsToolset`; pass `category: ""` when querying all log categories.
- Test discovery or validation: use `AutomationTestToolset.AutomationTestToolset`.
- C++ iteration: use `LiveCodingToolset.LiveCodingToolset`.
- UE AgentSkill management: use `ToolsetRegistry.AgentSkillToolset`, but create or update skills only after explicit user permission.

Optional Toolset plugins under `Engine/Plugins/Experimental/Toolsets/*` can add more MCP-visible domains after they are enabled, the editor is restarted, and `list_toolsets` confirms them. Use the smallest plugin set needed; do not enable `AllToolsets` by default.

- Plugin and config work: use `PluginToolset` for plugin discovery or creation, and `ConfigSettingsToolset` for config sections and settings.
- Procedural, graph, VFX, and dataflow work: use `PCGToolset`, `PCGSpatialToolset`, `NiagaraToolsets`, `DataflowAgent`, or `ChaosClothAssetToolset`.
- Gameplay systems: use `GameplayTagsToolset`, `GameFeaturesToolset`, `GASToolsets`, `DataRegistryToolset`, `StateTreeToolset`, or `WorldConditionsToolset`.
- UI and editor UI inspection: use `UMGToolSet`, `MVVMToolset`, or `SlateInspectorToolset`.
- Specialized asset workflows: use `PhysicsToolsets`, `AnimationAssistantToolset`, `SequencerAnimMixerToolset`, `ConversationToolset`, `MetaHumanGenerator`, or `SemanticSearchToolset` only when the project and live schemas justify them.
- External MCP servers inside UE: use `MCPClientToolset` only when UE needs to connect outward to another MCP server and expose those remote tools through Toolset Registry. It is not the Codex-to-UE editor control path.

For concrete controllable operations in each domain, load `references/mcp-tools.md` and use its "Concrete Control Surface" section before calling tools.

## Typical Tool Calls

- Connection check: call `list_toolsets`.
- Schema discovery: call `describe_toolset` with the exact Toolset name from `list_toolsets`.
- Current level read: call `editor_toolset.toolsets.scene.SceneTools` with short tool name `get_current_level`.
- Scene/Actor inspection: use `SceneTools.find_actors`, then `ActorTools.get_label`, `get_actor_transform`, `get_components`, or `get_actor_bounds`.
- Blueprint comparison: use `BlueprintTools.list_graphs`, `get_graph`, `list_variables`, `list_events`, `get_parent`, and read-only graph/object tools before any Blueprint mutation.
- Blueprint logic read: prefer `get_graph` to obtain the graph refPath, then try `read_graph_dsl`; if it returns an empty string or rejects the graph path, use `find_nodes` with `title: ""`, then `get_node_infos` for pins/connections or `get_connected_subgraph` from a specific event/input node.
- Editor context: use `EditorAppToolset.GetContentBrowserPath`, `GetOpenAssets`, `GetSelectedActors`, `GetSelectedAssets`, `GetCameraTransform`, or `IsPIERunning`.
- Logs and diagnostics: use `LogsToolset.GetLogEntries` with `category: ""` and a narrow `pattern`.
- Automation tests: call `DiscoverTests`, then `ListTests`; run tests only when the user asks for test execution.
- AgentSkill assets: call `ListSkills` and `GetSkills` freely; call `CreateSkill` or `UpdateSkill` only after explicit permission.

## Blueprint EventGraph Reading

Use this read-only playbook when the user asks to inspect Blueprint logic or compare a `.uasset` parser result against the live editor:

1. Call `BlueprintTools.list_graphs` for the Blueprint asset path.
2. Call `BlueprintTools.get_graph` for the target graph, usually `EventGraph`, and keep the returned graph refPath.
3. Try `BlueprintTools.read_graph_dsl` with that exact graph refPath.
4. If `read_graph_dsl` returns `""` or rejects the path, call `BlueprintTools.find_nodes` with `title: ""` on the same graph.
5. Pass all returned node refs to `BlueprintTools.get_node_infos` to read node titles, pin names, pin directions, pin categories, positions, and `connected_pins`.
6. For a specific execution chain, call `BlueprintTools.get_connected_subgraph` from an event or Enhanced Input node ref.
7. Summarize both execution flow and data flow. Execution pins show ordering; value pins show parameters such as axis values, action values, targets, booleans, and object refs.

Do not treat an empty Graph DSL result as proof that the graph is empty. Node and pin inspection is the reliable fallback.

When the live schema marks `blueprint`, `graph`, `node`, or class/object inputs as UObject references, pass an object with `refPath`, for example `{ "refPath": "/Game/...Asset.Asset:EventGraph" }`, rather than a bare string.

## Safety Rules

- Treat UE 5.8 MCP and Toolset APIs as experimental. APIs, schemas, return shapes, and data formats can change.
- Keep Unreal MCP local. It supports HTTP and Server-Sent Events only, binds to loopback by default, has no authentication layer, rejects non-loopback origins, and is not safe to expose beyond the local machine.
- Never create or update UE `UAgentSkill` assets without clear user authorization. `CreateSkill` and `UpdateSkill` write Blueprint-backed editor assets.
- Do not use `AllToolsets` as the default recommendation for production projects; prefer enabling the smallest Toolset set needed for the task.
- If a tool is missing after enabling, hot reload, or Game Feature activation, run `ModelContextProtocol.RefreshTools`; if schemas remain stale, reconnect the client.
- When project-specific conventions matter, use `AgentSkillToolset.ListSkills` and `AgentSkillToolset.GetSkills` before acting.
- Before save, compile, plugin, config, PIE, test, asset, or graph operations, inspect current state with the corresponding read-only Toolset operation when available.

Risk levels:

- Read-only: `list_toolsets`, `describe_toolset`, `get_current_level`, `list_graphs`, `get_graph`, `read_graph_dsl`, `find_nodes`, `get_node_infos`, `get_connected_subgraph`, `GetLogEntries`, `GetSelectedAssets`, `GetOpenAssets`, `ListSkills`, and `GetSkills`.
- State-inspection with editor context: selection, camera, viewport, Content Browser path, open asset, and PIE status reads.
- Mutating: create, move, delete, save, compile, import, set transform, set selection, set camera, run PIE, run tests, Live Coding compile, plugin/config edits, Blueprint graph edits, and AgentSkill create/update.

## Debugging

When connection or tool discovery fails, check in this order:

1. **Plugins**: Unreal MCP (`ModelContextProtocol`), `ToolsetRegistry`, and the target Toolset plugin are enabled.
2. **Server**: Auto Start is enabled or `ModelContextProtocol.StartServer [port]` was run. The default endpoint is `http://127.0.0.1:8000/mcp`.
3. **Client config**: `ModelContextProtocol.GenerateClientConfig Codex|ClaudeCode|All` wrote config under the project/workspace root, and the agent was launched from that root.
4. **Logs**: Use Output Log, `LogModelContextProtocol`, or `EditorToolset.LogsToolset.GetLogEntries` with `category: ""`.
5. **Refresh**: Run `ModelContextProtocol.RefreshTools` after new Toolsets, hot reloads, or Game Feature activation.
6. **Inspector**: Use MCP Inspector with Streamable HTTP against `/mcp` to list tools and inspect schemas outside the agent.

Classify logs before diagnosing:

- `LogModelContextProtocol` is the primary MCP server and tool discovery signal.
- `LogToolsetRegistry`, `LogPython`, Blueprint compiler, and target Toolset categories explain schema, Python, or domain tool failures.
- `LogHttp` requests to `datarouter.ol.epicgames.com` are usually Epic telemetry upload issues. They can be noisy, but they do not by themselves prove Unreal MCP failure.

## Project Boundary

For `uasset_read`, UE MCP is useful as an editor-visible semantic oracle for Blueprint graphs, variables, parent classes, logs, automation tests, selected/open assets, and scene state. It does not prove raw `.uasset` binary serialization fidelity. Keep parser acceptance tied to real sample outputs and tests, and use UE MCP as supporting comparison evidence.
