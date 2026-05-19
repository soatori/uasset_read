"""
Kismet 表达式系统 — 基类定义。

包含 KismetExpression 抽象基类和 KismetExpressionT 泛型子类。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from uasset_read.kismet.tokens import EExprToken

T = TypeVar("T")


class KismetExpression(ABC):
    """
    Kismet 字节码表达式抽象基类。

    所有 EX_* 指令的解析结果都继承此类。
    子类必须实现 Token 属性并定义 from_archive 类方法。
    """

    StatementIndex: int

    def __init__(self, statement_index: int = 0) -> None:
        self.StatementIndex = statement_index

    @property
    @abstractmethod
    def Token(self) -> EExprToken:
        """返回此表达式对应的 EExprToken 值。"""
        ...

    def to_dict(self) -> dict:
        """序列化为字典格式（用于 JSON 输出）。"""
        return {
            "Inst": self.Token.name,
            "StatementIndex": self.StatementIndex,
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} token={self.Token.name}>"


class KismetExpressionT(KismetExpression, Generic[T]):
    """
    携带值的 Kismet 表达式泛型基类。

    适用于具有关联数据（常量、变量引用等）的表达式。
    """

    Value: T

    def __init__(self, value: T, statement_index: int = 0) -> None:
        super().__init__(statement_index)
        self.Value = value

    def to_dict(self) -> dict:
        result = super().to_dict()
        result["Value"] = self.Value
        return result

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} token={self.Token.name} value={self.Value!r}>"
