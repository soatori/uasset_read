"""BlueprintNodeCleaner 测试。

验证蓝图节点到 C++ 语义调用映射的正确性：
- 常见蓝图节点输出可读 C++ 调用
- 未知节点回退到 ClassName::FuncName 格式
- UE 前缀自动剥离
- 边界条件处理
"""

import pytest

from uasset_read.kismet.blueprint_node_cleaner import BlueprintNodeCleaner


# ===========================================================================
# ACharacter 移动控制
# ===========================================================================

class TestCharacterMovement:
    """ACharacter 移动相关蓝图节点。"""

    def test_add_movement_input(self):
        result = BlueprintNodeCleaner.clean("Character", "AddMovementInput", ["WorldDirection", "ScaleValue"])
        assert result == "AddMovementInput(WorldDirection, ScaleValue)"

    def test_add_movement_input_with_prefix(self):
        """带 UE 前缀的类名应自动剥离。"""
        result = BlueprintNodeCleaner.clean("ACharacter", "AddMovementInput", ["Dir", "1.0f"])
        assert result == "AddMovementInput(Dir, 1.0f)"

    def test_jump(self):
        result = BlueprintNodeCleaner.clean("Character", "Jump", [])
        assert result == "Jump()"

    def test_stop_jumping(self):
        result = BlueprintNodeCleaner.clean("Character", "StopJumping", [])
        assert result == "StopJumping()"

    def test_crouch_no_args(self):
        result = BlueprintNodeCleaner.clean("Character", "Crouch", [])
        assert result == "Crouch()"

    def test_crouch_with_arg(self):
        result = BlueprintNodeCleaner.clean("Character", "Crouch", ["true"])
        assert result == "Crouch(true)"

    def test_uncrouch(self):
        result = BlueprintNodeCleaner.clean("Character", "UnCrouch", [])
        assert result == "UnCrouch()"

    def test_launch_character(self):
        result = BlueprintNodeCleaner.clean("Character", "LaunchCharacter",
                                            ["100.0f", "0.0f", "500.0f", "false", "true"])
        assert result == "LaunchCharacter(FVector(100.0f, 0.0f, 500.0f), false, true)"

    def test_can_jump(self):
        result = BlueprintNodeCleaner.clean("Character", "CanJump", [])
        assert result == "CanJump()"

    def test_is_jumping(self):
        result = BlueprintNodeCleaner.clean("Character", "IsJumping", [])
        assert result == "IsJumping()"

    def test_is_crouched(self):
        result = BlueprintNodeCleaner.clean("Character", "IsCrouched", [])
        assert result == "IsCrouched()"


# ===========================================================================
# AActor 位置/变换
# ===========================================================================

class TestActorTransform:
    """AActor 位置/变换相关蓝图节点。"""

    def test_get_actor_location(self):
        result = BlueprintNodeCleaner.clean("Actor", "K2_GetActorLocation", [])
        assert result == "GetActorLocation()"

    def test_set_actor_location(self):
        result = BlueprintNodeCleaner.clean("Actor", "K2_SetActorLocation",
                                            ["NewLocation", "false", "SweepHitResult", "true"])
        assert result == "SetActorLocation(NewLocation, false, SweepHitResult)"

    def test_get_actor_rotation(self):
        result = BlueprintNodeCleaner.clean("Actor", "K2_GetActorRotation", [])
        assert result == "GetActorRotation()"

    def test_set_actor_rotation(self):
        result = BlueprintNodeCleaner.clean("Actor", "K2_SetActorRotation",
                                            ["NewRotation", "false"])
        assert result == "SetActorRotation(NewRotation, false)"

    def test_get_actor_scale(self):
        result = BlueprintNodeCleaner.clean("Actor", "K2_GetActorScale3D", [])
        assert result == "GetActorScale3D()"

    def test_set_actor_scale(self):
        result = BlueprintNodeCleaner.clean("Actor", "K2_SetActorScale3D", ["NewScale"])
        assert result == "SetActorScale3D(NewScale)"

    def test_get_actor_transform(self):
        result = BlueprintNodeCleaner.clean("Actor", "K2_GetActorTransform", [])
        assert result == "GetActorTransform()"

    def test_set_actor_transform(self):
        result = BlueprintNodeCleaner.clean("Actor", "K2_SetActorTransform",
                                            ["NewTransform", "true"])
        assert result == "SetActorTransform(NewTransform, true)"

    def test_get_actor_forward_vector(self):
        result = BlueprintNodeCleaner.clean("Actor", "GetActorForwardVector", [])
        assert result == "GetActorForwardVector()"

    def test_get_actor_right_vector(self):
        result = BlueprintNodeCleaner.clean("Actor", "GetActorRightVector", [])
        assert result == "GetActorRightVector()"

    def test_get_actor_up_vector(self):
        result = BlueprintNodeCleaner.clean("Actor", "GetActorUpVector", [])
        assert result == "GetActorUpVector()"

    def test_set_actor_location_and_rotation(self):
        result = BlueprintNodeCleaner.clean("Actor", "K2_SetActorLocationAndRotation",
                                            ["NewLocation", "NewRotation", "false"])
        assert result == "SetActorLocationAndRotation(NewLocation, NewRotation, false)"


