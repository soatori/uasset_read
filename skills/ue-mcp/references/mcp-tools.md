# UE 5.8 Unreal MCP Tools Reference

Use this reference after `SKILL.md` triggers and the task needs concrete UE 5.8 MCP tool, Toolset, configuration, authoring, or diagnostic details. This reference covers Epic's official UE 5.8 `ModelContextProtocol` / Unreal MCP path only.

Primary evidence should come from the live editor schemas returned by `describe_toolset`, local UE 5.8 source, and Epic documentation. Public orientation sources:

- [Epic UE 5.8 Unreal MCP documentation](https://dev.epicgames.com/documentation/unreal-engine/unreal-mcp-in-unreal-editor?lang=en-US)
- [Unreal Engine 5.8 release announcement](https://www.unrealengine.com/news/unreal-engine-5-8-is-now-available)
- [EpicGames unreal-mcp skill](https://raw.githubusercontent.com/EpicGames/unreal-engine-skills-for-claude-code-plugin/main/skills/unreal-mcp/SKILL.md)
- [EpicGames unreal-mcp operations reference](https://raw.githubusercontent.com/EpicGames/unreal-engine-skills-for-claude-code-plugin/main/skills/unreal-mcp/references/operations.md)

## Architecture

UE 5.8 MCP has three practical layers:

| Layer | Plugin or path | Role |
|---|---|---|
| Connection | `ModelContextProtocol` | Embedded local HTTP/SSE MCP server, JSON-RPC sessions, client config generation, settings, console commands, direct runtime tool registration |
| Registry | `ToolsetRegistry` | Discovers `UToolsetDefinition` and Python `unreal.ToolsetDefinition`, generates schemas, executes tools, manages AgentSkill and sandbox support |
| Capability | `Engine/Plugins/Experimental/Toolsets/*` | Domain toolsets for editor, assets, automation tests, Live Coding, PCG, GAS, UI, Niagara, StateTree, and related workflows |

The friendly plugin name is **Unreal MCP**. Engine identifiers, console commands, settings, C++ symbols, and source paths use `ModelContextProtocol`.

`ModelContextProtocol` and `ModelContextProtocolEngine` are runtime modules. `ModelContextProtocolEditor` is editor-only and adapts Toolset Registry-discovered toolsets into MCP tools. Cooked or shipping builds can host an MCP server, but Toolset Registry auto-discovery is not available there.

## Setup And Configuration

| Item | Default or command | Notes |
|---|---|---|
| Enable plugin | Unreal MCP | Enable from Edit > Plugins. `ToolsetRegistry` is a dependency and is enabled automatically. Restart when prompted. |
| Auto Start Server | `false` | Editor Preferences > General > Model Context Protocol. When enabled, starts on editor launch. |
| Server URL | `http://127.0.0.1:8000/mcp` | Default bind is loopback only. |
| Server Port Number | `8000` | Can be changed in preferences or overridden by command. |
| Server URL Path | `/mcp` | Can be changed when defaults conflict with another local service. |
| Server name | `unreal-mcp` | Advertised in `serverInfo.name`. |
| Enable Tool Search | `true` | `tools/list` returns meta-tools instead of every tool schema. |

Console commands:

| Command | Purpose |
|---|---|
| `ModelContextProtocol.StartServer [port]` | Start the server, optionally overriding the port. |
| `ModelContextProtocol.StopServer` | Stop the server and close sessions. |
| `ModelContextProtocol.RefreshTools` | Re-poll registered tool providers. Use after new Toolsets, hot reloads, or Game Feature activation. |
| `ModelContextProtocol.GenerateClientConfig <Client|All>` | Generate client config in the project root. Supported clients include `ClaudeCode`, `Cursor`, `VSCode`, `Gemini`, `Codex`, and `All`. |

Command-line flags:

| Flag | Purpose |
|---|---|
| `-ModelContextProtocolStartServer` | Start the server during editor or commandlet startup regardless of Auto Start Server. |
| `-ModelContextProtocolPort=N` | Override the listening port, valid range `1..65535`; invalid values fall back to settings. |

Important console variables:

| CVar | Default | Purpose |
|---|---|---|
| `ModelContextProtocol.WrapPODToolResultsInObject` | `true` | Wrap primitive results in object-shaped responses for clients that require objects. |
| `ModelContextProtocol.AudioResultOggFormat` | `false` | Encode audio tool results as OGG instead of WAV. |
| `ModelContextProtocol.ProgressIntervalSeconds` | `1.0` | Minimum interval between MCP progress notifications. |
| `ModelContextProtocol.PaginationPageSize` | `0` | Maximum paginated response size; `0` disables pagination. |
| `ModelContextProtocol.EnableAnalytics` | `true` | Gate telemetry emission. |

Client config notes:

- JSON client configs such as Claude Code, Cursor, VS Code, and Gemini are merged with existing entries, so regenerating is safe.
- Codex CLI TOML config generation is write-once. The command refuses to overwrite an existing file; remove stale config manually before regenerating.
- Launch the agent from the project or workspace root where config files were generated.

## Tool Search

UE 5.8 defaults to Tool Search mode when `bEnableToolSearch=true`.

| Meta-tool | Purpose |
|---|---|
| `list_toolsets` | List available Toolset names and descriptions. |
| `describe_toolset` | Return the tool schemas for one Toolset. |
| `call_tool` | Invoke one named Toolset tool with arguments. |

Use `list_toolsets` before choosing a Toolset. Use `describe_toolset` before forming arguments. Use `call_tool` only after confirming the live schema.

In this MCP wrapper, pass:

```json
{
  "toolset_name": "editor_toolset.toolsets.scene.SceneTools",
  "tool_name": "get_current_level",
  "arguments": {}
}
```

Do not pass the fully qualified tool name as `tool_name`; the wrapper expects the short name. A fully qualified `tool_name` can return `Unknown tool`.

Common read-only templates:

Connection check:

```json
{
  "tool_name": "list_toolsets"
}
```

Describe Blueprint tools:

```json
{
  "tool_name": "describe_toolset",
  "arguments": {
    "toolset_name": "editor_toolset.toolsets.blueprint.BlueprintTools"
  }
}
```

Read current level:

```json
{
  "tool_name": "call_tool",
  "arguments": {
    "toolset_name": "editor_toolset.toolsets.scene.SceneTools",
    "tool_name": "get_current_level",
    "arguments": {}
  }
}
```

Query MCP logs:

```json
{
  "tool_name": "call_tool",
  "arguments": {
    "toolset_name": "EditorToolset.LogsToolset",
    "tool_name": "GetLogEntries",
    "arguments": {
      "category": "",
      "pattern": "LogModelContextProtocol"
    }
  }
}
```

## Built-In Toolset Map

These are candidate domains, not a guarantee that the current project has each Toolset enabled. Treat the live `list_toolsets` response as authoritative.

### Base Editor Stack

These are the Toolsets most commonly present when `ModelContextProtocol`, `ToolsetRegistry`, `EditorToolset`, `AutomationTestToolset`, and `LiveCodingToolset` are enabled.

| Toolset plugin or Toolset | Use for |
|---|---|
| `EditorToolset.EditorAppToolset` | Editor app state, viewport and editor screenshots, selection, camera, Content Browser, open assets, PIE state |
| `EditorToolset.LogsToolset` | Reading logs, listing categories, reading or changing verbosity |
| `editor_toolset.toolsets.scene.SceneTools` | Levels, Actor discovery, folders, traces, level instances, actor placement/removal |
| `editor_toolset.toolsets.actor.ActorTools` | Actor labels, tags, transforms, bounds, root/components, attachments |
| `editor_toolset.toolsets.asset.AssetTools` | Asset discovery, metadata, dirty/editable state, save/load, dependencies, referencers, allowed file reads/writes |
| `editor_toolset.toolsets.blueprint.BlueprintTools` | Blueprint parent, CDO, graphs, functions, events, variables, pins, Graph DSL, compile |
| `editor_toolset.toolsets.material.*` | Materials, material functions, material instances, parameters, expressions |
| `editor_toolset.toolsets.data_*` | DataAssets, DataTables, CurveTables, StringTables |
| `editor_toolset.toolsets.static_mesh.StaticMeshTools` | Static Mesh import and inspection, LODs, triangles, vertices, materials, collision, Nanite |
| `editor_toolset.toolsets.skeletal_mesh.SkeletalMeshTools` | Skeletal Mesh import and inspection, bones, materials, physics assets, morph targets, sockets |
| `editor_toolset.toolsets.texture.TextureTools` | Texture import and `Texture2D` size |
| `AutomationTestToolset.AutomationTestToolset` | Discover, list, run, stop, and inspect automation tests |
| `LiveCodingToolset.LiveCodingToolset` | Trigger Live Coding compilation and inspect compiler output |
| `ToolsetRegistry.AgentSkillToolset` | Listing, reading, creating, and updating UE AgentSkill assets |

### Toolset Plugin Use Matrix

These plugins exist in the UE 5.8 source under `Engine/Plugins/Experimental/Toolsets/*`. Enable only the needed plugin, restart the editor when required, run `list_toolsets`, then use `describe_toolset` for exact schemas.

| Category | Toolset plugin or Toolset | Use for |
|---|---|---|
| Plugin/config | `PluginToolset` | Plugin discovery, descriptors, dependencies, templates, and plugin creation or modification workflows |
| Plugin/config | `ConfigSettingsToolset` | Config containers, sections, property schemas, setting edits, save/reset flows |
| Procedural/graph | `PCGToolset`, `PCGSpatialToolset` | PCG graph, node, parameter, comment box, instance, spatial data, and execution workflows |
| Procedural/graph | `DataflowAgent` | Dataflow graph assets, nodes, connections, variables, comments, templates, and graph asset operations |
| VFX/assets | `NiagaraToolsets` | Niagara system, component, Blueprint, asset, topology, schema, and data inspection or editing |
| VFX/assets | `ChaosClothAssetToolset` | Chaos Cloth Asset creation, conversion, transfer, material, and skeletal mesh cloth assignment workflows |
| Gameplay | `GameplayTagsToolset` | Gameplay tag discovery, add/remove operations, redirects, and source management |
| Gameplay | `GameFeaturesToolset` | Game Feature plugin discovery, creation, state inspection, activation, and deactivation |
| Gameplay | `GASToolsets` | Ability System inspection, AttributeSet tasks, and GameplayCue discovery or creation |
| Gameplay | `DataRegistryToolset` | Data Registry discovery, source inspection, item lookup, and runtime registry checks |
| Gameplay | `StateTreeToolset`, `WorldConditionsToolset` | StateTree or World Conditions inspection when those plugins are enabled |
| UI | `UMGToolSet` | UMG widget creation, hierarchy, bindings, properties, and reflection-driven widget edits |
| UI | `MVVMToolset` | MVVM view model, field, binding, and widget-viewmodel data management |
| UI | `SlateInspectorToolset` | Slate widget tree inspection, editor UI location queries, and UI automation diagnostics |
| Physics/animation | `PhysicsToolsets` | Physics asset and constraint-oriented inspection or editing |
| Physics/animation | `AnimationAssistantToolset`, `SequencerAnimMixerToolset` | Animation-system and Sequencer animation mixer tasks |
| AI/dialogue | `AIModuleToolset`, `ConversationToolset` | AI module and conversation system tasks when schemas are exposed |
| Character/search | `MetaHumanGenerator`, `SemanticSearchToolset` | MetaHuman generation/editing and hybrid vector/BM25 asset search |
| External MCP bridge | `MCPClientToolset` | Connecting UE Editor outward to local/private MCP servers and wrapping remote MCP tools as Toolset Registry tools |

`MCPClientToolset` is the reverse bridge: it lets UE consume another MCP server. It is not required for Codex to control the Unreal Editor through the editor's own `ModelContextProtocol` server.

Do not enable `AllToolsets` by default. It aggregates many experimental plugins and can increase startup cost, schema noise, and mutation risk. Prefer enabling the smallest domain plugin set, then verify the live list before calling anything.

For GAS, Gameplay Tags, Game Features, StateTree, World Conditions, Niagara, UMG, MVVM, Slate Inspector, Dataflow, Physics, Chaos Cloth, Animation, Conversation, MetaHuman, Semantic Search, or any other specialized task, first verify the corresponding Toolset is present, then use `describe_toolset` for exact schemas. Do not infer individual tool names from the category name alone.

## Concrete Control Surface

Use this section only to choose a domain before calling `describe_toolset`.

| Domain | Controllable content |
|---|---|
| Editor/App | Search CVars, capture editor or viewport images, select Actors/assets, read or set editor camera transform, focus camera, convert world/screen coordinates, read or set Content Browser path, open assets, list open assets, inspect PIE state |
| Logs | Read current session entries, list categories, get/set verbosity |
| Scene | Load/current level, collision channels, find Actors, add/remove Actors, folders, traces, merge Actors, level instances, editability/source control, save Actor |
| Actor/components | Labels, tags, transform, look-at target, root component, owner, parent, attachment, bounds, component list, add/remove component |
| Assets/files | Folders, asset existence, duplicate/move/delete assets, metadata, dirty/editable/checked-out state, dependencies/referencers, plugin content paths, allowed project/plugin files |
| Blueprint | Create/compile, parent/CDO, graphs/functions/events, node/pin inspection, Graph DSL, variables, replication/category, event dispatchers, component events |
| Materials | Create materials/functions/collections, inspect expression classes and pins, connect/disconnect expressions, parameters, material property outputs, recompile |
| Automation tests | Discover, list, run by names or filters, status, results, stop |
| Custom tools | Python or C++ Toolsets through Toolset Registry; dynamic runtime tools through direct `IModelContextProtocolModule::AddTool()` registration |

## Blueprint EventGraph Reading Playbook

Use this when `read_graph_dsl` fails validation, returns an empty string, or omits details needed for `.uasset` parser comparison.

1. Verify the Blueprint Toolset schema:

```json
{
  "tool_name": "describe_toolset",
  "arguments": {
    "toolset_name": "editor_toolset.toolsets.blueprint.BlueprintTools"
  }
}
```

2. List graph refs for the asset:

```json
{
  "tool_name": "call_tool",
  "arguments": {
    "toolset_name": "editor_toolset.toolsets.blueprint.BlueprintTools",
    "tool_name": "list_graphs",
    "arguments": {
      "blueprint": {
        "refPath": "/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter.BP_FirstPersonCharacter"
      }
    }
  }
}
```

3. Resolve the target graph and keep the returned refPath:

```json
{
  "tool_name": "call_tool",
  "arguments": {
    "toolset_name": "editor_toolset.toolsets.blueprint.BlueprintTools",
    "tool_name": "get_graph",
    "arguments": {
      "blueprint": {
        "refPath": "/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter.BP_FirstPersonCharacter"
      },
      "graph_name": "EventGraph"
    }
  }
}
```

4. Try Graph DSL:

```json
{
  "tool_name": "call_tool",
  "arguments": {
    "toolset_name": "editor_toolset.toolsets.blueprint.BlueprintTools",
    "tool_name": "read_graph_dsl",
    "arguments": {
      "graph": {
        "refPath": "/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter.BP_FirstPersonCharacter:EventGraph"
      }
    }
  }
}
```

5. If DSL is empty or invalid, enumerate all nodes:

```json
{
  "tool_name": "call_tool",
  "arguments": {
    "toolset_name": "editor_toolset.toolsets.blueprint.BlueprintTools",
    "tool_name": "find_nodes",
    "arguments": {
      "graph": {
        "refPath": "/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter.BP_FirstPersonCharacter:EventGraph"
      },
      "title": ""
    }
  }
}
```

6. Fetch details for returned node refs:

```json
{
  "tool_name": "call_tool",
  "arguments": {
    "toolset_name": "editor_toolset.toolsets.blueprint.BlueprintTools",
    "tool_name": "get_node_infos",
    "arguments": {
      "nodes": [
        {
          "refPath": "/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter.BP_FirstPersonCharacter:EventGraph.K2Node_EnhancedInputAction_3"
        }
      ]
    }
  }
}
```

7. For one execution path, start from an event or input node:

```json
{
  "tool_name": "call_tool",
  "arguments": {
    "toolset_name": "editor_toolset.toolsets.blueprint.BlueprintTools",
    "tool_name": "get_connected_subgraph",
    "arguments": {
      "node": {
        "refPath": "/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter.BP_FirstPersonCharacter:EventGraph.K2Node_EnhancedInputAction_3"
      }
    }
  }
}
```

Interpretation rules:

- Execution pins define order of operations.
- Data pins define values passed into functions, including axis values, action values, targets, object refs, booleans, and structs.
- `connected_pins` is the source of truth for links when Graph DSL is empty.
- Node position is layout evidence only; do not infer execution order from position.
- UObject reference parameters use `{ "refPath": "..." }` objects in the live schema, even when the value is displayed as a path string in logs or summaries.

## AgentSkillToolset

`ToolsetRegistry.AgentSkillToolset` exposes these tools in current UE 5.8 schemas:

| Tool | Arguments | Result | Notes |
|---|---|---|---|
| `ListSkills` | none | map of skill path to description | Read-only |
| `GetSkills` | `skillPaths: string[]` | map of skill path to details | Read-only |
| `CreateSkill` | `folderPath`, `assetName`, `description`, `details.instructions` | created skill class path | Mutates UE assets; require user permission |
| `UpdateSkill` | `skillPath`, `description`, `details.instructions` | boolean | Mutates Blueprint-backed skills; require user permission |

`UpdateSkill` cannot persist changes to native C++ or transient Python-generated skills; edit their source instead.

## Authoring Custom Tools

Prefer the Toolset Registry for editor automation.

Python Toolsets:

```python
import unreal
import toolset_registry

@unreal.uclass()
class MyTools(unreal.ToolsetDefinition):
    """Provide project-specific tools."""

    @staticmethod
    @toolset_registry.tool_call
    def get_scene_info() -> dict:
        world = unreal.EditorLevelLibrary.get_editor_world()
        actors = unreal.EditorLevelLibrary.get_all_level_actors()
        return {"level_name": world.get_name(), "actor_count": len(actors)}
```

Python conventions:

- Place modules under a plugin `Content/Python/` directory.
- Decorate the class with `@unreal.uclass()` and inherit from `unreal.ToolsetDefinition`.
- Mark each advertised static method with `@toolset_registry.tool_call`.
- Use type hints and Google-style `Args:` / `Returns:` docstrings because they drive the tool schema.
- Omit `@toolset_registry.tool_call` for helpers that should not be advertised.

C++ conventions:

- Derive from `UToolsetDefinition`.
- Mark the class `UCLASS(BlueprintType, Hidden)`.
- Expose static methods with `UFUNCTION(meta = (AICallable))`.
- Use reflected parameter and return types, preferably structured `USTRUCT` results.
- Add `meta = (AIIgnore)` to suppress an otherwise eligible function.

After authoring:

- Run `ModelContextProtocol.RefreshTools` to force a registry re-poll.
- Live Coding can pick up changes to existing C++ function bodies.
- Adding a new `UFUNCTION` requires a full editor restart.
- Connected clients may hold old schemas; refresh tools and reconnect the client when schemas stay stale.

Direct registration:

- Use `IModelContextProtocolModule::AddTool()` for runtime/dynamic tools whose schemas are not reflection-driven.
- Directly registered tools run on the game thread as well.
- The caller owns deregistration when the tool lifetime ends.

## Runtime And Cooked Builds

`ModelContextProtocol` and `ModelContextProtocolEngine` can host a server outside the editor, including cooked and shipping builds when started through code. The Toolset Registry adapter is editor-only. Toolsets discovered through `ToolsetRegistry` are not auto-discovered in cooked builds; register runtime tools explicitly through `IModelContextProtocolModule::AddTool()`.

Tool Search meta-tools are also part of the editor-only adapter. Cooked-build direct registrations advertise tools eagerly.

## Limits And Diagnostics

- UE 5.8 MCP is experimental; API and schema details may change.
- Supported transports are HTTP and Server-Sent Events only; `stdio` and WebSocket are not supported.
- Default binding is loopback/localhost only. Non-loopback `Origin` headers are rejected.
- There is no authentication layer. Do not expose Unreal MCP beyond the local machine.
- Built-in shipping Toolsets do not broadly advertise MCP Resources or Prompts.
- Tool calls execute on the Unreal game thread serially. Do not issue overlapping dependent calls.
- Use Output Log, `LogModelContextProtocol`, `ModelContextProtocol.RefreshTools`, and MCP Inspector when tools are missing or schemas look stale.
- Launch MCP Inspector with `npx @modelcontextprotocol/inspector`, then connect to `http://127.0.0.1:8000/mcp` with Streamable HTTP.

Risk classification:

| Level | Examples | Handling |
|---|---|---|
| Read-only | `list_toolsets`, `describe_toolset`, current level, logs, graph refs, node infos, selected/open assets, `ListSkills`, `GetSkills` | Safe default; still use live schemas |
| Context reads | camera, viewport, Content Browser path, PIE status, selected actors/assets | Safe for inspection; avoid changing selection unless needed |
| Mutating editor state | create, move, delete, import, save, compile, set transform, set selection, run tests, Live Coding, PIE, plugin/config edits, AgentSkill create/update | Require task justification; inspect before and verify after |

Log classification:

- `LogModelContextProtocol`: primary signal for MCP server startup, sessions, tool registration, and tool refresh.
- `LogToolsetRegistry`: Toolset discovery, schema generation, and AgentSkill-related issues.
- `LogPython`: Python Toolset import or execution failures.
- Blueprint compiler categories: Blueprint graph or compile failures.
- `LogHttp` requests to `datarouter.ol.epicgames.com`: usually Epic telemetry upload noise. These warnings alone do not prove MCP transport failure.

Observed local call-shape pitfalls:

- `call_tool` expects short tool names with `toolset_name`, even if `describe_toolset` returns fully qualified names.
- Some schemas mark seemingly optional filters as required. Use empty strings or empty arrays only after confirming the schema, for example `find_actors` with `name: ""`, `tag: ""`, and `collision_channels: []`.
- For Blueprint graphs, use graph refs returned by `get_graph` or `list_graphs`, such as `/Game/...Blueprint.Blueprint:EventGraph`. Space-separated graph paths can fail EdGraph validation.
- `read_graph_dsl` can return an empty string for graphs that still contain nodes. Treat it as an optional decompiler, not the only way to inspect logic.
- To inspect Blueprint logic reliably, call `find_nodes` with `title: ""`, then pass returned node refs to `get_node_infos`. For one execution chain, call `get_connected_subgraph` with an event/input node ref. These return `input_pins`, `output_pins`, `connected_pins`, node positions, and `type_id`.
- `EditorToolset.LogsToolset.GetLogEntries` may default `category` to a missing category; pass `category: ""` for all logs.
- `AutomationTestToolset.DiscoverTests` can emit UE warnings before useful JSON state is available. Follow with `ListTests` or inspect logs before treating the session as failed.

## Public Case Boundary

Keep these public examples out of the official UE MCP capability model:

| Example type | What it can inform | What it must not imply |
|---|---|---|
| Jianying/CapCut MCP projects | General automation patterns and the need to distinguish runtime control from file/API wrappers | UE 5.8 Toolset names, Unreal Editor capabilities, or official `ModelContextProtocol` behavior |
| Third-party Unreal MCP projects | Task ideas such as level generation, viewport verification, Blueprint automation, and project analysis | Replacement for official UE 5.8 Tool Search, ToolsetRegistry, or schemas returned by `describe_toolset` |

If a user asks about Jianying/CapCut control, answer that it is a separate MCP ecosystem. UE 5.8 official Unreal MCP controls the Unreal Editor, not Jianying/CapCut.
