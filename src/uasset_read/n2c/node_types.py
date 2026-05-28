"""N2C 节点语义类型枚举（126 种）。

Phase 68 从 30 种扩展到 126 种（UE5.8 全覆盖）。
数据来源：UE5.8 Engine/Source/Editor/ 全模块扫描。
"""
from enum import Enum


class N2CNodeType(Enum):
    """K2Node 语义类型枚举（UE5.8 全覆盖）。

    包含 122 种类型，覆盖 BlueprintGraph、AnimGraph、AIGraph、
    UMGEditor、MovieSceneTools、GameplayTasksEditor 模块。
    """

    # === Phase 69 已用类型（30 种，保持不变）===

    CallFunction = "CallFunction"
    Event = "Event"
    CustomEvent = "CustomEvent"
    FunctionEntry = "FunctionEntry"
    FunctionResult = "FunctionResult"
    VariableGet = "VariableGet"
    VariableSet = "VariableSet"
    Branch = "Branch"               # K2Node_IfThenElse
    Sequence = "Sequence"           # K2Node_ExecutionSequence
    SwitchInt = "SwitchInt"         # K2Node_SwitchInteger
    SwitchString = "SwitchString"
    SwitchEnum = "SwitchEnum"
    DynamicCast = "DynamicCast"
    ClassDynamicCast = "ClassDynamicCast"
    MakeStruct = "MakeStruct"
    BreakStruct = "BreakStruct"
    MakeArray = "MakeArray"
    MakeMap = "MakeMap"
    MakeSet = "MakeSet"
    AddDelegate = "AddDelegate"
    CreateDelegate = "CreateDelegate"
    ClearDelegate = "ClearDelegate"
    AsyncAction = "AsyncAction"
    SpawnActor = "SpawnActor"
    Timeline = "Timeline"
    FormatText = "FormatText"
    LocalVariable = "LocalVariable"
    MathExpression = "MathExpression"
    EnumLiteral = "EnumLiteral"
    BitmaskLiteral = "BitmaskLiteral"

    # === Base / Root ===

    K2NodeBase = "K2NodeBase"       # K2Node 基类

    # === Function Calls 新增 ===

    CallArrayFunction = "CallArrayFunction"
    CallDelegate = "CallDelegate"
    CallParentFunction = "CallParentFunction"
    CallFunctionOnMember = "CallFunctionOnMember"
    CallDataTableFunction = "CallDataTableFunction"
    CallMaterialParameterCollectionFunction = "CallMaterialParameterCollectionFunction"
    Message = "Message"
    EditorPropertyAccessBase = "EditorPropertyAccessBase"
    PromotableOperator = "PromotableOperator"
    BinaryOperator = "BinaryOperator"       # K2Node_CommutativeAssociativeBinaryOperator
    AddComponent = "AddComponent"
    AnimGetter = "AnimGetter"
    InstancedStruct = "InstancedStruct"
    GetInputAxisValue = "GetInputAxisValue"
    GetInputAxisKeyValue = "GetInputAxisKeyValue"
    GetInputVectorAxisValue = "GetInputVectorAxisValue"

    # === Variables 新增 ===

    Variable = "Variable"                   # K2Node_Variable 基类
    VariableSetRef = "VariableSetRef"
    StructMemberGet = "StructMemberGet"
    StructMemberSet = "StructMemberSet"
    StructOperation = "StructOperation"     # K2Node_StructOperation 基类
    SetFieldsInStruct = "SetFieldsInStruct"

    # === Events 新增 ===

    ActorBoundEvent = "ActorBoundEvent"
    ComponentBoundEvent = "ComponentBoundEvent"
    GeneratedBoundEvent = "GeneratedBoundEvent"
    InputActionEvent = "InputActionEvent"
    InputAxisEvent = "InputAxisEvent"
    InputKeyEvent = "InputKeyEvent"
    InputTouchEvent = "InputTouchEvent"
    InputVectorAxisEvent = "InputVectorAxisEvent"
    WidgetAnimationEvent = "WidgetAnimationEvent"

    # === Flow Control 新增 ===

    MultiGate = "MultiGate"
    DoOnce = "DoOnce"                       # K2Node_DoOnceMultiInput
    Select = "Select"
    EaseFunction = "EaseFunction"

    # === Switches 新增 ===

    Switch = "Switch"                       # K2Node_Switch 基类
    SwitchName = "SwitchName"

    # === Structs 新增 ===
    # (MakeStruct, BreakStruct, StructOperation 已在上方)

    # === Containers 新增 ===

    MakeContainer = "MakeContainer"         # K2Node_MakeContainer 基类
    GetArrayItem = "GetArrayItem"
    MapForEach = "MapForEach"
    SetForEach = "SetForEach"

    # === Casting 新增 ===

    CastByteToEnum = "CastByteToEnum"

    # === Delegates 新增 ===

    RemoveDelegate = "RemoveDelegate"
    AssignDelegate = "AssignDelegate"
    BaseMCDelegate = "BaseMCDelegate"       # K2Node_BaseMCDelegate 基类
    DelegateSet = "DelegateSet"

    # === Async/Latent 新增 ===

    BaseAsyncTask = "BaseAsyncTask"         # K2Node_BaseAsyncTask 基类
    PlayMontage = "PlayMontage"
    LatentGameplayTaskCall = "LatentGameplayTaskCall"
    PlayAnimation = "PlayAnimation"

    # === Math/Logic 新增 ===
    # (MathExpression, PromotableOperator, BinaryOperator 已在上方)

    # === Literals 新增 ===

    Literal = "Literal"
    Self = "Self"

    # === Enum Operations 新增 ===

    GetEnumeratorName = "GetEnumeratorName"
    GetEnumeratorNameAsString = "GetEnumeratorNameAsString"
    GetNumEnumEntries = "GetNumEnumEntries"
    ForEachEnum = "ForEachEnum"             # K2Node_ForEachElementInEnum
    EnumEquality = "EnumEquality"
    EnumInequality = "EnumInequality"

    # === Object Creation 新增 ===

    SpawnActorFromClass = "SpawnActorFromClass"
    ConstructObject = "ConstructObject"     # K2Node_ConstructObjectFromClass 基类
    GenericCreateObject = "GenericCreateObject"
    AddComponentByClass = "AddComponentByClass"
    CreateWidget = "CreateWidget"
    CreateDragDropOperation = "CreateDragDropOperation"

    # === Input Actions 新增 ===

    InputAction = "InputAction"
    InputAxis = "InputAxis"                 # Note: K2Node_InputAxisKeyEvent in UE5.8
    InputKey = "InputKey"
    InputTouch = "InputTouch"
    InputAxisKeyEvent = "InputAxisKeyEvent"
    EnhancedInputAction = "EnhancedInputAction"  # UE5.5+ enhanced input system

    # === Subsystems 新增 ===

    GetSubsystem = "GetSubsystem"
    GetClassDefaults = "GetClassDefaults"

    # === Functions 新增 ===

    FunctionTerminator = "FunctionTerminator"
    EditablePinBase = "EditablePinBase"     # K2Node_EditablePinBase 基类

    # === Macros/Tunnels 新增 ===

    MacroInstance = "MacroInstance"
    Tunnel = "Tunnel"
    TunnelBoundary = "TunnelBoundary"
    Composite = "Composite"

    # === Asset Loading 新增 ===

    LoadAsset = "LoadAsset"
    ConvertAsset = "ConvertAsset"

    # === Data Table 新增 ===

    GetDataTableRow = "GetDataTableRow"

    # === Text/Formatting 新增 ===

    GenericToText = "GenericToText"

    # === Misc 新增 ===

    Knot = "Knot"
    TemporaryVariable = "TemporaryVariable"
    PureAssignmentStatement = "PureAssignmentStatement"
    AssignmentStatement = "AssignmentStatement"
    Copy = "Copy"
    DeadClass = "DeadClass"
    MakeVariable = "MakeVariable"
    SetVariableOnPersistentFrame = "SetVariableOnPersistentFrame"

    # === MovieScene 新增 ===

    GetSequenceBinding = "GetSequenceBinding"

    # === AI 新增 ===

    AIMoveTo = "AIMoveTo"

    # === AnimGraph 新增 ===

    AnimNodeReference = "AnimNodeReference"
    TransitionRuleGetter = "TransitionRuleGetter"

    # === Comment ===

    Comment = "Comment"  # EdGraphNode_Comment

    # === Fallback ===

    Unknown = "Unknown"