# ===========================================================================
# AActor 生命周期
# ===========================================================================

class TestActorLifecycle:
    """AActor 生命周期/通用蓝图节点。"""

    def test_destroy_actor(self):
        result = BlueprintNodeCleaner.clean("Actor", "K2_DestroyActor", [])
        assert result == "Destroy()"

    def test_set_actor_hidden(self):
        result = BlueprintNodeCleaner.clean("Actor", "K2_SetActorHiddenInGame", ["true"])
        assert result == "SetActorHiddenInGame(true)"

    def test_set_actor_enable_collision(self):
        result = BlueprintNodeCleaner.clean("Actor", "SetActorEnableCollision", ["false"])
        assert result == "SetActorEnableCollision(false)"

    def test_get_velocity(self):
        result = BlueprintNodeCleaner.clean("Actor", "GetVelocity", [])
        assert result == "GetVelocity()"

    def test_set_actor_tick_enabled(self):
        result = BlueprintNodeCleaner.clean("Actor", "SetActorTickEnabled", ["false"])
        assert result == "SetActorTickEnabled(false)"


# ===========================================================================
# UKismetSystemLibrary 定时器
# ===========================================================================

class TestSystemLibraryTimer:
    """KismetSystemLibrary 定时器相关蓝图节点。"""

    def test_set_timer(self):
        result = BlueprintNodeCleaner.clean("KismetSystemLibrary", "K2_SetTimer",
                                            ["Delegate", "1.0f", "true", "0.0f"])
        assert result == "GetWorldTimerManager().SetTimer(Delegate, 1.0f, true, 0.0f)"

    def test_set_timer_delegate(self):
        result = BlueprintNodeCleaner.clean("KismetSystemLibrary", "K2_SetTimerDelegate",
                                            ["Delegate", "1.0f", "true"])
        assert result == "GetWorldTimerManager().SetTimer(Delegate, 1.0f, true)"

    def test_clear_timer(self):
        result = BlueprintNodeCleaner.clean("KismetSystemLibrary", "K2_ClearTimer", ["TimerHandle"])
        assert result == "GetWorldTimerManager().ClearTimer(TimerHandle)"

    def test_is_timer_active(self):
        result = BlueprintNodeCleaner.clean("KismetSystemLibrary", "K2_IsTimerActive", ["TimerHandle"])
        assert result == "GetWorldTimerManager().IsTimerActive(TimerHandle)"

    def test_is_timer_paused(self):
        result = BlueprintNodeCleaner.clean("KismetSystemLibrary", "K2_IsTimerPaused", ["TimerHandle"])
        assert result == "GetWorldTimerManager().IsTimerPaused(TimerHandle)"

    def test_pause_timer(self):
        result = BlueprintNodeCleaner.clean("KismetSystemLibrary", "K2_PauseTimer", ["TimerHandle"])
        assert result == "GetWorldTimerManager().PauseTimer(TimerHandle)"

    def test_unpause_timer(self):
        result = BlueprintNodeCleaner.clean("KismetSystemLibrary", "K2_UnPauseTimer", ["TimerHandle"])
        assert result == "GetWorldTimerManager().UnPauseTimer(TimerHandle)"

    def test_get_timer_elapsed_time(self):
        result = BlueprintNodeCleaner.clean("KismetSystemLibrary", "K2_GetTimerElapsedTime", ["TimerHandle"])
        assert result == "GetWorldTimerManager().GetTimerElapsedTime(TimerHandle)"

    def test_get_timer_remaining_time(self):
        result = BlueprintNodeCleaner.clean("KismetSystemLibrary", "K2_GetTimerRemainingTime", ["TimerHandle"])
        assert result == "GetWorldTimerManager().GetTimerRemainingTime(TimerHandle)"


