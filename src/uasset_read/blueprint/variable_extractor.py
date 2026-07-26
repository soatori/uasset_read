"""Blueprint variable extraction module -- extracts blueprint variables, functions, and event metadata from property data.

Standalone module (per D-02), shared by property parsing and blueprint graph parsing.
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

from uasset_read.models.blueprint import BlueprintVariable, BlueprintMetadata, BlueprintFunction, BlueprintEvent, FunctionParameter
from uasset_read.models.properties import PropertyValue, StructValue
from uasset_read.models.core import FEdGraphPinType
from uasset_read.parsers.property_types import parse_default_value
from uasset_read.serializers.graph import read_ed_graph_pin_type
from uasset_read.constants import (
    CPF_Edit, CPF_EditConst, CPF_BlueprintVisible, CPF_BlueprintReadOnly,
    CPF_Transient, CPF_BlueprintAssignable, CPF_RepNotify, CPF_SaveGame,
    CPF_Net, CPF_InstancedReference, CPF_Config, CPF_Deprecated,
    CPF_Protected, CPF_ExposeOnSpawn,
    CPF_DuplicateTransient, CPF_NoClear, CPF_BlueprintCallable, CPF_Interp,
    CPF_NonPIEDuplicateTransient, format_guid_bytes, UE_NONE_SENTINEL,
)

# UE property type name -> standardized pin_category mapping
# Used to convert serialized names like "BoolProperty" to standard pin_category like "bool"
_PROPERTY_TYPE_TO_PIN_CATEGORY: Dict[str, str] = {
    "BoolProperty": "bool",
    "IntProperty": "int",
    "Int64Property": "int64",
    "UInt32Property": "uint32",
    "FloatProperty": "float",
    "DoubleProperty": "double",
    "StrProperty": "string",
    "NameProperty": "name",
    "TextProperty": "text",
    "ObjectProperty": "object",
    "ClassProperty": "class",
    "ArrayProperty": "array",
    "StructProperty": "struct",
    "MapProperty": "map",
    "SetProperty": "set",
    "EnumProperty": "byte",
    "ByteProperty": "byte",
    "DelegateProperty": "delegate",
    "MulticastDelegateProperty": "multicast_delegate",
    "InterfaceProperty": "interface",
    "WeakObjectProperty": "weak_object",
    "LazyObjectProperty": "lazy_object",
    "SoftObjectProperty": "soft_object",
    "SoftClassProperty": "soft_class",
}

# ============================================================================
# Pin Category to C++ type mapping
# ============================================================================

_PIN_CATEGORY_TO_CPP_TYPE = {
    # Basic types
    "real": "float",
    "double": "double",
    "float": "float",
    "int": "int32",
    "int32": "int32",
    "int64": "int64",
    "byte": "uint8",
    "bool": "bool",
    "boolean": "bool",
    # String types
    "string": "FString",
    "name": "FName",
    "text": "FText",
    # Struct types
    "struct": "FStruct",
    "vector": "FVector",
    "rotator": "FRotator",
    "transform": "FTransform",
    "vector2d": "FVector2D",
    "linearcolor": "FLinearColor",
    "guid": "FGuid",
    # Object types
    "object": "UObject*",
    "class": "UClass*",
    "widget": "UWidget*",
    # Special types
    "wildcard": "Wildcard",
    "exec": "void",
    "delegate": "void",
    "multicastdelegate": "void",
}

def _map_pin_category_to_cpp_type(pin_category: str) -> str:
    """Map pin_category to C++ type.

    Args:
        pin_category: Pin type name (e.g. "real", "object", "struct")

    Returns:
        C++ type string
    """
    normalized = pin_category.strip()

    # Exact match
    if normalized in _PIN_CATEGORY_TO_CPP_TYPE:
        return _PIN_CATEGORY_TO_CPP_TYPE[normalized]

    # Case-insensitive match
    lower_category = normalized.lower()
    for key, value in _PIN_CATEGORY_TO_CPP_TYPE.items():
        if key.lower() == lower_category:
            return value

    # If it's an object type path (starts with /Script/), return directly
    if normalized.startswith("/Script/"):
        return normalized

    # Default: return the original type name
    return normalized

# Blueprint asset metadata property names (not user-defined variables)
BLUEPRINT_METADATA_PROPERTY_NAMES = frozenset({
    # Core blueprint metadata
    "ParentClass",
    "ParentClassProperty",
    "SuperClass",
    "BlueprintGuid",
    "BlueprintCategory",
    "BlueprintDescription",
    "BlueprintType",
    "IsBlueprintBase",
    "KismetSchemaDeprecationWarning",
    "NativeParent",
    "ObjectArchitecture",
    "ObjectParentClass",
    "SupportedClasses",
    "HiddenCategories",
    "ModulesToIgnoreInReloadAndBlueprints",
    "None",  # Sentinel marker
    "NoneProperty",
    # Internal engine properties (not user-defined variables)
    "CachedEditorData",
    "BlueprintStatus",
    "BlueprintLogLevel",
    "BlueprintCompileOptions",
    "BlueprintGeneratedClass",
    "OriginalClassName",
    "HasBeenRegenerated",
    "RegenerateClassAttemptCount",
    "bBeingCompiled",
    "bCompiled",
    "bRegenerating",
    "bDuplicating",
    "bImportedFromAnotherAsset",
    "bCanUseSimplifiedConstructor",
    "bIsNewObject",
    "bHasDocumentedClass",
    "bDisplayCompileSucceededLog",
    "bForceFullDeployment",
    "bQueuedForDeletion",
    "bRecompileOnLoad",
    "bDisableCompileOnLoad",
    "bDeferCompilation",
    "bForceCompilation",
    "bCreateNewModule",
    "bLoadPublicModules",
    "bRecompileAfterLoad",
    "bEnableParallelCompilation",
    "bEnableCompilation",
    "bForceReregistration",
    "bForceRegeneration",
    "bIsIncrementalCompile",
    "bIsRegeneratingOnLoad",
    "bIsRegenerating",
    "bIsRegeneratingClass",
    "bIsRegeneratingInterface",
    "bIsRegeneratingStruct",
    "bIsRegeneratingEnum",
    "bIsRegeneratingFunction",
    "bIsRegeneratingVariable",
    "bIsRegeneratingEvent",
    "bIsRegeneratingDelegate",
    "bIsRegeneratingInterfaceFunction",
    "bIsRegeneratingInterfaceVariable",
    "bIsRegeneratingInterfaceEvent",
    "bIsRegeneratingInterfaceDelegate",
    "bIsRegeneratingStructVariable",
    "bIsRegeneratingStructFunction",
    "bIsRegeneratingStructEvent",
    "bIsRegeneratingStructDelegate",
    "bIsRegeneratingEnumValue",
    "bIsRegeneratingEnumFunction",
    "bIsRegeneratingEnumEvent",
    "bIsRegeneratingEnumDelegate",
    # Rendering/editor related
    "SelectedNodes",
    "GraphZoom",
    "PanningAmount",
    "bAllowRenaming",
    "bAllowMultipleOutputs",
    "bAllowMultipleInputs",
    # Variable description array (already handled via NewVariables)
    "NewVariables",
    # Function/event lists
    "UbergraphGraph",
    "FunctionList",
    "EventGraphs",
})

def _is_internal_engine_property(prop_name: str) -> bool:
    """Determine if property is an internal engine property (not user-defined variable).

    Only matches explicit engine internal property names (e.g. compile status flags, blueprint generated class references).
    Does not use prefix matching to avoid filtering out legitimate blueprint variables (e.g. bIsPlayer, CachedHealth).
    """
    # Explicit internal engine property names (exact match)
    internal_exact_names = frozenset({
        # Compile/generation status flags
        "bBeingCompiled",
        "bCompiled",
        "bRegenerating",
        "bDuplicating",
        "bImportedFromAnotherAsset",
        "bCanUseSimplifiedConstructor",
        "bIsNewObject",
        "bHasDocumentedClass",
        "bDisplayCompileSucceededLog",
        "bForceFullDeployment",
        "bQueuedForDeletion",
        "bRecompileOnLoad",
        "bDisableCompileOnLoad",
        "bDeferCompilation",
        "bForceCompilation",
        "bCreateNewModule",
        "bLoadPublicModules",
        "bRecompileAfterLoad",
        "bEnableParallelCompilation",
        "bEnableCompilation",
        "bForceReregistration",
        "bForceRegeneration",
        "bIsIncrementalCompile",
        "bIsRegeneratingOnLoad",
        "bIsRegenerating",
        "bIsRegeneratingClass",
        "bIsRegeneratingInterface",
        "bIsRegeneratingStruct",
        "bIsRegeneratingEnum",
        "bIsRegeneratingFunction",
        "bIsRegeneratingVariable",
        "bIsRegeneratingEvent",
        "bIsRegeneratingDelegate",
        "bIsRegeneratingInterfaceFunction",
        "bIsRegeneratingInterfaceVariable",
        "bIsRegeneratingInterfaceEvent",
        "bIsRegeneratingInterfaceDelegate",
        "bIsRegeneratingStructVariable",
        "bIsRegeneratingStructFunction",
        "bIsRegeneratingStructEvent",
        "bIsRegeneratingStructDelegate",
        "bIsRegeneratingEnumValue",
        "bIsRegeneratingEnumFunction",
        "bIsRegeneratingEnumEvent",
        "bIsRegeneratingEnumDelegate",
        # Blueprint generated class references
        "BlueprintGeneratedClass",
        # Editor related
        "SelectedNodes",
        "GraphZoom",
        "PanningAmount",
        "bAllowRenaming",
        "bAllowMultipleOutputs",
        "bAllowMultipleInputs",
    })

    return prop_name in internal_exact_names


def _map_property_flags(flags: int) -> Dict[str, bool]:
    """Map CPF_* bit flags to BlueprintVariable boolean attributes."""
    return {
        "is_edit_anywhere": bool(flags & CPF_Edit),
        "is_edit_instance_only": bool(flags & CPF_Edit) and not bool(flags & CPF_EditConst),
        "is_blueprint_readable": bool(flags & CPF_BlueprintVisible),
        "is_blueprint_read_only": bool(flags & CPF_BlueprintReadOnly),
        "is_net": bool(flags & CPF_Net),
        "is_replicated": bool(flags & CPF_Net),
        "is_transient": bool(flags & CPF_Transient),
        "is_blueprint_assignable": bool(flags & CPF_BlueprintAssignable),
        "is_rep_notify": bool(flags & CPF_RepNotify),
        "is_save_game": bool(flags & CPF_SaveGame),
    }

def _extract_pin_type_from_property(prop: PropertyValue) -> FEdGraphPinType:
    """Extract FEdGraphPinType type information from PropertyValue."""
    value = prop.value

    # StructProperty: look up pin_category, pin_subcategory, etc.
    if isinstance(value, dict):
        pin_category = value.get("pin_category", "")
        pin_subcategory = value.get("pin_subcategory", "")
        pin_subcategory_object = value.get("pin_subcategory_object")
        container_type = value.get("container_type", 0)

        # Handle StructValue objects (advanced property containers)
        if hasattr(prop, "type") and prop.type == "StructProperty":
            if isinstance(value, dict):
                pin_category = value.get("PinCategory", value.get("pin_category", ""))
                pin_subcategory = value.get("PinSubcategory", value.get("pin_subcategory", ""))
                if "PinSubcategoryObject" in value:
                    pin_subcategory_object = value["PinSubcategoryObject"]
                elif "pin_subcategory_object" in value:
                    pin_subcategory_object = value["pin_subcategory_object"]

        # When dict is a property value (containing object_class / struct_type) rather than a pin type dict,
        # infer type info from prop.type and dict content
        prop_type = getattr(prop, 'type', None)
        if not pin_category and prop_type:
            pin_category = _PROPERTY_TYPE_TO_PIN_CATEGORY.get(prop_type, "")
        if not pin_subcategory and prop_type:
            if prop_type in ("ObjectProperty", "ClassProperty"):
                pin_subcategory = value.get("object_class", value.get("object_name", ""))
            elif prop_type == "StructProperty":
                pin_subcategory = value.get("struct_type", "")

        # Standardize pin_category: convert UE internal type names like "BoolProperty" to standard names like "bool"
        if pin_category in _PROPERTY_TYPE_TO_PIN_CATEGORY:
            pin_category = _PROPERTY_TYPE_TO_PIN_CATEGORY[pin_category]

        return FEdGraphPinType(
            pin_category=pin_category,
            pin_subcategory=pin_subcategory,
            pin_subcategory_object=pin_subcategory_object,
            container_type=container_type,
        )

    # Simple type mapping
    type_mapping = {
        "BoolProperty": FEdGraphPinType(pin_category="bool"),
        "IntProperty": FEdGraphPinType(pin_category="int"),
        "Int64Property": FEdGraphPinType(pin_category="int64"),
        "FloatProperty": FEdGraphPinType(pin_category="float"),
        "DoubleProperty": FEdGraphPinType(pin_category="double"),
        "StrProperty": FEdGraphPinType(pin_category="string"),
        "NameProperty": FEdGraphPinType(pin_category="name"),
        "TextProperty": FEdGraphPinType(pin_category="text"),
        "ObjectProperty": FEdGraphPinType(pin_category="object"),
        "ClassProperty": FEdGraphPinType(pin_category="class"),
        "ArrayProperty": FEdGraphPinType(pin_category="array"),
        "StructProperty": FEdGraphPinType(pin_category="struct"),
        "MapProperty": FEdGraphPinType(pin_category="map"),
        "SetProperty": FEdGraphPinType(pin_category="set"),
        "EnumProperty": FEdGraphPinType(pin_category="byte", pin_subcategory="enum"),
        "ByteProperty": FEdGraphPinType(pin_category="byte"),
        "DelegateProperty": FEdGraphPinType(pin_category="delegate"),
        "MulticastDelegateProperty": FEdGraphPinType(pin_category="multicast_delegate"),
        "InterfaceProperty": FEdGraphPinType(pin_category="interface"),
        "WeakObjectProperty": FEdGraphPinType(pin_category="weak_object"),
        "LazyObjectProperty": FEdGraphPinType(pin_category="lazy_object"),
        "SoftObjectProperty": FEdGraphPinType(pin_category="soft_object"),
        "SoftClassProperty": FEdGraphPinType(pin_category="soft_class"),
    }

    # Non-dict values: look up standardized pin_category based on prop.type
    prop_type = getattr(prop, 'type', None)
    if prop_type and prop_type in type_mapping:
        return type_mapping[prop_type]

    # Fallback: standardize property type name to pin_category
    pin_category = "unknown"
    if prop_type:
        pin_category = _PROPERTY_TYPE_TO_PIN_CATEGORY.get(prop_type, prop_type)
    return FEdGraphPinType(pin_category=pin_category)

def extract_blueprint_variables(properties: List[PropertyValue]) -> List[BlueprintVariable]:
    """Extract blueprint variables from parsed property data.

    Iterates through PropertyValue list, identifies variable-related properties (containing name, type, category,
    flags, etc.), and converts them to BlueprintVariable instances.

    Args:
        properties: Parsed property value list

    Returns:
        List of BlueprintVariable instances
    """
    variables: List[BlueprintVariable] = []

    if not properties:
        return variables

    # Find variable description properties
    # UE blueprint variables typically appear in properties with a specific pattern
    # We iterate through all properties to identify possible variable definitions
    for prop in properties:
        prop_name = prop.name
        prop_value = prop.value

        if prop_name == "NewVariables" and isinstance(prop_value, list):
            variables.extend(_extract_blueprint_variable_descriptions(prop_value))
            continue

        # Skip sentinel markers, system properties, and blueprint metadata properties
        if prop_name in BLUEPRINT_METADATA_PROPERTY_NAMES:
            continue

        # Additional filter: skip properties starting with common internal engine property names
        # These properties are typically not user-defined blueprint variables
        if _is_internal_engine_property(prop_name):
            continue

        # Detect if this is a blueprint variable description property
        # Variables typically carry type information and default values
        var_type = _extract_pin_type_from_property(prop)

        # Extract category from property value
        category = ""
        if isinstance(prop_value, dict):
            category = prop_value.get("Category", prop_value.get("category", ""))

        # Extract property flags
        property_flags = 0
        if isinstance(prop_value, dict):
            property_flags = prop_value.get("property_flags", prop_value.get("PropertyFlags", 0))

        # Check if this is a component variable
        is_component = False
        if hasattr(prop, "type") and prop.type in ("ObjectProperty", "ClassProperty"):
            type_name = var_type.pin_subcategory or var_type.pin_category
            component_keywords = ["Component", "SceneComponent", "ActorComponent"]
            is_component = any(kw in type_name for kw in component_keywords)

        # Build BlueprintVariable
        flag_mapping = _map_property_flags(property_flags)
        flags_labels = parse_property_flags_to_labels(property_flags)

        # Extract default value
        default_value = None
        if isinstance(prop_value, dict):
            default_value = prop_value.get("default_value", prop_value.get("DefaultValue"))
        else:
            default_value = prop_value

        # Extract metadata
        metadata = {}
        meta_class = ""
        edit_condition = ""
        if isinstance(prop_value, dict):
            for key, val in prop_value.items():
                if key.lower().startswith("meta"):
                    metadata[key] = str(val)
            meta_class = prop_value.get("meta_class", prop_value.get("MetaClass", ""))
            edit_condition = prop_value.get("edit_condition", prop_value.get("EditCondition", ""))

        # Infer additional variable type attributes
        is_blueprint_writable = flag_mapping.get("is_blueprint_readable", False) and not flag_mapping.get("is_blueprint_read_only", False)

        var = BlueprintVariable(
            var_name=prop_name,
            var_type=var_type,
            category=category,
            property_flags=property_flags,
            default_value=default_value,
            is_component=is_component,
            metadata=metadata,
            flags_labels=flags_labels,
            edit_condition=edit_condition,
            meta_class=meta_class,
            **flag_mapping,
            is_blueprint_writable=is_blueprint_writable,
        )
        variables.append(var)

    return variables

def _extract_blueprint_variable_descriptions(items: List[Any]) -> List[BlueprintVariable]:
    """Expand FBPVariableDescription structs from UBlueprint.NewVariables."""
    variables: List[BlueprintVariable] = []
    for item in items:
        fields = item.fields if isinstance(item, StructValue) else item if isinstance(item, dict) else None
        if not fields:
            continue
        var_name = fields.get("VarName") or fields.get("var_name")
        if not var_name:
            continue
        property_flags = int(fields.get("PropertyFlags") or fields.get("property_flags") or 0)
        flag_mapping = _map_property_flags(property_flags)
        flags_labels = parse_property_flags_to_labels(property_flags)
        category = _text_or_string(fields.get("Category") or fields.get("category"))
        default_value = fields.get("DefaultValue", fields.get("default_value"))
        rep_condition = fields.get("ReplicationCondition", fields.get("replication_condition", 0))
        var = BlueprintVariable(
            var_name=str(var_name),
            var_type=_extract_var_type_from_description(fields.get("VarType")),
            category=category,
            property_flags=property_flags,
            default_value=default_value,
            metadata=_metadata_from_description(fields.get("MetaDataArray")),
            flags_labels=flags_labels,
            **flag_mapping,
            is_blueprint_writable=flag_mapping.get("is_blueprint_readable", False)
            and not flag_mapping.get("is_blueprint_read_only", False),
        )
        var.var_guid = _guid_from_description(fields.get("VarGuid"))
        var.friendly_name = str(fields.get("FriendlyName") or fields.get("friendly_name") or "")
        var.rep_notify_func = str(fields.get("RepNotifyFunc") or fields.get("rep_notify_func") or "")
        var.replication_condition = _replication_condition_value(rep_condition)

        # Component variable detection (aligned with read_blueprint_variable logic)
        type_str = ""
        if var.var_type:
            if var.var_type.pin_subcategory and var.var_type.pin_subcategory.lower() != "none":
                type_str = var.var_type.pin_subcategory
            elif var.var_type.pin_category:
                type_str = var.var_type.pin_category
        is_component_by_name = isinstance(type_str, str) and "Component" in type_str
        is_component_by_flag = (property_flags & CPF_InstancedReference) != 0
        var.is_component = is_component_by_name or is_component_by_flag

        variables.append(var)
    return variables

def _extract_var_type_from_description(value: Any) -> FEdGraphPinType:
    if isinstance(value, StructValue):
        fields = value.fields
    elif isinstance(value, dict) and value.get("kind") == "binary_or_native_property":
        raw_category = str(value.get("type") or "unknown")
        return FEdGraphPinType(
            pin_category=_PROPERTY_TYPE_TO_PIN_CATEGORY.get(raw_category, raw_category),
        )
    elif isinstance(value, dict):
        fields = value
    else:
        return FEdGraphPinType(pin_category="unknown")
    raw_category = str(fields.get("PinCategory") or fields.get("pin_category") or "unknown")
    return FEdGraphPinType(
        pin_category=_PROPERTY_TYPE_TO_PIN_CATEGORY.get(raw_category, raw_category),
        pin_subcategory=str(fields.get("PinSubCategory") or fields.get("PinSubcategory") or fields.get("pin_subcategory") or ""),
        container_type=int(fields.get("ContainerType") or fields.get("container_type") or 0),
    )

def _guid_from_description(value: Any) -> str:
    # StructValue(Guid, {A:int, B:int, C:int, D:int}) -- StructProperty parsing result
    if isinstance(value, StructValue) and value.struct_type == "Guid":
        fields = value.fields
        a = int(fields.get("A", 0))
        b = int(fields.get("B", 0))
        c = int(fields.get("C", 0))
        d = int(fields.get("D", 0))
        # Convert each uint32 to 4 bytes in little-endian order
        def _u32_to_bytes(v: int) -> bytes:
            return v.to_bytes(4, byteorder='little')
        raw = _u32_to_bytes(a) + _u32_to_bytes(b) + _u32_to_bytes(c) + _u32_to_bytes(d)
        return format_guid_bytes(raw)

    if isinstance(value, dict) and value.get("kind") == "binary_or_native_property":
        raw = value.get("raw_data")
        if isinstance(raw, bytes) and len(raw) == 16:
            return format_guid_bytes(raw)
    # #143: Guid in struct_binary_decoded format
    if isinstance(value, dict) and value.get("kind") == "struct_binary_decoded":
        if value.get("struct_type") == "Guid":
            fields = value.get("fields", {})
            a = int(fields.get("A", 0))
            b = int(fields.get("B", 0))
            c = int(fields.get("C", 0))
            d = int(fields.get("D", 0))
            raw = (
                a.to_bytes(4, byteorder="little")
                + b.to_bytes(4, byteorder="little")
                + c.to_bytes(4, byteorder="little")
                + d.to_bytes(4, byteorder="little")
            )
            return format_guid_bytes(raw)
    if isinstance(value, bytes) and len(value) == 16:
        return format_guid_bytes(value)
    if isinstance(value, str):
        return value
    return ""

def _text_or_string(value: Any) -> str:
    if hasattr(value, "source_string"):
        return str(value.source_string)
    return str(value or "")

def _metadata_from_description(value: Any) -> Dict[str, str]:
    metadata: Dict[str, str] = {}
    if isinstance(value, list):
        for item in value:
            fields = item.fields if isinstance(item, StructValue) else item if isinstance(item, dict) else {}
            key = fields.get("Key") or fields.get("Name") or fields.get("key")
            if key:
                metadata[str(key)] = str(fields.get("Value") or fields.get("value") or "")
    return metadata

def _replication_condition_value(value: Any) -> int:
    if isinstance(value, int):
        return value
    if hasattr(value, "value_name"):
        text = str(value.value_name)
        if text.endswith("COND_None"):
            return 0
    return 0

def parse_component_transform(properties: List[PropertyValue]) -> Dict[str, Any]:
    """Extract component transform attributes from parsed property data.

    Identifies and extracts RelativeLocation, RelativeRotation, RelativeScale3D,
    Mobility and other component transform-related properties.

    Args:
        properties: Parsed property value list

    Returns:
        Dictionary containing transform components, possible keys:
        - relative_location: {X, Y, Z}
        - relative_rotation: {Pitch, Yaw, Roll}
        - relative_scale3d: {X, Y, Z}
        - mobility: str
    """
    transform: Dict[str, Any] = {}

    for prop in properties:
        prop_name = prop.name
        prop_value = prop.value

        if prop_name == "RelativeLocation":
            transform["relative_location"] = _extract_vector(prop_value)
        elif prop_name == "RelativeRotation":
            transform["relative_rotation"] = _extract_rotator(prop_value)
        elif prop_name == "RelativeScale3D":
            transform["relative_scale3d"] = _extract_vector(prop_value)
        elif prop_name == "RelativeTranslation":
            transform["relative_translation"] = _extract_vector(prop_value)
        elif prop_name == "Mobility":
            transform["mobility"] = _extract_mobility(prop_value)

    return transform

def _extract_vector(value: Any) -> Dict[str, float]:
    """Extract Vector struct {X, Y, Z} from property value.

    Supports StructValue dataclass and dict types.
    """
    fields: Dict[str, Any] = {}
    if isinstance(value, StructValue):
        fields = value.fields
    elif isinstance(value, dict):
        fields = value

    if fields:
        x = fields.get("X", fields.get("x", 0.0))
        y = fields.get("Y", fields.get("y", 0.0))
        z = fields.get("Z", fields.get("z", 0.0))
        return {"X": float(x), "Y": float(y), "Z": float(z)}
    return {"X": 0.0, "Y": 0.0, "Z": 0.0}

def _extract_rotator(value: Any) -> Dict[str, float]:
    """Extract Rotator struct {Pitch, Yaw, Roll} from property value.

    Supports StructValue dataclass and dict types.
    """
    fields: Dict[str, Any] = {}
    if isinstance(value, StructValue):
        fields = value.fields
    elif isinstance(value, dict):
        fields = value

    if fields:
        pitch = fields.get("Pitch", fields.get("pitch", 0.0))
        yaw = fields.get("Yaw", fields.get("yaw", 0.0))
        roll = fields.get("Roll", fields.get("roll", 0.0))
        return {"Pitch": float(pitch), "Yaw": float(yaw), "Roll": float(roll)}
    return {"Pitch": 0.0, "Yaw": 0.0, "Roll": 0.0}

def _extract_mobility(value: Any) -> str:
    """Extract Mobility enum value from property value."""
    if isinstance(value, dict):
        return value.get("value", value.get("name", str(value)))
    if isinstance(value, str):
        return value
    return str(value) if value is not None else "Static"

def _extract_functions_from_bpgc_properties(properties: List[Any]) -> List[BlueprintFunction]:
    """Primary path: Extract functions from BPGC export properties.

    Looks for UbergraphFunction and FunctionList properties in BPGC exports.
    These are FPackageIndex references that resolve to function names.
    """
    functions: List[BlueprintFunction] = []
    for prop in properties:
        prop_name = getattr(prop, 'name', '')
        if prop_name == "UbergraphFunction":
            func_name = _resolve_property_to_function_name(prop.value)
            if func_name:
                functions.append(BlueprintFunction(name=func_name, is_implemented=False))
        elif prop_name == "FunctionList" and isinstance(prop.value, (list, tuple)):
            for item in prop.value:
                func_name = _resolve_property_to_function_name(item)
                if func_name:
                    functions.append(BlueprintFunction(name=func_name))
    return functions

def _resolve_property_to_function_name(value: Any) -> Optional[str]:
    """Resolve a property value to a function name string."""
    if value is None:
        return None
    if isinstance(value, str) and value and value != UE_NONE_SENTINEL:
        # UE path format: /Game/Path/To/PackageName.ClassName
        # First extract after last '/', then after last '.'
        raw = value.split('/')[-1] if '/' in value else value
        return raw.split('.')[-1] if '.' in raw else raw
    if isinstance(value, dict):
        obj_name = value.get('object_name') or value.get('resolved') or value.get('raw_index')
        if obj_name and obj_name != UE_NONE_SENTINEL:
            raw = str(obj_name)
            return raw.split('.')[-1] if '.' in raw else raw
    if hasattr(value, 'object_name'):
        name = getattr(value, 'object_name', None)
        if name and name != UE_NONE_SENTINEL:
            raw = str(name)
            return raw.split('.')[-1] if '.' in raw else raw
    return None

def _extract_functions_from_graphs(graphs) -> List[BlueprintFunction]:
    """Extract function metadata from graph K2Node_FunctionEntry and K2Node_Event nodes (fallback path).

    Iterates through graph list, finds K2Node_FunctionEntry / K2Node_Event nodes,
    and extracts function signatures from node_data and pins.
    """
    if not graphs:
        return []
    functions: List[BlueprintFunction] = []
    for graph in graphs:
        for node in getattr(graph, 'nodes', []):
            class_name = getattr(node, 'class_name', '')
            if class_name not in ("K2Node_FunctionEntry", "K2Node_Event"):
                continue

            nd = node.node_data or {}
            if not isinstance(nd, dict):
                continue

            is_event_node = class_name == "K2Node_Event"

            # Extract function name
            func_name = "Unknown"
            if is_event_node:
                er = nd.get("event_reference")
                if er and hasattr(er, 'member_name'):
                    mn = er.member_name
                    func_name = mn.split('/')[-1] if '/' in mn else mn
                    if func_name == UE_NONE_SENTINEL:
                        func_name = nd.get("custom_function_name", "Unknown")
                elif nd.get("custom_function_name"):
                    func_name = nd["custom_function_name"]
            else:
                fr = nd.get("function_reference")
                if fr and hasattr(fr, 'member_name'):
                    func_name = fr.member_name if fr.member_name != UE_NONE_SENTINEL else "Unknown"
                else:
                    func_name = nd.get("function_name", nd.get("custom_function_name", "Unknown"))

            # Extract parameters and return values from pins
            parameters: List[FunctionParameter] = []
            return_type = ""

            for pin in getattr(node, 'pins', []):
                pin_dir = getattr(pin, 'direction', '')
                pin_type_obj = getattr(pin, 'pin_type', None)
                pin_type_name = ""
                if pin_type_obj and hasattr(pin_type_obj, 'pin_category'):
                    pin_type_name = getattr(pin_type_obj, 'pin_category', '') or ""
                elif isinstance(pin_type_obj, dict):
                    pin_type_name = pin_type_obj.get("pin_category", pin_type_obj.get("category", ""))

                if isinstance(pin_dir, int):
                    is_output = pin_dir == 1
                    is_input = pin_dir == 0
                else:
                    is_output = pin_dir == "EGPD_Output"
                    is_input = pin_dir == "EGPD_Input"

                # Skip execution flow pins (exec) and delegate pins
                if pin_type_name.lower() in ("exec", "delegate", "multicastdelegate"):
                    continue

                pin_name = getattr(pin, 'pin_name', '')
                pin_name_lower = pin_name.lower()

                if not is_event_node and is_output:
                    # FunctionEntry: output pins containing "return" are return values, rest are output parameters
                    if "return" in pin_name_lower:
                        if return_type == "":
                            return_type = _map_pin_category_to_cpp_type(pin_type_name)
                    else:
                        cpp_type = _map_pin_category_to_cpp_type(pin_type_name)
                        parameters.append(FunctionParameter(
                            name=pin_name,
                            param_type=cpp_type,
                            is_input=False,
                            is_output=True,
                        ))
                elif is_input:
                    # Input pins as parameters (excluding self/target)
                    if pin_name_lower in ("self", "target", "worldcontext"):
                        continue
                    cpp_type = _map_pin_category_to_cpp_type(pin_type_name)
                    parameters.append(FunctionParameter(
                        name=pin_name,
                        param_type=cpp_type,
                        is_input=True,
                        is_output=False,
                    ))
                elif is_output and is_event_node:
                    # K2Node_Event output pins (non-exec/delegate) = event parameters
                    cpp_type = _map_pin_category_to_cpp_type(pin_type_name)
                    parameters.append(FunctionParameter(
                        name=pin_name,
                        param_type=cpp_type,
                        is_input=False,
                        is_output=True,
                    ))

            func = BlueprintFunction(
                name=func_name,
                return_type=return_type,
                parameters=parameters,
                is_implemented=not is_event_node,
            )
            # Mark event nodes
            if is_event_node:
                func.is_blueprint_implementable_event = True
                if nd.get("b_override_function", False):
                    func.is_blueprint_event = True
            functions.append(func)
    return functions

def _resolve_parent_class(
    properties: List[Any],
    export: Any,
    linker: Any = None,
    import_map: Any = None,
    export_map: Any = None,
) -> Optional[str]:
    """Resolve parent class from properties and export metadata.

    First looks for ParentClass / ParentClassProperty / SuperClass in properties,
    then infers from export's super_index.
    """
    parent_class = None
    for prop in properties:
        if prop.name in ("ParentClass", "ParentClassProperty", "SuperClass"):
            if prop.value and isinstance(prop.value, dict):
                if prop.value.get('raw_index'):
                    parent_class = prop.value.get('raw_index')
                elif prop.value.get('resolved'):
                    parent_class = prop.value.get('resolved')
                elif prop.value.get('object_name'):
                    object_name = prop.value.get('object_name')
                    class_package = prop.value.get('class_package', '')
                    if class_package:
                        parent_class = f"{class_package}.{object_name}"
                    else:
                        common_engine_classes = [
                            "Character", "Pawn", "Actor", "ActorComponent",
                            "SceneComponent", "Object", "Interface", "UserWidget",
                            "HUD", "PlayerController", "GameModeBase", "GameMode",
                            "Controller", "PlayerCameraManager", "PawnMovementComponent",
                            "CharacterMovementComponent", "SpringArmComponent",
                            "CameraComponent", "SkeletalMeshComponent", "StaticMeshComponent",
                            "BoxComponent", "SphereComponent", "CapsuleComponent",
                            "AudioComponent", "ParticleSystemComponent",
                            "WidgetComponent", "ChildActorComponent",
                            "Blueprint", "BlueprintGeneratedClass",
                        ]
                        if object_name in common_engine_classes:
                            parent_class = f"/Script/Engine.{object_name}"
                        else:
                            parent_class = object_name

    # Infer parent class from export's super_index
    if not parent_class and hasattr(export, 'super_index'):
        if linker is not None:
            from uasset_read.serializers.object_resources import resolve_parent_class_with_linker as _rpc
            parent_name, warn = _rpc(export.super_index, linker)
        else:
            from uasset_read.serializers.object_resources import resolve_parent_class as _rpc
            parent_name, warn = _rpc(export.super_index, import_map, export_map)
        if parent_name:
            parent_class = parent_name

    return parent_class


def _extract_and_merge_functions(
    properties: List[Any],
    graphs: Any = None,
) -> List[BlueprintFunction]:
    """Merge function lists from BPGC property path and graph path, deduplicated by name."""
    functions_bpgc = _extract_functions_from_bpgc_properties(properties) if properties else []
    functions_graph = _extract_functions_from_graphs(graphs) if graphs else []
    seen_names: set = set()
    functions: List[BlueprintFunction] = []
    for func in functions_bpgc + functions_graph:
        if func.name not in seen_names:
            seen_names.add(func.name)
            functions.append(func)
    return functions


def _extract_events_from_functions(functions: List[BlueprintFunction]) -> List[BlueprintEvent]:
    """Extract events from function list (implementable events and blueprint events)."""
    events: List[BlueprintEvent] = []
    for f in functions:
        if f.is_blueprint_implementable_event or f.is_blueprint_event:
            events.append(BlueprintEvent(
                name=f.name,
                event_type="Override" if f.is_blueprint_event else "Event",
                function_flags=f.function_flags,
                is_blueprint_event=f.is_blueprint_event,
                is_blueprint_implementable_event=f.is_blueprint_implementable_event,
                parameters=f.parameters,
            ))
    return events


def _extract_interfaces_from_props(
    props_list: List[Any],
    import_map: Any = None,
) -> List[Any]:
    """Extract ImplementedInterfaces from property list.

    Parses FBPInterfaceDescription structs, resolves Interface object reference indices to interface names.
    """
    from uasset_read.models.blueprint import BlueprintInterface
    result: List[Any] = []
    for prop in props_list:
        if prop.name == "ImplementedInterfaces" and isinstance(prop.value, list):
            for item in prop.value:
                fields = {}
                if isinstance(item, dict):
                    fields = item
                elif hasattr(item, "fields"):
                    fields = getattr(item, "fields", {})

                iface_ref = fields.get("Interface", None)
                iface_name = ""
                if isinstance(iface_ref, int) and import_map and iface_ref < 0:
                    idx = -iface_ref - 1
                    if idx < len(import_map):
                        imp = import_map[idx]
                        iface_name = str(getattr(imp, "object_name", ""))
                elif isinstance(iface_ref, str):
                    iface_name = iface_ref
                if iface_name:
                    result.append(BlueprintInterface(name=iface_name))
            break
    return result


def _extract_interfaces(
    properties: List[Any],
    export: Any,
    export_map: Any = None,
    archive: Any = None,
    summary: Any = None,
    name_map: Any = None,
    import_map: Any = None,
    linker: Any = None,
) -> List[Any]:
    """Extract ImplementedInterfaces (from current export or other blueprint exports).

    First searches in current export properties, then iterates other blueprint exports if not found.
    """
    from uasset_read.parsers.property_parser import parse_properties_from_export

    interfaces = _extract_interfaces_from_props(properties, import_map)

    # If current export has no ImplementedInterfaces, search in other blueprint exports
    if not interfaces and export_map:
        from uasset_read.serializers.object_resources import detect_blueprint_with_linker as _dbl
        for other_export in export_map:
            if other_export is export:
                continue
            is_bp = _dbl(other_export, linker) if linker else False
            if not is_bp:
                continue
            try:
                other_props = parse_properties_from_export(
                    other_export, archive, summary, name_map, export_map, import_map,
                )
                interfaces = _extract_interfaces_from_props(other_props, import_map)
            except (KeyError, TypeError, ValueError) as e:
                logger.debug("Failed to extract interface properties: %s", e, exc_info=True)
            if interfaces:
                break

    return interfaces


def extract_blueprint_metadata(
    export,
    archive,
    import_map,
    export_map,
    name_map,
    summary,
    linker=None,
    graphs=None,
) -> tuple:
    """Combine variable extraction and general metadata to build BlueprintMetadata instance.

    Equivalent migration from uasset_read.py section 6100-6220.
    Reads properties from the specified export and extracts blueprint metadata.

    Args:
        export: ObjectExport entry (typically BPGC)
        archive: FArchive instance
        import_map: Import table
        export_map: Export table
        name_map: Name table
        summary: PackageFileSummary
        linker: PackageLinker instance (optional, for more precise parent class resolution)
        graphs: UEdGraph list (optional, for extracting functions from K2Node_FunctionEntry)

    Returns:
        Tuple[BlueprintMetadata | None, str | None] -- (metadata, warning)
    """
    from uasset_read.parsers.property_parser import parse_properties_from_export

    if export is None or export.serial_size <= 0:
        return None, None

    # Parse export properties
    try:
        properties = parse_properties_from_export(
            export, archive, summary, name_map, export_map, import_map,
        )
    except (KeyError, TypeError, ValueError):
        return None, None

    if not properties:
        return None, None

    # Extract variables
    variables = extract_blueprint_variables(properties)

    # Extract parent class
    parent_class = _resolve_parent_class(properties, export, linker, import_map, export_map)

    # Extract functions (BPGC + graph path merged and deduplicated)
    functions = _extract_and_merge_functions(properties, graphs)

    # Extract events
    events = _extract_events_from_functions(functions)

    # Extract description
    description = ""
    for prop in properties:
        if prop.name == "BlueprintDescription":
            description = str(prop.value) if prop.value else ""
            break

    # Extract interfaces
    interfaces = _extract_interfaces(
        properties, export, export_map, archive, summary, name_map, import_map, linker,
    )

    meta = BlueprintMetadata(
        is_blueprint=True,
        parent_class=parent_class,
        description=description,
        interfaces=interfaces,
        variables=variables,
        functions=functions,
        events=events,
    )
    return meta, None

def parse_property_flags_to_labels(flags: int) -> List[str]:
    """Convert CPF_* bit flags to readable label list.

    Equivalent migration from uasset_read.py section 4775-4827.
    Includes semantic mapping: CPF_Edit -> EditAnywhere/EditConst,
    CPF_BlueprintVisible -> BlueprintReadWrite/BlueprintReadOnly.
    """
    labels = []

    # Edit flags (mutually exclusive modes)
    if flags & CPF_Edit:
        if flags & CPF_EditConst:
            labels.append("EditConst")
        else:
            labels.append("EditAnywhere")

    # Blueprint visibility flags (mutually exclusive)
    if flags & CPF_BlueprintVisible:
        if flags & CPF_BlueprintReadOnly:
            labels.append("BlueprintReadOnly")
        else:
            labels.append("BlueprintReadWrite")

    # Component reference flags
    if flags & CPF_InstancedReference:
        labels.append("InstancedReference")

    # Other flags
    if flags & CPF_Protected:
        labels.append("Protected")
    if flags & CPF_ExposeOnSpawn:
        labels.append("ExposeOnSpawn")
    if flags & CPF_Config:
        labels.append("Config")
    if flags & CPF_Transient:
        labels.append("Transient")
    if flags & CPF_SaveGame:
        labels.append("SaveGame")
    if flags & CPF_Deprecated:
        labels.append("Deprecated")
    if flags & CPF_BlueprintAssignable:
        labels.append("BlueprintAssignable")
    if flags & CPF_BlueprintCallable:
        labels.append("BlueprintCallable")
    if flags & CPF_RepNotify:
        labels.append("RepNotify")
    if flags & CPF_Interp:
        labels.append("Interp")
    if flags & CPF_Net:
        labels.append("Net")
        labels.append("Replicated")

    return labels

def read_blueprint_variable(
    archive,
    name_map: List[str],
    summary,
) -> BlueprintVariable:
    """
    Read FBPVariableDescription from blueprint export (BLUE-03).

    Reference: UE C++ FBPVariableDescription::Serialize() implementation.

    Serialization order:
    1. VarName (FName)
    2. VarGuid (FGuid - 16 bytes) -- skipped
    3. VarType (FEdGraphPinType)
    4. FriendlyName (FString)
    5. Category (FText -- simplified to FString)
    6. PropertyFlags (uint64)
    7. RepNotifyFunc (FName) -- skipped
    8. ReplicationCondition (uint8) -- skipped
    9. MetaDataArray (TArray)
    10. DefaultValue (FString)
    """
    var = BlueprintVariable(
        var_name=archive.read_name(name_map)
    )

    var.var_guid = _read_guid(archive)

    # VarType (FEdGraphPinType)
    var.var_type = read_ed_graph_pin_type(archive, name_map, summary)

    # FriendlyName (FString)
    var.friendly_name = archive.read_fstring()

    # Category (FText) -- simplified to FString
    var.category = archive.read_fstring()

    var.property_flags = archive.read_u64()

    var.rep_notify_func = archive.read_name(name_map)

    var.replication_condition = archive.read_u8()

    meta_count = archive.read_i32()
    var.metadata = {}
    for _ in range(meta_count):
        key = archive.read_name(name_map)
        value = archive.read_fstring()
        if key:
            var.metadata[key] = value

    # Parse PropertyFlags to readable labels
    var.flags_labels = parse_property_flags_to_labels(var.property_flags)

    # Parse property flags to boolean fields
    flags = var.property_flags
    var.is_edit_anywhere = bool(flags & CPF_Edit)
    var.is_edit_instance_only = bool(flags & CPF_Edit) and not bool(flags & CPF_EditConst)
    var.is_blueprint_read_only = bool(flags & CPF_BlueprintReadOnly)
    var.is_blueprint_readable = bool(flags & CPF_BlueprintVisible)
    var.is_blueprint_writable = bool(flags & CPF_BlueprintVisible) and not bool(flags & CPF_BlueprintReadOnly)
    var.is_transient = bool(flags & CPF_Transient)
    var.is_duplicate_transient = bool(flags & CPF_DuplicateTransient)
    var.is_save_game = bool(flags & CPF_SaveGame)
    var.is_no_clear = bool(flags & CPF_NoClear)
    var.is_reference_only = False
    var.is_blueprint_assignable = bool(flags & CPF_BlueprintAssignable)
    var.is_blueprint_callable = bool(flags & CPF_BlueprintCallable)
    var.is_rep_notify = bool(flags & CPF_RepNotify)
    var.is_interp = bool(flags & CPF_Interp)
    var.is_expose_on_spawn = bool(flags & CPF_ExposeOnSpawn)
    var.is_net = bool(flags & CPF_Net)
    var.is_replicated = bool(flags & CPF_Net)
    var.is_non_pi_ed_duplicate_transient = bool(flags & CPF_NonPIEDuplicateTransient)

    # Extract metadata fields
    var.edit_condition = var.metadata.get('EditCondition', '')
    var.meta_class = var.metadata.get('MetaClass', '')
    var.edit_category = var.metadata.get('Category', '')
    var.edit_widget = var.metadata.get('EditWidget', '')

    default_str = archive.read_fstring()
    var.default_value = parse_default_value(default_str, var.var_type)

    # Component variable identification (double verification)
    type_str = ""
    if var.var_type:
        if var.var_type.pin_subcategory and var.var_type.pin_subcategory.lower() != "none":
            type_str = var.var_type.pin_subcategory
        elif var.var_type.pin_category:
            type_str = var.var_type.pin_category

    is_component_by_name = isinstance(type_str, str) and "Component" in type_str
    is_component_by_flag = (var.property_flags & CPF_InstancedReference) != 0
    var.is_component = is_component_by_name or is_component_by_flag

    return var

def _read_guid(archive) -> str:
    data = archive.read_bytes(16) if hasattr(archive, "read_bytes") else archive.read(16)
    return (
        f"{data[0]:02x}{data[1]:02x}{data[2]:02x}{data[3]:02x}-"
        f"{data[4]:02x}{data[5]:02x}-"
        f"{data[6]:02x}{data[7]:02x}-"
        f"{data[8]:02x}{data[9]:02x}-"
        f"{data[10]:02x}{data[11]:02x}{data[12]:02x}{data[13]:02x}{data[14]:02x}{data[15]:02x}"
    )
