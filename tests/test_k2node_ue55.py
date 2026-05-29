"""UE5.5 K2Node 扩展测试"""
from uasset_read.models.node_types import K2NodeMessage


def test_k2node_message_class_exists():
    """验证 K2NodeMessage 类存在"""
    assert K2NodeMessage is not None
    assert hasattr(K2NodeMessage, 'message_name')
