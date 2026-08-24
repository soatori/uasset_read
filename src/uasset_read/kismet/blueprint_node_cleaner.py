"""Blueprint node to C++ semantic call mapper.

Converts common blueprint nodes (e.g. ACharacter::AddMovementInput) into
readable C++ semantic calls, making decompiled output closer to hand-written code.

Design principles:
- Complements MathFunctionCleaner: MathFunctionCleaner handles math/string/system library functions,
  BlueprintNodeCleaner handles game logic/character control/Actor operations and other blueprint nodes.
- Used as a post-processing step for KismetTranslator output; does not modify the expression tree itself.
- Unknown nodes fall back to ClassName::FuncName format.

Usage:
    from uasset_read.kismet.blueprint_node_cleaner import BlueprintNodeCleaner

    result = BlueprintNodeCleaner.clean("Character", "AddMovementInput", ["WorldDirection", "ScaleValue"])
    # → "AddMovementInput(WorldDirection, ScaleValue)"
"""

from typing import Callable


# ===========================================================================
# Mapping entry data structures
# ===========================================================================

class _MappingEntry:
    """Single blueprint node mapping entry.

    Attributes:
        class_name: UE class name (without prefix, e.g. "Character" not "ACharacter")
        func_name: UE function name (e.g. "AddMovementInput")
        handler: Callback function that generates C++ output
    """

    __slots__ = ("class_name", "func_name", "handler")

    def __init__(
        self,
        class_name: str,
        func_name: str,
        handler: Callable[[list[str]], str],
    ) -> None:
        self.class_name = class_name
        self.func_name = func_name
        self.handler = handler


# ===========================================================================
# Mapping table: sub-functions split by category
# ===========================================================================

def _add_character_mappings(_add: Callable) -> None:
    """ACharacter movement control mappings."""
    _add("Character", "AddMovementInput",
         lambda p: f"AddMovementInput({p[0]}, {p[1]})" if len(p) >= 2
         else f"AddMovementInput({', '.join(p)})")

    _add("Character", "Jump",
         lambda p: "Jump()")

    _add("Character", "StopJumping",
         lambda p: "StopJumping()")

    _add("Character", "Crouch",
         lambda p: "Crouch()" if not p else f"Crouch({p[0]})")

    _add("Character", "UnCrouch",
         lambda p: "UnCrouch()" if not p else f"UnCrouch({p[0]})")

    _add("Character", "LaunchCharacter",
         lambda p: f"LaunchCharacter(FVector({p[0]}, {p[1]}, {p[2]}), {p[3]}, {p[4]})"
         if len(p) >= 5 else f"LaunchCharacter({', '.join(p)})")

    _add("Character", "CanJump",
         lambda p: "CanJump()")

    _add("Character", "IsJumping",
         lambda p: "IsJumping()")

    _add("Character", "IsCrouched",
         lambda p: "IsCrouched()")