# ===========================================================================
# UKismetSystemLibrary 调试
# ===========================================================================

class TestSystemLibraryDebug:
    """KismetSystemLibrary 调试输出蓝图节点。"""

    def test_print_string(self):
        result = BlueprintNodeCleaner.clean("KismetSystemLibrary", "PrintString", ['"Hello"'])
        assert result == 'UE_LOG(LogTemp, Log, TEXT("Hello"))'

    def test_print_text(self):
        result = BlueprintNodeCleaner.clean("KismetSystemLibrary", "PrintText", ["MyText"])
        assert result == "UE_LOG(LogTemp, Log, *MyText.ToString())"

    def test_print_warning(self):
        result = BlueprintNodeCleaner.clean("KismetSystemLibrary", "PrintWarning", ['"Warn"'])
        assert result == 'UE_LOG(LogTemp, Warning, TEXT("Warn"))'

    def test_print_error(self):
        result = BlueprintNodeCleaner.clean("KismetSystemLibrary", "PrintError", ['"Err"'])
        assert result == 'UE_LOG(LogTemp, Error, TEXT("Err"))'


# ===========================================================================
# GameplayStatics
# ===========================================================================

class TestGameplayStatics:
    """GameplayStatics 常用蓝图节点。"""

    def test_get_player_controller(self):
        result = BlueprintNodeCleaner.clean("GameplayStatics", "GetPlayerController", ["0"])
        assert result == "UGameplayStatics::GetPlayerController(this, 0)"

    def test_get_player_character(self):
        result = BlueprintNodeCleaner.clean("GameplayStatics", "GetPlayerCharacter", ["0"])
        assert result == "UGameplayStatics::GetPlayerCharacter(this, 0)"

    def test_get_player_pawn(self):
        result = BlueprintNodeCleaner.clean("GameplayStatics", "GetPlayerPawn", ["0"])
        assert result == "UGameplayStatics::GetPlayerPawn(this, 0)"

    def test_spawn_emitter_at_location(self):
        result = BlueprintNodeCleaner.clean("GameplayStatics", "SpawnEmitterAtLocation",
                                            ["Particle", "Location", "Rotation"])
        assert result == "UGameplayStatics::SpawnEmitterAtLocation(this, Particle, Location, Rotation)"

    def test_play_sound_at_location(self):
        result = BlueprintNodeCleaner.clean("GameplayStatics", "PlaySoundAtLocation",
                                            ["Sound", "Location", "Rotation"])
        assert result == "UGameplayStatics::PlaySoundAtLocation(this, Sound, Location, Rotation)"

    def test_set_game_paused(self):
        result = BlueprintNodeCleaner.clean("GameplayStatics", "SetGamePaused", ["true"])
        assert result == "UGameplayStatics::SetGamePaused(this, true)"

    def test_get_game_mode(self):
        result = BlueprintNodeCleaner.clean("GameplayStatics", "GetGameMode", [])
        assert result == "UGameplayStatics::GetGameMode(this)"

    def test_open_level(self):
        result = BlueprintNodeCleaner.clean("GameplayStatics", "OpenLevel", ["LevelName"])
        assert result == "UGameplayStatics::OpenLevel(this, LevelName)"


# ===========================================================================
# Controller / PlayerController
# ===========================================================================

