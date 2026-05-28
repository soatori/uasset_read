"""N2C 处理器补全测试。"""
import pytest
from uasset_read.n2c.processors.comment import CommentProcessor
from uasset_read.n2c.processors.enhanced_input import EnhancedInputActionProcessor
from uasset_read.n2c.node_types import N2CNodeType


def test_comment_processor_importable():
    """CommentProcessor 应可导入。"""
    assert CommentProcessor is not None


def test_enhanced_input_processor_importable():
    """EnhancedInputActionProcessor 应可导入。"""
    assert EnhancedInputActionProcessor is not None


def test_comment_processor_node_types():
    """CommentProcessor 应处理 Comment 类型。"""
    proc = CommentProcessor()
    assert N2CNodeType.Comment in proc.node_types


def test_enhanced_input_processor_node_types():
    """EnhancedInputActionProcessor 应处理 EnhancedInputAction 类型。"""
    proc = EnhancedInputActionProcessor()
    assert N2CNodeType.EnhancedInputAction in proc.node_types
