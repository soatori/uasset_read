"""UE5.5 K2Node 扩展测试"""
from uasset_read.models.node_types import K2NodeMessage


def test_k2node_message_class_exists():
    """验证 K2NodeMessage 类存在"""
    assert K2NodeMessage is not None
    assert hasattr(K2NodeMessage, 'message_name')


def test_all_k2node_classes_exist():
    """验证所有 K2Node 类存在"""
    from uasset_read.models.node_types import (
        K2NodeCallDelegate, K2NodeCallArrayFunction, K2NodeCallParentFunction,
        K2NodeFunctionResult, K2NodeCreateWidget, K2NodeAddDelegate, K2NodeMacroInstance
    )

    assert K2NodeCallDelegate is not None
    assert K2NodeCallArrayFunction is not None
    assert K2NodeCallParentFunction is not None
    assert K2NodeFunctionResult is not None
    assert K2NodeCreateWidget is not None
    assert K2NodeAddDelegate is not None
    assert K2NodeMacroInstance is not None
