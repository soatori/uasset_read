---
title: C++ Code Generation
section: cpp-gen
---

# C++ Code Generation

The C++ code generation module (Phase 56-66) converts UE blueprint data into C++ skeleton code, providing a complete mapping from `.uasset` parse results to standard UE C++ header files.

## Module Structure

| Submodule | Path | Responsibility |
|-----------|------|----------------|
| Type Mapping | `cpp_gen/cpp_type_mapper.py` | UE type path -> C++ type name |
| Property Mapping | `cpp_gen/cpp_uproperty_mapper.py` | CPF flags -> UPROPERTY specifiers |
| Skeleton Extraction | `cpp_gen/extract_cpp_skeleton.py` | LinkerParseResult -> CppClassIR |
| JSON IR | `cpp_gen/formatters/cpp_json_ir.py` | C++ class skeleton data model |
| Header Generation | `cpp_gen/formatters/cpp_header_formatter.py` | CppClassIR -> .h text |
| Default Value Formatting | `cpp_gen/cpp_default_value_formatter.py` | Default values / Transform / component initialization |
| Constructor IR | `cpp_gen/cpp_constructor_ir_builder.py` | Constructor IR building |
| Constructor Formatting | `cpp_gen/cpp_constructor_formatter.py` | Constructor text generation |

## Public API

```python
# Type mapping
UE_TO_CPP_TYPE_MAP: Dict[str, str]          # UE type path -> C++ type name dictionary
ENGINE_CLASS_PATHS: Dict[str, str]          # Engine class path -> C++ class name dictionary
ue_path_to_cpp_type(ue_type: str) -> str    # UE type path -> C++ type name
ue_package_path_to_cpp_class(path: str) -> str  # Package path -> C++ class name

# Property mapping
CPF_TO_UPROPERTY_MAP: List[Tuple]           # CPF flags -> UPROPERTY specifier mapping rules
cpf_flags_to_uproperty_marks(flags, is_component=False) -> List[str]

# Skeleton extraction
extract_cpp_class_skeleton(result) -> CppClassIR  # LinkerParseResult -> CppClassIR

# JSON IR formatting
CppProperty       # Single C++ UPROPERTY declaration data model
CppHeaderMeta     # Header file metadata model
CppClassIR        # Complete C++ class skeleton IR data model
CppMethodIR       # Blueprint function -> C++ method declaration
CppCallParameter  # Function parameter data model
CppCallStatement  # Call statement reference data model
format_cpp_class_json(ir) -> Dict  # JSON IR formatting function

# .h header file generation
format_cpp_header(ir) -> str         # CppClassIR -> .h text conversion
format_cpp_call_statements(stmts) -> str  # Call statement list -> .cpp text

# Constructor extraction
extract_cpp_constructor(ir) -> str   # Generate complete constructor text
build_constructor_sections(ir) -> Dict  # Build constructor sections
format_cpp_constructor(ir) -> str    # Format constructor text

# Default value formatting (Phase 59)
format_cpp_default_value(...)        # Format default values
format_cpp_transform(...)            # Format Transform assignments
format_cpp_component_init(...)       # Format component initialization
format_cpp_input_action_load(...)    # Format input action loading
```

## Data Models

### CppProperty

Single C++ UPROPERTY declaration.

| Property | Type | Description |
|----------|------|-------------|
| `cpp_type` | `str` | C++ type name (e.g. `"USceneComponent*"`, `"FVector"`, `"float"`) |
| `name` | `str` | Property name (e.g. `"DefaultSceneRoot"`, `"MoveSpeed"`) |
| `uproperty_marks` | `List[str]` | UPROPERTY specifier list |
| `category` | `str` | Property category (`"component"` or `"variable"`) |
| `default_value` | `Any` | Default value (`None` for components) |
| `cpp_comment` | `str` | Optional comment (original UE type reference) |

### CppHeaderMeta

Header file metadata.

