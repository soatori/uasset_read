"""IR (Intermediate Representation) data structures — PackageIR hierarchy model.

IR is the unified data source for parse results; renderers only receive PackageIR
and do not access ParseResult. All GUIDs (Node/Pin) are normalized to 32-char
lowercase hex.

Layering:
- This module (ir.py) defines presentation models: simplified representation for
  renderers (str type, str direction, etc.)
- models/core.py defines serialization models, preserving UE native types
  (int direction, nested objects, etc.)
- IR Builder converts serialization models (UEdGraph*) to presentation models
  (GraphIR*).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .diagnostics import OffsetRangeDiagnostic, StructuredDiagnostic


@dataclass
class PackageHeaderIR:
    """Package header info, fully aligned with UE file format.

    Fields sourced from PackageFileSummary (UE's FPackageFileSummary).
    """
    # Core fields (required)
    package_name: str
    package_class: str
    package_flags: int
    total_export_count: int
    total_import_count: int
    ue_version: str
    saved_hash: bytes = field(default_factory=lambda: b'')

    # File version
    file_version_ue4: int = 0
    file_version_ue5: int = 0
    file_version_licensee: int = 0

    # Header structure offset
    total_header_size: int = 0
    custom_versions: list[dict] = field(default_factory=list)
    folder_name: str = ""

    # Name table
    name_count: int = 0
    name_offset: int = 0

    # Soft reference path table
    soft_object_paths_count: int = 0
    soft_object_paths_offset: int = 0

    # Localization
    localization_id: str = ""

    # Gatherable text data
    gatherable_text_data_count: int = 0
    gatherable_text_data_offset: int = 0

    # Export/Import table
    export_count: int = 0
    export_offset: int = 0
    import_count: int = 0
    import_offset: int = 0

    # Metadata
    metadata_offset: int = 0

    # Dependency table
    depends_offset: int = 0

    # Soft package references
    soft_package_references_count: int = 0
    soft_package_references_offset: int = 0

    # Searchable names
    searchable_names_offset: int = 0

    # Thumbnail table
    thumbnail_table_offset: int = 0

    # Import type hierarchies
    import_type_hierarchies_count: int = 0
    import_type_hierarchies_offset: int = 0

    # Persistent GUID
    persistent_guid: str = "00000000000000000000000000000000"

    # Version generations
    generations: list[dict] = field(default_factory=list)

    # Engine version
    saved_by_engine_version: str = ""
    compatible_with_engine_version: str = ""

    # Compression
    compression_flags: int = 0

    # Package source
    package_source: int = 0

    # Bulk data
    bulk_data_start_offset: int = 0

    # World tile info
    world_tile_info_data_offset: int = 0

    # Chunk IDs
    chunk_ids: list[int] = field(default_factory=list)

    # Preload dependencies
    preload_dependency_count: int = 0
    preload_dependency_offset: int = 0

    # Name reference count
    names_referenced_from_export_data_count: int = 0

    # Payload TOC
    payload_toc_offset: int = 0

    # Data resources
    data_resource_offset: int = 0

    # Enriched summary fields
    total_properties: int = 0
    total_name_entries: int = 0


@dataclass
class PinIR:
    """Single Pin presentation model (IR layer).

    Differences from serialization model UEdGraphPin:
    - direction is str ("EGPD_Input"/"EGPD_Output") instead of int
    - pin_category/pin_subcategory etc. are structured fields replacing
      _safe_str() stringification of FEdGraphPinType
    - linked_to is a list of str GUIDs instead of UObjectInstance list

    Added fields (v0.5.2) corresponding to 10 FEdGraphPinType structured attributes:
    - pin_category: Pin type category ("bool"/"int"/"float"/"object"/"struct"/"exec" etc.)
    - pin_subcategory: Pin subtype (e.g. "bool"->"int" subtype path)
    - pin_subcategory_object: Resolved PinSubCategoryObject name (e.g. "/Script/Engine.Actor")
    - container_type: Container type ("None"/"Array"/"Set"/"Map"), maps to EPinContainerType
    - is_reference: Passed by reference
    - is_const: Immutable constant
    - is_weak_pointer: Weak reference
    - is_uobject_wrapper: UObject wrapper type (e.g. TSubclassOf)
    - is_map_key: Map container key type flag (from PinValueType)
    - is_map_value: Map container value type flag (from PinValueType)
    """
    pin_name: str
    pin_type: str  # Backward compat: FEdGraphPinType _safe_str() output
    linked_to: list[str]
    direction: str
    default_value: str | None
    pin_guid: str = ""  # Pin GUID (used to build pin_guid -> node_guid index)
    # --- Structured type fields (FEdGraphPinType decomposition) ---
    pin_category: str = ""
    pin_subcategory: str = ""
    pin_subcategory_object_name: str | None = None
    container_type: str = "None"
    is_reference: bool = False
    is_const: bool = False
    is_weak_pointer: bool = False
    is_uobject_wrapper: bool = False
    is_map_key: bool = False
    is_map_value: bool = False
    # Map terminal type fields (Map container specific)
    map_key_pin_category: str = ""
    map_key_pin_subcategory: str = ""
    map_key_pin_subcategory_object_name: str | None = None


@dataclass
class NodeIR:
    """Single node presentation model (IR layer).

    Differences from serialization model UEdGraphNode:
    - node_class is str, corresponding to UEdGraphNode.class_name
    - pins is list[PinIR] instead of list[UEdGraphPin]
    - Contains IR-specific fields like execution_flow and macro_expansion
    - Does not contain node_pos_x/y (not needed by renderers)
    """
    node_guid: str
    node_class: str
    node_comment: str | None
    pins: list[PinIR]
    execution_flow: list[dict]
    macro_expansion: dict | None = None
    # Enhanced Input related fields (v0.5.2)
    input_action_path: str | None = None  # Input Action asset path
    trigger_events: list[dict] = field(default_factory=list)  # Trigger events list
    event_type: str | None = None  # Event type (Triggered/Completed/Started/Stopped/Ongoing)


@dataclass
class GraphIR:
    """Single graph presentation model (IR layer).

    Differences from serialization model UEdGraph:
    - nodes is list[NodeIR] instead of list[UEdGraphNode]
    - Contains IR-specific fields like execution_chains
    - Does not contain schema/b_editable (not needed by renderers)
    """
    graph_guid: str
    graph_name: str
    graph_class: str
    nodes: list[NodeIR]
    execution_chains: list[list[str]]
    subgraphs: list["GraphIR"] = field(default_factory=list)
    graph_type: str | None = None


@dataclass
class PropertyIR:
    """Single property IR representation."""
    name: str
    type: str
    value: Any
    array_index: int
    guid: str | None


@dataclass
class ExportRawIR:
    """UE raw export table fields (corresponds to FObjectExport).

    Preserves all UE serialization table fields, isolated from the parsed
    semantic fields (ExportIR).

    Note: package_flags corresponds to FObjectExport.PackageFlags, only meaningful
    when the export is a top-level package forced into the export table via
    OBJECTMARK_ForceTagExp (stores the original package flags).
    Different from PackageHeaderIR.package_flags (FPackageFileSummary.PackageFlags).
    See ObjectResource.h:359-363.
    """
    class_index: int = 0
    super_index: int = 0
    outer_index: int = 0
    template_index: int = 0
    object_flags: int = 0
    serial_offset: int = 0
    package_flags: int = 0  # FObjectExport.PackageFlags (only meaningful for top-level package exports)
    b_forced_export: bool = False
    b_not_for_client: bool = False
    b_not_for_server: bool = False
    b_is_inherited_instance: bool = False
    b_not_always_loaded_for_editor_game: bool = False
    b_is_asset: bool = False
    b_generate_public_hash: bool = False
    script_serialization_start_offset: int = 0
    script_serialization_end_offset: int = 0
    guid: str = ""


@dataclass
class ImportIR:
    """Single import object IR representation, aligned with UE's FObjectImport."""
    index: int
    class_package: str
    class_name: str
    object_name: str
    outer_index: int = 0
    is_asset: bool = False
    package_flags: int = 0
    outer_index_resolved: str | None = None
    package_name: str = ""
    b_import_optional: bool = False


@dataclass
class ExportIR:
    """Single export object IR representation."""
    index: int
    object_name: str
    object_class: str
    serial_size: int
    outer_index_resolved: str | None
    super_index_resolved: str | None
    parent_class: str | None
    properties: list[PropertyIR]
    graphs: list[GraphIR]
    bulk_data: dict | None
    parse_status: str = "success"
    fallback_reason: str | None = None
    error_message: str | None = None
    asset_type_data: dict | None = None
    anim_blueprint: AnimBlueprintIR | None = None
    anim_sequence: AnimSequenceIR | None = None
    anim_montage: AnimMontageIR | None = None
    ue_export_raw: ExportRawIR | None = None
    diagnostics: dict | None = None
    # Lazy load flag
    is_loaded: bool = False
    lazy_load_archive: bytes | None = None

    # --- Proxied properties from ExportRawIR (backward compat) ---

    @property
    def template_index(self) -> int:
        return self.ue_export_raw.template_index if self.ue_export_raw else 0

    @property
    def object_flags(self) -> int:
        return self.ue_export_raw.object_flags if self.ue_export_raw else 0

    @property
    def package_flags(self) -> int:
        return self.ue_export_raw.package_flags if self.ue_export_raw else 0

    @property
    def b_forced_export(self) -> bool:
        return self.ue_export_raw.b_forced_export if self.ue_export_raw else False

    @property
    def b_not_for_client(self) -> bool:
        return self.ue_export_raw.b_not_for_client if self.ue_export_raw else False

    @property
    def b_not_for_server(self) -> bool:
        return self.ue_export_raw.b_not_for_server if self.ue_export_raw else False

    @property
    def b_is_asset(self) -> bool:
        return self.ue_export_raw.b_is_asset if self.ue_export_raw else False

    @property
    def b_generate_public_hash(self) -> bool:
        return self.ue_export_raw.b_generate_public_hash if self.ue_export_raw else False

    @property
    def b_not_always_loaded_for_editor_game(self) -> bool:
        return self.ue_export_raw.b_not_always_loaded_for_editor_game if self.ue_export_raw else False

    @property
    def guid(self) -> str:
        return self.ue_export_raw.guid if self.ue_export_raw else ""


@dataclass
class ExportDependencyIR:
    """Export dependency relationships.

    Corresponds to dependency fields in UE's FExportMapEntry.
    Describes serialization and creation order dependencies between exports.
    """
    export_index: int
    serialization_before_serialization: list[int]
    create_before_serialization: list[int]
    serialization_before_create: list[int]
    create_before_create: list[int]


@dataclass
class BlueprintFunctionIR:
    """Blueprint function IR (full metadata, equivalent to UFunction description)."""
    name: str
    return_type: str
    parameters: list[dict]
    function_flags: int = 0
    is_implemented: bool = True  # False = inherited event placeholder (e.g. ReceiveBeginPlay)
    is_pure: bool = False
    is_blueprint_callable: bool = False
    is_const: bool = False
    is_static: bool = False
    is_net: bool = False
    is_net_reliable: bool = False
    is_blueprint_private: bool = False
    access_specifier: str = "Public"
    meta_data: dict = field(default_factory=dict)
    implementation: dict | None = None
    function_graph: dict | None = None
    implementation_status: str = "missing"  # "decompiled"|"graph_only"|"metadata_only"|"missing"


@dataclass
class BlueprintEventIR:
    """Blueprint event IR (full metadata, equivalent to blueprint event description)."""
    name: str
    event_type: str
    parameters: list[dict]
    function_flags: int = 0
    is_override: bool = False
    override_parent_class: str = ""
    override_parent_event: str = ""
    is_interface_event: bool = False
    interface_class: str = ""
    is_net: bool = False
    is_net_multicast: bool = False
    is_replicated: bool = False
    is_cosmetic: bool = False
    is_static: bool = False
    meta_data: dict = field(default_factory=dict)
    implementation: dict | None = None
    function_graph: dict | None = None
    implementation_status: str = "missing"  # "decompiled"|"graph_only"|"metadata_only"|"missing"


@dataclass
class BlueprintIR:
    """Blueprint metadata IR (from BlueprintMetadata)."""
    parent_class: str | None
    description: str = ""
    interfaces: list[dict] = field(default_factory=list)
    functions: list[BlueprintFunctionIR] = field(default_factory=list)
    events: list[BlueprintEventIR] = field(default_factory=list)
    components: list[dict] = field(default_factory=list)


@dataclass
class DecompiledFunctionIR:
    """Decompiled function IR (from KismetDecompiledResult)."""
    name: str
    signature: str
    cpp_code: str
    parameters: list[dict]
    return_type: str
    fallback_reasons: list[str] = field(default_factory=list)
    bytecode_confidence: str = "verified"
    # "verified" | "fallback" | "heuristic" | "graph_topology" | "failed"
    bytecode_status: str = "unknown"   # "parsed" | "failed" | "unknown"
    bytecode_source: str = "unknown"   # "function_export" | "fallback_or_serial_scan" | "unknown"
    logic_source: str = "current_asset"  # "current_asset" | "graph_topology"
    warnings: list[str] = field(default_factory=list)


@dataclass
class ExecutionChainIR:
    """Execution chain IR."""
    event: str
    chain: list[str]


@dataclass
class FunctionGraphIR:
    """Function graph data (based on _build_function_graphs_safe() actual fields)."""
    function_name: str
    graph_source: str = ""
    entry_node_guid: str = ""
    signature: dict = field(default_factory=dict)
    execution_flows: list[dict] = field(default_factory=list)
    fallback_reason: str | None = None


@dataclass
class LinkerSummaryIR:
    """Package linker summary."""
    has_linker: bool
    import_paths: list[str]
    export_paths: list[str]


@dataclass
class VariableIR:
    """Blueprint variable IR (full metadata, equivalent to FBPVariableDescription)."""
    name: str
    type: str
    default_value: str | None
    kind: str = "user"  # "user" | "component" | "input_action" | "metadata"
    guid: str | None = None
    category: str = ""
    property_flags: int = 0
    replication_condition: int = 0
    rep_notify_func: str = ""
    friendly_name: str = ""
    metadata: dict = field(default_factory=dict)
    flags_labels: list[str] = field(default_factory=list)
    edit_condition: str = ""
    is_edit_anywhere: bool = False
    is_visible_anywhere: bool = False
    is_blueprint_read_only: bool = False
    is_transient: bool = False
    is_replicated: bool = False
    is_rep_notify: bool = False
    is_expose_on_spawn: bool = False
    is_save_game: bool = False


@dataclass
class SourceSiteContextIR:
    """Localization context information — FTextSourceSiteContext.

    Reference: GatherableTextData.h:12
    Describes where text is used in source code and its localization attributes.
    """
    key_name: str
    site_description: str
    is_editor_only: bool
    is_optional: bool


@dataclass
class GatherableTextDataIR:
    """Gatherable text data — FGatherableTextData.

    Reference: GatherableTextData.h:49
    Contains namespace name, source string, and source context list.
    """
    namespace_name: str
    source_string: str
    source_site_contexts: list[SourceSiteContextIR]


@dataclass
class HexViewEntryIR:
    """Single read operation IR representation (converted from HexViewEntry)."""
    key: str
    type: str
    value: Any
    start: int
    stop: int
    size: int
    field_path: str | None = None
    semantic_type: str | None = None
    value_hex: str | None = None
    value_size: int | None = None


@dataclass
class DebugIR:
    """Debug data IR (parsing trace information)."""
    hex_view: list[HexViewEntryIR] = field(default_factory=list)
    hex_view_truncated_count: int = 0
    """Number of hex view entries dropped by BoundedEventBuffer truncation."""


@dataclass
class AnimationDataIR:
    """Animation data aggregation."""
    anim_blueprint: AnimBlueprintIR | None = None
    anim_sequence: AnimSequenceIR | None = None
    anim_montage: AnimMontageIR | None = None


@dataclass
class PackageDependenciesIR:
    """Package dependency data."""
    resolved_parent_assets: list[dict] = field(default_factory=list)
    inherited_blueprint_graphs: list[dict] = field(default_factory=list)
    depends_map: list[list[int]] = field(default_factory=list)
    resolved_depends_map: list[list[dict]] = field(default_factory=list)
    soft_object_paths: list[dict] = field(default_factory=list)
    soft_package_references: list[str] = field(default_factory=list)
    asset_registry_data_offset: int = 0
    asset_registry_data: dict | None = None


@dataclass
class DiagnosticsDataIR:
    """Diagnostic and status data."""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    status: str = "success"
    status_message: str | None = None
    status_code: str | None = None
    diagnostics_truncated_count: int = 0
    """Number of diagnostics entries dropped by BoundedEventBuffer truncation."""


@dataclass
class PackageIR:
    """Top-level IR structure (recomposed)."""
    header: PackageHeaderIR
    name_map: tuple[str, ...]
    imports: list[ImportIR]  # Fix: original list[dict] was a type annotation bug
    exports: list[ExportIR]
    linker: LinkerSummaryIR | None
    blueprint: BlueprintIR | None = None
    decompiled_functions: list[DecompiledFunctionIR] = field(default_factory=list)
    execution_chains: list[ExecutionChainIR] = field(default_factory=list)
    variables: list[VariableIR] = field(default_factory=list)
    animation: AnimationDataIR | None = None
    diagnostics: list[OffsetRangeDiagnostic | StructuredDiagnostic] = field(default_factory=list)
    function_graphs: list[dict] = field(default_factory=list)
    logic_sources: list[dict] = field(default_factory=list)
    dependencies: PackageDependenciesIR | None = None
    diagnostics_data: DiagnosticsDataIR | None = None
    debug: DebugIR | None = None
    import_map: list[dict] = field(default_factory=list)
    name_map_entries: list[str] = field(default_factory=list)
    statistics: dict = field(default_factory=dict)


# Animation models re-exported from ir_anim.py for backward compat
from .ir_anim import (  # noqa: F401
    AnimNotifyIR,
    BakedExitTransitionIR,
    BakedStateIR,
    BakedTransitionIR,
    BakedStateMachineIR,
    AnimBlueprintIR,
    AnimSequenceIR,
    AnimMontageIR,
)