def _add_actor_mappings(_add: Callable) -> None:
    """AActor general operation mappings (including KismetSystemLibrary, GameplayStatics, etc.)."""
    # AActor location/transform
    _add("Actor", "K2_GetActorLocation",
         lambda p: "GetActorLocation()")

    _add("Actor", "K2_SetActorLocation",
         lambda p: f"SetActorLocation({p[0]}, {p[1]}, {p[2]})"
         if len(p) >= 3 else f"SetActorLocation({', '.join(p)})")

    _add("Actor", "K2_SetActorLocationAndRotation",
         lambda p: f"SetActorLocationAndRotation({p[0]}, {p[1]}, {p[2]})"
         if len(p) >= 3 else f"SetActorLocationAndRotation({', '.join(p)})")

    _add("Actor", "K2_GetActorRotation",
         lambda p: "GetActorRotation()")

    _add("Actor", "K2_SetActorRotation",
         lambda p: f"SetActorRotation({p[0]}, {p[1]})"
         if len(p) >= 2 else f"SetActorRotation({', '.join(p)})")

    _add("Actor", "K2_GetActorScale3D",
         lambda p: "GetActorScale3D()")

    _add("Actor", "K2_SetActorScale3D",
         lambda p: f"SetActorScale3D({p[0]})")

    _add("Actor", "K2_SetActorTransform",
         lambda p: f"SetActorTransform({p[0]}, {p[1]})"
         if len(p) >= 2 else f"SetActorTransform({', '.join(p)})")

    _add("Actor", "K2_GetActorTransform",
         lambda p: "GetActorTransform()")

    _add("Actor", "GetActorForwardVector",
         lambda p: "GetActorForwardVector()")

    _add("Actor", "GetActorRightVector",
         lambda p: "GetActorRightVector()")

    _add("Actor", "GetActorUpVector",
         lambda p: "GetActorUpVector()")

    # AActor lifecycle / general
    _add("Actor", "K2_DestroyActor",
         lambda p: "Destroy()")

    _add("Actor", "K2_SetActorHiddenInGame",
         lambda p: f"SetActorHiddenInGame({p[0]})"
         if p else "SetActorHiddenInGame()")

    _add("Actor", "SetActorEnableCollision",
         lambda p: f"SetActorEnableCollision({p[0]})"
         if p else "SetActorEnableCollision()")

    _add("Actor", "GetActorBounds",
         lambda p: f"GetActorBounds({p[0]}, {p[1]}, {p[2]})"
         if len(p) >= 3 else f"GetActorBounds({', '.join(p)})")

    _add("Actor", "GetVelocity",
         lambda p: "GetVelocity()")

    _add("Actor", "GetActorEnableCollision",
         lambda p: "GetActorEnableCollision()")

    _add("Actor", "IsHidden",
         lambda p: "IsHidden()")

    _add("Actor", "SetActorTickEnabled",
         lambda p: f"SetActorTickEnabled({p[0]})"
         if p else "SetActorTickEnabled()")

    # AActor components
    _add("Actor", "GetComponentByClass",
         lambda p: f"GetComponentByClass<{p[0]}>()"
         if p else "GetComponentByClass()")

    _add("Actor", "GetComponentsByClass",
         lambda p: f"GetComponentsByClass<{p[0]}>()"
         if p else "GetComponentsByClass()")

    # AActor attachment
    _add("Actor", "K2_AttachToActor",
         lambda p: f"AttachToActor({p[0]}, {p[1]}, {p[2]}, {p[3]})"
         if len(p) >= 4 else f"AttachToActor({', '.join(p)})")

    _add("Actor", "K2_AttachToComponent",
         lambda p: f"AttachToComponent({p[0]}, {p[1]}, {p[2]}, {p[3]})"
         if len(p) >= 4 else f"AttachToComponent({', '.join(p)})")

    _add("Actor", "K2_DetachFromActor",
         lambda p: f"DetachFromActor({p[0]}, {p[1]}, {p[2]})"
         if len(p) >= 3 else f"DetachFromActor({', '.join(p)})")

    # UKismetSystemLibrary timers
    _add("KismetSystemLibrary", "K2_SetTimer",
         lambda p: f"GetWorldTimerManager().SetTimer({p[0]}, {p[1]}, {p[2]}, {p[3]})"
         if len(p) >= 4 else f"GetWorldTimerManager().SetTimer({', '.join(p)})")

    _add("KismetSystemLibrary", "K2_SetTimerDelegate",
         lambda p: f"GetWorldTimerManager().SetTimer({p[0]}, {p[1]}, {p[2]})"
         if len(p) >= 3 else f"GetWorldTimerManager().SetTimer({', '.join(p)})")

    _add("KismetSystemLibrary", "K2_ClearTimer",
         lambda p: f"GetWorldTimerManager().ClearTimer({p[0]})"
         if p else "GetWorldTimerManager().ClearTimer()")

    _add("KismetSystemLibrary", "K2_IsTimerActive",
         lambda p: f"GetWorldTimerManager().IsTimerActive({p[0]})"
         if p else "GetWorldTimerManager().IsTimerActive()")

    _add("KismetSystemLibrary", "K2_IsTimerPaused",
         lambda p: f"GetWorldTimerManager().IsTimerPaused({p[0]})"
         if p else "GetWorldTimerManager().IsTimerPaused()")

    _add("KismetSystemLibrary", "K2_PauseTimer",
         lambda p: f"GetWorldTimerManager().PauseTimer({p[0]})"
         if p else "GetWorldTimerManager().PauseTimer()")

    _add("KismetSystemLibrary", "K2_UnPauseTimer",
         lambda p: f"GetWorldTimerManager().UnPauseTimer({p[0]})"
         if p else "GetWorldTimerManager().UnPauseTimer()")

    _add("KismetSystemLibrary", "K2_GetTimerElapsedTime",
         lambda p: f"GetWorldTimerManager().GetTimerElapsedTime({p[0]})"
         if p else "GetWorldTimerManager().GetTimerElapsedTime()")

    _add("KismetSystemLibrary", "K2_GetTimerRemainingTime",
         lambda p: f"GetWorldTimerManager().GetTimerRemainingTime({p[0]})"
         if p else "GetWorldTimerManager().GetTimerRemainingTime()")

    # UKismetSystemLibrary debug
    _add("KismetSystemLibrary", "PrintString",
         lambda p: f'UE_LOG(LogTemp, Log, TEXT({p[0]}))'
         if p else 'UE_LOG(LogTemp, Log, TEXT(""))')

    _add("KismetSystemLibrary", "PrintText",
         lambda p: f'UE_LOG(LogTemp, Log, *{p[0]}.ToString())'
         if p else 'UE_LOG(LogTemp, Log, TEXT(""))')

    _add("KismetSystemLibrary", "PrintWarning",
         lambda p: f'UE_LOG(LogTemp, Warning, TEXT({p[0]}))'
         if p else 'UE_LOG(LogTemp, Warning, TEXT(""))')

    _add("KismetSystemLibrary", "PrintError",
         lambda p: f'UE_LOG(LogTemp, Error, TEXT({p[0]}))'
         if p else 'UE_LOG(LogTemp, Error, TEXT(""))')

    # UKismetSystemLibrary collision/raycast
    _add("KismetSystemLibrary", "LineTraceSingle",
         lambda p: f"GetWorld()->LineTraceSingleByChannel({p[0]}, {p[1]}, {p[2]})"
         if len(p) >= 3 else f"LineTraceSingle({', '.join(p)})")

    _add("KismetSystemLibrary", "LineTraceMulti",
         lambda p: f"GetWorld()->LineTraceMultiByChannel({p[0]}, {p[1]}, {p[2]})"
         if len(p) >= 3 else f"LineTraceMulti({', '.join(p)})")

    _add("KismetSystemLibrary", "SphereOverlapActors",
         lambda p: f"GetWorld()->OverlapMultiByChannel({p[0]}, {p[1]}, {p[2]})"
         if len(p) >= 3 else f"SphereOverlapActors({', '.join(p)})")

    # UKismetSystemLibrary delay/async
    _add("KismetSystemLibrary", "Delay",
         lambda p: f"UKismetSystemLibrary::Delay(this, {p[0]}, {{}})"
         if p else "UKismetSystemLibrary::Delay(this, 0.0f, {})")

    # UKismetMathLibrary common math (supplements semantic mappings not covered by MathFunctionCleaner)
    _add("KismetMathLibrary", "RandomUnitVector",
         lambda p: "FMath::VRand()")

    _add("KismetMathLibrary", "RandomUnitVectorInConeInDegrees",
         lambda p: f"FMath::VRandCone({p[0]}, FMath::DegreesToRadians({p[1]}))"
         if len(p) >= 2 else f"FMath::VRandCone({', '.join(p)})")

    _add("KismetMathLibrary", "RandomUnitVectorInConeInRadians",
         lambda p: f"FMath::VRandCone({p[0]}, {p[1]})"
         if len(p) >= 2 else f"FMath::VRandCone({', '.join(p)})")

    _add("KismetMathLibrary", "GetForwardVector",
         lambda p: f"{p[0]}.Vector()" if p else "FRotator().Vector()")

    _add("KismetMathLibrary", "FindLookAtRotation",
         lambda p: f"({p[1]} - {p[0]}).Rotation()"
         if len(p) >= 2 else f"FindLookAtRotation({', '.join(p)})")

    # GameplayStatics
    _add("GameplayStatics", "GetPlayerController",
         lambda p: f"UGameplayStatics::GetPlayerController(this, {p[0]})"
         if p else "UGameplayStatics::GetPlayerController(this, 0)")

    _add("GameplayStatics", "GetPlayerCharacter",
         lambda p: f"UGameplayStatics::GetPlayerCharacter(this, {p[0]})"
         if p else "UGameplayStatics::GetPlayerCharacter(this, 0)")

    _add("GameplayStatics", "GetPlayerPawn",
         lambda p: f"UGameplayStatics::GetPlayerPawn(this, {p[0]})"
         if p else "UGameplayStatics::GetPlayerPawn(this, 0)")

    _add("GameplayStatics", "SpawnEmitterAtLocation",
         lambda p: f"UGameplayStatics::SpawnEmitterAtLocation(this, {p[0]}, {p[1]}, {p[2]})"
         if len(p) >= 3 else f"UGameplayStatics::SpawnEmitterAtLocation(this, {', '.join(p)})")

    _add("GameplayStatics", "PlaySoundAtLocation",
         lambda p: f"UGameplayStatics::PlaySoundAtLocation(this, {p[0]}, {p[1]}, {p[2]})"
         if len(p) >= 3 else f"UGameplayStatics::PlaySoundAtLocation(this, {', '.join(p)})")

    _add("GameplayStatics", "OpenLevel",
         lambda p: f"UGameplayStatics::OpenLevel(this, {p[0]})"
         if p else "UGameplayStatics::OpenLevel(this, NAME_None)")

    _add("GameplayStatics", "SetGamePaused",
         lambda p: f"UGameplayStatics::SetGamePaused(this, {p[0]})"
         if p else "UGameplayStatics::SetGamePaused(this, true)")

    _add("GameplayStatics", "GetGameMode",
         lambda p: "UGameplayStatics::GetGameMode(this)")

    _add("GameplayStatics", "GetGameState",
         lambda p: "UGameplayStatics::GetGameState(this)")

    # Controller
    _add("Controller", "GetControlRotation",
         lambda p: "GetControlRotation()")

    _add("Controller", "SetControlRotation",
         lambda p: f"SetControlRotation({p[0]})"
         if p else "SetControlRotation()")

    _add("Controller", "GetPawn",
         lambda p: "GetPawn()")

    _add("Controller", "Possess",
         lambda p: f"Possess({p[0]})" if p else "Possess()")

    _add("Controller", "UnPossess",
         lambda p: "UnPossess()")

    # PlayerController
    _add("PlayerController", "GetHUD",
         lambda p: "GetHUD()")

    _add("PlayerController", "WasInputKeyJustPressed",
         lambda p: f"WasInputKeyJustPressed({p[0]})"
         if p else "WasInputKeyJustPressed()")

    _add("PlayerController", "WasInputKeyJustReleased",
         lambda p: f"WasInputKeyJustReleased({p[0]})"
         if p else "WasInputKeyJustReleased()")

    _add("PlayerController", "IsInputKeyDown",
         lambda p: f"IsInputKeyDown({p[0]})"
         if p else "IsInputKeyDown()")

    _add("PlayerController", "GetInputMouseDelta",
         lambda p: f"GetInputMouseDelta({p[0]}, {p[1]})"
         if len(p) >= 2 else f"GetInputMouseDelta({', '.join(p)})")

    # SceneComponent
    _add("SceneComponent", "K2_SetWorldLocation",
         lambda p: f"SetWorldLocation({p[0]}, {p[1]})"
         if len(p) >= 2 else f"SetWorldLocation({', '.join(p)})")

    _add("SceneComponent", "K2_SetWorldRotation",
         lambda p: f"SetWorldRotation({p[0]}, {p[1]})"
         if len(p) >= 2 else f"SetWorldRotation({', '.join(p)})")

    _add("SceneComponent", "K2_SetRelativeLocation",
         lambda p: f"SetRelativeLocation({p[0]}, {p[1]})"
         if len(p) >= 2 else f"SetRelativeLocation({', '.join(p)})")

    _add("SceneComponent", "K2_SetRelativeRotation",
         lambda p: f"SetRelativeRotation({p[0]}, {p[1]})"
         if len(p) >= 2 else f"SetRelativeRotation({', '.join(p)})")

    _add("SceneComponent", "GetComponentLocation",
         lambda p: "GetComponentLocation()")

    _add("SceneComponent", "GetComponentRotation",
         lambda p: "GetComponentRotation()")

    _add("SceneComponent", "GetComponentScale",
         lambda p: "GetComponentScale()")

    _add("SceneComponent", "GetForwardVector",
         lambda p: "GetForwardVector()")

    _add("SceneComponent", "GetRightVector",
         lambda p: "GetRightVector()")

    _add("SceneComponent", "GetUpVector",
         lambda p: "GetUpVector()")

    # PrimitiveComponent
    _add("PrimitiveComponent", "SetSimulatePhysics",
         lambda p: f"SetSimulatePhysics({p[0]})"
         if p else "SetSimulatePhysics()")

    _add("PrimitiveComponent", "SetPhysicsLinearVelocity",
         lambda p: f"SetPhysicsLinearVelocity({p[0]}, {p[1]})"
         if len(p) >= 2 else f"SetPhysicsLinearVelocity({', '.join(p)})")

    _add("PrimitiveComponent", "GetPhysicsLinearVelocity",
         lambda p: "GetPhysicsLinearVelocity()")

    _add("PrimitiveComponent", "SetPhysicsAngularVelocityInDegrees",
         lambda p: f"SetPhysicsAngularVelocityInDegrees({p[0]}, {p[1]})"
         if len(p) >= 2 else f"SetPhysicsAngularVelocityInDegrees({', '.join(p)})")

    _add("PrimitiveComponent", "AddImpulse",
         lambda p: f"AddImpulse({p[0]}, {p[1]})"
         if len(p) >= 2 else f"AddImpulse({', '.join(p)})")

    _add("PrimitiveComponent", "AddForce",
         lambda p: f"AddForce({p[0]}, {p[1]})"
         if len(p) >= 2 else f"AddForce({', '.join(p)})")

    _add("PrimitiveComponent", "SetCollisionEnabled",
         lambda p: f"SetCollisionEnabled({p[0]})"
         if p else "SetCollisionEnabled()")

    _add("PrimitiveComponent", "SetCollisionResponseToAllChannels",
         lambda p: f"SetCollisionResponseToAllChannels({p[0]})"
         if p else "SetCollisionResponseToAllChannels()")


