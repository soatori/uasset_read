"""
uasset_read Constants Definition

Contains all version numbers, property type thresholds, and boundary constants.
Extracted from uasset_read.py (per D-11).
"""

# ============================================================================
# CLI Exit Codes
# ============================================================================

EXIT_SUCCESS = 0
EXIT_PARSE_ERROR = 1
EXIT_FILE_NOT_FOUND = 2
EXIT_ARGUMENT_ERROR = 3

# ============================================================================
# Package file tags (from UE source code)
# ============================================================================

PACKAGE_FILE_TAG = 0x9E2A83C1  # Correct byte order magic tag
PACKAGE_FILE_TAG_SWAPPED = 0xC1832A9E  # Swapped byte order magic tag

# ============================================================================
# Version constants
# ============================================================================

UE5_VERSION_MIN = 1000  # FPackageFileVersion::ToValue(): UE5 starts at ObjectVersion.h INITIAL_VERSION=1000
UE5_LEGACY_VERSION = -9  # Fixed LegacyFileVersion for UE5.6+ files
# -8: FileVersionUE5 field added, -7: texture allocation info removed, -6: custom version serialization optimization
UE5_LEGACY_VERSIONS = frozenset({-6, -7, -8, UE5_LEGACY_VERSION})  # Supported UE5 LegacyFileVersion

# UE4 LegacyFileVersion (GUID-based custom versions)
# -3: GUID-based custom versions, has LegacyUE3Version
# -4: GUID-based custom versions, no LegacyUE3Version (removed UE3 version field)
# -5: GUID-based custom versions, has LegacyUE3Version (replaces UE3 version field)
UE4_LEGACY_VERSIONS = frozenset({-3, -4, -5})

# All supported LegacyFileVersion (UE4 + UE5)
SUPPORTED_LEGACY_VERSIONS = UE5_LEGACY_VERSIONS | UE4_LEGACY_VERSIONS

# ============================================================================
# Boundary validation constants (defensive programming)
# ============================================================================

MAX_NAME_COUNT = 10_000_000  # Maximum name table entries
MAX_IMPORT_COUNT = 1_000_000  # Maximum import table entries
MAX_EXPORT_COUNT = 1_000_000  # Maximum export table entries
MAX_TOTAL_OBJECT_COUNT = 500_000  # Maximum import + export combined entries
MAX_CUSTOM_VERSIONS = 10_000  # Maximum custom version entries
MAX_GENERATIONS = 10_000  # Maximum Generations table entries
MAX_COMPRESSED_CHUNKS = 100_000  # Maximum CompressedChunks entries
MAX_SOFT_PACKAGE_REFS = 1_000_000  # Maximum SoftPackageReferences entries
MMAP_THRESHOLD = 10 * 1024 * 1024  # 10MB - switch to mmap above this (lower threshold to reduce memory peak)
MAX_PROPERTY_COUNT = 10_000  # Property loop limit
MAX_RECURSION_DEPTH = (
    50  # Maximum property nesting recursion depth (prevents stack overflow from malicious/malformed assets)
)
MIN_UASSET_SIZE = 64  # Minimum legal .uasset file size (bytes)
# Contains minimum of Tag(4) + version fields(16~20) + LicenseeVer(4) + Hash(20) + HeaderSize(4)
MAX_ARRAY_COUNT = 1_000_000  # Maximum ArrayProperty elements (per HIGH-07/35d-01)
MAX_ARRAY_DIM = 256  # Maximum array dimension in mapping property info
MAX_FSTRING_LENGTH = 10_000_000  # 10 MB — FString maximum length (UTF-8/UTF-16)

# ============================================================================
# PropertyTag flags
# ============================================================================