| Property | Type | Description |
|----------|------|-------------|
| `pragma_once` | `bool` | Whether to include `#pragma once` (default `True`) |
| `includes` | `List[str]` | List of included header files |
| `forward_declarations` | `List[str]` | Forward declaration list |
| `generated_include` | `str` | `.generated.h` include path (must be the last include) |

### CppClassIR

Complete C++ class skeleton IR.

| Property | Type | Description |
|----------|------|-------------|
| `name` | `str` | C++ class name (e.g. `"ABP_FirstPersonCharacter"`) |
| `parent_class` | `str` | Parent class name (e.g. `"ACharacter"`) |
| `header_meta` | `CppHeaderMeta` | Header file metadata |
| `properties` | `List[CppProperty]` | Property list (components + variables) |
| `methods` | `List[CppMethodIR]` | Method list (populated in Phase 57) |
| `constructor` | `Dict` | Constructor data (populated in Phase 59) |

### CppMethodIR

Blueprint function -> C++ method declaration (Phase 57).

| Property | Type | Description |
|----------|------|-------------|
| `cpp_name` | `str` | C++ function name (cleaned) |
| `return_type` | `str` | C++ return type (default `"void"`) |
| `parameters` | `List[CppCallParameter]` | Parameter list |
| `ufunction_specifiers` | `List[str]` | UFUNCTION macro specifiers |
| `is_override` | `bool` | Whether it is `bOverrideFunction` |
| `is_const` | `bool` | `const` method modifier |
| `is_static` | `bool` | `static` method modifier |
| `is_pure` | `bool` | Pure function (no side effects) |
| `is_event` | `bool` | Event function |
| `access_modifier` | `str` | Access modifier (`public`/`protected`/`private`) |
| `body_text` | `str` | Kismet decompiled function body text (Phase 66) |

## Usage Example

```python
from uasset_read import parse_uasset_with_linker
from uasset_read.cpp_gen import (
    extract_cpp_class_skeleton,
    format_cpp_header,
    format_cpp_class_json,
)

# 1. Parse blueprint asset
result = parse_uasset_with_linker("path/to/BP_Character.uasset")

# 2. Extract C++ class skeleton
class_ir = extract_cpp_class_skeleton(result)

# 3. Generate .h header file text
header_text = format_cpp_header(class_ir)
print(header_text)

# 4. Generate JSON IR output
json_output = format_cpp_class_json(class_ir)
```

## UE Type Mapping

### Core Type Mapping Table

| UE Type Path | C++ Type |
|--------------|----------|
| `/Script/CoreUObject.Vector` | `FVector` |
| `/Script/CoreUObject.Rotator` | `FRotator` |
| `/Script/CoreUObject.Transform` | `FTransform` |
| `/Script/CoreUObject.Vector2D` | `FVector2D` |
| `/Script/CoreUObject.LinearColor` | `FLinearColor` |
| `/Script/CoreUObject.Name` | `FName` |
| `/Script/CoreUObject.Text` | `FText` |
| `/Script/CoreUObject.String` | `FString` |
| `/Script/CoreUObject.Guid` | `FGuid` |
| `/Script/Engine.HitResult` | `FHitResult` |
| `/Script/Engine.TimerHandle` | `FTimerHandle` |
| `/Script/Engine.GameplayTag` | `FGameplayTag` |

### Actor Types

| UE Type Path | C++ Type |
|--------------|----------|
| `/Script/Engine.Actor` | `AActor` |
| `/Script/Engine.Pawn` | `APawn` |
| `/Script/Engine.Character` | `ACharacter` |
| `/Script/Engine.Controller` | `AController` |
| `/Script/Engine.PlayerController` | `APlayerController` |
| `/Script/Engine.GameModeBase` | `AGameModeBase` |

### Component Types

| UE Type Path | C++ Type |
|--------------|----------|
| `/Script/Engine.SceneComponent` | `USceneComponent` |
| `/Script/Engine.ActorComponent` | `UActorComponent` |
| `/Script/Engine.StaticMeshComponent` | `UStaticMeshComponent` |
| `/Script/Engine.SkeletalMeshComponent` | `USkeletalMeshComponent` |
| `/Script/Engine.CameraComponent` | `UCameraComponent` |
| `/Script/Engine.SpringArmComponent` | `USpringArmComponent` |
| `/Script/Engine.CapsuleComponent` | `UCapsuleComponent` |
| `/Script/Engine.ArrowComponent` | `UArrowComponent` |

