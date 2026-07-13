"""Kismet 未知/游戏特定 token 处理测试。

覆盖 tokens.py 和 special.py 中为 0x6E, 0x6F, 0xF9, 0xFD, 0xFE
定义的占位 token，确保字节码提取器能正确处理它们而不崩溃。

参考：CUE4Parse EExprToken.cs — 这些 token 在 UE5 社区中无标准名称，
属于游戏特定扩展（WuWa, DeltaForce, 2XKO, Borderlands4 等）。
"""

from __future__ import annotations

import pytest

from uasset_read.exceptions import ParseError
from uasset_read.kismet.archive import FKismetArchive
from uasset_read.kismet.expressions import EXPR_CLASS_MAP
from uasset_read.kismet.expressions.special import (
    EX_Unknown6E,
    EX_Unknown6F,
    EX_UnknownF9,
    EX_UnknownFD,
    EX_UnknownFE,
)
from uasset_read.kismet.tokens import EExprToken


# ---------------------------------------------------------------------------
# Token 枚举定义验证
# ---------------------------------------------------------------------------

class TestTokenDefinitions:
    """验证 token 枚举值与已知 UE5 扩展对齐。"""

    def test_ex_6e_value(self):
        assert EExprToken.EX_6E == 0x6E

    def test_ex_6f_value(self):
        assert EExprToken.EX_6F == 0x6F

    def test_ex_f9_value(self):
        assert EExprToken.EX_F9 == 0xF9

    def test_ex_fd_value(self):
        assert EExprToken.EX_FD == 0xFD

    def test_ex_fe_value(self):
        assert EExprToken.EX_FE == 0xFE

    def test_all_five_tokens_exist(self):
        """五个 token 都应在 EExprToken 中定义。"""
        for name in ("EX_6E", "EX_6F", "EX_F9", "EX_FD", "EX_FE"):
            assert hasattr(EExprToken, name), f"Missing EExprToken.{name}"


# ---------------------------------------------------------------------------
# EXPR_CLASS_MAP 映射验证
# ---------------------------------------------------------------------------

class TestExprClassMapMapping:
    """验证 EXPR_CLASS_MAP 为每个 token 注册了正确的表达式类。"""

    @pytest.mark.parametrize(
        "token,expr_cls",
        [
            (EExprToken.EX_6E, EX_Unknown6E),
            (EExprToken.EX_6F, EX_Unknown6F),
            (EExprToken.EX_F9, EX_UnknownF9),
            (EExprToken.EX_FD, EX_UnknownFD),
            (EExprToken.EX_FE, EX_UnknownFE),
        ],
        ids=["0x6E", "0x6F", "0xF9", "0xFD", "0xFE"],
    )
    def test_expr_class_map_contains_token(self, token, expr_cls):
        assert EXPR_CLASS_MAP.get(token) is expr_cls


# ---------------------------------------------------------------------------
# 表达式类基础属性验证
# ---------------------------------------------------------------------------

class TestExpressionClassBasics:
    """验证每个占位表达式类的基本属性。"""

    @pytest.mark.parametrize(
        "expr_cls,token",
        [
            (EX_Unknown6E, EExprToken.EX_6E),
            (EX_Unknown6F, EExprToken.EX_6F),
            (EX_UnknownF9, EExprToken.EX_F9),
            (EX_UnknownFD, EExprToken.EX_FD),
            (EX_UnknownFE, EExprToken.EX_FE),
        ],
        ids=["0x6E", "0x6F", "0xF9", "0xFD", "0xFE"],
    )
    def test_token_property_matches(self, expr_cls, token):
        expr = expr_cls()
        assert expr.Token == token

    @pytest.mark.parametrize(
        "token_byte",
        [0x6E, 0x6F, 0xF9, 0xFD, 0xFE],
        ids=["0x6E", "0x6F", "0xF9", "0xFD", "0xFE"],
    )
    def test_to_dict_has_inst_key(self, token_byte):
        """通过 archive 创建的表达式应能正确序列化为 dict。"""
        archive = _archive(bytes([token_byte]))
        expr = archive.read_expression()
        d = expr.to_dict()
        assert "Inst" in d
        assert "StatementIndex" in d

    @pytest.mark.parametrize(
        "expr_cls",
        [EX_Unknown6E, EX_Unknown6F, EX_UnknownF9, EX_UnknownFD, EX_UnknownFE],
        ids=["0x6E", "0x6F", "0xF9", "0xFD", "0xFE"],
    )
    def test_default_value_is_empty_bytes(self, expr_cls):
        expr = expr_cls()
        assert expr.Value == b""