def _add_pawn_mappings(_add: Callable) -> None:
    """APawn character control mappings."""
    _add("Pawn", "AddControllerYawInput",
         lambda p: f"AddControllerYawInput({p[0]})"
         if p else "AddControllerYawInput()")

    _add("Pawn", "AddControllerPitchInput",
         lambda p: f"AddControllerPitchInput({p[0]})"
         if p else "AddControllerPitchInput()")

    _add("Pawn", "AddControllerRollInput",
         lambda p: f"AddControllerRollInput({p[0]})"
         if p else "AddControllerRollInput()")

    _add("Pawn", "GetController",
         lambda p: "GetController()")

    _add("Pawn", "IsControlled",
         lambda p: "IsControlled()")

    _add("Pawn", "IsPlayerControlled",
         lambda p: "IsPlayerControlled()")


def _add_anim_mappings(_add: Callable) -> None:
    """AnimInstance animation mappings."""
    _add("AnimInstance", "Montage_Play",
         lambda p: f"Montage_Play({p[0]}, {p[1]})"
         if len(p) >= 2 else f"Montage_Play({', '.join(p)})")

    _add("AnimInstance", "Montage_Stop",
         lambda p: f"Montage_Stop({p[0]})"
         if p else "Montage_Stop()")

    _add("AnimInstance", "Montage_IsPlaying",
         lambda p: f"Montage_IsPlaying({p[0]})"
         if p else "Montage_IsPlaying()")

    _add("AnimInstance", "Montage_JumpToSection",
         lambda p: f"Montage_JumpToSection({p[0]}, {p[1]})"
         if len(p) >= 2 else f"Montage_JumpToSection({', '.join(p)})")

    _add("AnimInstance", "TryGetPawnOwner",
         lambda p: "TryGetPawnOwner()")