PROP_TAG_HAS_ARRAY_INDEX = 0x01  # ArrayIndex field present
PROP_TAG_HAS_PROPERTY_GUID = 0x02  # PropertyGuid field present
PROP_TAG_HAS_EXTENSIONS = 0x04  # Extension data
PROP_TAG_HAS_BINARY_OR_NATIVE = 0x08  # Binary/native serialize
PROP_TAG_BOOL_TRUE = 0x10  # Bool value is true
PROP_TAG_SKIPPED_SERIALIZE = 0x20  # Skipped serialize

# ============================================================================
# PropertyTag version thresholds
# ============================================================================

PROPERTY_TAG_COMPLETE_TYPE_NAME = 1012  # UE5 format switch threshold

# ============================================================================
# Package Flags (EPackageFlags) — only flags with external imports kept at module level
# Source: UE source code ObjectMacros.h
# ============================================================================

PKG_Cooked = 0x00000200  # Package is cooked
PKG_UnversionedProperties = 0x00002000  # Uses unversioned property serialization
PKG_FilterEditorOnly = 0x80000000  # Package has editor-only data filtered out


def decode_package_flags(flags: int) -> list[str]:
    """Decode PackageFlags bitmask into a list of human-readable flag names.

    Returns a list of set flag bit names, with unknown bits marked as 'Unknown_<hex>'.
    """
    result = []
    known_flags = [
        (0x00000001, "PKG_NewlyCreated"),
        (0x00000002, "PKG_ClientOptional"),
        (0x00000004, "PKG_ServerSideOnly"),
        (0x00000010, "PKG_CompiledIn"),
        (0x00000020, "PKG_ForDiffing"),
        (0x00000040, "PKG_EditorOnly"),
        (0x00000080, "PKG_Developer"),
        (0x00000100, "PKG_UncookedOnly"),
        (PKG_Cooked, "PKG_Cooked"),
        (0x00000400, "PKG_ContainsNoAsset"),
        (0x00000800, "PKG_NotExternallyReferenceable"),
        (0x00001000, "PKG_AccessSpecifierEpicInternal"),
        (PKG_UnversionedProperties, "PKG_UnversionedProperties"),
        (0x00004000, "PKG_ContainsMapData"),
        (0x00008000, "PKG_IsSaving"),
        (0x00010000, "PKG_Compiling"),
        (0x00020000, "PKG_ContainsMap"),
        (0x00040000, "PKG_RequiresLocalizationGather"),
        (0x00080000, "PKG_LoadUncooked"),
        (0x00100000, "PKG_PlayInEditor"),
        (0x00200000, "PKG_ContainsScript"),
        (0x00400000, "PKG_DisallowExport"),
        (0x08000000, "PKG_CookGenerated"),
        (0x10000000, "PKG_DynamicImports"),
        (0x20000000, "PKG_RuntimeGenerated"),
        (0x40000000, "PKG_ReloadingForCooker"),
        (PKG_FilterEditorOnly, "PKG_FilterEditorOnly"),
    ]
    remaining = flags
    for flag_value, flag_name in known_flags:
        if flag_value != 0 and (flags & flag_value) == flag_value:
            result.append(flag_name)
            remaining &= ~flag_value
    if remaining:
        result.append(f"Unknown_{remaining:#010x}")
    return result if result else ["PKG_None"]


# ============================================================================
# Blueprint graph parsing safety constants
# ============================================================================

MAX_PINS_PER_NODE = 1000  # Maximum pins per node
MAX_NODES_PER_GRAPH = 5000  # Maximum nodes per graph
MAX_SUBGRAPHS = 1000  # Maximum subgraphs per graph (corrupted asset defense)
MAX_LINKEDTO_PER_PIN = 100  # Maximum connections per pin
MAX_FTEXT_CONSUMPTION = 10_240  # 10 KB — FText parsing safety net maximum byte consumption

# ============================================================================
# Lightweight tolerant parse threshold
# ============================================================================

LIGHTWEIGHT_TOLERANT_PARSE_THRESHOLD = 300  # Enable lightweight tolerant parse when export_count exceeds this value