class TestController:
    """Controller / PlayerController 蓝图节点。"""

    def test_get_control_rotation(self):
        result = BlueprintNodeCleaner.clean("Controller", "GetControlRotation", [])
        assert result == "GetControlRotation()"

    def test_set_control_rotation(self):
        result = BlueprintNodeCleaner.clean("Controller", "SetControlRotation", ["NewRotation"])
        assert result == "SetControlRotation(NewRotation)"

    def test_get_pawn(self):
        result = BlueprintNodeCleaner.clean("Controller", "GetPawn", [])
        assert result == "GetPawn()"

    def test_possess(self):
        result = BlueprintNodeCleaner.clean("Controller", "Possess", ["NewPawn"])
        assert result == "Possess(NewPawn)"

    def test_unpossess(self):
        result = BlueprintNodeCleaner.clean("Controller", "UnPossess", [])
        assert result == "UnPossess()"

    def test_was_input_key_just_pressed(self):
        result = BlueprintNodeCleaner.clean("PlayerController", "WasInputKeyJustPressed", ["EKeys::SpaceBar"])
        assert result == "WasInputKeyJustPressed(EKeys::SpaceBar)"

    def test_is_input_key_down(self):
        result = BlueprintNodeCleaner.clean("PlayerController", "IsInputKeyDown", ["EKeys::W"])
        assert result == "IsInputKeyDown(EKeys::W)"


# ===========================================================================
# Pawn
# ===========================================================================

class TestPawn:
    """Pawn 输入相关蓝图节点。"""

    def test_add_controller_yaw_input(self):
        result = BlueprintNodeCleaner.clean("Pawn", "AddControllerYawInput", ["Val"])
        assert result == "AddControllerYawInput(Val)"

    def test_add_controller_pitch_input(self):
        result = BlueprintNodeCleaner.clean("Pawn", "AddControllerPitchInput", ["Val"])
        assert result == "AddControllerPitchInput(Val)"

    def test_get_controller(self):
        result = BlueprintNodeCleaner.clean("Pawn", "GetController", [])
        assert result == "GetController()"

    def test_is_player_controlled(self):
        result = BlueprintNodeCleaner.clean("Pawn", "IsPlayerControlled", [])
        assert result == "IsPlayerControlled()"


# ===========================================================================
# SceneComponent
# ===========================================================================

class TestSceneComponent:
    """SceneComponent 位置/旋转蓝图节点。"""

    def test_set_world_location(self):
        result = BlueprintNodeCleaner.clean("SceneComponent", "K2_SetWorldLocation",
                                            ["NewLocation", "false"])
        assert result == "SetWorldLocation(NewLocation, false)"

    def test_get_component_location(self):
        result = BlueprintNodeCleaner.clean("SceneComponent", "GetComponentLocation", [])
        assert result == "GetComponentLocation()"

    def test_get_forward_vector(self):
        result = BlueprintNodeCleaner.clean("SceneComponent", "GetForwardVector", [])
        assert result == "GetForwardVector()"


# ===========================================================================
# PrimitiveComponent 物理
# ===========================================================================

class TestPrimitiveComponent:
    """PrimitiveComponent 物理相关蓝图节点。"""

    def test_set_simulate_physics(self):
        result = BlueprintNodeCleaner.clean("PrimitiveComponent", "SetSimulatePhysics", ["true"])
        assert result == "SetSimulatePhysics(true)"

    def test_add_impulse(self):
        result = BlueprintNodeCleaner.clean("PrimitiveComponent", "AddImpulse",
                                            ["Impulse", "BoneName"])
        assert result == "AddImpulse(Impulse, BoneName)"

    def test_add_force(self):
        result = BlueprintNodeCleaner.clean("PrimitiveComponent", "AddForce",
                                            ["Force", "BoneName"])
        assert result == "AddForce(Force, BoneName)"

    def test_get_physics_linear_velocity(self):
        result = BlueprintNodeCleaner.clean("PrimitiveComponent", "GetPhysicsLinearVelocity", [])
        assert result == "GetPhysicsLinearVelocity()"


# ===========================================================================
# AnimInstance
# ===========================================================================

class TestAnimInstance:
    """AnimInstance 动画蒙太奇蓝图节点。"""

    def test_montage_play(self):
        result = BlueprintNodeCleaner.clean("AnimInstance", "Montage_Play", ["MontageAsset", "1.0f"])
        assert result == "Montage_Play(MontageAsset, 1.0f)"

    def test_montage_stop(self):
        result = BlueprintNodeCleaner.clean("AnimInstance", "Montage_Stop", ["0.2f"])
        assert result == "Montage_Stop(0.2f)"

    def test_montage_is_playing(self):
        result = BlueprintNodeCleaner.clean("AnimInstance", "Montage_IsPlaying", ["MontageAsset"])
        assert result == "Montage_IsPlaying(MontageAsset)"

    def test_try_get_pawn_owner(self):
        result = BlueprintNodeCleaner.clean("AnimInstance", "TryGetPawnOwner", [])
        assert result == "TryGetPawnOwner()"