def _add_widget_mappings(_add: Callable) -> None:
    """UserWidget UI mappings."""
    _add("UserWidget", "SetVisibility",
         lambda p: f"SetVisibility({p[0]})"
         if p else "SetVisibility()")

    _add("UserWidget", "GetVisibility",
         lambda p: "GetVisibility()")

    _add("UserWidget", "AddToViewport",
         lambda p: "AddToViewport()" if not p else f"AddToViewport({p[0]})")

    _add("UserWidget", "RemoveFromParent",
         lambda p: "RemoveFromParent()")

    _add("UserWidget", "SetIsEnabled",
         lambda p: f"SetIsEnabled({p[0]})"
         if p else "SetIsEnabled()")


def _add_niagara_mappings(_add: Callable) -> None:
    """NiagaraComponent particle mappings."""
    _add("NiagaraComponent", "SetNiagaraVariableFloat",
         lambda p: f"SetNiagaraVariableFloat({p[0]}, {p[1]})"
         if len(p) >= 2 else f"SetNiagaraVariableFloat({', '.join(p)})")

    _add("NiagaraComponent", "SetNiagaraVariableVec3",
         lambda p: f"SetNiagaraVariableVec3({p[0]}, {p[1]})"
         if len(p) >= 2 else f"SetNiagaraVariableVec3({', '.join(p)})")

    _add("NiagaraComponent", "Activate",
         lambda p: "Activate()" if not p else f"Activate({p[0]})")

    _add("NiagaraComponent", "Deactivate",
         lambda p: "Deactivate()")