# ---------------------------------------------------------------------------
# FKismetArchive 解析集成测试
# ---------------------------------------------------------------------------

def _archive(data: bytes, tolerant: bool = True) -> FKismetArchive:
    return FKismetArchive(data, "test-bytecode", [], tolerant=tolerant)


class TestFKismetArchiveParsing:
    """验证 FKismetArchive.read_expression() 能正确解析这些 token。"""

    @pytest.mark.parametrize(
        "token_byte,expr_cls",
        [
            (0x6E, EX_Unknown6E),
            (0x6F, EX_Unknown6F),
            (0xF9, EX_UnknownF9),
            (0xFD, EX_UnknownFD),
            (0xFE, EX_UnknownFE),
        ],
        ids=["0x6E", "0x6F", "0xF9", "0xFD", "0xFE"],
    )
    def test_read_expression_single_token(self, token_byte, expr_cls):
        """单个 token 应被正确解析为对应的表达式类。"""
        archive = _archive(bytes([token_byte]))
        expr = archive.read_expression()
        assert isinstance(expr, expr_cls)
        assert archive.tell() == 1

    @pytest.mark.parametrize(
        "token_byte",
        [0x6E, 0x6F, 0xF9, 0xFD, 0xFE],
        ids=["0x6E", "0x6F", "0xF9", "0xFD", "0xFE"],
    )
    def test_token_in_non_tolerant_mode(self, token_byte):
        """非 tolerant 模式下，这些 token 应被正常处理（已在 EXPR_CLASS_MAP 中）。"""
        archive = _archive(bytes([token_byte]), tolerant=False)
        expr = archive.read_expression()
        assert expr.Token.value == token_byte

    def test_mixed_tokens_sequence(self):
        """混合多个未知 token 的序列应被完整解析。"""
        data = bytes([0x6E, 0x6F, 0xF9, 0xFD, 0xFE])
        archive = _archive(data)
        results = []
        while archive.tell() < len(data):
            results.append(archive.read_expression())
        assert len(results) == 5
        expected_types = [EX_Unknown6E, EX_Unknown6F, EX_UnknownF9, EX_UnknownFD, EX_UnknownFE]
        for expr, expected_cls in zip(results, expected_types):
            assert isinstance(expr, expected_cls)

    def test_token_followed_by_end_of_script(self):
        """未知 token 后跟 EX_EndOfScript 应正常终止。"""
        data = bytes([0x6E, 0x53])  # EX_6E then EX_EndOfScript
        archive = _archive(data)
        expr1 = archive.read_expression()
        expr2 = archive.read_expression()
        assert isinstance(expr1, EX_Unknown6E)
        assert expr2.Token == EExprToken.EX_EndOfScript


# ---------------------------------------------------------------------------
# StatementIndex 验证
# ---------------------------------------------------------------------------

class TestStatementIndex:
    """验证 StatementIndex 正确设置。"""

    @pytest.mark.parametrize(
        "token_byte",
        [0x6E, 0x6F, 0xF9, 0xFD, 0xFE],
        ids=["0x6E", "0x6F", "0xF9", "0xFD", "0xFE"],
    )
    def test_statement_index_is_zero_for_first_token(self, token_byte):
        archive = _archive(bytes([token_byte]))
        expr = archive.read_expression()
        assert expr.StatementIndex == 0

    def test_statement_index_increments(self):
        data = bytes([0x6E, 0x6F])
        archive = _archive(data)
        expr1 = archive.read_expression()
        expr2 = archive.read_expression()
        assert expr1.StatementIndex == 0
        assert expr2.StatementIndex == 1