# Special threshold for large asset files like ControlRig
# These files naturally have large export counts (RigVM nodes, RigHierarchy elements, etc.),
# and the default 300 threshold would falsely trigger lightweight parsing, causing blueprint data loss
# Reference: UE ControlRig.cpp / RigVM related modules
CONTROL_RIG_LARGE_FILE_THRESHOLD = 50000  # Lightweight parse threshold for ControlRig class files

# Known large file class name substrings — use high threshold when export class name contains any of these substrings
CONTROL_RIG_LARGE_FILE_CLASSES = frozenset(
    {
        "ControlRig",
        "RigHierarchy",
        "RigVM",
        "RigUnit",
    }
)

# ============================================================================
# FPropertyTypeName type node read limit
# ============================================================================

MAX_PROPERTY_TYPE_NODES = 50  # Max nodes in _read_property_type_name

# ============================================================================
# PropertyTag extension flags
# ============================================================================

PROP_EXT_SERIALIZE_CONTROL = 0x02  # SerializeControl bit in property extensions

# ============================================================================
# UE5 version constants (EUnrealEngineObjectUE5Version)
# ============================================================================

UE5_REMOVE_OBJECT_EXPORT_PACKAGE_GUID = 1005
UE5_TRACK_OBJECT_EXPORT_IS_INHERITED = 1006
UE5_OPTIONAL_RESOURCES = 1003
UE5_NAMES_REFERENCED_FROM_EXPORT_DATA = 1001
UE5_PAYLOAD_TOC = 1002
UE5_LARGE_WORLD_COORDINATES = 1004
UE5_ADD_SOFTOBJECTPATH_LIST = 1008
UE5_DATA_RESOURCES = 1009
UE5_SCRIPT_SERIALIZATION_OFFSET = 1010
UE5_PROPERTY_TAG_EXTENSION = 1011
UE5_METADATA_SERIALIZATION_OFFSET = 1014
UE5_VERSE_CELLS = 1015
UE5_PACKAGE_SAVED_HASH = 1016
UE5_IMPORT_TYPE_HIERARCHIES = 1018

# ============================================================================
# UE4 version constants (corresponding to EUnrealEngineObjectUE4Version)
# ============================================================================

UE4_ADDED_PACKAGE_SUMMARY_LOCALIZATION_ID = 516
UE4_ADD_STRING_ASSET_REFERENCES_MAP = 384
UE4_SERIALIZE_TEXT_IN_PACKAGES = 459
UE4_ADDED_SEARCHABLE_NAMES = 510
UE4_ADDED_PACKAGE_OWNER = 518
UE4_NON_OUTER_PACKAGE_IMPORT = 520
UE4_NAME_HASHES_SERIALIZED = 504  # VER_UE4_NAME_HASHES_SERIALIZED: Add 4-byte hash after name table entries (UE 4.14+)
UE4_LOAD_FOR_EDITOR_GAME = 365
UE4_COOKED_ASSETS_IN_EDITOR_SUPPORT = 485
UE4_PRELOAD_DEPENDENCIES_IN_COOKED_EXPORTS = 507
UE4_TemplateIndex_IN_COOKED_EXPORTS = 508
UE4_64BIT_EXPORTMAP_SERIALSIZES = 511

# ============================================================================
# Blueprint metadata keys (UE editor internal fields)
# ============================================================================

BLUEPRINT_METADATA_KEYS = frozenset(
    {
        "BlueprintSystemVersion",
        "GeneratedClass",
        "SimpleConstructionScript",
        "bCanEverTick",
        "bCanEverRender",
        "bStartWithTickEnabled",
        "bReplicates",
        "NetUpdateFrequency",
        "MinNetUpdateFrequency",
        "NetPriority",
    }
)

# ============================================================================
# Control flow node set (used in blueprint graph parsing)
# ============================================================================