# ===========================================================================
# Mapping table construction entry point
# ===========================================================================

def _make_mappings() -> dict[str, _MappingEntry]:
    """Build mapping table, keyed by normalized "ClassName::FuncName" format."""
    entries: list[_MappingEntry] = []

    def _add(cls: str, func: str, handler: Callable[[list[str]], str]) -> None:
        entries.append(_MappingEntry(cls, func, handler))

    _add_character_mappings(_add)
    _add_actor_mappings(_add)
    _add_pawn_mappings(_add)
    _add_anim_mappings(_add)
    _add_widget_mappings(_add)
    _add_niagara_mappings(_add)

    result: dict[str, _MappingEntry] = {}
    for entry in entries:
        key = f"{entry.class_name}::{entry.func_name}"
        result[key] = entry
    return result


# Pre-built mapping table (module-level singleton)
_MAPPINGS: dict[str, _MappingEntry] = _make_mappings()

# Known class name set (for prefix stripping match)
_KNOWN_CLASSES: set[str] = {e.class_name for e in _MAPPINGS.values()}


# ===========================================================================
# BlueprintNodeCleaner — main entry point
# ===========================================================================

class BlueprintNodeCleaner:
    """Blueprint node C++ semantic call mapper.

    Converts resolved ClassName::FuncName format to more readable C++ calls.
    Used as a post-processing step for KismetTranslator output.

    Usage:
        result = BlueprintNodeCleaner.clean("Character", "AddMovementInput", ["WorldDirection", "1.0f"])
        # -> "AddMovementInput(WorldDirection, 1.0f)"

        # Class names with UE prefix are auto-stripped
        result = BlueprintNodeCleaner.clean("ACharacter", "Jump", [])
        # -> "Jump()"

        # Unknown nodes fall back to ClassName::FuncName format
        result = BlueprintNodeCleaner.clean("MyClass", "MyFunc", ["arg1"])
        # -> "MyClass::MyFunc(arg1)"
    """

    @staticmethod
    def clean(class_name: str, func_name: str, params: list[str]) -> str:
        """Convert Blueprint node call to C++ semantic format.

        Args:
            class_name: UE class name (with or without prefix, e.g. "ACharacter" or "Character")
            func_name: Function name (e.g. "AddMovementInput")
            params: List of already-translated parameter strings

        Returns:
            Cleaned C++ expression string
        """
        if not func_name:
            return f"{class_name}::{func_name}({', '.join(params)})"

        # Strip UE prefix (A=Actor, U=Object, F=Struct, I=Interface, E=Enum)
        stripped_class = _strip_ue_prefix(class_name)

        # Try exact match
        key = f"{stripped_class}::{func_name}"
        entry = _MAPPINGS.get(key)
        if entry is not None:
            return entry.handler(params)

        # Try matching by func_name only (for cross-class generic functions)
        # Only used when func_name is unique in the mapping table
        func_only_entry = _find_unique_func(func_name)
        if func_only_entry is not None:
            return func_only_entry.handler(params)

        # Fallback: ClassName::FuncName format
        return f"{class_name}::{func_name}({', '.join(params)})"



# ===========================================================================
# Helper functions
# ===========================================================================

def _strip_ue_prefix(class_name: str) -> str:
    """Strip UE type prefix.

    "ACharacter" -> "Character"
    "UKismetSystemLibrary" -> "KismetSystemLibrary"
    "FVector" -> "Vector"
    "Character" -> "Character" (no prefix, unchanged)
    """
    if len(class_name) > 1 and class_name[0] in "AUFEISB" and class_name[1].isupper():
        return class_name[1:]
    return class_name


def _find_unique_func(func_name: str) -> _MappingEntry | None:
    """Find whether func_name is unique in the mapping table.

    If the same func_name maps to only one class, returns that entry;
    otherwise returns None (to avoid ambiguity).
    """
    matches = [e for e in _MAPPINGS.values() if e.func_name == func_name]
    if len(matches) == 1:
        return matches[0]
    return None