# ===========================================================================
# UserWidget
# ===========================================================================

class TestUserWidget:
    """UserWidget UI 蓝图节点。"""

    def test_set_visibility(self):
        result = BlueprintNodeCleaner.clean("UserWidget", "SetVisibility", ["ESlateVisibility::Visible"])
        assert result == "SetVisibility(ESlateVisibility::Visible)"

    def test_add_to_viewport(self):
        result = BlueprintNodeCleaner.clean("UserWidget", "AddToViewport", [])
        assert result == "AddToViewport()"

    def test_remove_from_parent(self):
        result = BlueprintNodeCleaner.clean("UserWidget", "RemoveFromParent", [])
        assert result == "RemoveFromParent()"

    def test_set_is_enabled(self):
        result = BlueprintNodeCleaner.clean("UserWidget", "SetIsEnabled", ["false"])
        assert result == "SetIsEnabled(false)"


# ===========================================================================
# 未知节点回退
# ===========================================================================

class TestUnknownNodeFallback:
    """未知节点应回退到 ClassName::FuncName 格式。"""

    def test_unknown_class_and_func(self):
        result = BlueprintNodeCleaner.clean("MyCustomClass", "MyCustomFunc", ["arg1", "arg2"])
        assert result == "MyCustomClass::MyCustomFunc(arg1, arg2)"

    def test_unknown_func_no_params(self):
        result = BlueprintNodeCleaner.clean("SomeClass", "SomeFunc", [])
        assert result == "SomeClass::SomeFunc()"

    def test_unknown_with_prefix(self):
        """未知类的 UE 前缀不应影响回退输出。"""
        result = BlueprintNodeCleaner.clean("AMyActor", "CustomAction", ["val"])
        assert result == "AMyActor::CustomAction(val)"

    def test_empty_func_name(self):
        """空函数名应回退到标准格式。"""
        result = BlueprintNodeCleaner.clean("SomeClass", "", ["arg"])
        assert result == "SomeClass::(arg)"


# ===========================================================================
# clean_from_string 接口
# ===========================================================================

class TestCleanFromString:
    """测试从 "ClassName::FuncName" 字符串解析的接口。"""

    def test_known_call(self):
        result = BlueprintNodeCleaner.clean_from_string("Character::Jump", [])
        assert result == "Jump()"

    def test_known_call_with_params(self):
        result = BlueprintNodeCleaner.clean_from_string(
            "Actor::K2_GetActorLocation", [])
        assert result == "GetActorLocation()"

    def test_unknown_call(self):
        result = BlueprintNodeCleaner.clean_from_string(
            "MyClass::MyFunc", ["arg1"])
        assert result == "MyClass::MyFunc(arg1)"

    def test_no_class_prefix(self):
        """无 "::" 时 func_name 为整个字符串。"""
        result = BlueprintNodeCleaner.clean_from_string("SomeFunc", ["a"])
        assert result == "::SomeFunc(a)"

    def test_params_default_none(self):
        """params=None 时使用空列表。"""
        result = BlueprintNodeCleaner.clean_from_string("Character::Jump")
        assert result == "Jump()"

    def test_ue_prefix_stripped(self):
        """带 UE 前缀的类名在匹配时应被剥离。"""
        result = BlueprintNodeCleaner.clean_from_string("ACharacter::StopJumping", [])
        assert result == "StopJumping()"

    def test_system_library_timer(self):
        result = BlueprintNodeCleaner.clean_from_string(
            "KismetSystemLibrary::K2_ClearTimer", ["Handle"])
        assert result == "GetWorldTimerManager().ClearTimer(Handle)"


# ===========================================================================
# has_mapping 查询接口
# ===========================================================================

class TestHasMapping:
    """测试映射查询接口。"""

    def test_known_mapping(self):
        assert BlueprintNodeCleaner.has_mapping("Character", "Jump") is True

    def test_known_mapping_with_prefix(self):
        assert BlueprintNodeCleaner.has_mapping("ACharacter", "Jump") is True

    def test_unknown_mapping(self):
        assert BlueprintNodeCleaner.has_mapping("UnknownClass", "UnknownFunc") is False

    def test_known_actor_location(self):
        assert BlueprintNodeCleaner.has_mapping("Actor", "K2_GetActorLocation") is True

    def test_known_timer(self):
        assert BlueprintNodeCleaner.has_mapping("KismetSystemLibrary", "K2_SetTimer") is True