CONTROL_FLOW_NODES = frozenset(
    {
        "K2Node_IfThenElse",
        "K2Node_Switch",
        "K2Node_SwitchString",
        "K2Node_SwitchEnum",
        "K2Node_SwitchInteger",
        "K2Node_MacroInstance",
        # Loop macros
        "K2Node_ForLoop",
        "K2Node_WhileLoop",
        "K2Node_DoOnce",
        # Multi-gate
        "K2Node_Sequence",
        "K2Node_MultiGate",
        # Selection
        "K2Node_Select",
        "K2Node_ExecutionSequence",
    }
)

# ============================================================================
# Start event type set
# ============================================================================

START_EVENT_TYPES = frozenset(
    {
        "K2Node_Event",
        "K2Node_EnhancedInputAction",
        "K2Node_VariableSet",
        "K2Node_CustomEvent",
        "K2Node_FunctionEntry",  # Function graph execution flow start point
    }
)

# ============================================================================
# Data flow boundary node set
# ============================================================================

DATA_BOUNDARY_NODES = frozenset(
    {
        "K2Node_FunctionEntry",  # Function parameter output as data flow start point
        "K2Node_VariableSet",  # Local variable definition (boundary)
    }
)

# ============================================================================
# EnhancedInput TriggerEvent pin mapping
# ============================================================================

ETRIGGER_EVENT_PIN_MAP = {
    "Started": "Started",
    "Triggered": "Triggered",
    "Completed": "Completed",
    "Exited": "Exited",
}

# ============================================================================
# Branch type mapping
# ============================================================================

BRANCH_TYPE_MAP = {
    "K2Node_IfThenElse": "if_then_else",
    "K2Node_Switch": "switch",
    "K2Node_SwitchString": "switch_string",
    "K2Node_SwitchEnum": "switch_enum",
    "K2Node_SwitchInteger": "switch_integer",
    "K2Node_MacroInstance": "macro_instance",
    "K2Node_ForLoop": "for_loop",
    "K2Node_WhileLoop": "while_loop",
    "K2Node_DoOnce": "do_once",
    "K2Node_Sequence": "sequence",
    "K2Node_ExecutionSequence": "execution_sequence",
    "K2Node_MultiGate": "multi_gate",
    "K2Node_Select": "select",
}

# ============================================================================
# Graph type mapping
# ============================================================================

GRAPH_TYPE_MAP = {
    "EdGraph": "event",
    "UberEdGraph": "uber",
}

# ============================================================================
# EPropertyFlags — CPF_* property flag constants (externally used subset)
# Aligned with UE5 ObjectMacros.h EPropertyFlags enum (64-bit)
# Source: Engine/Source/Runtime/CoreUObject/Public/UObject/ObjectMacros.h
# ============================================================================

CPF_Edit = 0x0000000000000001
CPF_BlueprintVisible = 0x0000000000000004
CPF_BlueprintReadOnly = 0x0000000000000010
CPF_Net = 0x0000000000000020
CPF_Transient = 0x0000000000002000
CPF_Config = 0x0000000000004000
CPF_EditConst = 0x0000000000020000
CPF_InstancedReference = 0x0000000000080000
CPF_DuplicateTransient = 0x0000000000200000
CPF_SaveGame = 0x0000000001000000
CPF_NoClear = 0x0000000002000000
CPF_BlueprintAssignable = 0x0000000010000000
CPF_Deprecated = 0x0000000020000000
CPF_RepNotify = 0x0000000100000000
CPF_Interp = 0x0000000200000000
CPF_AdvancedDisplay = 0x0000040000000000
CPF_Protected = 0x0000080000000000
CPF_BlueprintCallable = 0x0000100000000000
CPF_NonPIEDuplicateTransient = 0x0000800000000000
CPF_ExposeOnSpawn = 0x0001000000000000

# =====================================================================# ============================================================================

