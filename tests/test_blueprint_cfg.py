from tests.fixtures import find_function


def test_jump_if_not_creates_true_and_false_edges(ue58_blueprint_document):
    # Design gate 2: UE5.8 sample must expose IfThenElse / EX_JumpIfNot.
    functions = []
    for obj in ue58_blueprint_document.objects:
        functions.extend(((obj.semantic or {}).get("functions") or []))
    assert functions, "UE5.8 blueprint must expose functions"
    opcodes = {item["opcode"] for fn in functions for item in fn["instructions"]}
    assert "EX_JumpIfNot" in opcodes
    kinds = {edge["kind"] for fn in functions for edge in fn["cfg"]["edges"]}
    assert {"true", "false"} <= kinds


def test_instruction_ranges_are_monotonic(stackobot_document):
    for obj in stackobot_document.objects:
        for fn in ((obj.semantic or {}).get("functions") or []):
            instrs = fn["instructions"]
            statement_indexes = [item["statement_index"] for item in instrs]
            serialized_starts = [item["serialized_start"] for item in instrs]
            assert statement_indexes == sorted(statement_indexes)
            assert serialized_starts == sorted(serialized_starts)
            assert all(item["logical_end"] > item["statement_index"] for item in instrs)
            assert all(item["serialized_end"] > item["serialized_start"] for item in instrs)


def test_jump_targets_use_statement_index_not_serialized_offset(ue58_blueprint_document):
    function = find_function(ue58_blueprint_document, "NewFunction")
    valid_targets = {item["statement_index"] for item in function["instructions"]}
    branch = next(item for item in function["instructions"] if item["opcode"] == "EX_JumpIfNot")
    assert branch["jump_target_statement_index"] in valid_targets
    assert branch["jump_target_statement_index"] != branch["serialized_start"]


def test_computed_jump_is_marked_not_enumerated(stackobot_document):
    for obj in stackobot_document.objects:
        for fn in ((obj.semantic or {}).get("functions") or []):
            for edge in fn["cfg"]["edges"]:
                if edge["kind"] == "computed_jump":
                    assert edge["targets_known"] is False


def test_cfg_blocks_carry_instructions_matching_ordinals(stackobot_document):
    """blocks[].instructions is the brief projection; ordinals stay in sync."""
    for obj in stackobot_document.objects:
        for fn in ((obj.semantic or {}).get("functions") or []):
            instrs = fn.get("instructions") or []
            blocks = (fn.get("cfg") or {}).get("blocks") or []
            if not instrs:
                continue
            concat: list[dict] = []
            for block in blocks:
                block_instrs = block.get("instructions")
                ordinals = block.get("instruction_ordinals") or []
                assert block_instrs is not None, "blocks must expose instructions"
                assert len(block_instrs) == len(ordinals)
                assert [item["statement_ordinal"] for item in block_instrs] == ordinals
                concat.extend(block_instrs)
            assert concat == instrs, "block instructions must cover fn instructions in order"
