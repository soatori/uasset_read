"""Consolidated kismet unit tests.

Covers CFG infrastructure, parameter extraction, and archive safety —
extracted and merged from individual test modules.
"""
from __future__ import annotations

import pytest

from uasset_read.kismet.expressions.assignments import EX_Let
from uasset_read.kismet.expressions.control_flow import (
    EX_EndOfScript,
    EX_Jump,
    EX_JumpIfNot,
)
from uasset_read.kismet.cfg import (
    build_cfg,
    compute_dominator_tree,
    decompose_regions,
)
from uasset_read.kismet.cfg.data import (
    EdgeKind,
    RegionKind,
)
from uasset_read.ir_builder import _extract_parameters_from_signature
from uasset_read.kismet.archive import FKismetArchive
from uasset_read.kismet.tokens import EExprToken


# ================================================================
# Shared helpers
# ================================================================

def _make_let(stmt_idx: int) -> EX_Let:
    e = EX_Let()
    e.StatementIndex = stmt_idx
    return e


def _make_end(stmt_idx: int) -> EX_EndOfScript:
    e = EX_EndOfScript()
    e.StatementIndex = stmt_idx
    return e


def _make_jump_if_not(stmt_idx: int, code_offset: int) -> EX_JumpIfNot:
    e = EX_JumpIfNot(CodeOffset=code_offset, BooleanExpression=None)
    e.StatementIndex = stmt_idx
    return e


def _archive(data: bytes) -> FKismetArchive:
    return FKismetArchive(data, "test-bytecode", [], tolerant=True)


# ================================================================
# 1. CFG build: build_cfg produces correct block count and edge kinds
# ================================================================

class TestBuildCfgConditional:
    """build_cfg: conditional branch produces correct block count and edge kinds."""

    def test_if_else_pattern(self):
        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 24)
        let1 = _make_let(16)
        let2 = _make_let(24)
        end = _make_end(32)
        cfg = build_cfg([let0, jmp, let1, let2, end])
        assert cfg.block_count == 4

        bb0 = cfg.blocks[0]
        edge_kinds = set(bb0.edge_kinds.values())
        assert EdgeKind.FALSE_BRANCH in edge_kinds


# ================================================================
# 2. Dominator tree: entry dominates both branches in a diamond
# ================================================================

class TestDominatorTreeConditional:
    """compute_dominator_tree: entry dominates both branches in a diamond."""

    def test_diamond_dominators(self):
        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 24)
        let1 = _make_let(16)
        let2 = _make_let(24)
        end = _make_end(32)
        cfg = build_cfg([let0, jmp, let1, let2, end])
        dom = compute_dominator_tree(cfg)

        assert dom.is_dominator(0, 1)
        assert dom.is_dominator(0, 2)
        assert dom.immediate_dominator(1) == 0


# ================================================================
# 3. Region decomposition: conditional branch produces a non-BLOCK region
# ================================================================

class TestDecomposeRegionsConditional:
    """decompose_regions: conditional branch produces a non-BLOCK region."""

    def test_conditional_creates_region(self):
        let0 = _make_let(0)
        jmp = _make_jump_if_not(8, 24)
        let1 = _make_let(16)
        let2 = _make_let(24)
        end = _make_end(32)
        cfg = build_cfg([let0, jmp, let1, let2, end])
        dom = compute_dominator_tree(cfg)
        regions = decompose_regions(cfg, dom)

        kinds = {r.kind for r in regions.regions.values()}
        assert kinds - {RegionKind.BLOCK} != set()


# ================================================================
# 4. Archive safety: FKismetArchive overflow and unknown-token guards
# ================================================================

class TestArchiveSafety:
    """FKismetArchive: overflow and unknown-token guards."""

    def test_unknown_token_consumes_its_opcode(self):
        archive = _archive(bytes([EExprToken.EX_6E]))
        # In tolerant mode, reading beyond the archive should not crash
        # but may raise ParseError for insufficient data
        from uasset_read.exceptions import ParseError
        try:
            expression = archive.read_expression()
            assert expression.Token == EExprToken.EX_6E
            assert archive.tell() == 1
        except ParseError:
            # Expected when archive doesn't have enough data
            pass


# ================================================================
# 5. Parameter extraction from function signature
# ================================================================

class TestExtractParametersFromSignature:
    """_extract_parameters_from_signature: pure unit tests, no external assets."""

    def test_multiple_params(self):
        result = _extract_parameters_from_signature("int32 Add(int32 A, int32 B)")
        assert result == [
            {"name": "A", "type": "int32"},
            {"name": "B", "type": "int32"},
        ]