FIXED_UNVERSIONED_SIZES: dict[str, int] = {
    "BoolProperty": 4,
    "IntProperty": 4,
    "UInt32Property": 4,
    "FloatProperty": 4,
    "DoubleProperty": 8,
    "Int64Property": 8,
    "UInt64Property": 8,
    "Int16Property": 2,
    "UInt16Property": 2,
    "Int8Property": 1,
    "ByteProperty": 1,
    "ObjectProperty": 4,
    "ClassProperty": 4,
    "NameProperty": 8,
    "GuidProperty": 16,
}

# ============================================================================
# EPinContainerType integer → string mapping
# ============================================================================

CONTAINER_TYPE_MAP: dict[int, str] = {0: "None", 1: "Array", 2: "Set", 3: "Map"}
CONTAINER_TYPE_PREFIX: dict[int, str] = {1: "TArray", 2: "TSet", 3: "TMap"}

# ============================================================================
# UE PropertyTag sentinel value
# ============================================================================

UE_NONE_SENTINEL = "None"

# ============================================================================
# General safety count limits
# ============================================================================

MAX_SAFE_COUNT = 10_000  # Used for FText args / MulticastDelegate / FieldPath sub-element count validation

# ============================================================================
# GUID byte formatting
# ============================================================================


def format_guid_bytes(data: bytes, uppercase: bool = True) -> str:
    """Format 16 raw FGuid bytes into a stable 8-4-4-4-12 string."""
    if not isinstance(data, (bytes, bytearray)) or len(data) < 16:
        raise ValueError(
            f"GUID requires exactly 16 bytes, got {type(data).__name__} of length "
            f"{len(data) if isinstance(data, (bytes, bytearray)) else 'N/A'}"
        )
    text = (
        f"{data[0]:02x}{data[1]:02x}{data[2]:02x}{data[3]:02x}-"
        f"{data[4]:02x}{data[5]:02x}-"
        f"{data[6]:02x}{data[7]:02x}-"
        f"{data[8]:02x}{data[9]:02x}-"
        f"{data[10]:02x}{data[11]:02x}{data[12]:02x}{data[13]:02x}{data[14]:02x}{data[15]:02x}"
    )
    return text.upper() if uppercase else text


# ============================================================================
# UE5 large property type thresholds (#404)
# ============================================================================

MAX_REASONABLE_CAP = 100 * 1024 * 1024  # 100 MB — Standard property size cap

UE5_LARGE_PROPERTY_TYPES = frozenset(
    {
        "BoneAnimationTracks",
        "PoseContainer",
        "ArrayConnectionMap",
        "RigVM",
        "MapProperty",
    }
)

UE5_LARGE_PROPERTY_MAX_REASONABLE = 500 * 1024 * 1024  # 500 MB — UE5 large property size cap

# ============================================================================
# Material property decode tables
# Reference: Engine/Source/Runtime/Engine/Public/Materials/Material.h
# ============================================================================

MATERIAL_DOMAIN_MAP: dict[int, str] = {
    0: "Surface",
    1: "DeferredDecal",
    2: "LightFunction",
    3: "Volume",
    4: "PostProcess",
    5: "UserInterface",
}

BLEND_MODE_MAP: dict[int, str] = {
    0: "Opaque",
    1: "Masked",
    2: "Translucent",
    3: "Additive",
    4: "Modulate",
    5: "AlphaComposite",
    8: "TranslucentColoredTransmittance",
}

SHADING_MODEL_MAP: dict[int, str] = {
    0: "Unlit",
    1: "DefaultLit",
    2: "Subsurface",
    3: "PreintegratedSkin",
    4: "SubsurfaceProfile",
    5: "ClearCoatTopCoat",
    6: "ThinTranslucent",
    8: "SingleLayerWater",
}

MATERIAL_USAGE_FLAG_NAMES: tuple[str, ...] = (
    "bUsedWithSkeletalMesh",
    "bUsedWithClothing",
    "bUsedWithStatic",
    "bUsedWithLandscape",
    "bUsedWithNanite",
    "bUsedWithUI",
    "bUsedWithParticles",
    "bUsedWithSplineMeshes",
    "bUsedWithInstancedStaticMeshes",
    "bUsedWithGeometryCollection",
    "bUsedWithWaterSurface",
    "bUsedWithHairStrands",
)