### Primitive Types

| UE Type | C++ Type |
|---------|----------|
| `float` | `float` |
| `double` | `double` |
| `bool` | `bool` |
| `int` / `int32` | `int32` |
| `int64` | `int64` |
| `byte` | `uint8` |
| `name` | `FName` |
| `text` | `FText` |
| `string` | `FString` |

### Type Inference Heuristics

For unknown type paths, the system uses the following heuristic rules:

- **Actor suffixes** (`Actor`, `Pawn`, `Character`, `Controller`, `GameMode`, etc.) -> `A` prefix
- **Component suffixes** -> `U` prefix
- **Default** -> `U` prefix (UObject)

## CPF -> UPROPERTY Mapping

| CPF Flag | UPROPERTY Specifier |
|----------|---------------------|
| `CPF_Edit` + `CPF_BlueprintVisible` | `EditAnywhere, BlueprintReadWrite` |
| `CPF_EditAnywhere` | `EditAnywhere` |
| `CPF_EditInstanceOnly` | `EditInstanceOnly` |
| `CPF_BlueprintReadOnly` | `BlueprintReadOnly` |
| `CPF_BlueprintReadWrite` | `BlueprintReadWrite` |
| `CPF_InstancedReference` | `Instanced` |
| `CPF_BlueprintAssignable` | `BlueprintAssignable` |
| `CPF_BlueprintCallable` | `BlueprintCallable` |
| `CPF_Replicated` | `Replicated` |
| `CPF_Net` (without Replicated) | `Net` |
| `CPF_Transient` | `Transient` |
| `CPF_DuplicateTransient` | `DuplicateTransient` |
| `CPF_Config` | `Config` |
| `CPF_SaveGame` | `SaveGame` |
| `CPF_NoClear` | `NoClear` |
| `CPF_ExposeOnSpawn` | `ExposeOnSpawn` |
| `CPF_Interp` | `Interp` |
| `CPF_RepNotify` | `RepNotify` |
| `CPF_Protected` | `Protected` |
| `CPF_AdvancedDisplay` | `AdvancedDisplay` |

### Component Default Specifiers

For component properties (`is_component=True`), if no explicit visibility/edit flags are set, the following are automatically added:
- `VisibleAnywhere`
- `BlueprintReadOnly`

## Function Flags (UFunctionFlags)

| Flag | Value | Description |
|------|-------|-------------|
| `FUNC_Final` | `0x00000001` | Final function (not overridable) |
| `FUNC_BlueprintAuthorityOnly` | `0x00000004` | Executes on authority only |
| `FUNC_BlueprintCosmetic` | `0x00000008` | Cosmetic-only execution |
| `FUNC_Exec` | `0x00000100` | Console command |
| `FUNC_Native` | `0x00000200` | Native function |
| `FUNC_Event` | `0x00000400` | Event function |
| `FUNC_UbergraphFunction` | `0x00001000` | Ubergraph function |
| `FUNC_Static` | `0x00002000` | Static function |
| `FUNC_BlueprintCallable` | `0x00040000` | Blueprint callable |
| `FUNC_BlueprintPure` | `0x00080000` | Pure function (no side effects) |
| `FUNC_Const` | `0x00200000` | const function |
| `FUNC_BlueprintEvent` | `0x08000000` | Blueprint event |

## Header File Generation Template

The generated `.h` files follow the UE standard format:

