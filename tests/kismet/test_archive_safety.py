"""Kismet archive resource-boundary regression tests."""

from __future__ import annotations

import pytest

from uasset_read.exceptions import ParseError
from uasset_read.kismet.archive import FKismetArchive
from uasset_read.kismet.expressions import EX_Nothing
from uasset_read.kismet.tokens import EExprToken


def _archive(data: bytes) -> FKismetArchive:
    return FKismetArchive(data, "test-bytecode", [], tolerant=True)


def test_unknown_6e_consumes_its_opcode() -> None:
    archive = _archive(bytes([EExprToken.EX_6E]))

    expression = archive.read_expression()

    assert expression.Token == EExprToken.EX_6E
    assert archive.tell() == 1


def test_read_expression_rejects_handler_that_makes_no_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from uasset_read.kismet import archive as archive_module

    class NonProgressingExpression(EX_Nothing):
        @classmethod
        def from_archive(cls, archive, name_map):
            archive.seek(archive.tell() - 1)
            return cls()

    monkeypatch.setitem(
        archive_module.EXPR_CLASS_MAP,
        EExprToken.EX_Nothing,
        NonProgressingExpression,
    )
    archive = _archive(bytes([EExprToken.EX_Nothing]))

    with pytest.raises(ParseError, match="made no progress.*offset 0"):
        archive.read_expression()


def test_read_expression_array_is_bounded_by_remaining_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = _archive(b"\x00\x00")
    monkeypatch.setattr(archive, "read_expression", lambda: EX_Nothing())

    with pytest.raises(ParseError, match="expression array exceeded 2 items"):
        archive.read_expression_array(EExprToken.EX_EndArray)


def test_read_expression_rejects_excessive_recursion_depth() -> None:
    data = bytes([EExprToken.EX_Return]) * 257 + bytes([EExprToken.EX_Nothing])
    archive = _archive(data)

    with pytest.raises(ParseError, match="recursion depth exceeded 256"):
        archive.read_expression()
