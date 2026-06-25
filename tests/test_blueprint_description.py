"""BlueprintDescription 提取测试（Issue #169 部分）。"""
import pytest


def test_blueprint_has_description():
    """蓝图应包含 description 字段"""
    from uasset_read.parse_uasset import parse_uasset_with_linker
    result = parse_uasset_with_linker(
        "E:/Develop/lib/Samples/FirstPerson/Content/FirstPerson/Blueprints/BP_FirstPersonCharacter.uasset",
        tolerant=True,
    )
    assert result.is_success, f"解析失败: {result.errors}"
    blueprint = result.blueprint
    assert blueprint is not None, "蓝图数据不应为 None"
    assert blueprint.description is not None, "description 不应为 None"
    assert len(blueprint.description) > 0, f"description 不应为空，实际值: '{blueprint.description}'"
    print(f"BlueprintDescription: {blueprint.description}")