```cpp
#pragma once

#include "CoreMinimal.h"
#include "Engine/GameFramework/Character.h"
#include "ABP_FirstPersonCharacter.generated.h"

UCLASS(Blueprintable)
class ABP_FirstPersonCharacter : public ACharacter
{
    GENERATED_BODY()

public:
    ABP_FirstPersonCharacter();

protected:
    // Components
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Instanced, Category = "Components", meta = (AllowPrivateAccess = "true"))
    USceneComponent* DefaultSceneRoot;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Instanced, Category = "Components", meta = (AllowPrivateAccess = "true"))
    USkeletalMeshComponent* FirstPersonMesh;

    // Variables
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Movement")
    float MoveSpeed = 100.0f;

public:
    // Blueprint Functions
    UFUNCTION(BlueprintCallable)
    void Move(double LeftRight, double ForwardBackward);

    void PrimaryThumbstick(double Axis_X, double Axis_Y) override;
};
```

## JSON IR Output Format

```json
{
  "cpp_class": {
    "name": "ABP_FirstPersonCharacter",
    "parent_class": "ACharacter",
    "header_meta": {
      "pragma_once": true,
      "includes": ["\"Engine/GameFramework/Character.h\""],
      "forward_declarations": [],
      "generated_include": "\"ABP_FirstPersonCharacter.generated.h\""
    },
    "properties": [
      {
        "cpp_type": "USceneComponent*",
        "name": "DefaultSceneRoot",
        "uproperty_marks": ["VisibleAnywhere", "BlueprintReadOnly", "Instanced"],
        "category": "component"
      }
    ],
    "methods": [],
    "constructor": {
      "component_creations": [],
      "component_assignments": [],
      "default_values": []
    }
  },
  "output_version": "1.0"
}
```

## Name Cleaning Rules

### Component Name Cleaning

The system removes the following UE internal suffixes:

| Pattern | Example | Result |
|---------|---------|--------|
| `_GEN_VARIABLE$` | `FirstPersonMesh_GEN_VARIABLE` | `FirstPersonMesh` |
| `_\d+__[A-F0-9]+$` | `CameraComponent_0__CCE3C0B4` | `CameraComponent` |
| `_\d+$` | `Arrow_1` | `Arrow` |

### Class Name Simplification

| Input | Output |
|-------|--------|
| `/Game/FirstPerson/Blueprints/BP_FirstPersonCharacter` | `BP_FirstPersonCharacter` |
| `Game_FirstPerson_Blueprints_BP_FirstPersonCharacter` | `BP_FirstPersonCharacter` |

### C++ Identifier Cleaning

| Input | Output |
|-------|--------|
| `Left / Right` | `LeftRight` |
| `Primary Thumbstick` | `PrimaryThumbstick` |
| `2DValue` | `_2DValue` |

## Blueprint Metadata Filtering

The following blueprint internal metadata properties will **not** be output as C++ member variables:

| Category | Property Name |
|----------|---------------|
| Blueprint System | `BlueprintSystemVersion`, `BlueprintGuid`, `bLegacyNeedToPurgeSkelRefs` |
| Construction Script | `SimpleConstructionScript` |
| Graph Related | `UbergraphPages`, `FunctionGraphs`, `NewVariables`, `CategorySorting` |
| Class References | `ThumbnailInfo`, `GeneratedClass`, `PropertyGuids` |
| Ubergraph | `UbergraphFunction`, `UbergraphFrame` |

## Input Action Variable Extraction (P2)

Automatically extracts input action references from `K2Node_EnhancedInputAction` nodes, generating `UInputAction*` member variables:

```cpp
UPROPERTY(EditAnywhere, Category = "Input")
UInputAction* IA_Jump;  // Input Action: /Game/Input/IA_Jump.IA_Jump
```

## Function Body Injection (Phase 66)

Kismet-decompiled `cpp_code` is automatically injected into `CppMethodIR.body_text`. Matching logic:

1. **Exact match**: `function_name == cpp_name`
2. **Cleaned match**: `function_name` after cleaning == `cpp_name`
3. **Case-insensitive match**

## Related Sections

- [[Kismet]] — Kismet bytecode decompilation
- [[Blueprint]] — Blueprint variable/component/metadata extraction
- [[Linker]] — Object linker and PackageLinker
- [[Renderer System]] — Renderers and output formats