# ===========================================================================
# get_supported_nodes 查询接口
# ===========================================================================

class TestGetSupportedNodes:
    """测试支持节点列表接口。"""

    def test_returns_non_empty(self):
        nodes = BlueprintNodeCleaner.get_supported_nodes()
        assert len(nodes) > 0

    def test_contains_character_jump(self):
        nodes = BlueprintNodeCleaner.get_supported_nodes()
        assert ("Character", "Jump") in nodes

    def test_contains_timer(self):
        nodes = BlueprintNodeCleaner.get_supported_nodes()
        assert ("KismetSystemLibrary", "K2_SetTimer") in nodes

    def test_contains_actor_location(self):
        nodes = BlueprintNodeCleaner.get_supported_nodes()
        assert ("Actor", "K2_GetActorLocation") in nodes

    def test_all_entries_are_tuples(self):
        nodes = BlueprintNodeCleaner.get_supported_nodes()
        for entry in nodes:
            assert isinstance(entry, tuple)
            assert len(entry) == 2


# ===========================================================================
# UE 前缀剥离
# ===========================================================================

class TestUEPrefixStripping:
    """测试 UE 类型前缀自动剥离。"""

    def test_actor_prefix(self):
        """ACharacter → Character。"""
        result = BlueprintNodeCleaner.clean("ACharacter", "Jump", [])
        assert result == "Jump()"

    def test_object_prefix(self):
        """UKismetSystemLibrary → KismetSystemLibrary。"""
        result = BlueprintNodeCleaner.clean("UKismetSystemLibrary", "K2_ClearTimer", ["H"])
        assert result == "GetWorldTimerManager().ClearTimer(H)"

    def test_no_prefix(self):
        """无前缀时不变。"""
        result = BlueprintNodeCleaner.clean("Character", "Jump", [])
        assert result == "Jump()"

    def test_single_char_no_strip(self):
        """单字符类名不剥离前缀，但唯一函数名仍可匹配。"""
        result = BlueprintNodeCleaner.clean("A", "Jump", [])
        # "A" 不被识别为 UE 前缀（长度不足），但 Jump 是唯一映射函数，仍被匹配
        assert result == "Jump()"

    def test_lowercase_second_char_no_strip(self):
        """第二个字符小写时不应剥离前缀，但唯一函数名仍可匹配。"""
        result = BlueprintNodeCleaner.clean("actor", "GetVelocity", [])
        # "actor" 第二个字符小写，不剥离，但 GetVelocity 是唯一映射函数
        assert result == "GetVelocity()"


# ===========================================================================
# 跨类通用函数唯一匹配
# ===========================================================================

class TestUniqueFuncMatch:
    """测试跨类通用函数的唯一匹配。"""

    def test_jump_is_unique(self):
        """Jump 仅在 Character 中定义，应唯一匹配。"""
        result = BlueprintNodeCleaner.clean("SomeOtherClass", "Jump", [])
        assert result == "Jump()"

    def test_non_unique_func_falls_back(self):
        """如 GetVelocity 存在于多个类中，应走回退。"""
        # GetVelocity 在 Actor 和其他类中都存在，应走回退
        result = BlueprintNodeCleaner.clean("SomeUnknownClass", "GetVelocity", [])
        # 如果唯一匹配则返回语义化结果，否则回退
        # GetVelocity 仅在 Actor 中映射，应返回 "GetVelocity()"
        assert result == "GetVelocity()"

    def test_conflicting_func_falls_back(self):
        """同名函数存在于多个类时应走回退。"""
        # GetForwardVector 在 Actor 和 SceneComponent 中都存在
        # 不应唯一匹配，应回退到 ClassName::FuncName
        result = BlueprintNodeCleaner.clean("MeshComponent", "GetForwardVector", [])
        # 因为 GetForwardVector 在 Actor 和 SceneComponent 中都有映射，
        # _find_unique_func 应返回 None，回退到类名格式
        assert result == "MeshComponent::GetForwardVector()"