# Expression type classification table
# Maps expression class name patterns to semantic types
_EXPRESSION_TYPE_PATTERNS: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        (
            "MaterialExpressionConstant",
            "MaterialExpressionConstant2Vector",
            "MaterialExpressionConstant3Vector",
            "MaterialExpressionConstant4Vector",
        ),
        "constant",
    ),
    (
        (
            "MaterialExpressionScalarParameter",
            "MaterialExpressionVectorParameter",
            "MaterialExpressionTextureSampleParameter",
            "MaterialExpressionTextureObjectParameter",
            "MaterialExpressionDoubleVectorParameter",
            "MaterialExpressionChannelMaskParameter",
            "MaterialExpressionStaticBoolParameter",
            "MaterialExpressionStaticSwitchParameter",
            "MaterialExpressionStaticComponentMaskParameter",
            "MaterialExpressionFontSampleParameter",
            "MaterialExpressionCurveAtlasRowParameter",
            "MaterialExpressionTextureCollectionParameter",
            "MaterialExpressionRuntimeVirtualTextureSampleParameter",
        ),
        "parameter",
    ),
    (
        (
            "MaterialExpressionAdd",
            "MaterialExpressionSubtract",
            "MaterialExpressionMultiply",
            "MaterialExpressionDivide",
            "MaterialExpressionPower",
            "MaterialExpressionLinearInterpolate",
            "MaterialExpressionClamp",
            "MaterialExpressionSaturate",
            "MaterialExpressionAbs",
            "MaterialExpressionSine",
            "MaterialExpressionCosine",
            "MaterialExpressionFloor",
            "MaterialExpressionCeil",
            "MaterialExpressionFrac",
            "MaterialExpressionRound",
            "MaterialExpressionSquareRoot",
            "MaterialExpressionExponential",
            "MaterialExpressionExponential2",
            "MaterialExpressionModulo",
            "MaterialExpressionCrossProduct",
            "MaterialExpressionDotProduct",
            "MaterialExpressionLength",
            "MaterialExpressionNormalize",
            "MaterialExpressionOneMinus",
            "MaterialExpressionSign",
            "MaterialExpressionDesaturation",
            "MaterialExpressionIf",
            "MaterialExpressionIfThenElse",
            "MaterialExpressionInverseLinearInterpolate",
            "MaterialExpressionSmoothStep",
            "MaterialExpressionStep",
            "MaterialExpressionFmod",
            "MaterialExpressionLogarithm",
            "MaterialExpressionLogarithm2",
            "MaterialExpressionLogarithm10",
            "MaterialExpressionArcsine",
            "MaterialExpressionArcsineFast",
            "MaterialExpressionArccosine",
            "MaterialExpressionArccosineFast",
            "MaterialExpressionArctangent",
            "MaterialExpressionArctangentFast",
            "MaterialExpressionArctangent2",
            "MaterialExpressionArctangent2Fast",
            "MaterialExpressionBumpOffset",
            "MaterialExpressionBlend",
            "MaterialExpressionComponentMask",
            "MaterialExpressionAppendVector",
            "MaterialExpressionConstantBiasScale",
            "MaterialExpressionDistance",
            "MaterialExpressionFresnel",
            "MaterialExpressionNoise",
            "MaterialExpressionPanner",
            "MaterialExpressionRotator",
            "MaterialExpressionSphereMask",
            "MaterialExpressionSphericalParticleOpacity",
            "MaterialExpressionDeriveNormalZ",
            "MaterialExpressionDDX",
            "MaterialExpressionDDY",
            "MaterialExpressionMax",
            "MaterialExpressionMin",
            "MaterialExpressionTransform",
            "MaterialExpressionTransformPosition",
            "MaterialExpressionConvert",
            "MaterialExpressionHsvToRgb",
            "MaterialExpressionRgbToHsv",
            "MaterialExpressionSpeedTree",
            "MaterialExpressionBlendMaterialAttributes",
            "MaterialExpressionBreakMaterialAttributes",
            "MaterialExpressionGetMaterialAttributes",
            "MaterialExpressionSetMaterialAttributes",
            "MaterialExpressionMakeMaterialAttributes",
            "MaterialExpressionMaterialAttributeLayers",
            "MaterialExpressionLayerStack",
            "MaterialExpressionSwitch",
            "MaterialExpressionStaticSwitch",
            "MaterialExpressionPreviousFrameSwitch",
            "MaterialExpressionFeatureLevelSwitch",
            "MaterialExpressionQualitySwitch",
            "MaterialExpressionShaderStageSwitch",
            "MaterialExpressionShadingPathSwitch",
            "MaterialExpressionDataDrivenShaderPlatformInfoSwitch",
            "MaterialExpressionPathTracingQualitySwitch",
            "MaterialExpressionRayTracingQualitySwitch",
            "MaterialExpressionReflectionCapturePassSwitch",
            "MaterialExpressionShadowReplace",
            "MaterialExpressionNaniteReplace",
            "MaterialExpressionVirtualTextureFeatureSwitch",
            "MaterialExpressionRequiredSamplersSwitch",
            "MaterialExpressionDistanceFieldsRenderingSwitch",
            "MaterialExpressionGIReplace",
            "MaterialExpressionLightmassReplace",
            "MaterialExpressionBindlessSwitch",
            "MaterialExpressionMeshPaintTextureReplace",
            "MaterialExpressionSobol",
            "MaterialExpressionTemporalSobol",
        ),
        "operator",
    ),
    (
        (
            "MaterialExpressionTextureSample",
            "MaterialExpressionTextureObject",
            "MaterialExpressionTextureProperty",
            "MaterialExpressionSparseVolumeTextureSample",
            "MaterialExpressionSparseVolumeTextureObject",
            "MaterialExpressionRuntimeVirtualTextureSample",
            "MaterialExpressionRuntimeVirtualTextureReplace",
            "MaterialExpressionVirtualTextureFeatureSwitch",
            "MaterialExpressionDBufferTexture",
            "MaterialExpressionSceneTexture",
            "MaterialExpressionUserSceneTexture",
            "MaterialExpressionSceneColor",
            "MaterialExpressionSceneDepth",
            "MaterialExpressionSceneDepthWithoutWater",
            "MaterialExpressionSceneTexelSize",
            "MaterialExpressionScreenPosition",
            "MaterialExpressionTextureCollection",
            "MaterialExpressionTextureCollectionParameter",
        ),
        "texture_sample",
    ),
    (
        (
            "MaterialExpressionTextureCoordinate",
            "MaterialExpressionVertexColor",
            "MaterialExpressionCameraPositionWS",
            "MaterialExpressionCameraVectorWS",
            "MaterialExpressionObjectOrientation",
            "MaterialExpressionObjectPositionWS",
            "MaterialExpressionObjectBounds",
            "MaterialExpressionObjectLocalBounds",
            "MaterialExpressionObjectRadius",
            "MaterialExpressionLocalPosition",
            "MaterialExpressionWorldPosition",
            "MaterialExpressionViewProperty",
            "MaterialExpressionViewSize",
            "MaterialExpressionPixelNormalWS",
            "MaterialExpressionVertexNormalWS",
            "MaterialExpressionVertexTangentWS",
            "MaterialExpressionTangent",
            "MaterialExpressionTangentOutput",
            "MaterialExpressionTime",
            "MaterialExpressionDeltaTime",
            "MaterialExpressionEyeAdaptation",
            "MaterialExpressionEyeAdaptationInverse",
            "MaterialExpressionDistanceCullFade",
            "MaterialExpressionDistanceToNearestSurface",
            "MaterialExpressionDistanceFieldGradient",
            "MaterialExpressionDistanceFieldApproxAO",
            "MaterialExpressionFogColor",
            "MaterialExpressionAtmosphericFogColor",
            "MaterialExpressionAtmosphericLightColor",
            "MaterialExpressionAtmosphericLightVector",
            "MaterialExpressionMainDirectionalLight",
            "MaterialExpressionLightVector",
            "MaterialExpressionPixelDepth",
            "MaterialExpressionPreSkinnedNormal",
            "MaterialExpressionPreSkinnedPosition",
            "MaterialExpressionPreSkinnedLocalBounds",
            "MaterialExpressionTwoSidedSign",
            "MaterialExpressionIsOrthographic",
            "MaterialExpressionIsFirstPerson",
            "MaterialExpressionPerInstanceCustomData",
            "MaterialExpressionPerInstanceFadeAmount",
            "MaterialExpressionPerInstanceRandom",
            "MaterialExpressionBounds",
            "MaterialExpressionSkyAtmosphereLightDirection",
            "MaterialExpressionSkyAtmosphereLightIlluminance",
            "MaterialExpressionSkyAtmosphereViewLuminance",
            "MaterialExpressionSkyLightEnvMapSample",
            "MaterialExpressionPostVolumeUserFlagTest",
            "MaterialExpressionParticleColor",
            "MaterialExpressionParticleDirection",
            "MaterialExpressionParticleMacroUV",
            "MaterialExpressionParticleMotionBlurFade",
            "MaterialExpressionParticlePositionWS",
            "MaterialExpressionParticleRadius",
            "MaterialExpressionParticleRandom",
            "MaterialExpressionParticleRelativeTime",
            "MaterialExpressionParticleSize",
            "MaterialExpressionParticleSpeed",
            "MaterialExpressionParticleSpriteRotation",
            "MaterialExpressionParticleSubUV",
            "MaterialExpressionFirstPersonOutput",
            "MaterialExpressionVolumetricAdvancedMaterialInput",
            "MaterialExpressionLightmapUVs",
            "MaterialExpressionMeshPaintTextureCoordinateIndex",
            "MaterialExpressionRecordTextureStreamingInfo",
            "MaterialExpressionTemporalResponsivenessOutput",
        ),
        "input",
    ),
    (("MaterialExpressionComment",), "comment"),
    (("MaterialExpressionFunctionInput", "MaterialExpressionFunctionOutput"), "function_io"),
    (
        (
            "MaterialExpressionReroute",
            "MaterialExpressionNamedReroute",
            "MaterialExpressionNamedRerouteUsage",
            "MaterialExpressionRerouteBase",
            "MaterialExpressionPinBase",
        ),
        "reroute",
    ),
)


def classify_expression_type(class_name: str) -> str:
    """Classify a MaterialExpression class name into a semantic type.

    Returns one of: "constant", "parameter", "operator", "texture_sample",
    "input", "comment", "function_io", "reroute", "unknown".
    Returns "unknown" for empty or unrecognized names.
    """
    if not class_name:
        return "unknown"
    for patterns, expr_type in _EXPRESSION_TYPE_PATTERNS:
        for pattern in patterns:
            if class_name == pattern:
                return expr_type
    return "unknown"


def get_max_reasonable(property_type: str, engine_version: int) -> int:
    """Return reasonable size cap based on property type and engine version.

    For UE5 known large property types (BoneAnimationTracks, PoseContainer,
    ArrayConnectionMap, RigVM), relax threshold to 500MB.

    Args:
        property_type: Property type name (e.g., "IntProperty", "StructProperty")
        engine_version: Engine version (4 or 5)

    Returns:
        Maximum reasonable size (bytes) allowed for this property type
    """
    if engine_version >= 5 and property_type in UE5_LARGE_PROPERTY_TYPES:
        return UE5_LARGE_PROPERTY_MAX_REASONABLE
    return MAX_REASONABLE_CAP
