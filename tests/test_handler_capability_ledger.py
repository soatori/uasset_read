"""Pinned v2 coverage ledger for every class name the v1 registry dispatched.

Recorded when the v1 ClassHandler stack was deleted (code-size wave 1).
HANDLER_CLASSES: a handlers_impl handler must keep claiming each name.
FALLBACK_CLASSES: no dedicated handler is claimed; the generic tagged-property
parse is the defined v2 home. The six names marked "former v1 extractor" had
real v1 semantics (five property-projections, one binary reader); porting them
to v2 handlers is deferred to the handler-semantic-tiers work and requires
real fixtures first (see tests/samples/manifest.json fixture gaps).
"""
from uasset_read.models.object_model import ObjectRecord, ObjectStatus
from uasset_read.parsers.asset_types.handlers_impl import get_handlers
from uasset_read.versioning import VersionContext

HANDLER_CLASSES = (
    "AnimBlueprintGeneratedClass", "AnimComposite", "AnimLayerInterface",
    "CurveTable", "DataTable", "Material", "MaterialFunction",
    "MaterialInstance", "MaterialInstanceConstant",
    "MaterialParameterCollection", "NiagaraGraph", "NiagaraNodeFunctionCall",
    "NiagaraNodeInput", "NiagaraNodeOp", "NiagaraNodeOutput",
    "NiagaraNodeParameterMapGet", "NiagaraNodeParameterMapSet",
    "NiagaraNodeReroute", "NiagaraNodeSelect", "NiagaraNodeStaticSwitch",
    "NiagaraScript", "NiagaraScriptVariable", "PhysicalMaterial",
    "PhysicsAsset", "Skeleton", "SkeletalMesh", "SoundAttenuation",
    "SoundCue", "SoundWave", "StaticMesh", "StringTable", "Texture2D",
    "TextureCube", "UserDefinedEnum", "UserDefinedStruct",
)
FALLBACK_CLASSES = (
    "AimOffsetBlendSpace", "AimOffsetBlendSpace1D", "AnimBlendSpace",
    "AnimBlendSpace1D", "AnimBoneCompressionSettings",
    "AnimCurveCompressionCodec", "AnimMontage",  # former v1 extractor
    "AnimSequence",  # former v1 extractor
    "AnimationDataModel", "BehaviorTree", "BlackboardData", "ClothAsset",
    "CubeBuilder", "CurveFloat", "CurveLinearColor", "CurveVector",
    "DataAsset", "DialogueVoice", "DialogueWave", "FoliageType",
    "GroomAsset", "Landscape", "LandscapeGrassType",
    "LandscapeLayerInfoObject", "Level",
    "LevelSequence",  # former v1 extractor (binary); generic parse verified richer on Lyra sample
    "MediaPlayer", "MediaSource", "MediaTexture",
    "MovieScene",  # former v1 extractor
    "MovieSceneControlRigParameterSection",  # former v1 extractor
    "MovieSceneControlRigParameterTrack",  # former v1 extractor
    "ParticleSystem", "PoseAsset", "PrimaryDataAsset", "ReverbEffect",
    "SkeletalMeshLODSettings", "SoundClass", "SoundConcurrency",
    "SoundMix", "SoundSubmix", "SparseVolumeTexture", "SubsurfaceProfile",
    "Texture2DArray", "TextureRenderTarget2D", "TextureRenderTargetCube",
    "VolumeTexture", "WidgetBlueprint", "WidgetBlueprintGeneratedClass",
    "World",
)

def _record(class_name):
    return ObjectRecord(id="export:0", table_index=0, name="X",
                        class_name=class_name, status=ObjectStatus())

def test_handler_classes_still_claimed():
    handlers = get_handlers()
    ctx = VersionContext()
    for name in HANDLER_CLASSES:
        assert any(h.supports(_record(name), ctx) for h in handlers), name

def test_fallback_classes_stay_unclaimed():
    handlers = get_handlers()
    ctx = VersionContext()
    for name in FALLBACK_CLASSES:
        assert not any(h.supports(_record(name), ctx) for h in handlers), name
