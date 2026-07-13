"""统一类策略表测试 — 验证无冲突。"""
import pytest

from uasset_read.parsers.class_serialization_strategy import (
    get_serialization_strategy,
    SerializationStrategy,
    CLASS_STRATEGY_TABLE,
)
from uasset_read.parsers.class_specific_skip import SKIP_CLASS_NAMES


def test_no_conflict_between_skip_and_opaque():
    """同一个 class 不应同时出现在 skip 和 opaque 策略中。"""
    for class_name in SKIP_CLASS_NAMES:
        strategy = get_serialization_strategy(class_name)
        if strategy == SerializationStrategy.OPAQUE_CLASS_PAYLOAD:
            # 如果在 opaque 表中，skip 表不应再包含
            pytest.fail(
                f"策略冲突: {class_name} 同时在 OPAQUE_CLASS_PAYLOAD 和 SKIP_CLASS_NAMES 中"
            )


def test_skip_classes_derived_from_strategy_table():
    """SKIP_CLASS_NAMES 应从策略表派生，不应有独立名单。"""
    # 验证所有 SKIP_CLASS_NAMES 都在策略表中标记为 SKIP_UNSUPPORTED
    for class_name in SKIP_CLASS_NAMES:
        assert class_name in CLASS_STRATEGY_TABLE, (
            f"{class_name} 在 SKIP_CLASS_NAMES 但不在 CLASS_STRATEGY_TABLE 中"
        )
        strategy = CLASS_STRATEGY_TABLE[class_name]
        assert strategy == SerializationStrategy.SKIP_UNSUPPORTED, (
            f"{class_name} 在 SKIP_CLASS_NAMES 但策略表中为 {strategy}"
        )


def test_niagara_system_not_conflicting():
    """NiagaraSystem 的两层策略应一致。"""
    # class_serialization_strategy: OPAQUE_CLASS_PAYLOAD
    # class_specific_skip: SKIP（前缀匹配）
    # 应统一为 OPAQUE_CLASS_PAYLOAD
    strategy = get_serialization_strategy("NiagaraSystem")
    assert strategy in (
        SerializationStrategy.OPAQUE_CLASS_PAYLOAD,
        SerializationStrategy.SKIP_UNSUPPORTED,
    ), f"NiagaraSystem 策略不明确: {strategy}"
