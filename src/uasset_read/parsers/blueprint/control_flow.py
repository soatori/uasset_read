"""Basic blocks and typed CFG construction (plan Task 7).

Blocks split in the logical StatementIndex/CodeOffset coordinate system at
entry, every jump target, conditional fallthrough after EX_JumpIfNot, and
returns (EX_Return / end of script). Jump targets are never resolved against
serialized disk offsets or list ordinals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from uasset_read.models.diagnostics import Diagnostic
from uasset_read.parsers.blueprint.bytecode import (
    BytecodeInstruction,
    project_instruction,
)


@dataclass
class BasicBlock:
    start_statement_index: int
    end_statement_index: int
    instructions: list[BytecodeInstruction]


@dataclass
class ControlFlowEdge:
    source_block: int
    target_block: int
    kind: Literal[
        "fallthrough",
        "true",
        "false",
        "jump",
        "loop_back",
        "computed_jump",
        "return",
    ]
    targets_known: bool = True


@dataclass
class ControlFlowGraph:
    blocks: list[BasicBlock]
    edges: list[ControlFlowEdge]
    entry: int
    metadata: dict[str, Any]


def project_cfg_edge(edge: ControlFlowEdge) -> dict[str, Any]:
    return {
        "source_block": edge.source_block,
        "target_block": edge.target_block,
        "kind": edge.kind,
        "targets_known": edge.targets_known,
    }


def project_cfg(cfg: ControlFlowGraph) -> dict[str, Any]:
    return {
        "blocks": [
            {
                "start_statement_index": block.start_statement_index,
                "end_statement_index": block.end_statement_index,
                # Same projection as functions[].instructions so block payloads
                # cover the function instruction list in order (Task 7 invariant).
                "instruction_ordinals": [item.statement_ordinal for item in block.instructions],
                "instructions": [project_instruction(item) for item in block.instructions],
            }
            for block in cfg.blocks
        ],
        "edges": [project_cfg_edge(edge) for edge in cfg.edges],
        "entry": cfg.entry,
        "metadata": dict(cfg.metadata),
    }


_TERMINATOR_KINDS = frozenset({"unconditional", "conditional_false", "computed"})


def _is_return_like(instruction: BytecodeInstruction) -> bool:
    return instruction.opcode in {"EX_Return", "EX_EndOfScript"} or instruction.parse_status == "unavailable"


def build_cfg(
    instructions: list[BytecodeInstruction],
    *,
    diagnostics: list[Any] | None = None,
) -> ControlFlowGraph:
    """Build basic blocks and typed edges from normalized instructions.

    Jump targets prefer an exact top-level ``statement_index`` match; a target
    that does not land on a documented instruction boundary yields
    ``targets_known=False`` plus a diagnostic — never a guessed nearest edge.
    """
    if not instructions:
        return ControlFlowGraph(blocks=[], edges=[], entry=0, metadata={})

    diags = diagnostics if diagnostics is not None else []
    index_to_pos = {instr.statement_index: pos for pos, instr in enumerate(instructions)}

    def _jump_edge(source_block: int, target_stmt: int, kind: Literal["false", "jump"]) -> None:
        """One unresolved jump: boundary diagnostic + never-guessed edge."""
        diags.append(
            Diagnostic(
                code="CFG_JUMP_TARGET_UNRESOLVED",
                message=(f"jump target {target_stmt} does not land on a top-level instruction boundary"),
                stage="semantic.functions.cfg",
            )
        )
        edges.append(
            ControlFlowEdge(
                source_block=source_block,
                target_block=-1,
                kind=kind,
                targets_known=False,
            )
        )

    # --- Leader collection (logical statement indexes) ---
    leaders: set[int] = {instructions[0].statement_index}
    for pos, instr in enumerate(instructions):
        if instr.jump_kind in {"unconditional", "conditional_false"} and instr.jump_target_statement_index is not None:
            target = instr.jump_target_statement_index
            if target in index_to_pos:
                leaders.add(target)
            # Fallthrough after a branch is always a new block.
            if pos + 1 < len(instructions):
                leaders.add(instructions[pos + 1].statement_index)
        elif instr.jump_kind == "computed":
            if pos + 1 < len(instructions):
                leaders.add(instructions[pos + 1].statement_index)
        elif _is_return_like(instr):
            if pos + 1 < len(instructions):
                leaders.add(instructions[pos + 1].statement_index)

    # --- Split into blocks in instruction order ---
    blocks: list[BasicBlock] = []
    current: list[BytecodeInstruction] = []
    for instr in instructions:
        if current and instr.statement_index in leaders:
            blocks.append(
                BasicBlock(
                    start_statement_index=current[0].statement_index,
                    end_statement_index=current[-1].logical_end,
                    instructions=list(current),
                )
            )
            current = []
        current.append(instr)
    if current:
        blocks.append(
            BasicBlock(
                start_statement_index=current[0].statement_index,
                end_statement_index=current[-1].logical_end,
                instructions=list(current),
            )
        )

    block_of_stmt = {
        block.instructions[i].statement_index: bidx
        for bidx, block in enumerate(blocks)
        for i in range(len(block.instructions))
    }

    # --- Typed edges ---
    edges: list[ControlFlowEdge] = []
    for bidx, block in enumerate(blocks):
        last = block.instructions[-1]
        # Conditional: false -> target, true -> fallthrough.
        if last.jump_kind == "conditional_false" and last.jump_target_statement_index is not None:
            target_stmt = last.jump_target_statement_index
            if target_stmt in block_of_stmt:
                edges.append(
                    ControlFlowEdge(
                        source_block=bidx,
                        target_block=block_of_stmt[target_stmt],
                        kind="false",
                        targets_known=True,
                    )
                )
            else:
                _jump_edge(bidx, target_stmt, "false")
            if bidx + 1 < len(blocks):
                edges.append(ControlFlowEdge(source_block=bidx, target_block=bidx + 1, kind="true"))
            continue

        if last.jump_kind == "unconditional" and last.jump_target_statement_index is not None:
            target_stmt = last.jump_target_statement_index
            if target_stmt in block_of_stmt:
                tb = block_of_stmt[target_stmt]
                kind = "loop_back" if tb <= bidx else "jump"
                edges.append(ControlFlowEdge(source_block=bidx, target_block=tb, kind=kind))
            else:
                _jump_edge(bidx, target_stmt, "jump")
            continue

        if last.jump_kind == "computed":
            edges.append(
                ControlFlowEdge(
                    source_block=bidx,
                    target_block=-1,
                    kind="computed_jump",
                    targets_known=False,
                )
            )
            continue

        if last.parse_status == "unavailable":
            edges.append(
                ControlFlowEdge(
                    source_block=bidx,
                    target_block=-1,
                    kind="jump",
                    targets_known=False,
                )
            )
            continue

        if _is_return_like(last) or last.opcode == "EX_Return":
            # Terminal; no outgoing fallthrough.
            continue

        if bidx + 1 < len(blocks):
            edges.append(ControlFlowEdge(source_block=bidx, target_block=bidx + 1, kind="fallthrough"))

    return ControlFlowGraph(
        blocks=blocks,
        edges=edges,
        entry=0,
        metadata={"kind": "statement_index_cfg"},
    )
